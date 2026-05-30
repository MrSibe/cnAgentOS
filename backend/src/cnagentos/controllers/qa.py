"""智能问数 API 控制器"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import (
    CurrentContext,
    DbSession,
    require_csrf,
    require_permission,
)
from cnagentos.schemas import (
    QASessionCreate,
    QASessionUpdate,
    QAQuestionRequest,
)
from cnagentos.services.qa_engine import QAEngineService


router = APIRouter(prefix="/api/v1/qa", tags=["智能问数"])

QAUser = Annotated[CurrentContext, Depends(require_permission("qa.use"))]


def _get_qa_service(session: DbSession, context: CurrentContext, request: Request) -> QAEngineService:
    return QAEngineService(
        session=session,
        actor=context.user,
        ip_address=request.client.host if request.client else None,
    )


# =============================================================================
# 会话管理
# =============================================================================

@router.get("/sessions")
async def list_sessions(
    request: Request,
    session: DbSession,
    context: QAUser,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
):
    """获取当前用户的会话列表"""
    service = _get_qa_service(session, context, request)
    data, total = await service.list_sessions(page, page_size, q)
    return success_response(
        request, data, meta={"page": page, "page_size": page_size, "total": total}
    )


@router.post("/sessions", status_code=201)
async def create_session(
    request: Request,
    session: DbSession,
    payload: QASessionCreate,
    context: QAUser,
    _: None = Depends(require_csrf),
):
    """创建新会话"""
    service = _get_qa_service(session, context, request)
    data = await service.create_session(payload)
    return success_response(request, data, status_code=201)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    session: DbSession,
    context: QAUser,
):
    """获取会话详情"""
    service = _get_qa_service(session, context, request)
    data = await service.get_session(session_id)
    return success_response(request, data)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: Request,
    session: DbSession,
    payload: QASessionUpdate,
    context: QAUser,
    _: None = Depends(require_csrf),
):
    """更新会话"""
    service = _get_qa_service(session, context, request)
    data = await service.update_session(session_id, payload)
    return success_response(request, data)


# =============================================================================
# 消息管理
# =============================================================================

@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    request: Request,
    session: DbSession,
    context: QAUser,
):
    """获取会话中的消息列表"""
    service = _get_qa_service(session, context, request)
    data = await service.list_messages(session_id)
    return success_response(request, data)


# =============================================================================
# 流式问答
# =============================================================================

@router.post("/sessions/{session_id}/questions/stream")
async def ask_question(
    session_id: str,
    request: Request,
    session: DbSession,
    payload: QAQuestionRequest,
    context: QAUser,
    _: None = Depends(require_csrf),
):
    """流式提问并获取回答
    
    使用 SSE (Server-Sent Events) 返回流式回答。
    
    事件流:
    - data: {'content': '...', 'full_content': '...'} - 增量内容片段
    - event: completed - 完成事件，包含 message_id 和 citations
    - event: error - 错误事件
    - data: [DONE] - 结束标记
    """
    service = _get_qa_service(session, context, request)
    _, generator = await service.stream_question(session_id, payload)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# 引用管理
# =============================================================================

@router.get("/messages/{message_id}/citations")
async def get_citations(
    message_id: str,
    request: Request,
    session: DbSession,
    context: QAUser,
):
    """获取回答的引用列表"""
    service = _get_qa_service(session, context, request)
    data = await service.get_citations(message_id)
    return success_response(request, data)
