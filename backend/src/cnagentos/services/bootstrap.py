from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.api import ApiError
from cnagentos.models.entities import Function, Permission, Role, RolePermission, User, UserRole
from cnagentos.security import hash_password


SYSTEM_ROLE_CODE = "system_admin"
PERMISSIONS = [
    ("users.manage", "用户管理", "platform", "管理用户与账户状态"),
    ("roles.manage", "角色管理", "platform", "管理角色与角色权限映射"),
    ("functions.manage", "导航管理", "platform", "管理后台功能导航配置"),
    ("models.view", "查看模型", "models", "查看模型配置与统计"),
    ("models.manage", "管理模型", "models", "新增、编辑、启停和设定默认模型"),
    ("models.test", "测试模型", "models", "发起模型测试调用"),
    ("watch.sources.manage", "管理数据源", "watch", "管理数据源与规则"),
    ("watch.tasks.run", "运行采集", "watch", "发起采集任务"),
    ("watch.tasks.view", "查看采集", "watch", "查看任务与执行结果"),
    ("data.items.view", "查看内容", "data", "查看数据仓库内容"),
    ("data.items.manage", "治理内容", "data", "调整内容可用状态"),
    ("qa.use", "智能问数", "qa", "使用智能问数"),
    ("audit.view", "查看审计", "platform", "查看审计记录"),
]
SYSTEM_ROLE_PERMISSION_CODES = {item[0] for item in PERMISSIONS}
SYSTEM_FUNCTIONS = [
    ("admin", "系统管理", None, None, "settings", 10, None),
    ("admin_users", "用户管理", "admin", "/admin/users", "users", 10, "users.manage"),
    ("admin_roles", "角色管理", "admin", "/admin/roles", "shield", 20, "roles.manage"),
    (
        "admin_functions",
        "导航管理",
        "admin",
        "/admin/functions",
        "menu",
        30,
        "functions.manage",
    ),
    ("admin_audit", "审计日志", "admin", "/admin/audit-logs", "history", 40, "audit.view"),
]


async def initialize_reference_data(session: AsyncSession) -> Role:
    permissions: dict[str, Permission] = {}
    for code, name, module, description in PERMISSIONS:
        permission = await session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(
                id=str(uuid4()),
                code=code,
                name=name,
                module=module,
                description=description,
            )
            session.add(permission)
        permissions[code] = permission
    await session.flush()

    system_role = await session.scalar(select(Role).where(Role.code == SYSTEM_ROLE_CODE))
    if system_role is None:
        system_role = Role(
            id=str(uuid4()),
            code=SYSTEM_ROLE_CODE,
            name="系统管理员",
            description="系统内置全量管理角色",
            is_system=True,
            status="active",
        )
        session.add(system_role)
        await session.flush()

    for permission in permissions.values():
        link = await session.get(RolePermission, (system_role.id, permission.id))
        if link is None:
            session.add(RolePermission(role_id=system_role.id, permission_id=permission.id))

    function_ids: dict[str, str] = {}
    for code, name, parent_code, route_path, icon, sort_order, required_code in SYSTEM_FUNCTIONS:
        function = await session.scalar(select(Function).where(Function.code == code))
        if function is None:
            function = Function(
                id=str(uuid4()),
                code=code,
                name=name,
                parent_id=function_ids.get(parent_code),
                route_path=route_path,
                icon=icon,
                sort_order=sort_order,
                required_permission_code=required_code,
                status="active",
                is_system=True,
            )
            session.add(function)
            await session.flush()
        function_ids[code] = function.id
    return system_role


async def create_system_admin(
    session: AsyncSession, username: str, display_name: str, password: str
) -> tuple[User, bool]:
    system_role = await initialize_reference_data(session)
    existing = await session.scalar(select(User).where(User.username == username))
    if existing is not None:
        if not existing.is_system_admin:
            raise ApiError(409, "CONFLICT", "用户名已被非系统账户使用")
        link = await session.get(UserRole, (existing.id, system_role.id))
        if link is None:
            session.add(UserRole(user_id=existing.id, role_id=system_role.id))
        await session.commit()
        return existing, False

    user = User(
        id=str(uuid4()),
        username=username,
        display_name=display_name,
        password_hash=hash_password(password),
        status="active",
        is_system_admin=True,
    )
    session.add(user)
    await session.flush()
    session.add(UserRole(user_id=user.id, role_id=system_role.id))
    await session.commit()
    return user, True
