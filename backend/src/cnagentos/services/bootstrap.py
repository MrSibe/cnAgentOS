from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cnagentos.api import ApiError
from cnagentos.models.entities import Function, Permission, Role, RolePermission, User, UserRole
from cnagentos.security import hash_password
from cnagentos.services.seed_employees import seed_phase7_default_data


SYSTEM_ROLE_CODE = "system_admin"
DEFAULT_USER_ROLE_CODE = "default_user"
PERMISSIONS = [
    # Platform
    ("users.manage", "用户管理", "platform", "管理用户与账户状态"),
    ("roles.manage", "角色管理", "platform", "管理角色与角色权限映射"),
    ("functions.manage", "导航管理", "platform", "管理后台功能导航配置"),
    ("audit.view", "查看审计", "platform", "查看审计记录"),
    ("auth.register", "用户注册", "platform", "允许自助注册为普通用户"),
    ("tools.view", "查看工具", "platform", "查看工具注册表"),
    ("tools.manage", "管理工具", "platform", "注册、配置、启停工具"),
    ("files.view", "查看文件", "platform", "查看文件管理"),
    ("files.manage", "管理文件", "platform", "删除文件、管理存储"),
    # Models
    ("models.view", "查看模型", "models", "查看模型配置与统计"),
    ("models.manage", "管理模型", "models", "新增、编辑、启停和设定默认模型"),
    ("models.test", "测试模型", "models", "发起模型测试调用"),
    # Watch
    ("watch.sources.manage", "管理数据源", "watch", "管理数据源与规则"),
    ("watch.tasks.run", "运行采集", "watch", "发起采集任务"),
    ("watch.tasks.view", "查看采集", "watch", "查看任务与执行结果"),
    # Data
    ("data.items.view", "查看内容", "data", "查看数据仓库内容"),
    ("data.items.manage", "治理内容", "data", "调整内容可用状态"),
    # Q&A
    ("qa.use", "智能问数", "qa", "使用智能问数"),
    # Chat (Phase 6+)
    ("chat.contacts.view", "查看联系人", "chat", "查看通讯录和联系人信息"),
    ("chat.friends.request", "好友请求", "chat", "发送和接受好友请求"),
    ("chat.groups.create", "创建群组", "chat", "创建群聊"),
    ("chat.groups.manage", "管理群组", "chat", "管理群成员和群设置"),
    ("chat.messages.send", "发送消息", "chat", "发送聊天消息"),
    ("chat.files.upload", "上传文件", "chat", "在聊天中上传文件"),
    # Digital Employees (Phase 7+)
    ("employee.chat", "员工对话", "employee", "通过 @提及触发数字员工回复"),
    ("employee.manage", "管理员工", "employee", "管理数字员工配置"),
    # Sentiment Analysis (Phase 8+)
    ("sentiment.view", "查看舆情", "sentiment", "查看舆情分析报告"),
    ("sentiment.manage", "管理舆情", "sentiment", "运行分析任务、管理报告"),
    # Automation (Phase 9+)
    ("automation.view", "查看自动化", "automation", "查看定时任务"),
    ("automation.manage", "管理自动化", "automation", "创建、编辑、启停定时任务"),
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
    ("admin_model_engine", "模型引擎", None, None, "cpu", 50, None),
    ("admin_models", "模型配置", "admin_model_engine", "/admin/models", "settings", 10, "models.view"),
    ("admin_model_calls", "调用记录", "admin_model_engine", "/admin/model-calls", "activity", 20, "models.view"),
    ("watch", "智能瞭望", None, None, "file-search", 20, None),
    (
        "watch_sources",
        "数据源与规则",
        "watch",
        "/admin/watch-sources",
        "file-search",
        10,
        "watch.sources.manage",
    ),
    (
        "watch_tasks",
        "采集任务",
        "watch",
        "/admin/collection-tasks",
        "activity",
        20,
        "watch.tasks.view",
    ),
    ("data", "数据仓库", None, None, "activity", 30, None),
    (
        "data_items",
        "内容治理",
        "data",
        "/admin/knowledge-items",
        "file-search",
        10,
        "data.items.view",
    ),
    ("qa", "智能问数", None, "/qa", "sparkles", 40, "qa.use"),
    # Phase 6-9 extension navigation entries (added in Phase 5 as reference;
    # actual activation happens in their respective phases):
    ("admin_chat_groups", "群管理", "admin", "/admin/chat-groups", "chat-dot-square", 50, "chat.groups.manage"),
    ("admin_chat_servers", "服务器管理", "admin", "/admin/servers", "connection", 55, "tools.manage"),
    ("admin_files", "文件管理", "admin", "/admin/files", "folder-opened", 60, "files.view"),
    ("admin_employees", "数字员工", "admin", "/admin/digital-employees", "robot", 70, "employee.manage"),
    ("admin_tools", "工具管理", "admin", "/admin/tools", "tools", 80, "tools.manage"),
    ("admin_dashboard", "数智大屏", "admin", "/admin/dashboard", "data-analysis", 90, "sentiment.view"),
    ("admin_sentiment", "舆情分析", "admin", "/admin/sentiment", "chat-dot-square", 100, "sentiment.view"),
    # ("admin_automation", "定时任务", "admin", "/admin/scheduled-tasks", "timer", 90, "automation.view"),
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

    # Create the default_user role for self-registered users (Phase 6+)
    default_role = await session.scalar(select(Role).where(Role.code == DEFAULT_USER_ROLE_CODE))
    if default_role is None:
        default_role = Role(
            id=str(uuid4()),
            code=DEFAULT_USER_ROLE_CODE,
            name="普通用户",
            description="自助注册用户的默认角色 (Phase 6 起使用)",
            is_system=True,
            status="active",
        )
        session.add(default_role)
        await session.flush()

    # Grant Phase 6-7 chat permissions to default_user role (self-registered users)
    default_chat_perms = [
        "chat.contacts.view",
        "chat.friends.request",
        "chat.groups.create",
        "chat.messages.send",
        "chat.files.upload",
        "employee.chat",
    ]
    for code in default_chat_perms:
        perm = permissions.get(code)
        if perm:
            link = await session.get(RolePermission, (default_role.id, perm.id))
            if link is None:
                session.add(RolePermission(role_id=default_role.id, permission_id=perm.id))

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

    # Seed Phase 7 default data (digital employees, built-in tools)
    await seed_phase7_default_data(session)

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


SYSTEM_TASK_USER_ID = "system-task"


async def ensure_system_task_user(session: AsyncSession) -> User:
    """Ensure the system-task user exists for background job audit attribution."""
    user = await session.get(User, SYSTEM_TASK_USER_ID)
    if user is None:
        user = User(
            id=SYSTEM_TASK_USER_ID,
            username=SYSTEM_TASK_USER_ID,
            display_name="System Task",
            password_hash="",  # No password, cannot login
            status="active",
            is_system_admin=False,
        )
        session.add(user)
        await session.flush()
    return user
