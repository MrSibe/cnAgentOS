# 认证与 RBAC API

## 权限代码

本模块后台操作使用 `users.manage`、`roles.manage` 和 `functions.manage`。权限字典可被登录管理员查看；分配角色权限要求 `roles.manage`；配置后台功能导航要求 `functions.manage`。

## 认证接口

### `POST /api/v1/auth/login`

调用方：登录页面。权限：公开接口。

请求：

```json
{"username":"operator","password":"<password>"}
```

响应 `200`：

```json
{
  "data": {
    "user": {"id":"uuid","username":"operator","display_name":"运营管理员"},
    "csrf_token": "<token>"
  }
}
```

规则：

- 用户不存在、密码错误或账户停用统一返回 `401 LOGIN_FAILED`，不透露具体原因。
- 成功后创建受保护会话并更新最近登录时间。

### `POST /api/v1/auth/logout`

调用方：已登录用户。权限：登录即可。

响应 `204`，销毁当前会话。该请求需要 CSRF 防护。

### `GET /api/v1/auth/me`

调用方：登录后的界面初始化。权限：登录即可。

响应：

```json
{
  "data": {
    "id":"uuid",
    "username":"operator",
    "display_name":"运营管理员",
    "permissions":["models.view","qa.use"],
    "csrf_token":"<token>"
  }
}
```

规则：页面刷新或重新初始化后通过本接口获取当前会话的 CSRF token，前端不得持久化会话 Cookie 内容。

### `GET /api/v1/auth/navigation`

调用方：登录后后台布局。权限：登录即可。

返回当前用户可见的启用导航树：

```json
{
  "data": [
    {
      "id":"uuid",
      "code":"watch",
      "name":"瞭望管理",
      "icon":"binoculars",
      "children":[
        {"id":"uuid","code":"watch_sources","name":"数据源管理","route_path":"/admin/watch-sources"}
      ]
    }
  ]
}
```

规则：服务端依据导航状态和当前用户权限过滤；导航结果不赋予额外接口权限。

## 用户管理接口

### `GET /api/v1/admin/users`

权限：`users.manage`。

查询参数：`page`、`page_size`、`q`、`status`。

列表项返回 `id`、`username`、`display_name`、`status`、`is_system_admin`、角色摘要及时间字段；不得返回密码字段。

### `POST /api/v1/admin/users`

权限：`users.manage`。

请求：

```json
{
  "username":"analyst",
  "display_name":"分析员",
  "password":"<initial-password>",
  "role_ids":["uuid"]
}
```

响应 `201`：返回不含密码的用户对象。

规则：登录名唯一；密码满足服务端安全策略；角色必须为启用状态；写入 `user.created` 审计。

### `PATCH /api/v1/admin/users/{user_id}`

权限：`users.manage`。

可修改字段：

```json
{"display_name":"新名称","role_ids":["uuid"]}
```

规则：角色映射更新在事务中完成；不得通过此接口修改密码或系统保护标志。

### `PATCH /api/v1/admin/users/{user_id}/status`

权限：`users.manage`。

请求：`{"status":"active"}` 或 `{"status":"disabled"}`。

规则：不得停用最后一个可执行管理操作的系统管理员；冲突返回 `409 INVALID_STATE`。

### `POST /api/v1/admin/users/{user_id}/password-reset`

权限：`users.manage`。

请求：`{"new_password":"<new-password>"}`。

响应 `204`。规则：不返回密码值；写入审计，详情不得记录密码。

## 角色与权限接口

### `GET /api/v1/admin/permissions`

权限：`roles.manage`。

返回系统定义的权限字典，字段为 `id`、`code`、`name`、`module`、`description`。

### `GET /api/v1/admin/roles`

权限：`roles.manage`。支持 `page`、`page_size`、`q`、`status`，返回角色及已授予权限代码列表。

### `POST /api/v1/admin/roles`

权限：`roles.manage`。

请求：

```json
{
  "code":"watch_operator",
  "name":"采集操作员",
  "description":"维护来源并运行采集任务",
  "permission_ids":["uuid"]
}
```

响应 `201`。规则：角色代码唯一；只能授予现有权限；不能通过接口创建系统角色。

### `PATCH /api/v1/admin/roles/{role_id}`

权限：`roles.manage`。

可修改字段：`name`、`description`、`status`、`permission_ids`。

规则：系统角色的 `code`、停用状态和关键权限不可被破坏；角色变更写审计。

### `DELETE /api/v1/admin/roles/{role_id}`

权限：`roles.manage`。

响应 `204`。规则：仅可删除未分配用户的非系统角色；否则返回 `409 CONFLICT`。如需保留分配历史，优先使用停用。

## 功能导航接口

### `GET /api/v1/admin/functions`

权限：`functions.manage`。

返回完整后台导航树或扁平配置列表，包含 `code`、`name`、`parent_id`、`route_path`、`icon`、`sort_order`、`required_permission_code`、`status` 与 `is_system`。

### `POST /api/v1/admin/functions`

权限：`functions.manage`。

请求：

```json
{
  "code":"watch_sources",
  "name":"数据源管理",
  "parent_id":"uuid",
  "route_path":"/admin/watch-sources",
  "icon":"database",
  "sort_order":10,
  "required_permission_code":"watch.sources.manage"
}
```

响应 `201`：返回新导航项，初始 `status` 为 `disabled`。

规则：`code` 唯一；父项存在；权限代码已定义；正式启用前目标页面应已实现并受对应权限保护。

### `PATCH /api/v1/admin/functions/{function_id}`

权限：`functions.manage`。

可修改字段：`name`、`parent_id`、`route_path`、`icon`、`sort_order`、`required_permission_code`、`status`。

规则：拒绝循环层级；系统功能不得删除或移除安全所需的权限关联；成功和失败的变更均按审计策略记录。

### `DELETE /api/v1/admin/functions/{function_id}`

权限：`functions.manage`。

响应 `204`。规则：仅允许删除没有子项且非系统的未启用配置；业务中已使用的功能入口优先停用而非删除。

## 审计查看接口

### `GET /api/v1/admin/audit-logs`

权限：`audit.view`。

查询参数：`page`、`page_size`、`actor_user_id`、`action`、`target_type`、`target_id`、`created_from`、`created_to`、`result`。

返回审计动作代码、操作者摘要、目标、结果、发生时间和已脱敏详情。

规则：不得返回密码、会话令牌、模型凭据、数据源认证配置或包含上述信息的错误原文；审计记录不通过普通管理接口修改或删除。
