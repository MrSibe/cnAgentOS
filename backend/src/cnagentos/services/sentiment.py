"""Sentiment analysis service — task management and AI-powered analysis (Phase 8)."""

import json
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


SENTIMENT_SYSTEM_PROMPT = """你是一个智能舆情分析助手。你的任务是分析提供的新闻/文章内容，并输出结构化的分析报告。

请按以下 JSON 格式输出（不要有任何其他文字）：

对于情感分析 (sentiment):
{
  "report_type": "sentiment",
  "report_data": {
    "positive_count": 数量,
    "neutral_count": 数量,
    "negative_count": 数量,
    "details": [
      {"content_title": "标题", "sentiment": "positive/neutral/negative", "confidence": 0.0-1.0}
    ]
  },
  "summary_text": "情感分析总体摘要"
}

对于关键词提取 (keyword):
{
  "report_type": "keyword",
  "report_data": {
    "keywords": [
      {"word": "关键词", "count": 出现次数, "weight": 0.0-1.0}
    ]
  },
  "summary_text": "关键词分析摘要"
}

对于热点挖掘 (hotspot):
{
  "report_type": "hotspot",
  "report_data": {
    "hotspots": [
      {"title": "热点主题", "related_count": 相关文章数, "description": "描述"}
    ]
  },
  "summary_text": "热点分析摘要"
}

对于综合分析 (full):
需要输出所有上述三种报告，外加总体摘要。格式为 JSON 数组：
[
  {sentiment报告},
  {keyword报告},
  {hotspot报告},
  {
    "report_type": "summary",
    "report_data": {},
    "summary_text": "总体舆情分析摘要，包含风险提示"
  }
]"""


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
            task_type=data.task_type,
            data_scope=data.data_scope,
            include_chat_data=data.include_chat_data,
            status="pending",
            created_by=self.actor_id,
        )
        self.session.add(task)
        await self.session.flush()

        # Audit
        self.session.add(AuditLog(
            id=str(uuid4()),
            actor_user_id=self.actor_id,
            action="sentiment.task.create",
            target_type="sentiment_task",
            target_id=task.id,
            result="succeeded",
            detail={"name": data.name, "task_type": data.task_type},
            ip_address=self.ip_address,
            created_at=utc_now(),
        ))
        await self.session.commit()
        return self._task_to_dict(task)

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
        except ApiError:
            task.status = "failed"
            task.error_message = "分析任务执行失败"
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

        # 2. Build data scope filter
        scope = task.data_scope or {}
        start_date_str = scope.get("start_date")
        end_date_str = scope.get("end_date")
        source_ids = scope.get("source_ids")

        query = select(KnowledgeItem).where(KnowledgeItem.status == "available")
        if start_date_str:
            query = query.where(KnowledgeItem.collected_at >= start_date_str)
        if end_date_str:
            query = query.where(KnowledgeItem.collected_at <= end_date_str + "T23:59:59")
        if source_ids:
            query = query.where(KnowledgeItem.source_id.in_(source_ids))

        rows = (await self.session.scalars(query.limit(200))).all()
        if not rows:
            raise ApiError(400, "VALIDATION_ERROR", "没有符合条件的知识内容可供分析")

        # 3. Build analysis content
        content_parts = []
        for item in rows:
            content_parts.append(
                f"标题: {item.title}\n摘要: {item.summary or item.content[:200]}\n---"
            )
        analysis_content = "\n".join(content_parts[:100])

        # 4. Get chat messages if requested
        chat_content = ""
        if task.include_chat_data:
            chat_messages = (
                (
                    await self.session.execute(
                        select(Message.content)
                        .order_by(Message.created_at.desc())
                        .limit(200)
                    )
                )
                .scalars()
                .all()
            )
            if chat_messages:
                chat_content = "聊天消息:\n" + "\n".join(
                    f"- {msg[:200]}" for msg in reversed(chat_messages)
                )

        # 5. Decrypt API key
        api_key = None
        try:
            api_key = decrypt(model.credential_ciphertext)
        except InvalidToken:
            raise ApiError(422, "MODEL_UNAVAILABLE", "模型凭据无效")

        # 6. Call model
        from cnagentos.services.model_provider import ModelProviderClient

        task_type = task.task_type
        prompt = SENTIMENT_SYSTEM_PROMPT
        user_msg = f"请对以下{len(rows)}条内容进行{'综合分析' if task_type=='full' else task_type}：\n\n{analysis_content}"
        if chat_content:
            user_msg += f"\n\n{chat_content}"

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
            input_tokens=0,
            output_tokens=0,
            status="running",
            created_at=utc_now(),
        )
        self.session.add(call_log)
        await self.session.flush()

        start_time = utc_now()
        try:
            response = await client.complete_chat_with_messages(
                model.name,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_msg},
                ],
            )
            latency = int((utc_now() - start_time).total_seconds() * 1000)

            call_log.status = "succeeded"
            call_log.latency_ms = latency
            call_log.input_tokens = response.usage.prompt_tokens
            call_log.output_tokens = response.usage.completion_tokens
        except Exception as exc:
            latency = int((utc_now() - start_time).total_seconds() * 1000)
            call_log.status = "failed"
            call_log.error_code = "UPSTREAM_ERROR"
            call_log.latency_ms = latency
            await self.session.flush()
            raise ApiError(502, "UPSTREAM_ERROR", f"模型调用失败: {str(exc)[:200]}")

        await self.session.flush()

        # 7. Parse and save reports
        reply_text = response.reply.strip()
        await self._save_reports(task, reply_text, len(rows))

    async def _save_reports(
        self, task: SentimentTask, reply_text: str, item_count: int,
    ) -> None:
        """Parse model response and save report records."""
        # Try to parse as JSON
        try:
            # Remove markdown code block markers if present
            cleaned = reply_text.strip()
            if cleaned.startswith("```"):
                # Find the JSON content
                start = cleaned.find("{")
                if start == -1:
                    start = cleaned.find("[")
                if start >= 0:
                    cleaned = cleaned[start:]
                end = cleaned.rfind("}")
                if end >= 0:
                    cleaned = cleaned[:end + 1]
                elif cleaned.rfind("]") >= 0:
                    end = cleaned.rfind("]")
                    cleaned = cleaned[:end + 1]

            reports_data = json.loads(cleaned)

            # Normalize to list
            if isinstance(reports_data, dict):
                reports_data = [reports_data]

            for report_datum in reports_data:
                if not isinstance(report_datum, dict):
                    continue
                report_type = report_datum.get("report_type", task.task_type)
                self.session.add(SentimentReport(
                    id=str(uuid4()),
                    task_id=task.id,
                    report_type=report_type,
                    report_data=report_datum.get("report_data", {}),
                    summary_text=report_datum.get("summary_text") or "",
                    source_item_count=item_count,
                    created_at=utc_now(),
                ))
        except (json.JSONDecodeError, ValueError):
            # Fallback: save raw text as summary report
            self.session.add(SentimentReport(
                id=str(uuid4()),
                task_id=task.id,
                report_type="summary",
                report_data={"raw": reply_text[:5000]},
                summary_text=reply_text[:500],
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
            "task_type": task.task_type,
            "data_scope": task.data_scope,
            "include_chat_data": task.include_chat_data,
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
