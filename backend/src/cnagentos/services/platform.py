from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.api import ApiError
from cnagentos.models.entities import (
    AuditLog,
    Function,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from cnagentos.schemas import FunctionCreate, FunctionUpdate, RoleCreate, RoleUpdate, UserCreate, UserUpdate
from cnagentos.security import hash_password
from cnagentos.services.auth import revoke_user_sessions
from cnagentos.services.bootstrap import SYSTEM_ROLE_CODE, SYSTEM_ROLE_PERMISSION_CODES


VALID_ACCOUNT_STATUSES = {"active", "disabled"}


class PlatformService:
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

    async def audit_failure(
        self,
        action: str,
        target_type: str,
        target_id: str | None,
        error_code: str,
    ) -> None:
        await self.session.rollback()
        await self._audit(
            action, target_type, target_id, "failed", {"error_code": error_code}
        )
        await self.session.commit()

    async def _roles_for_user(self, user_id: str) -> list[dict]:
        roles = (
            await self.session.scalars(
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user_id)
                .order_by(Role.name)
            )
        ).all()
        return [{"id": role.id, "code": role.code, "name": role.name} for role in roles]

    async def _serialize_user(self, user: User, roles_by_user: dict[str, list[dict]]) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "status": user.status,
            "is_system_admin": user.is_system_admin,
            "roles": roles_by_user.get(user.id, []),
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    async def _roles_map(self, user_ids: list[str]) -> dict[str, list[dict]]:
        if not user_ids:
            return {}
        rows = (
            await self.session.execute(
                select(UserRole.user_id, Role.id, Role.code, Role.name)
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id.in_(list(set(user_ids))))
                .order_by(Role.name)
            )
        ).all()
        result: dict[str, list[dict]] = {uid: [] for uid in user_ids}
        for row in rows:
            result.setdefault(row[0], []).append(
                {"id": row[1], "code": row[2], "name": row[3]}
            )
        return result

    async def list_users(
        self, page: int, page_size: int, q: str | None, status: str | None
    ) -> tuple[list[dict], int]:
        conditions = []
        if q:
            conditions.append(
                or_(User.username.ilike(f"%{q}%"), User.display_name.ilike(f"%{q}%"))
            )
        if status:
            if status not in VALID_ACCOUNT_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(User.status == status)
        total = await self.session.scalar(
            select(func.count()).select_from(User).where(*conditions)
        )
        users = (
            await self.session.scalars(
                select(User)
                .where(*conditions)
                .order_by(User.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        roles_by_user = await self._roles_map([u.id for u in users])
        return [await self._serialize_user(user, roles_by_user) for user in users], int(total or 0)

    async def _active_roles(self, role_ids: list[str]) -> list[Role]:
        if not role_ids:
            return []
        unique_ids = set(role_ids)
        roles = (
            await self.session.scalars(
                select(Role).where(Role.id.in_(unique_ids), Role.status == "active")
            )
        ).all()
        if len(roles) != len(unique_ids):
            raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"role_ids": "角色不存在或已停用"})
        return list(roles)

    async def create_user(self, payload: UserCreate) -> dict:
        if await self.session.scalar(select(User).where(User.username == payload.username)):
            raise ApiError(409, "CONFLICT", "登录名已存在")
        roles = await self._active_roles(payload.role_ids)
        user = User(
            id=str(uuid4()),
            username=payload.username,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
            status="active",
            is_system_admin=False,
        )
        self.session.add(user)
        await self.session.flush()
        for role in roles:
            self.session.add(UserRole(user_id=user.id, role_id=role.id))
        await self._audit("user.created", "user", user.id, "succeeded", {"username": user.username})
        await self.session.commit()
        return await self._serialize_user(user, await self._roles_map([user.id]))

    async def _ensure_system_admin_role(self, user: User, role_ids: list[str]) -> None:
        if not user.is_system_admin:
            return
        system_role = await self.session.scalar(
            select(Role).where(Role.code == SYSTEM_ROLE_CODE)
        )
        if system_role is None or system_role.id not in role_ids:
            raise ApiError(409, "INVALID_STATE", "系统管理员必须保留系统管理角色")

    async def update_user(self, user_id: str, payload: UserUpdate) -> dict:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ApiError(404, "NOT_FOUND", "用户不存在")
        if payload.display_name is not None:
            user.display_name = payload.display_name
        if payload.role_ids is not None:
            roles = await self._active_roles(payload.role_ids)
            await self._ensure_system_admin_role(user, payload.role_ids)
            old_links = (
                await self.session.scalars(
                    select(UserRole).where(UserRole.user_id == user.id)
                )
            ).all()
            for link in old_links:
                await self.session.delete(link)
            for role in roles:
                self.session.add(UserRole(user_id=user.id, role_id=role.id))
        await self._audit("user.updated", "user", user.id, "succeeded")
        await self.session.commit()
        return await self._serialize_user(user, await self._roles_map([user.id]))

    async def update_user_status(self, user_id: str, status: str) -> dict:
        if status not in VALID_ACCOUNT_STATUSES:
            raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
        user = await self.session.get(User, user_id)
        if user is None:
            raise ApiError(404, "NOT_FOUND", "用户不存在")
        if status == "disabled" and user.is_system_admin and user.status == "active":
            active_admins = (
                await self.session.scalars(
                    select(User.id)
                    .where(User.is_system_admin.is_(True), User.status == "active")
                    .order_by(User.id)
                    .with_for_update()
                )
            ).all()
            if len(active_admins) <= 1:
                raise ApiError(409, "INVALID_STATE", "不得停用最后一个系统管理员")
        user.status = status
        if status == "disabled":
            await revoke_user_sessions(self.session, user.id)
        await self._audit(
            "user.status_changed", "user", user.id, "succeeded", {"status": status}
        )
        await self.session.commit()
        return await self._serialize_user(user, await self._roles_map([user.id]))

    async def reset_user_password(self, user_id: str, new_password: str) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            raise ApiError(404, "NOT_FOUND", "用户不存在")
        user.password_hash = hash_password(new_password)
        await revoke_user_sessions(self.session, user.id)
        await self._audit("user.password_reset", "user", user.id, "succeeded")
        await self.session.commit()

    async def list_permissions(self) -> list[dict]:
        permissions = (await self.session.scalars(select(Permission).order_by(Permission.code))).all()
        return [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "module": item.module,
                "description": item.description,
            }
            for item in permissions
        ]

    async def _permission_codes_for_role(self, role_id: str) -> list[str]:
        return list(
            (
                await self.session.scalars(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role_id)
                    .order_by(Permission.code)
                )
            ).all()
        )

    async def _serialize_role(self, role: Role) -> dict:
        return {
            "id": role.id,
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "is_system": role.is_system,
            "status": role.status,
            "permissions": await self._permission_codes_for_role(role.id),
            "created_at": role.created_at,
            "updated_at": role.updated_at,
        }

    async def list_roles(
        self, page: int, page_size: int, q: str | None, status: str | None
    ) -> tuple[list[dict], int]:
        conditions = []
        if q:
            conditions.append(or_(Role.code.ilike(f"%{q}%"), Role.name.ilike(f"%{q}%")))
        if status:
            if status not in VALID_ACCOUNT_STATUSES:
                raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
            conditions.append(Role.status == status)
        total = await self.session.scalar(
            select(func.count()).select_from(Role).where(*conditions)
        )
        roles = (
            await self.session.scalars(
                select(Role)
                .where(*conditions)
                .order_by(Role.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return [await self._serialize_role(role) for role in roles], int(total or 0)

    async def _permissions_from_ids(self, permission_ids: list[str]) -> list[Permission]:
        if not permission_ids:
            return []
        unique_ids = set(permission_ids)
        permissions = (
            await self.session.scalars(select(Permission).where(Permission.id.in_(unique_ids)))
        ).all()
        if len(permissions) != len(unique_ids):
            raise ApiError(
                400, "VALIDATION_ERROR", "请求参数无效", {"permission_ids": "包含未知权限"}
            )
        return list(permissions)

    async def create_role(self, payload: RoleCreate) -> dict:
        if await self.session.scalar(select(Role).where(Role.code == payload.code)):
            raise ApiError(409, "CONFLICT", "角色代码已存在")
        permissions = await self._permissions_from_ids(payload.permission_ids)
        role = Role(
            id=str(uuid4()),
            code=payload.code,
            name=payload.name,
            description=payload.description,
            status="active",
            is_system=False,
        )
        self.session.add(role)
        await self.session.flush()
        for permission in permissions:
            self.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await self._audit("role.created", "role", role.id, "succeeded", {"code": role.code})
        await self.session.commit()
        return await self._serialize_role(role)

    async def update_role(self, role_id: str, payload: RoleUpdate) -> dict:
        role = await self.session.get(Role, role_id)
        if role is None:
            raise ApiError(404, "NOT_FOUND", "角色不存在")
        if payload.status is not None and payload.status not in VALID_ACCOUNT_STATUSES:
            raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
        if role.is_system and payload.status == "disabled":
            raise ApiError(409, "INVALID_STATE", "系统角色不得停用")
        if payload.name is not None:
            role.name = payload.name
        if "description" in payload.model_fields_set:
            role.description = payload.description
        if payload.status is not None:
            role.status = payload.status
        if payload.permission_ids is not None:
            permissions = await self._permissions_from_ids(payload.permission_ids)
            if role.is_system and not SYSTEM_ROLE_PERMISSION_CODES.issubset(
                {permission.code for permission in permissions}
            ):
                raise ApiError(409, "INVALID_STATE", "系统角色不得失去关键权限")
            links = (
                await self.session.scalars(
                    select(RolePermission).where(RolePermission.role_id == role.id)
                )
            ).all()
            for link in links:
                await self.session.delete(link)
            for permission in permissions:
                self.session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await self._audit("role.updated", "role", role.id, "succeeded")
        await self.session.commit()
        return await self._serialize_role(role)

    async def delete_role(self, role_id: str) -> None:
        role = await self.session.get(Role, role_id)
        if role is None:
            raise ApiError(404, "NOT_FOUND", "角色不存在")
        if role.is_system:
            raise ApiError(409, "CONFLICT", "系统角色不得删除")
        assigned = await self.session.scalar(
            select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)
        )
        if int(assigned or 0):
            raise ApiError(409, "CONFLICT", "已分配用户的角色不得删除")
        await self._audit("role.deleted", "role", role.id, "succeeded", {"code": role.code})
        await self.session.delete(role)
        await self.session.commit()

    @staticmethod
    def _serialize_function(function: Function) -> dict:
        return {
            "id": function.id,
            "code": function.code,
            "name": function.name,
            "parent_id": function.parent_id,
            "route_path": function.route_path,
            "icon": function.icon,
            "sort_order": function.sort_order,
            "required_permission_code": function.required_permission_code,
            "status": function.status,
            "is_system": function.is_system,
        }

    async def list_functions(self) -> list[dict]:
        functions = (
            await self.session.scalars(
                select(Function).order_by(Function.parent_id, Function.sort_order, Function.code)
            )
        ).all()
        return [self._serialize_function(item) for item in functions]

    async def _validate_permission_code(self, code: str | None) -> None:
        if code and not await self.session.scalar(
            select(Permission).where(Permission.code == code)
        ):
            raise ApiError(
                400,
                "VALIDATION_ERROR",
                "请求参数无效",
                {"required_permission_code": "未知权限代码"},
            )

    async def _validate_parent(self, parent_id: str | None, function_id: str | None = None) -> None:
        current_id = parent_id
        while current_id:
            if current_id == function_id:
                raise ApiError(409, "INVALID_STATE", "导航层级不得构成循环")
            parent = await self.session.get(Function, current_id)
            if parent is None:
                raise ApiError(
                    400, "VALIDATION_ERROR", "请求参数无效", {"parent_id": "父功能不存在"}
                )
            current_id = parent.parent_id

    async def create_function(self, payload: FunctionCreate) -> dict:
        if await self.session.scalar(select(Function).where(Function.code == payload.code)):
            raise ApiError(409, "CONFLICT", "功能代码已存在")
        await self._validate_parent(payload.parent_id)
        await self._validate_permission_code(payload.required_permission_code)
        function = Function(
            id=str(uuid4()),
            code=payload.code,
            name=payload.name,
            parent_id=payload.parent_id,
            route_path=payload.route_path,
            icon=payload.icon,
            sort_order=payload.sort_order,
            required_permission_code=payload.required_permission_code,
            status="disabled",
            is_system=False,
        )
        self.session.add(function)
        await self._audit(
            "function.created", "function", function.id, "succeeded", {"code": function.code}
        )
        await self.session.commit()
        return self._serialize_function(function)

    async def update_function(self, function_id: str, payload: FunctionUpdate) -> dict:
        function = await self.session.get(Function, function_id)
        if function is None:
            raise ApiError(404, "NOT_FOUND", "功能不存在")
        if payload.status is not None and payload.status not in VALID_ACCOUNT_STATUSES:
            raise ApiError(400, "VALIDATION_ERROR", "请求参数无效", {"status": "无效状态"})
        if "parent_id" in payload.model_fields_set:
            await self._validate_parent(payload.parent_id, function.id)
            function.parent_id = payload.parent_id
        if "required_permission_code" in payload.model_fields_set:
            await self._validate_permission_code(payload.required_permission_code)
            if (
                function.is_system
                and function.required_permission_code != payload.required_permission_code
            ):
                raise ApiError(409, "INVALID_STATE", "系统功能不得修改权限关联")
            function.required_permission_code = payload.required_permission_code
        for field in ("name", "route_path", "icon", "sort_order", "status"):
            if field in payload.model_fields_set:
                setattr(function, field, getattr(payload, field))
        await self._audit("function.updated", "function", function.id, "succeeded")
        await self.session.commit()
        return self._serialize_function(function)

    async def delete_function(self, function_id: str) -> None:
        function = await self.session.get(Function, function_id)
        if function is None:
            raise ApiError(404, "NOT_FOUND", "功能不存在")
        if function.is_system or function.status == "active":
            raise ApiError(409, "CONFLICT", "系统或已启用功能不得删除")
        has_children = await self.session.scalar(
            select(func.count()).select_from(Function).where(Function.parent_id == function.id)
        )
        if int(has_children or 0):
            raise ApiError(409, "CONFLICT", "包含子项的功能不得删除")
        await self._audit(
            "function.deleted", "function", function.id, "succeeded", {"code": function.code}
        )
        await self.session.delete(function)
        await self.session.commit()

    async def navigation_for(self, permission_codes: set[str]) -> list[dict]:
        functions = (
            await self.session.scalars(
                select(Function).where(Function.status == "active").order_by(Function.sort_order)
            )
        ).all()
        visible = {
            item.id: item
            for item in functions
            if not item.required_permission_code
            or item.required_permission_code in permission_codes
        }
        children: dict[str | None, list[Function]] = {}
        for function in visible.values():
            children.setdefault(function.parent_id, []).append(function)

        def build(parent_id: str | None) -> list[dict]:
            output = []
            for function in children.get(parent_id, []):
                child_items = build(function.id)
                if function.route_path is None and not child_items:
                    continue
                item = {
                    "id": function.id,
                    "code": function.code,
                    "name": function.name,
                    "icon": function.icon,
                }
                if function.route_path:
                    item["route_path"] = function.route_path
                if child_items:
                    item["children"] = child_items
                output.append(item)
            return output

        return build(None)

    async def list_audit_logs(
        self,
        page: int,
        page_size: int,
        actor_user_id: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        result: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[dict], int]:
        conditions = []
        for column, value in (
            (AuditLog.actor_user_id, actor_user_id),
            (AuditLog.action, action),
            (AuditLog.target_type, target_type),
            (AuditLog.target_id, target_id),
            (AuditLog.result, result),
        ):
            if value:
                conditions.append(column == value)
        if created_from:
            conditions.append(AuditLog.created_at >= created_from)
        if created_to:
            conditions.append(AuditLog.created_at <= created_to)
        total = await self.session.scalar(
            select(func.count()).select_from(AuditLog).where(*conditions)
        )
        logs = (
            await self.session.scalars(
                select(AuditLog)
                .where(*conditions)
                .order_by(AuditLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        data = []
        for log in logs:
            actor = await self.session.get(User, log.actor_user_id) if log.actor_user_id else None
            data.append(
                {
                    "id": log.id,
                    "action": log.action,
                    "actor": (
                        {"id": actor.id, "username": actor.username, "display_name": actor.display_name}
                        if actor
                        else None
                    ),
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "result": log.result,
                    "detail": log.detail,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at,
                }
            )
        return data, int(total or 0)
