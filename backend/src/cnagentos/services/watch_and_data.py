"""
Watch and Data service for collection management.

Handles data sources, rules, collection tasks, and knowledge items.
"""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    AuditLog,
    CollectionTask,
    CollectionTaskItem,
    CollectionTaskSource,
    KnowledgeItem,
    User,
    WatchRule,
    WatchSource,
    utc_now,
)
from cnagentos.schemas import (
    CollectionTaskCreate,
    KnowledgeItemFilters,
    WatchRuleCreate,
    WatchRuleUpdate,
    WatchSourceCreate,
    WatchSourceUpdate,
)
from cnagentos.security import (
    SSRFValidationError,
    decrypt,
    encrypt,
    generate_mask,
    validate_request_headers,
    validate_url,
)

VALID_SOURCE_TYPES = {"web_api", "web_page"}
VALID_RULE_STATUSES = {"active", "disabled"}
VALID_TASK_STATUSES = {"pending", "running", "succeeded", "partial_failed", "failed", "cancelled"}
VALID_ITEM_STATUSES = {"available", "excluded", "archived"}
INGEST_RESULTS = {"created", "updated", "duplicate"}
ALLOWED_EXTRACTOR_TYPES = {"json", "html"}


class WatchService:
    def __init__(
        self, session: AsyncSession, actor: User, ip_address: str | None = None
    ) -> None:
        self.session = session
        self.actor = actor
        self.actor_id = actor.id
        self.ip_address = ip_address

    async def _audit(
        self,
        action: str,
        target_type: str,
        target_id: str | None,
        result: str,
        detail: dict | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                id=str(uuid4()),
                actor_user_id=self.actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                result=result,
                detail=detail,
                ip_address=self.ip_address,
            )
        )

    async def _serialize_source(self, source: WatchSource) -> dict:
        return {
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "entry_url": source.entry_url,
            "allowed_hosts": source.allowed_hosts,
            "auth_configured": source.auth_ciphertext is not None,
            "auth_mask": source.auth_mask,
            "status": source.status,
            "description": source.description,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
        }

    async def _serialize_rule(self, rule: WatchRule) -> dict:
        return {
            "id": rule.id,
            "source_id": rule.source_id,
            "name": rule.name,
            "request_method": rule.request_method,
            "request_headers": rule.request_headers,
            "request_params": rule.request_params,
            "extractor_type": rule.extractor_type,
            "extractor_config": rule.extractor_config,
            "status": rule.status,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
        }

    # --- Data Source CRUD ---
    async def list_sources(
        self, page: int, page_size: int, q: str | None, status: str | None, source_type: str | None
    ) -> tuple[list[dict], int]:
        conditions = []
        if q:
            conditions.append(
                WatchSource.name.ilike(f"%{q}%")
                | WatchSource.entry_url.ilike(f"%{q}%")
            )
        if status:
            if status not in VALID_SOURCE_TYPES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(WatchSource.status == status)
        if source_type:
            if source_type not in VALID_SOURCE_TYPES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"source_type": "无效类型"})
            conditions.append(WatchSource.source_type == source_type)
        total = await self.session.scalar(
            select(func.count()).select_from(WatchSource).where(*conditions)
        )
        sources = (
            await self.session.scalars(
                select(WatchSource)
                .where(*conditions)
                .order_by(WatchSource.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [await self._serialize_source(s) for s in sources], int(total or 0)

    async def create_source(self, payload: WatchSourceCreate) -> dict:
        try:
            validate_url(payload.entry_url, payload.allowed_hosts)
        except SSRFValidationError as e:
            raise ApiError(422, "SOURCE_UNSAFE", str(e), {"reason": e.reason})

        if payload.auth_config:
            validate_request_headers(payload.auth_config.get("headers"))

        source = WatchSource(
            id=str(uuid4()),
            name=payload.name,
            source_type=payload.source_type,
            entry_url=payload.entry_url,
            allowed_hosts=payload.allowed_hosts,
            status="disabled",
            description=payload.description,
            created_by=self.actor_id,
        )
        if payload.auth_config:
            auth_json = json.dumps(payload.auth_config)
            source.auth_ciphertext = encrypt(auth_json)
            source.auth_mask = "****已配置"

        self.session.add(source)
        await self._audit("watch.source.created", "watch_source", source.id, "succeeded", {"name": source.name})
        await self.session.commit()
        return await self._serialize_source(source)

    async def get_source(self, source_id: str) -> dict:
        source = await self.session.get(WatchSource, source_id)
        if source is None:
            raise ApiError(404, "NOT_FOUND", "数据源不存在")
        return await self._serialize_source(source)

    async def update_source(self, source_id: str, payload: WatchSourceUpdate) -> dict:
        source = await self.session.get(WatchSource, source_id)
        if source is None:
            raise ApiError(404, "NOT_FOUND", "数据源不存在")

        if payload.entry_url or payload.allowed_hosts:
            check_url = payload.entry_url or source.entry_url
            check_hosts = payload.allowed_hosts or source.allowed_hosts
            try:
                validate_url(check_url, check_hosts)
            except SSRFValidationError as e:
                raise ApiError(422, "SOURCE_UNSAFE", str(e), {"reason": e.reason})

        if payload.name is not None:
            source.name = payload.name
        if payload.entry_url is not None:
            source.entry_url = payload.entry_url
        if payload.allowed_hosts is not None:
            source.allowed_hosts = payload.allowed_hosts
        if "description" in payload.model_fields_set:
            source.description = payload.description
        if payload.auth_config is not None:
            validate_request_headers(payload.auth_config.get("headers"))
            auth_json = json.dumps(payload.auth_config)
            source.auth_ciphertext = encrypt(auth_json)
            source.auth_mask = "****已配置"

        await self._audit("watch.source.updated", "watch_source", source.id, "succeeded")
        await self.session.commit()
        return await self._serialize_source(source)

    async def update_source_status(self, source_id: str, status: str) -> dict:
        if status not in VALID_SOURCE_TYPES:
            raise ApiError(409, "INVALID_STATE", "无效的状态值")

        source = await self.session.get(WatchSource, source_id)
        if source is None:
            raise ApiError(404, "NOT_FOUND", "数据源不存在")

        if status == "active":
            has_active_rule = await self.session.scalar(
                select(func.count())
                .select_from(WatchRule)
                .where(WatchRule.source_id == source_id, WatchRule.status == "active")
            )
            if not has_active_rule:
                raise ApiError(409, "INVALID_STATE", "启用数据源前至少需要一条启用状态的采集规则")

        source.status = status
        await self._audit(
            "watch.source.status_changed",
            "watch_source",
            source.id,
            "succeeded",
            {"status": status},
        )
        await self.session.commit()
        return await self._serialize_source(source)

    # --- Watch Rules CRUD ---
    async def list_rules(self, source_id: str) -> list[dict]:
        source = await self.session.get(WatchSource, source_id)
        if source is None:
            raise ApiError(404, "NOT_FOUND", "数据源不存在")

        rules = (
            await self.session.scalars(
                select(WatchRule)
                .where(WatchRule.source_id == source_id)
                .order_by(WatchRule.created_at.desc())
            )
        ).all()
        return [await self._serialize_rule(r) for r in rules]

    async def create_rule(self, source_id: str, payload: WatchRuleCreate) -> dict:
        source = await self.session.get(WatchSource, source_id)
        if source is None:
            raise ApiError(404, "NOT_FOUND", "数据源不存在")

        if payload.extractor_type not in ALLOWED_EXTRACTOR_TYPES:
            raise ApiError(400, "VALIDATION_ERROR", "不支持的解析类型")

        if payload.request_headers:
            validate_request_headers(payload.request_headers)

        rule = WatchRule(
            id=str(uuid4()),
            source_id=source_id,
            name=payload.name,
            request_method=payload.request_method,
            request_headers=payload.request_headers,
            request_params=payload.request_params,
            extractor_type=payload.extractor_type,
            extractor_config=payload.extractor_config,
            status="disabled",
        )
        self.session.add(rule)
        await self._audit("watch.rule.created", "watch_rule", rule.id, "succeeded", {"name": rule.name})
        await self.session.commit()
        return await self._serialize_rule(rule)

    async def update_rule(self, rule_id: str, payload: WatchRuleUpdate) -> dict:
        rule = await self.session.get(WatchRule, rule_id)
        if rule is None:
            raise ApiError(404, "NOT_FOUND", "采集规则不存在")

        source = await self.session.get(WatchSource, rule.source_id)
        if source is None:
            raise ApiError(404, "NOT_FOUND", "关联的数据源不存在")

        if payload.extractor_type and payload.extractor_type not in ALLOWED_EXTRACTOR_TYPES:
            raise ApiError(400, "VALIDATION_ERROR", "不支持的解析类型")

        if payload.request_headers:
            validate_request_headers(payload.request_headers)

        if payload.name is not None:
            rule.name = payload.name
        if payload.request_method is not None:
            rule.request_method = payload.request_method
        if payload.request_headers is not None:
            rule.request_headers = payload.request_headers
        if payload.request_params is not None:
            rule.request_params = payload.request_params
        if payload.extractor_type is not None:
            rule.extractor_type = payload.extractor_type
        if payload.extractor_config is not None:
            rule.extractor_config = payload.extractor_config
        if payload.status is not None:
            if payload.status == "active":
                try:
                    validate_url(source.entry_url, source.allowed_hosts)
                except SSRFValidationError as e:
                    raise ApiError(422, "SOURCE_UNSAFE", str(e), {"reason": e.reason})
            rule.status = payload.status

        await self._audit("watch.rule.updated", "watch_rule", rule.id, "succeeded")
        await self.session.commit()
        return await self._serialize_rule(rule)

    # --- Collection Tasks ---
    async def create_task(self, payload: CollectionTaskCreate) -> dict:
        source_ids = set()
        for target in payload.targets:
            source_ids.add(target.source_id)

        for source_id in source_ids:
            source = await self.session.get(WatchSource, source_id)
            if source is None:
                raise ApiError(404, "NOT_FOUND", f"数据源 {source_id} 不存在")
            if source.status != "active":
                raise ApiError(409, "INVALID_STATE", f"数据源 {source.name} 未启用")

            try:
                validate_url(source.entry_url, source.allowed_hosts)
            except SSRFValidationError as e:
                raise ApiError(422, "SOURCE_UNSAFE", str(e), {"reason": e.reason})

            for target in payload.targets:
                if target.source_id == source_id:
                    rule = await self.session.get(WatchRule, target.rule_id)
                    if rule is None:
                        raise ApiError(404, "NOT_FOUND", f"规则 {target.rule_id} 不存在")
                    if rule.source_id != source_id:
                        raise ApiError(400, "VALIDATION_ERROR", f"规则 {target.rule_id} 不属于数据源 {source_id}")
                    if rule.status != "active":
                        raise ApiError(409, "INVALID_STATE", f"规则 {rule.name} 未启用")

        task = CollectionTask(
            id=str(uuid4()),
            created_by=self.actor_id,
            status="pending",
            trigger_type="manual",
            source_count=len(source_ids),
        )
        self.session.add(task)

        for target in payload.targets:
            task_source = CollectionTaskSource(
                task_id=task.id,
                source_id=target.source_id,
                rule_id=target.rule_id,
                status="pending",
            )
            self.session.add(task_source)

        await self._audit("watch.task.created", "collection_task", task.id, "succeeded", {"targets": len(payload.targets)})
        await self.session.commit()
        return {
            "id": task.id,
            "status": task.status,
            "created_at": task.created_at,
        }

    async def list_tasks(
        self,
        page: int,
        page_size: int,
        status: str | None,
        started_from: datetime | None,
        started_to: datetime | None,
    ) -> tuple[list[dict], int]:
        conditions = []
        if status:
            if status not in VALID_TASK_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(CollectionTask.status == status)
        if started_from:
            conditions.append(CollectionTask.created_at >= started_from)
        if started_to:
            conditions.append(CollectionTask.created_at <= started_to)

        total = await self.session.scalar(
            select(func.count()).select_from(CollectionTask).where(*conditions)
        )
        tasks = (
            await self.session.scalars(
                select(CollectionTask)
                .where(*conditions)
                .order_by(CollectionTask.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        data = []
        for task in tasks:
            data.append({
                "id": task.id,
                "status": task.status,
                "trigger_type": task.trigger_type,
                "source_count": task.source_count,
                "item_success_count": task.item_success_count,
                "item_failure_count": task.item_failure_count,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "created_at": task.created_at,
            })
        return data, int(total or 0)

    async def get_task(self, task_id: str) -> dict:
        task = await self.session.get(CollectionTask, task_id)
        if task is None:
            raise ApiError(404, "NOT_FOUND", "任务不存在")

        await self.session.scalars(
            select(CollectionTaskSource).where(CollectionTaskSource.task_id == task_id)
        )
        task_sources = (
            await self.session.scalars(
                select(CollectionTaskSource)
                .options(selectinload(CollectionTaskSource.source), selectinload(CollectionTaskSource.rule))
                .where(CollectionTaskSource.task_id == task_id)
            )
        ).all()

        sources_data = []
        for ts in task_sources:
            sources_data.append({
                "source_id": ts.source_id,
                "source_name": ts.source.name if ts.source else None,
                "rule_id": ts.rule_id,
                "rule_name": ts.rule.name if ts.rule else None,
                "status": ts.status,
                "failure_summary": ts.failure_summary,
                "started_at": ts.started_at,
                "finished_at": ts.finished_at,
            })

        return {
            "id": task.id,
            "status": task.status,
            "trigger_type": task.trigger_type,
            "source_count": task.source_count,
            "item_success_count": task.item_success_count,
            "item_failure_count": task.item_failure_count,
            "failure_summary": task.failure_summary,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "created_at": task.created_at,
            "sources": sources_data,
        }

    async def cancel_task(self, task_id: str) -> dict:
        task = await self.session.get(CollectionTask, task_id)
        if task is None:
            raise ApiError(404, "NOT_FOUND", "任务不存在")

        if task.status != "pending":
            raise ApiError(409, "INVALID_STATE", "只能取消待执行的任务")

        task.status = "cancelled"
        await self._audit("watch.task.cancelled", "collection_task", task.id, "succeeded")
        await self.session.commit()
        return {"id": task.id, "status": task.status}

    async def execute_task(self, task_id: str) -> None:
        """Execute a collection task asynchronously."""
        task = await self.session.get(CollectionTask, task_id)
        if task is None or task.status != "pending":
            return

        task.status = "running"
        task.started_at = utc_now()
        await self.session.commit()

        try:
            task_sources = (
                await self.session.scalars(
                    select(CollectionTaskSource)
                    .options(selectinload(CollectionTaskSource.source), selectinload(CollectionTaskSource.rule))
                    .where(CollectionTaskSource.task_id == task_id)
                )
            ).all()

            total_success = 0
            total_failure = 0
            failure_reasons = []

            for ts in task_sources:
                ts.status = "running"
                ts.started_at = utc_now()
                await self.session.commit()

                try:
                    success_count, failure_count, reason = await self._execute_source_collection(ts)
                    total_success += success_count
                    total_failure += failure_count
                    if reason:
                        failure_reasons.append(reason)
                    ts.status = "succeeded" if failure_count == 0 else "failed"
                except Exception as e:
                    ts.status = "failed"
                    ts.failure_summary = str(e)[:500]
                    total_failure += 1
                    failure_reasons.append(str(e)[:200])

                ts.finished_at = utc_now()
                await self.session.commit()

            task.item_success_count = total_success
            task.item_failure_count = total_failure
            task.failure_summary = "; ".join(failure_reasons[:5]) if failure_reasons else None

            if total_failure > 0 and total_success > 0:
                task.status = "partial_failed"
            elif total_failure > 0:
                task.status = "failed"
            else:
                task.status = "succeeded"

        except Exception as e:
            task.status = "failed"
            task.failure_summary = str(e)[:500]
        finally:
            task.finished_at = utc_now()
            await self.session.commit()

    async def _execute_source_collection(self, task_source: CollectionTaskSource) -> tuple[int, int, str | None]:
        """Execute collection for a single source/rule."""
        source = task_source.source
        rule = task_source.rule

        if not source or not rule:
            return 0, 1, "数据源或规则不存在"

        headers = {"Accept": "text/html,application/json", **rule.request_headers} if rule.request_headers else {}
        params = rule.request_params or {}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method=rule.request_method,
                    url=source.entry_url,
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
        except httpx.RequestError as e:
            return 0, 1, f"请求失败: {str(e)[:200]}"

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or rule.extractor_type == "json":
            items = self._extract_json_items(response.text, rule.extractor_config)
        else:
            items = self._extract_html_items(response.text, rule.extractor_config)

        success_count = 0
        failure_count = 0
        for item_data in items:
            try:
                await self._ingest_item(task_source.task_id, source, item_data)
                success_count += 1
            except Exception:
                failure_count += 1

        return success_count, failure_count, None

    def _extract_json_items(self, text: str, config: dict) -> list[dict]:
        """Extract items from JSON response."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []

        items = []
        items_key = config.get("items_key", "data")
        if items_key in data:
            items = data[items_key] if isinstance(data[items_key], list) else [data[items_key]]
        elif isinstance(data, list):
            items = data
        return items

    def _extract_html_items(self, html: str, config: dict) -> list[dict]:
        """Extract items from HTML response."""
        soup = BeautifulSoup(html, "html.parser")
        items = []

        item_selector = config.get("item_selector", "a")
        title_selector = config.get("title_selector")
        url_selector = config.get("url_selector", "a@href")
        content_selector = config.get("content_selector")

        for element in soup.select(item_selector):
            item = {}
            if title_selector:
                title_elem = element.select_one(title_selector)
                if title_elem:
                    item["title"] = title_elem.get_text(strip=True)
            else:
                item["title"] = element.get_text(strip=True)[:200]

            if "@href" in url_selector:
                attr = url_selector.split("@")[1]
                href = element.get(attr)
                item["url"] = href
            else:
                url_elem = element.select_one(url_selector)
                if url_elem:
                    item["url"] = url_elem.get_text(strip=True)

            if content_selector:
                content_elem = element.select_one(content_selector)
                if content_elem:
                    item["content"] = content_elem.get_text(strip=True)

            if item.get("title") or item.get("url"):
                items.append(item)

        return items

    async def _ingest_item(self, task_id: str, source: WatchSource, item_data: dict) -> None:
        """Ingest a single collected item."""
        content = item_data.get("content") or item_data.get("title", "")
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        existing = await self.session.scalar(
            select(KnowledgeItem)
            .where(KnowledgeItem.source_id == source.id, KnowledgeItem.content_hash == content_hash)
        )

        if existing:
            ingest_result = "duplicate"
            item = existing
        else:
            ingest_result = "created"
            item = KnowledgeItem(
                id=str(uuid4()),
                source_id=source.id,
                task_id=task_id,
                title=item_data.get("title", "")[:512],
                content=content,
                canonical_url=item_data.get("url"),
                content_hash=content_hash,
                collected_at=utc_now(),
                status="available",
            )
            self.session.add(item)

        task_item = CollectionTaskItem(
            task_id=task_id,
            knowledge_item_id=item.id,
            source_id=source.id,
            ingest_result=ingest_result,
        )
        self.session.add(task_item)
        await self.session.flush()

    # --- Knowledge Items ---
    async def list_knowledge_items(
        self,
        page: int,
        page_size: int,
        q: str | None,
        filters: KnowledgeItemFilters,
    ) -> tuple[list[dict], int]:
        conditions = []
        if q:
            conditions.append(
                KnowledgeItem.title.ilike(f"%{q}%")
                | KnowledgeItem.content.ilike(f"%{q}%")
            )
        if filters.source_id:
            conditions.append(KnowledgeItem.source_id == filters.source_id)
        if filters.status:
            if filters.status not in VALID_ITEM_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(KnowledgeItem.status == filters.status)
        if filters.collected_from:
            conditions.append(KnowledgeItem.collected_at >= filters.collected_from)
        if filters.collected_to:
            conditions.append(KnowledgeItem.collected_at <= filters.collected_to)

        total = await self.session.scalar(
            select(func.count()).select_from(KnowledgeItem).where(*conditions)
        )
        items = (
            await self.session.scalars(
                select(KnowledgeItem)
                .options(selectinload(KnowledgeItem.source))
                .where(*conditions)
                .order_by(KnowledgeItem.collected_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()

        data = []
        for item in items:
            data.append({
                "id": item.id,
                "source_id": item.source_id,
                "source_name": item.source.name if item.source else None,
                "title": item.title,
                "summary": item.summary or (item.content[:200] + "..." if len(item.content) > 200 else item.content),
                "canonical_url": item.canonical_url,
                "content_hash": item.content_hash,
                "status": item.status,
                "published_at": item.published_at,
                "collected_at": item.collected_at,
                "reviewed_at": item.reviewed_at,
                "created_at": item.created_at,
            })
        return data, int(total or 0)

    async def get_knowledge_item(self, item_id: str) -> dict:
        item = await self.session.get(KnowledgeItem, item_id)
        if item is None:
            raise ApiError(404, "NOT_FOUND", "内容不存在")
        return {
            "id": item.id,
            "source_id": item.source_id,
            "title": item.title,
            "content": item.content,
            "summary": item.summary,
            "canonical_url": item.canonical_url,
            "content_hash": item.content_hash,
            "status": item.status,
            "published_at": item.published_at,
            "collected_at": item.collected_at,
            "reviewed_at": item.reviewed_at,
            "created_at": item.created_at,
        }

    async def update_knowledge_item_status(self, item_id: str, status: str) -> dict:
        if status not in VALID_ITEM_STATUSES:
            raise ApiError(409, "INVALID_STATE", "无效的状态值")

        item = await self.session.get(KnowledgeItem, item_id)
        if item is None:
            raise ApiError(404, "NOT_FOUND", "内容不存在")

        old_status = item.status
        item.status = status
        item.reviewed_by = self.actor_id
        item.reviewed_at = utc_now()

        await self._audit(
            "data.item.status_changed",
            "knowledge_item",
            item.id,
            "succeeded",
            {"old_status": old_status, "new_status": status},
        )
        await self.session.commit()
        return {
            "id": item.id,
            "status": item.status,
            "reviewed_at": item.reviewed_at,
        }
