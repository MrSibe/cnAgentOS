"""Admin REST API for dashboard statistics and sentiment analysis (Phase 8)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import (
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import SentimentTaskCreate
from cnagentos.services.dashboard import DashboardService
from cnagentos.services.sentiment import SentimentAnalysisService

router = APIRouter(prefix="/api/v1/admin", tags=["管理端-数智大屏与舆情分析"])

# Permission guards
SentimentViewer = Annotated[CurrentContext, Depends(require_permission("sentiment.view"))]
SentimentAdmin = Annotated[CurrentContext, Depends(require_permission("sentiment.manage"))]


def dash_service(session: DbSession) -> DashboardService:
    return DashboardService(session)


def sentiment_service(
    request: Request, session: DbSession, context: CurrentContext,
) -> SentimentAnalysisService:
    return SentimentAnalysisService(
        session, context.user, request.client.host if request.client else None,
    )


# =============================================================================
# Dashboard Statistics
# =============================================================================


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
):
    svc = dash_service(session)
    return success_response(request, await svc.get_stats())


@router.get("/dashboard/trends")
async def get_dashboard_trends(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
    days: int = Query(default=30, ge=1, le=90),
):
    svc = dash_service(session)
    return success_response(request, await svc.get_trends(days))


@router.get("/dashboard/keywords")
async def get_dashboard_keywords(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
    limit: int = Query(default=50, ge=10, le=200),
):
    svc = dash_service(session)
    return success_response(request, await svc.get_keywords(limit))


# =============================================================================
# Sentiment Analysis Tasks
# =============================================================================


@router.get("/sentiment/tasks")
async def list_sentiment_tasks(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    svc = sentiment_service(request, session, context)
    data, total = await svc.list_tasks(page, page_size, status)
    return success_response(request, data, page=page, page_size=page_size, total=total)


@router.post("/sentiment/tasks")
async def create_sentiment_task(
    request: Request,
    session: DbSession,
    context: SentimentAdmin,
    payload: SentimentTaskCreate,
    _=Depends(require_csrf),
):
    svc = sentiment_service(request, session, context)
    return success_response(request, await svc.create_task(payload))


@router.get("/sentiment/tasks/{task_id}")
async def get_sentiment_task(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
    task_id: str,
):
    svc = sentiment_service(request, session, context)
    return success_response(request, await svc.get_task(task_id))


@router.get("/sentiment/tasks/{task_id}/reports")
async def get_sentiment_task_reports(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
    task_id: str,
):
    svc = sentiment_service(request, session, context)
    return success_response(request, await svc.get_task_reports(task_id))


@router.get("/sentiment/reports/{report_id}")
async def get_sentiment_report(
    request: Request,
    session: DbSession,
    context: SentimentViewer,
    report_id: str,
):
    svc = sentiment_service(request, session, context)
    return success_response(request, await svc.get_report(report_id))
