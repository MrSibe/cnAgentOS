"""Sentiment analysis service — task management and AI-powered analysis (Phase 8)."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    AuditLog,
    KnowledgeItem,
    Message,
    ModelCallLog,
    ModelConfig,
    SentimentReport,
    SentimentTask,
    User,
    utc_now,
)
from cnagentos.schemas import SentimentTaskCreate
from cnagentos.security import decrypt, InvalidToken


def _now() -> datetime:
    return utc_now()


SENTIMENT_SYSTEM_PROMPT = """你是一个智能舆情分析助手。你的任务是基于提供的聊天记录或采集内容进行风险评估和分析，输出一份综合的分析报告。

请用中文输出一篇完整的分析报告，包含以下内容（不要输出 JSON，直接写文章）：

1. **总体评估**：整体风险等级（低/中/高）和核心结论
2. **关键发现**：列出最重要的风险信号或趋势（至少 2-5 条）
3. **详细分析**：对数据的深入分析
4. **建议**：可操作的改进建议（至少 2-3 条）

请确保报告结构清晰、内容充实，使用 markdown 格式排版。"""


class SentimentAnalysisService:
    """Manage sentiment analysis tasks and orchestrate AI-powered analysis."""

    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None,
    ) -> None:
        self.session = session
        self.actor = actor
        self.actor_id = actor.id
        self.ip_address = ip_address

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    async def create_task(self, data: SentimentTaskCreate) -> dict:
        task = SentimentTask(
            id=str(uuid4()),
            name=data.name,
            task_type=data.scope,
            data_scope=data.data_scope,
            include_chat_data=(data.scope == "chat"),
            status="running",
            started_at=utc_now(),
            created_by=self.actor_id,
        )
        self.session.add(task)
        await self.session.flush()

        # Execute analysis immediately (synchronous)
        try:
            await self._execute_analysis(task)
            task.status = "completed"
            task.progress = 100
            task.completed_at = utc_now()
        except ApiError as exc:
            task.status = "failed"
            task.error_message = exc.message[:500]
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)[:500]

        # Pre-load reports before commit (avoid lazy-load after session close)
        report_rows = (
            (await self.session.scalars(
                select(SentimentReport).where(SentimentReport.task_id == task.id)
            )).all()
        )
        report_dicts = [self._report_to_dict(r) for r in report_rows]

        # Audit
        self.session.add(AuditLog(
            id=str(uuid4()),
            actor_user_id=self.actor_id,
            action="sentiment.task.create",
            target_type="sentiment_task",
            target_id=task.id,
            result="succeeded" if task.status == "completed" else "failed",
            detail={"name": data.name, "scope": data.scope, "status": task.status},
            ip_address=self.ip_address,
            created_at=utc_now(),
        ))
        await self.session.commit()

        result = self._task_to_dict(task, include_reports=False)
        result["reports"] = report_dicts
        return result

    async def run_task(self, task_id: str) -> dict:
        task = await self.session.get(SentimentTask, task_id)
        if task is None:
            raise ApiError(404, "NOT_FOUND", "舆情分析任务不存在")

        if task.status == "running":
            raise ApiError(409, "INVALID_STATE", "任务正在运行中")

        # Mark as running
        task.status = "running"
        task.progress = 0
        task.started_at = utc_now()
        task.error_message = None
        await self.session.flush()

        try:
            await self._execute_analysis(task)
            task.status = "completed"
            task.progress = 100
            task.completed_at = utc_now()
        except ApiError as exc:
            task.status = "failed"
            task.error_message = exc.message[:500]
            raise
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)[:500]
        finally:
            # Audit
            self.session.add(AuditLog(
                id=str(uuid4()),
                actor_user_id=self.actor_id,
                action="sentiment.task.run",
                target_type="sentiment_task",
                target_id=task.id,
                result="succeeded" if task.status == "completed" else "failed",
                detail={"status": task.status, "task_type": task.task_type},
                ip_address=self.ip_address,
                created_at=utc_now(),
            ))
            await self.session.commit()

        return self._task_to_dict(task)

    async def _execute_analysis(self, task: SentimentTask) -> None:
        """Execute the analysis: gather data, call model, save reports."""
        # 1. Get default model
        model = await self.session.scalar(
            select(ModelConfig).where(
                ModelConfig.is_default.is_(True),
                ModelConfig.status == "active",
            )
        )
        if model is None:
            raise ApiError(422, "MODEL_UNAVAILABLE", "系统未配置默认模型或默认模型未启用")

        # 2. Gather content based on scope
        scope_val = task.task_type  # stores "chat" or "data_warehouse"
        scope_data = task.data_scope or {}
        start_date_str = scope_data.get("start_date")
        end_date_str = scope_data.get("end_date")

        if scope_val == "chat":
            analysis_content, source_count = await self._build_chat_content(
                start_date_str, end_date_str,
            )
            scope_label = "聊天记录"
        else:
            source_ids = scope_data.get("source_ids")
            analysis_content, source_count = await self._build_warehouse_content(
                start_date_str, end_date_str, source_ids,
            )
            scope_label = "数据仓库内容"

        if not analysis_content:
            raise ApiError(400, "VALIDATION_ERROR", f"没有符合条件的{scope_label}可供分析")

        # 3. Decrypt API key
        api_key = None
        try:
            api_key = decrypt(model.credential_ciphertext)
        except InvalidToken:
            raise ApiError(422, "MODEL_UNAVAILABLE", "模型凭据无效")

        # 4. Call model
        from cnagentos.services.model_provider import ModelProviderClient

        prompt = SENTIMENT_SYSTEM_PROMPT
        user_msg = f"请对以下{source_count}条{scope_label}进行舆情分析：\n\n{analysis_content}"

        client = ModelProviderClient(
            api_key=api_key,
            base_url=model.base_url,
            timeout_seconds=model.timeout_seconds,
        )

        call_log = ModelCallLog(
            id=str(uuid4()),
            model_config_id=model.id,
            caller_user_id=self.actor_id,
            purpose="sentiment_analysis",
            related_id=task.id,
            prompt_tokens=0,
            completion_tokens=0,
            status="running",
            started_at=utc_now(),
        )
        self.session.add(call_log)
        await self.session.flush()

        start_time = utc_now()
        try:
            response = await client.complete_chat_with_messages(
                model.model_name,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_msg},
                ],
            )
            latency = int((utc_now() - start_time).total_seconds() * 1000)

            call_log.status = "succeeded"
            call_log.latency_ms = latency
            call_log.prompt_tokens = response.usage.prompt_tokens
            call_log.completion_tokens = response.usage.completion_tokens
            call_log.finished_at = utc_now()
        except Exception as exc:
            latency = int((utc_now() - start_time).total_seconds() * 1000)
            call_log.status = "failed"
            call_log.error_code = "UPSTREAM_ERROR"
            call_log.latency_ms = latency
            call_log.finished_at = utc_now()
            await self.session.flush()
            raise ApiError(502, "UPSTREAM_ERROR", f"模型调用失败: {str(exc)[:200]}")

        await self.session.flush()

        # 5. Parse and save report
        reply_text = response.reply.strip()
        await self._save_report(task, reply_text, source_count)

    async def _build_chat_content(
        self, start_date_str: str | None, end_date_str: str | None,
    ) -> tuple[str, int]:
        """Fetch chat messages within date range and format for analysis."""
        from cnagentos.models.entities import Message

        query = select(Message.content, Message.created_at).order_by(Message.created_at.desc())
        if start_date_str:
            start_dt = datetime.fromisoformat(start_date_str)
            query = query.where(Message.created_at >= start_dt)
        if end_date_str:
            end_dt = datetime.fromisoformat(end_date_str).replace(
                hour=23, minute=59, second=59, microsecond=999999,
            )
            query = query.where(Message.created_at <= end_dt)

        rows = (await self.session.execute(query.limit(200))).all()
        if not rows:
            return "", 0

        parts = []
        for msg_content, msg_time in rows:
            ts = msg_time.isoformat() if msg_time else ""
            text = (msg_content or "")[:200]
            parts.append(f"[{ts}] {text}")
        return "\n".join(parts), len(rows)

    async def _build_warehouse_content(
        self, start_date_str: str | None, end_date_str: str | None,
        source_ids: list[str] | None,
    ) -> tuple[str, int]:
        """Fetch knowledge items within filters and format for analysis."""
        query = select(KnowledgeItem).where(KnowledgeItem.status == "available")
        if start_date_str:
            start_dt = datetime.fromisoformat(start_date_str)
            query = query.where(KnowledgeItem.collected_at >= start_dt)
        if end_date_str:
            end_dt = datetime.fromisoformat(end_date_str).replace(
                hour=23, minute=59, second=59, microsecond=999999,
            )
            query = query.where(KnowledgeItem.collected_at <= end_dt)
        if source_ids:
            query = query.where(KnowledgeItem.source_id.in_(source_ids))

        rows = (await self.session.scalars(query.limit(200))).all()
        if not rows:
            return "", 0

        parts = []
        for item in rows:
            parts.append(
                f"标题: {item.title}\n摘要: {item.summary or (item.content or '')[:200]}\n---"
            )
        return "\n".join(parts[:100]), len(rows)

    async def _save_report(
        self, task: SentimentTask, reply_text: str, item_count: int,
    ) -> None:
        """Save the AI-generated report as plain text."""
        self.session.add(SentimentReport(
            id=str(uuid4()),
            task_id=task.id,
            report_type="summary",
            report_data={"raw": reply_text[:5000]},
            summary_text=reply_text[:5000],
            source_item_count=item_count,
            created_at=utc_now(),
        ))

    async def list_tasks(
        self, page: int = 1, page_size: int = 20, status: str | None = None,
    ) -> tuple[list[dict], int]:
        query = select(SentimentTask)
        count_query = select(func.count(SentimentTask.id))
        if status:
            query = query.where(SentimentTask.status == status)
            count_query = count_query.where(SentimentTask.status == status)

        total = (await self.session.scalar(count_query)) or 0
        rows = (
            (
                await self.session.scalars(
                    query.options(selectinload(SentimentTask.creator))
                    .order_by(SentimentTask.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .all()
        )
        return [self._task_to_dict(t) for t in rows], total

    async def get_task(self, task_id: str) -> dict:
        task = await self.session.get(
            SentimentTask, task_id,
            options=[selectinload(SentimentTask.creator),
                     selectinload(SentimentTask.reports)],
        )
        if task is None:
            raise ApiError(404, "NOT_FOUND", "舆情分析任务不存在")
        return self._task_to_dict(task, include_reports=True)

    async def get_task_reports(self, task_id: str) -> list[dict]:
        task = await self.session.get(SentimentTask, task_id)
        if task is None:
            raise ApiError(404, "NOT_FOUND", "舆情分析任务不存在")
        rows = (
            (
                await self.session.scalars(
                    select(SentimentReport)
                    .where(SentimentReport.task_id == task_id)
                    .order_by(SentimentReport.created_at.asc())
                )
            )
            .all()
        )
        return [self._report_to_dict(r) for r in rows]

    async def get_report(self, report_id: str) -> dict:
        report = await self.session.get(SentimentReport, report_id)
        if report is None:
            raise ApiError(404, "NOT_FOUND", "舆情分析报告不存在")
        return self._report_to_dict(report)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _task_to_dict(
        self, task: SentimentTask, include_reports: bool = False,
    ) -> dict:
        d = {
            "id": task.id,
            "name": task.name,
            "scope": task.task_type,
            "data_scope": task.data_scope,
            "status": task.status,
            "progress": task.progress,
            "error_message": task.error_message,
            "source_item_count": sum(
                (r.source_item_count for r in (task.reports or [])), 0
            ) if include_reports else 0,
            "created_by": (
                {"id": task.creator.id, "display_name": task.creator.display_name}
                if task.creator else None
            ),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
        if include_reports and task.reports:
            d["reports"] = [self._report_to_dict(r) for r in task.reports]
        return d

    def _report_to_dict(self, report: SentimentReport) -> dict:
        return {
            "id": report.id,
            "task_id": report.task_id,
            "report_type": report.report_type,
            "report_data": report.report_data,
            "summary_text": report.summary_text,
            "source_item_count": report.source_item_count,
            "period_start": report.period_start.isoformat() if report.period_start else None,
            "period_end": report.period_end.isoformat() if report.period_end else None,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        }
