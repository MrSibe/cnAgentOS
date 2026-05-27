from __future__ import annotations

import argparse
import json
import mimetypes
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = ROOT / "app" / "views" / "static"

CSRF_TOKEN = "dev-csrf-token"


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class DevApi:
    permissions = [
        {"id": "perm-users", "code": "users.manage", "name": "用户管理", "module": "认证与权限", "description": "维护用户与状态"},
        {"id": "perm-roles", "code": "roles.manage", "name": "角色管理", "module": "认证与权限", "description": "维护角色与授权"},
        {"id": "perm-functions", "code": "functions.manage", "name": "功能导航管理", "module": "认证与权限", "description": "维护后台菜单"},
        {"id": "perm-models-view", "code": "models.view", "name": "模型查看", "module": "模型引擎", "description": "查看模型配置与统计"},
        {"id": "perm-models-manage", "code": "models.manage", "name": "模型管理", "module": "模型引擎", "description": "维护模型配置"},
        {"id": "perm-models-test", "code": "models.test", "name": "模型测试", "module": "模型引擎", "description": "执行模型连接测试"},
        {"id": "perm-audit", "code": "audit.view", "name": "审计查看", "module": "安全审计", "description": "查看脱敏审计记录"},
    ]

    users = [
        {
            "id": "user-admin",
            "username": "admin",
            "display_name": "系统管理员",
            "status": "active",
            "is_system_admin": True,
            "roles": [{"id": "role-admin", "name": "系统管理员"}],
            "created_at": "2026-05-27T06:00:00Z",
            "updated_at": "2026-05-27T06:00:00Z",
        },
        {
            "id": "user-ops",
            "username": "operator",
            "display_name": "运营管理员",
            "status": "active",
            "is_system_admin": False,
            "roles": [{"id": "role-ops", "name": "模型运营"}],
            "created_at": "2026-05-27T06:20:00Z",
            "updated_at": "2026-05-27T06:25:00Z",
        },
    ]

    roles = [
        {
            "id": "role-admin",
            "code": "system_admin",
            "name": "系统管理员",
            "description": "拥有首版后台管理能力",
            "status": "active",
            "is_system": True,
            "permission_codes": [item["code"] for item in permissions],
        },
        {
            "id": "role-ops",
            "code": "model_operator",
            "name": "模型运营",
            "description": "维护模型配置并执行测试",
            "status": "active",
            "is_system": False,
            "permission_codes": ["models.view", "models.manage", "models.test"],
        },
    ]

    functions = [
        {"id": "fn-admin", "code": "admin", "name": "系统管理", "parent_id": None, "route_path": None, "icon": "shield", "sort_order": 10, "required_permission_code": None, "status": "active", "is_system": True},
        {"id": "fn-users", "code": "users", "name": "用户管理", "parent_id": "fn-admin", "route_path": "/admin/users", "icon": "users", "sort_order": 10, "required_permission_code": "users.manage", "status": "active", "is_system": True},
        {"id": "fn-roles", "code": "roles", "name": "角色权限", "parent_id": "fn-admin", "route_path": "/admin/roles", "icon": "key", "sort_order": 20, "required_permission_code": "roles.manage", "status": "active", "is_system": True},
        {"id": "fn-permissions", "code": "permissions", "name": "权限字典", "parent_id": "fn-admin", "route_path": "/admin/permissions", "icon": "key", "sort_order": 30, "required_permission_code": "roles.manage", "status": "active", "is_system": True},
        {"id": "fn-functions", "code": "functions", "name": "功能导航", "parent_id": "fn-admin", "route_path": "/admin/functions", "icon": "menu", "sort_order": 40, "required_permission_code": "functions.manage", "status": "active", "is_system": True},
        {"id": "fn-engine", "code": "engine", "name": "模型引擎", "parent_id": None, "route_path": None, "icon": "cpu", "sort_order": 20, "required_permission_code": None, "status": "active", "is_system": True},
        {"id": "fn-models", "code": "models", "name": "模型配置", "parent_id": "fn-engine", "route_path": "/admin/models", "icon": "sparkles", "sort_order": 10, "required_permission_code": "models.view", "status": "active", "is_system": True},
        {"id": "fn-model-calls", "code": "model_calls", "name": "调用记录", "parent_id": "fn-engine", "route_path": "/admin/model-calls", "icon": "activity", "sort_order": 20, "required_permission_code": "models.view", "status": "active", "is_system": True},
        {"id": "fn-audit", "code": "audit", "name": "审计日志", "parent_id": None, "route_path": "/admin/audit-logs", "icon": "file-search", "sort_order": 90, "required_permission_code": "audit.view", "status": "active", "is_system": True},
    ]

    models = [
        {
            "id": "model-main",
            "name": "主模型",
            "provider_type": "openai_compatible",
            "model_name": "demo-chat",
            "base_url": "https://provider.example/v1",
            "credential_configured": True,
            "credential_mask": "****demo",
            "status": "active",
            "is_default": True,
            "timeout_seconds": 60,
            "description": "用于 Phase1 界面联调的脱敏示例",
            "updated_at": "2026-05-27T06:30:00Z",
        }
    ]

    model_calls = [
        {"id": "call-001", "model_config_id": "model-main", "model_name": "主模型", "purpose": "connection_test", "streamed": False, "status": "succeeded", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "latency_ms": 320, "started_at": "2026-05-27T06:35:00Z"},
    ]

    audit_logs = [
        {"id": "audit-001", "actor": {"id": "user-admin", "display_name": "系统管理员"}, "action": "model.default.updated", "target_type": "model_config", "target_id": "model-main", "result": "succeeded", "detail": {"credential": "masked"}, "created_at": "2026-05-27T06:36:00Z"},
    ]

    @classmethod
    def response(
        cls,
        method: str,
        path: str,
        query: dict[str, list[str]],
        body: dict | None,
        authenticated: bool,
    ) -> tuple[int, dict]:
        if path == "/api/v1/auth/login" and method == "POST":
            username = (body or {}).get("username")
            password = (body or {}).get("password")
            if username and password:
                return HTTPStatus.OK, {
                    "data": {
                        "user": {"id": "user-admin", "username": username, "display_name": "系统管理员"},
                        "csrf_token": CSRF_TOKEN,
                    }
                }
            return HTTPStatus.UNAUTHORIZED, {"error": {"code": "LOGIN_FAILED", "message": "登录失败"}}

        if not authenticated:
            return HTTPStatus.UNAUTHORIZED, {"error": {"code": "AUTH_REQUIRED", "message": "需要登录"}}

        if path == "/api/v1/auth/logout" and method == "POST":
            return HTTPStatus.NO_CONTENT, {}

        if path == "/api/v1/auth/me" and method == "GET":
            return HTTPStatus.OK, {
                "data": {
                    "id": "user-admin",
                    "username": "admin",
                    "display_name": "系统管理员",
                    "permissions": [item["code"] for item in cls.permissions],
                }
            }

        if path == "/api/v1/auth/navigation" and method == "GET":
            return HTTPStatus.OK, {"data": cls._navigation_tree()}

        if path == "/api/v1/admin/permissions" and method == "GET":
            return cls._page(cls.permissions, query)

        if path == "/api/v1/admin/users":
            if method == "GET":
                return cls._page(cls.users, query)
            if method == "POST":
                user = {
                    "id": f"user-{len(cls.users) + 1}",
                    "username": (body or {}).get("username", "new-user"),
                    "display_name": (body or {}).get("display_name", "新用户"),
                    "status": "active",
                    "is_system_admin": False,
                    "roles": [],
                    "created_at": "2026-05-27T07:00:00Z",
                    "updated_at": "2026-05-27T07:00:00Z",
                }
                cls.users.append(user)
                return HTTPStatus.CREATED, {"data": user}

        if path == "/api/v1/admin/roles":
            if method == "GET":
                return cls._page(cls.roles, query)
            if method == "POST":
                role = {
                    "id": f"role-{len(cls.roles) + 1}",
                    "code": (body or {}).get("code", "custom_role"),
                    "name": (body or {}).get("name", "自定义角色"),
                    "description": (body or {}).get("description", ""),
                    "status": "active",
                    "is_system": False,
                    "permission_codes": [],
                }
                cls.roles.append(role)
                return HTTPStatus.CREATED, {"data": role}

        if path == "/api/v1/admin/functions":
            if method == "GET":
                return cls._page(cls.functions, query)
            if method == "POST":
                item = {
                    "id": f"fn-{len(cls.functions) + 1}",
                    "code": (body or {}).get("code", "new_function"),
                    "name": (body or {}).get("name", "新功能"),
                    "parent_id": (body or {}).get("parent_id"),
                    "route_path": (body or {}).get("route_path"),
                    "icon": (body or {}).get("icon", "circle"),
                    "sort_order": int((body or {}).get("sort_order", 100)),
                    "required_permission_code": (body or {}).get("required_permission_code"),
                    "status": "disabled",
                    "is_system": False,
                }
                cls.functions.append(item)
                return HTTPStatus.CREATED, {"data": item}

        if path == "/api/v1/admin/models":
            if method == "GET":
                return cls._page(cls.models, query)
            if method == "POST":
                item = {
                    "id": f"model-{len(cls.models) + 1}",
                    "name": (body or {}).get("name", "新模型"),
                    "provider_type": "openai_compatible",
                    "model_name": (body or {}).get("model_name", ""),
                    "base_url": (body or {}).get("base_url", ""),
                    "credential_configured": bool((body or {}).get("api_key")),
                    "credential_mask": "****demo" if (body or {}).get("api_key") else "",
                    "status": "disabled",
                    "is_default": False,
                    "timeout_seconds": int((body or {}).get("timeout_seconds", 60)),
                    "description": (body or {}).get("description", ""),
                    "updated_at": "2026-05-27T07:05:00Z",
                }
                cls.models.append(item)
                return HTTPStatus.CREATED, {"data": item}

        if path.startswith("/api/v1/admin/models/") and path.endswith("/connection-tests") and method == "POST":
            call_log_id = f"call-{len(cls.model_calls) + 1:03d}"
            cls.model_calls.append(
                {
                    "id": call_log_id,
                    "model_config_id": path.split("/")[5],
                    "model_name": "主模型",
                    "purpose": "connection_test",
                    "streamed": False,
                    "status": "succeeded",
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                    "latency_ms": 280,
                    "started_at": "2026-05-27T07:10:00Z",
                }
            )
            return HTTPStatus.OK, {
                "data": {
                    "call_log_id": call_log_id,
                    "reply": "连接正常",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14},
                    "latency_ms": 280,
                }
            }

        if path == "/api/v1/admin/model-calls" and method == "GET":
            return cls._page(cls.model_calls, query)

        if path == "/api/v1/admin/model-calls/summary" and method == "GET":
            total = len(cls.model_calls)
            succeeded = len([item for item in cls.model_calls if item["status"] == "succeeded"])
            failed = len([item for item in cls.model_calls if item["status"] == "failed"])
            return HTTPStatus.OK, {"data": {"total_calls": total, "succeeded_calls": succeeded, "failed_calls": failed, "total_tokens": 15, "average_latency_ms": 320}}

        if path == "/api/v1/admin/audit-logs" and method == "GET":
            return cls._page(cls.audit_logs, query)

        return HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND", "message": "资源不存在"}}

    @classmethod
    def stream_model_test(cls) -> list[tuple[str, dict]]:
        call_log_id = f"call-{len(cls.model_calls) + 1:03d}"
        cls.model_calls.append(
            {
                "id": call_log_id,
                "model_config_id": "model-main",
                "model_name": "主模型",
                "purpose": "connection_test",
                "streamed": True,
                "status": "succeeded",
                "prompt_tokens": 8,
                "completion_tokens": 2,
                "total_tokens": 10,
                "latency_ms": 420,
                "started_at": "2026-05-27T07:12:00Z",
            }
        )
        return [
            ("delta", {"content": "连接"}),
            ("delta", {"content": "正常"}),
            ("completed", {"call_log_id": call_log_id, "usage": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10}}),
        ]

    @classmethod
    def _page(cls, items: list[dict], query: dict[str, list[str]]) -> tuple[int, dict]:
        q = query.get("q", [""])[0].strip().lower()
        status = query.get("status", [""])[0].strip()
        data = items
        if q:
            data = [item for item in data if q in json.dumps(item, ensure_ascii=False).lower()]
        if status:
            data = [item for item in data if item.get("status") == status]
        return HTTPStatus.OK, {"data": data, "meta": {"page": 1, "page_size": 20, "total": len(data)}}

    @classmethod
    def _navigation_tree(cls) -> list[dict]:
        active = [item for item in cls.functions if item["status"] == "active"]
        by_parent: dict[str | None, list[dict]] = {}
        for item in active:
            by_parent.setdefault(item["parent_id"], []).append(item)

        def build(parent_id: str | None) -> list[dict]:
            nodes = []
            for item in sorted(by_parent.get(parent_id, []), key=lambda value: value["sort_order"]):
                node = {
                    "id": item["id"],
                    "code": item["code"],
                    "name": item["name"],
                    "icon": item["icon"],
                    "route_path": item["route_path"],
                    "children": build(item["id"]),
                }
                nodes.append(node)
            return nodes

        return build(None)


