"""Dashboard statistics aggregation service (Phase 8)."""

import re
from collections import Counter
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.models.entities import (
    CollectionTask,
    KnowledgeItem,
    ModelCallLog,
    QaSession,
    SentimentTask,
    User,
    WatchSource,
)


def _naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DashboardService:
    """Aggregate cross-module statistics for the smart dashboard."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stats(self) -> dict:
        """Return aggregated statistics across all major modules."""
        import asyncio

        results = await asyncio.gather(
            self._count_knowledge_items(),
            self._count_watch_sources(),
            self._count_collection_tasks(),
            self._count_qa_sessions(),
            self._count_users(),
            self._count_chat_messages(),
            return_exceptions=True,
        )

        def _safe(val, default):
            return val if not isinstance(val, Exception) else default

        return {
            "knowledge_items": _safe(results[0], {"total": 0}),
            "watch_sources": _safe(results[1], {"total": 0}),
            "collection_tasks": _safe(results[2], {"total": 0}),
            "qa_sessions": _safe(results[3], {"total": 0}),
            "users": _safe(results[4], {"total": 0, "active_today": 0}),
            "chat_messages": _safe(results[5], {"total_24h": 0, "total": 0}),
            "updated_at": _naive_utc().isoformat(),
        }

    async def _count_knowledge_items(self) -> dict:
        rows = (
            await self.session.execute(
                select(KnowledgeItem.status, func.count(KnowledgeItem.id))
                .group_by(KnowledgeItem.status)
            )
        ).all()
        total = 0
        result = {}
        for status, cnt in rows:
            result[status] = cnt
            total += cnt
        result["total"] = total
        return result

    async def _count_watch_sources(self) -> dict:
        rows = (
            await self.session.execute(
                select(WatchSource.status, func.count(WatchSource.id))
                .group_by(WatchSource.status)
            )
        ).all()
        total = 0
        result = {}
        for status, cnt in rows:
            result[status] = cnt
            total += cnt
        result["total"] = total
        return result

    async def _count_collection_tasks(self) -> dict:
        rows = (
            await self.session.execute(
                select(CollectionTask.status, func.count(CollectionTask.id))
                .group_by(CollectionTask.status)
            )
        ).all()
        total = 0
        result = {}
        for status, cnt in rows:
            result[status] = cnt
            total += cnt
        result["total"] = total
        return result

    async def _count_qa_sessions(self) -> dict:
        rows = (
            await self.session.execute(
                select(QaSession.status, func.count(QaSession.id))
                .group_by(QaSession.status)
            )
        ).all()
        total = 0
        result = {}
        for status, cnt in rows:
            result[status] = cnt
            total += cnt
        result["total"] = total
        return result

    async def _count_users(self) -> dict:
        total = (await self.session.scalar(select(func.count(User.id)))) or 0
        today = _naive_utc().date()
        today_start = datetime(today.year, today.month, today.day, tzinfo=None)
        # Count users who logged in today via auth_sessions (approximate active count)
        active_today = (
            await self.session.scalar(
                select(func.count(func.distinct(ModelCallLog.caller_user_id)))
                .where(ModelCallLog.created_at >= today_start)
            )
        ) or 0
        return {"total": total, "active_today": active_today}

    async def _count_chat_messages(self) -> dict:
        """Count total messages and last 24h messages (aggregate only, no content)."""
        from cnagentos.models.entities import Message

        total = (await self.session.scalar(select(func.count(Message.id)))) or 0
        since = _naive_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        last_24h = (
            await self.session.scalar(
                select(func.count(Message.id))
                .where(Message.created_at >= since)
            )
        ) or 0
        return {"total_24h": last_24h, "total": total}

    async def get_trends(self, days: int = 30) -> dict:
        """Return daily trend data for knowledge items, QA questions, and messages."""
        from cnagentos.models.entities import Message, QaMessage

        days = min(max(days, 1), 90)
        since = _naive_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        # Build date list for filling gaps
        date_list = [
            (
                date.fromordinal(
                    since.toordinal() - i
                ).isoformat()
            )
            for i in range(days - 1, -1, -1)
        ]

        def _fill(tuples: list[tuple], key: str) -> list[dict]:
            """Fill gaps in daily series with zero counts."""
            counts = {str(d): c for d, c in tuples if d}
            return [{"date": d, key: counts.get(d, 0)} for d in date_list]

        knowledge_tuples = (
            (
                await self.session.execute(
                    select(
                        func.date(KnowledgeItem.collected_at).label("d"),
                        func.count(KnowledgeItem.id),
                    )
                    .where(KnowledgeItem.collected_at >= since)
                    .group_by(text("d"))
                )
            )
            .all()
        )

        qa_tuples = (
            (
                await self.session.execute(
                    select(
                        func.date(QaMessage.created_at).label("d"),
                        func.count(QaMessage.id),
                    )
                    .where(QaMessage.created_at >= since)
                    .where(QaMessage.role == "user")
                    .group_by(text("d"))
                )
            )
            .all()
        )

        msg_tuples = (
            (
                await self.session.execute(
                    select(
                        func.date(Message.created_at).label("d"),
                        func.count(Message.id),
                    )
                    .where(Message.created_at >= since)
                    .group_by(text("d"))
                )
            )
            .all()
        )

        return {
            "knowledge_items": _fill(knowledge_tuples, "count"),
            "qa_questions": _fill(qa_tuples, "count"),
            "chat_messages": _fill(msg_tuples, "count"),
        }

    async def get_keywords(self, limit: int = 50) -> list[dict]:
        """Extract keywords from available knowledge item titles and summaries."""
        limit = min(max(limit, 10), 200)
        items = (
            (
                await self.session.execute(
                    select(KnowledgeItem.title, KnowledgeItem.summary)
                    .where(KnowledgeItem.status == "available")
                    .limit(500)
                )
            )
            .all()
        )

        stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
            "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
            "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
            "与", "及", "或", "但", "而", "从", "被", "把", "对", "等", "可以",
            "进行", "使用", "通过", "以及", "并且", "因为", "所以", "如果",
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "can", "could", "may", "might", "shall", "should", "this",
            "that", "these", "those", "it", "its", "they", "them",
            "for", "with", "about", "into", "over", "after", "before",
            "and", "but", "or", "not", "so", "if", "then", "than",
            "also", "very", "just", "each", "all", "any", "both",
        }

        counter: Counter = Counter()
        word_pattern = re.compile(r"[a-zA-Z一-鿿]{2,}")

        for title, summary in items:
            text_content = (title or "") + " " + (summary or "")
            words = word_pattern.findall(text_content.lower())
            for w in words:
                if w not in stop_words:
                    counter[w] += 1

        most_common = counter.most_common(limit)
        return [{"word": word, "count": count} for word, count in most_common]
