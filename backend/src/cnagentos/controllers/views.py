from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response


PROJECT_ROOT = Path(__file__).resolve().parents[4]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_ASSETS = FRONTEND_DIST / "assets"
INDEX_FILE = FRONTEND_DIST / "index.html"

router = APIRouter(tags=["views"])


@router.get("/", include_in_schema=False)
def frontend_entry() -> Response:
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return HTMLResponse(
        """
        <!doctype html>
        <html lang="zh-CN">
          <head><meta charset="utf-8"><title>cnAgentOS 前端未构建</title></head>
          <body>
            <h1>cnAgentOS 前端尚未构建</h1>
            <p>请在仓库根目录执行 <code>pnpm --dir frontend build</code>，或开发时运行 <code>pnpm --dir frontend dev</code>。</p>
          </body>
        </html>
        """,
        status_code=503,
    )


async def index() -> Response:
    return frontend_entry()


@router.get("/admin", include_in_schema=False)
@router.get("/admin/{path:path}", include_in_schema=False)
async def admin_view(path: str = "") -> Response:
    return frontend_entry()
