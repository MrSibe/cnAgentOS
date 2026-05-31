"""Chat file upload/download endpoints (Phase 7).

Upload via REST (multipart/form-data), then reference the returned ``file_id``
in a WebSocket ``send_message`` with ``content_type: "file"``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, UploadFile

from cnagentos.api import success_response
from cnagentos.controllers.dependencies import CurrentContext, DbSession, require_permission
from cnagentos.services.file import FileService, MAX_FILE_SIZE, ALLOWED_CONTENT_TYPES
from cnagentos.services.file_storage import FileStorageService

router = APIRouter(prefix="/api/v1/chat/files", tags=["聊天-文件"])

ChatFileUser = Annotated[CurrentContext, Depends(require_permission("chat.files.upload"))]


def service_for(request: Request, session: DbSession, context: CurrentContext) -> FileService:
    return FileService(
        session, context.user, request.client.host if request.client else None,
    )


@router.post("/upload")
async def upload_file(
    request: Request,
    session: DbSession,
    context: ChatFileUser,
    file: UploadFile,
):
    """Upload a file and return its metadata.

    The caller should then send the returned ``id`` in a WebSocket
    ``send_message`` frame with ``content_type: "file"``.
    """
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"

    svc = service_for(request, session, context)
    result = await svc.upload_file(data, file.filename or "unnamed", content_type)
    # Add download URL
    result["url"] = f"/api/v1/chat/files/{result['id']}/download"
    return success_response(request, result)


@router.get("/{file_id}")
async def get_file_metadata(
    request: Request,
    session: DbSession,
    context: ChatFileUser,
    file_id: str,
):
    svc = service_for(request, session, context)
    result = await svc.get_file_metadata(file_id)
    result["url"] = f"/api/v1/chat/files/{file_id}/download"
    return success_response(request, result)


@router.get("/{file_id}/download")
async def download_file(
    request: Request,
    session: DbSession,
    context: ChatFileUser,
    file_id: str,
):
    from fastapi.responses import StreamingResponse
    import io

    svc = service_for(request, session, context)
    data, filename, mime_type = await svc.download_file(file_id)
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )
