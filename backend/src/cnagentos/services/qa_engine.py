"""智能问数编排服务

管理会话、消息、引用和模型编排的领域服务。
"""

import json
import time
from collections.abc import AsyncIterator
from uuid import uuid4

from openai import APIConnectionError, APIStatusError, APITimeoutError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    KnowledgeItem,
    ModelCallLog,
    ModelConfig,
    QaCitation,
    QaMessage,
    QaSession,
    User,
    utc_now,
)
from cnagentos.schemas import (
    QASessionCreate,
    QASessionUpdate,
    QAQuestionRequest,
)
from cnagentos.security import decrypt, InvalidToken
from cnagentos.services.model_provider import ModelProviderClient
from cnagentos.services.qa_knowledge import (
    RetrievedKnowledge,
    retrieve_available_knowledge,
    build_prompt_with_context,
)
from cnagentos.services.qa_security import (
    get_owned_session,
    get_owned_answer_message,
    validate_question_text,
    validate_retrieved_knowledge_items,
    write_qa_audit,
)


VALID_SESSION_STATUSES = {"active", "archived"}
VALID_MESSAGE_STATUSES = {"completed", "streaming", "failed"}
NO_EVIDENCE_ANSWER = "未找到可用于回答该问题的系统依据。请先在数据仓库中确认已有状态为 available 的相关内容。"