class DevRequestHandler(BaseHTTPRequestHandler):
    server_version = "cnAgentOSDev/0.1"

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/v1/admin/models/") and parsed.path.endswith("/connection-tests/stream"):
            if not self._authenticated():
                self._send_json_error(HTTPStatus.UNAUTHORIZED, "AUTH_REQUIRED", "需要登录")
                return
            if not self._valid_csrf():
                self._send_json_error(HTTPStatus.FORBIDDEN, "CSRF_INVALID", "CSRF 校验失败")
                return
            self._send_sse()
            return
        if parsed.path.startswith("/api/v1/"):
            self._send_api(parsed.path, parse_qs(parsed.query))
            return
        self._send_static(parsed.path)

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _send_api(self, path: str, query: dict[str, list[str]]) -> None:
        if path != "/api/v1/auth/login":
            if not self._authenticated():
                self._send_json_error(HTTPStatus.UNAUTHORIZED, "AUTH_REQUIRED", "需要登录")
                return
            if self.command in {"POST", "PUT", "PATCH", "DELETE"} and not self._valid_csrf():
                self._send_json_error(HTTPStatus.FORBIDDEN, "CSRF_INVALID", "CSRF 校验失败")
                return

        status, payload = DevApi.response(self.command, path, query, self._read_json(), self._authenticated())
        if status == HTTPStatus.NO_CONTENT:
            self.send_response(status)
            self.send_header("Set-Cookie", "cnagentos_session=; Path=/; Max-Age=0; SameSite=Lax")
            self.end_headers()
            return

        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if path == "/api/v1/auth/login" and status == HTTPStatus.OK:
            self.send_header("Set-Cookie", "cnagentos_session=dev-session; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()
        self.wfile.write(body)

    def _authenticated(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        return "cnagentos_session=dev-session" in cookie

    def _valid_csrf(self) -> bool:
        return self.headers.get("X-CSRF-Token") == CSRF_TOKEN

    def _send_json_error(self, status: HTTPStatus, code: str, message: str) -> None:
        body = _json_bytes({"error": {"code": code, "message": message}})
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for event, data in DevApi.stream_model_test():
            chunk = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(chunk)
            self.wfile.flush()
            time.sleep(0.2)
        self.close_connection = True

    def _send_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            file_path = STATIC_ROOT / "index.html"
        else:
            clean = request_path.lstrip("/")
            file_path = (STATIC_ROOT / clean).resolve()
            if not file_path.is_file() or STATIC_ROOT not in file_path.parents:
                file_path = STATIC_ROOT / "index.html"

        content = file_path.read_bytes()
        content_type = self._content_type(file_path)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _content_type(self, file_path: Path) -> str:
        if file_path.suffix == ".js":
            return "text/javascript"
        return mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the cnAgentOS Phase 1 view development server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DevRequestHandler)
    print(f"cnAgentOS Phase 1 view server: http://{args.host}:{args.port}")
    server.serve_forever()
