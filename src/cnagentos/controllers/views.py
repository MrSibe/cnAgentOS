import mimetypes
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


STATIC_ROOT = Path(__file__).resolve().parents[1] / "views" / "static"
INDEX_FILE = STATIC_ROOT / "index.html"
mimetypes.add_type("text/javascript", ".js")

router = APIRouter(tags=["views"])


@router.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


@router.get("/admin", include_in_schema=False)
@router.get("/admin/{path:path}", include_in_schema=False)
async def admin_view(path: str = "") -> FileResponse:
    return FileResponse(INDEX_FILE)