class QAEngineService:
    """智能问数编排服务"""
    
    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None
    ) -> None:
        self.session = session
        self.actor = actor
        self.actor_id = actor.id
        self.ip_address = ip_address
    
    # -------------------------------------------------------------------------
    # 会话管理
    # -------------------------------------------------------------------------
    
    async def _serialize_session(self, sess: QaSession) -> dict:
        return {
            "id": sess.id,
            "title": sess.title,
            "status": sess.status,
            "updated_at": sess.updated_at,
            "created_at": sess.created_at,
        }
    
    async def list_sessions(
        self, page: int, page_size: int, q: str | None
    ) -> tuple[list[dict], int]:
        conditions = [QaSession.user_id == self.actor_id]
        if q:
            conditions.append(QaSession.title.ilike(f"%{q}%"))
        
        total = await self.session.scalar(
            select(func.count()).select_from(QaSession).where(*conditions)
        )
        sessions = (
            await self.session.scalars(
                select(QaSession)
                .where(*conditions)
                .order_by(QaSession.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        
        return [await self._serialize_session(s) for s in sessions], int(total or 0)
    
    async def create_session(self, payload: QASessionCreate) -> dict:
        session = QaSession(
            id=str(uuid4()),
            user_id=self.actor_id,
            title=payload.title,
            status="active",
        )
        self.session.add(session)
        await write_qa_audit(
            self.session, self.actor, "qa.session.created", "qa_session",
            session.id, "succeeded", {"title": session.title}, self.ip_address
        )
        await self.session.commit()
        return await self._serialize_session(session)
    
    async def get_session(self, session_id: str) -> dict:
        session = await get_owned_session(self.session, self.actor, session_id)
        return await self._serialize_session(session)
    
    async def update_session(self, session_id: str, payload: QASessionUpdate) -> dict:
        session = await get_owned_session(self.session, self.actor, session_id)
        
        if payload.title is not None:
            session.title = payload.title
        if payload.status is not None:
            if payload.status not in VALID_SESSION_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "无效的会话状态")
            session.status = payload.status
        
        await write_qa_audit(
            self.session, self.actor, "qa.session.updated", "qa_session",
            session.id, "succeeded", {"title": session.title, "status": session.status}, self.ip_address
        )
        await self.session.commit()
        return await self._serialize_session(session)
    
    # -------------------------------------------------------------------------
    # 消息管理
    # -------------------------------------------------------------------------
    
    async def _serialize_message(self, msg: QaMessage) -> dict:
        citations = []
        for citation in msg.citations:
            ki = citation.knowledge_item
            source_name = ki.source.name if ki and ki.source else None
            citations.append({
                "knowledge_item_id": citation.knowledge_item_id,
                "rank": citation.rank,
                "title": ki.title if ki else None,
                "source_name": source_name,
                "excerpt": citation.excerpt,
            })
        
        return {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "status": msg.status,
            "error_summary": msg.error_summary,
            "created_at": msg.created_at,
            "citations": citations,
        }
    
    async def list_messages(self, session_id: str) -> list[dict]:
        session = await get_owned_session(self.session, self.actor, session_id)
        
        messages = (
            await self.session.scalars(
                select(QaMessage)
                .options(
                    selectinload(QaMessage.citations)
                    .selectinload(QaCitation.knowledge_item)
                    .selectinload(KnowledgeItem.source)
                )
                .where(QaMessage.session_id == session_id)
                .order_by(QaMessage.created_at.asc())
            )
        ).all()
        
        return [await self._serialize_message(m) for m in messages]
    
    # -------------------------------------------------------------------------
    # 引用管理
    # -------------------------------------------------------------------------
    
    async def get_citations(self, message_id: str) -> list[dict]:
        message = await get_owned_answer_message(self.session, self.actor, message_id)

        citations = []
        for citation in message.citations:
            ki = citation.knowledge_item
            source_name = ki.source.name if ki.source else None
            citations.append({
                "knowledge_item_id": citation.knowledge_item_id,
                "rank": citation.rank,
                "title": ki.title if ki else None,
                "source_name": source_name,
                "excerpt": citation.excerpt,
                "current_status": ki.status if ki else None,
            })

        await write_qa_audit(
            self.session,
            self.actor,
            "qa.citations.viewed",
            "qa_message",
            message.id,
            "succeeded",
            {"citations_count": len(citations)},
            self.ip_address,
        )
        await self.session.commit()

        citations.sort(key=lambda x: x["rank"])
        return citations
    
    # -------------------------------------------------------------------------
    # 默认模型获取
    # -------------------------------------------------------------------------
    
    async def _get_default_model(self) -> ModelConfig | None:
        model = await self.session.scalar(
            select(ModelConfig).where(
                ModelConfig.is_default.is_(True),
                ModelConfig.status == "active"
            )
        )
        return model
    
    # -------------------------------------------------------------------------
    # SSE 流式问答
    # -------------------------------------------------------------------------
    
    def _stream_error_event(self, code: str, message: str) -> str:
        payload = {"event": "error", "error": {"code": code, "message": message}}
        return f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    
    async def _save_citations(
        self,
        answer_message_id: str,
        knowledge_items: list[RetrievedKnowledge],
    ) -> list[dict]:
        citations = []
        for rank, item in enumerate(knowledge_items, 1):
            citation = QaCitation(
                answer_message_id=answer_message_id,
                knowledge_item_id=item.knowledge_item_id,
                rank=rank,
                excerpt=item.excerpt,
            )
            self.session.add(citation)
            citations.append({
                "knowledge_item_id": item.knowledge_item_id,
                "rank": rank,
                "title": item.title,
                "source_name": item.source_name,
                "excerpt": item.excerpt,
            })
        return citations
    
    async def stream_question(
        self, session_id: str, payload: QAQuestionRequest
    ) -> tuple[QaMessage, AsyncIterator[str]]:
        session = await get_owned_session(self.session, self.actor, session_id)
        if session.status != "active":
            raise ApiError(400, "INVALID_STATE", "会话已归档，无法提问")
        
        question = validate_question_text(payload.question)
        
        default_model = await self._get_default_model()
        if default_model is None:
            raise ApiError(422, "MODEL_UNAVAILABLE", "系统未配置默认模型")
        
        try:
            api_key = decrypt(default_model.credential_ciphertext)
        except InvalidToken:
            raise ApiError(422, "MODEL_UNAVAILABLE", "默认模型凭据无效")
        except RuntimeError:
            raise ApiError(500, "INTERNAL_ERROR", "加密模块未初始化")
        
        user_message = QaMessage(
            id=str(uuid4()),
            session_id=session_id,
            role="user",
            content=question,
            status="completed",
        )
        self.session.add(user_message)

        await write_qa_audit(
            self.session,
            self.actor,
            "qa.question.submitted",
            "qa_message",
            user_message.id,
            "succeeded",
            {"session_id": session_id, "question_length": len(question)},
            self.ip_address,
        )

        answer_message = QaMessage(
            id=str(uuid4()),
            session_id=session_id,
            role="assistant",
            reply_to_id=user_message.id,
            content="",
            status="streaming",
        )
        self.session.add(answer_message)
        
        await write_qa_audit(
            self.session, self.actor, "qa.answer.started", "qa_message",
            answer_message.id, "succeeded", {"session_id": session_id}, self.ip_address
        )

        await self.session.flush()

        knowledge_items = await retrieve_available_knowledge(
            self.session, question
        )
        validated_items = validate_retrieved_knowledge_items(knowledge_items)

        if not validated_items:
            answer_message.content = NO_EVIDENCE_ANSWER
            answer_message.status = "completed"
            answer_message.updated_at = utc_now()
            session.updated_at = utc_now()
            await write_qa_audit(
                self.session,
                self.actor,
                "qa.answer.completed",
                "qa_message",
                answer_message.id,
                "succeeded",
                {"citations_count": 0, "strategy": "no_evidence"},
                self.ip_address,
            )
            await self.session.commit()

            async def no_evidence_generate() -> AsyncIterator[str]:
                yield f"data: {json.dumps({'content': NO_EVIDENCE_ANSWER, 'full_content': NO_EVIDENCE_ANSWER}, ensure_ascii=False)}\n\n"
                completed_payload = {
                    "event": "completed",
                    "message_id": answer_message.id,
                    "citations": [],
                }
                yield f"event: completed\ndata: {json.dumps(completed_payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return answer_message, no_evidence_generate()

        call_log = ModelCallLog(
            id=str(uuid4()),
            model_config_id=default_model.id,
            caller_user_id=self.actor_id,
            purpose="qa_answer",
            related_id=answer_message.id,
            streamed=True,
            status="running",
            started_at=utc_now(),
        )
        answer_message.model_call_log_id = call_log.id
        self.session.add(call_log)
        await self.session.flush()
        
        prompt = build_prompt_with_context(question, validated_items)
        
        await self.session.commit()
        
        start_time = time.monotonic()
        
        async def generate() -> AsyncIterator[str]:
            nonlocal answer_message, call_log
            
            try:
                accumulated_content = []
                
                async for chunk in ModelProviderClient(
                    api_key=api_key,
                    base_url=default_model.base_url,
                    timeout_seconds=default_model.timeout_seconds,
                ).stream_chat(default_model.model_name, prompt):
                    delta = ""
                    if "choices" in chunk and chunk["choices"]:
                        delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    
                    if delta:
                        accumulated_content.append(delta)
                        content_so_far = "".join(accumulated_content)
                        yield f"data: {json.dumps({'content': delta, 'full_content': content_so_far}, ensure_ascii=False)}\n\n"
                
                final_content = "".join(accumulated_content)
                
                answer_message = await self.session.get(QaMessage, answer_message.id)
                if answer_message:
                    answer_message.content = final_content
                    answer_message.status = "completed"
                    answer_message.updated_at = utc_now()

                    call_log = await self.session.get(ModelCallLog, call_log.id)
                    if call_log:
                        call_log.status = "succeeded"
                        call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
                        call_log.finished_at = utc_now()

                    await self._save_citations(answer_message.id, validated_items)
                    session_obj = await self.session.get(QaSession, session_id)
                    if session_obj:
                        session_obj.updated_at = utc_now()

                await write_qa_audit(
                    self.session, self.actor, "qa.answer.completed", "qa_message",
                    answer_message.id, "succeeded", {"citations_count": len(validated_items)}, self.ip_address
                )
                await self.session.commit()
                
                citations_data = [
                    {
                        "knowledge_item_id": item.knowledge_item_id,
                        "rank": rank,
                        "title": item.title,
                        "source_name": item.source_name,
                        "excerpt": item.excerpt,
                    }
                    for rank, item in enumerate(validated_items, 1)
                ]
                
                completed_payload = {
                    "event": "completed",
                    "message_id": answer_message.id,
                    "citations": citations_data,
                }
                yield f"event: completed\ndata: {json.dumps(completed_payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                
            except APIStatusError as exc:
                await self._handle_stream_error(
                    answer_message.id, call_log.id, start_time,
                    f"HTTP_{exc.status_code}", "上游模型服务返回错误"
                )
                yield self._stream_error_event(
                    f"HTTP_{exc.status_code}", "上游模型服务返回错误"
                )
                yield "data: [DONE]\n\n"

            except APITimeoutError:
                await self._handle_stream_error(
                    answer_message.id, call_log.id, start_time,
                    "TIMEOUT", "模型服务响应超时"
                )
                yield self._stream_error_event("TIMEOUT", "模型服务响应超时")
                yield "data: [DONE]\n\n"

            except APIConnectionError:
                await self._handle_stream_error(
                    answer_message.id, call_log.id, start_time,
                    "CONNECTION_ERROR", "无法连接到模型服务"
                )
                yield self._stream_error_event("CONNECTION_ERROR", "无法连接到模型服务")
                yield "data: [DONE]\n\n"

            except Exception:
                await self._handle_stream_error(
                    answer_message.id, call_log.id, start_time,
                    "UPSTREAM_ERROR", "流式响应出错"
                )
                yield self._stream_error_event("UPSTREAM_ERROR", "流式响应出错")
                yield "data: [DONE]\n\n"
        
        return answer_message, generate()
    
    async def _handle_stream_error(
        self,
        answer_id: str,
        call_log_id: str,
        start_time: float,
        error_code: str,
        error_msg: str,
    ) -> None:
        answer_message = await self.session.get(QaMessage, answer_id)
        if answer_message:
            answer_message.status = "failed"
            answer_message.error_summary = error_msg
            answer_message.updated_at = utc_now()

        call_log = await self.session.get(ModelCallLog, call_log_id)
        if call_log:
            call_log.status = "failed"
            call_log.error_code = error_code
            call_log.latency_ms = int((time.monotonic() - start_time) * 1000)
            call_log.finished_at = utc_now()

        await write_qa_audit(
            self.session, self.actor, "qa.answer.failed", "qa_message",
            answer_id, "failed", {"error_code": error_code}, self.ip_address
        )
        await self.session.commit()
