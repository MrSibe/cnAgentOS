# 首版数据库契约

## 1. 设计约定

本文定义正式重写版本的数据模型，不继承原型数据库。实现可选择适合 Python 应用的关系型数据库和迁移工具，但必须保持本文的业务字段、关系和约束语义。

- 主键统一使用应用生成的 `id`，建议 UUID 字符串，避免业务中依赖连续编号。
- 时间字段使用 UTC 时间：`created_at`、`updated_at`；任务与调用另有开始/结束时间。
- 状态字段使用文档列出的枚举值，不使用含义不明的数字标志。
- JSON 字段用于结构化但形态可扩展的配置，写入前必须校验 schema。
- 默认采用逻辑停用/归档；只有关联关系或明确的临时记录允许物理删除。

## 2. 认证与 RBAC

### `users`

用户身份与账户状态。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 用户标识 |
| `username` | string | UNIQUE, NOT NULL | 登录名 |
| `display_name` | string | NOT NULL | 展示名称 |
| `password_hash` | string | NOT NULL, sensitive | 密码慢哈希结果 |
| `status` | string | `active/disabled` | 登录与使用状态 |
| `is_system_admin` | boolean | default false | 保护初始化管理员 |
| `last_login_at` | datetime | nullable | 最近成功登录时间 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

规则：`username` 不允许重复；`password_hash` 永不通过 API 返回；系统管理员不得被停用到系统无可管理账户的状态。

### `auth_sessions`

服务端会话记录；浏览器 Cookie 仅保存不可预测的会话令牌，数据库保存其哈希。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 会话标识 |
| `user_id` | string | FK -> `users.id` | 登录用户 |
| `token_hash` | string | UNIQUE, NOT NULL, sensitive | 会话令牌哈希 |
| `csrf_secret_hash` | string | NOT NULL, sensitive | CSRF 校验秘密的哈希或等价安全材料 |
| `expires_at` | datetime | NOT NULL | 过期时间 |
| `revoked_at` | datetime | nullable | 注销或强制失效时间 |
| `ip_address` | string | nullable | 登录来源审计参考 |
| `user_agent` | string | nullable | 客户端审计参考 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `last_seen_at` | datetime | nullable | 最近活动时间 |

规则：退出、用户停用或密码重置可撤销相关会话；原始会话令牌仅通过受保护 Cookie 发送，不写入日志或数据库；CSRF token 由当前会话安全派生并只保存校验哈希。

### `roles`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 角色标识 |
| `code` | string | UNIQUE, NOT NULL | 稳定权限分配标识 |
| `name` | string | NOT NULL | 展示名称 |
| `description` | string | nullable | 说明 |
| `is_system` | boolean | default false | 系统角色保护标志 |
| `status` | string | `active/disabled` | 是否可继续分配 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

### `permissions`

权限字典由系统版本维护，管理端可查看并将其授予角色，首版不允许任意创造未知权限代码。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 权限标识 |
| `code` | string | UNIQUE, NOT NULL | 如 `watch.tasks.run` |
| `name` | string | NOT NULL | 展示名称 |
| `module` | string | NOT NULL | 权限所属模块 |
| `function_id` | string | FK -> `functions.id`, nullable | 对应后台功能导航模块 |
| `description` | string | nullable | 控制范围说明 |
| `created_at` | datetime | NOT NULL | 创建时间 |

### `functions`

后台功能导航资源，用于配置页面入口、层级和展示权限；功能项不等同于业务接口实现。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 功能标识 |
| `code` | string | UNIQUE, NOT NULL | 稳定功能代码，如 `watch_sources` |
| `name` | string | NOT NULL | 菜单展示名称 |
| `parent_id` | string | FK -> `functions.id`, nullable | 上级菜单 |
| `route_path` | string | nullable | 页面跳转路径；目录项可为空 |
| `icon` | string | nullable | 前端认可的图标标识 |
| `sort_order` | integer | NOT NULL | 同级顺序 |
| `required_permission_code` | string | nullable | 展示该入口需满足的权限代码 |
| `status` | string | `active/disabled` | 菜单入口状态 |
| `is_system` | boolean | default false | 内置关键功能保护 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

规则：父子关系不得构成循环；系统功能不能被物理删除；`required_permission_code` 必须为空或对应已定义权限。

### `user_roles`

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `user_id` | string | FK -> `users.id`, composite PK |
| `role_id` | string | FK -> `roles.id`, composite PK |
| `created_at` | datetime | NOT NULL |

### `role_permissions`

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `role_id` | string | FK -> `roles.id`, composite PK |
| `permission_id` | string | FK -> `permissions.id`, composite PK |
| `created_at` | datetime | NOT NULL |

## 3. 模型引擎

### `model_configs`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 模型配置标识 |
| `name` | string | NOT NULL | 管理端展示名 |
| `provider_type` | string | default `openai_compatible` | 接入协议类型 |
| `model_name` | string | NOT NULL | 远端模型标识 |
| `base_url` | string | NOT NULL | 服务地址 |
| `credential_ciphertext` | text | NOT NULL, sensitive | 加密后的 API 凭据 |
| `credential_mask` | string | NOT NULL | 页面展示掩码，如 `****abcd` |
| `status` | string | `active/disabled` | 是否允许调用 |
| `is_default` | boolean | default false | 是否为默认模型 |
| `timeout_seconds` | integer | positive | 请求超时配置 |
| `description` | string | nullable | 用途说明 |
| `created_by` | string | FK -> `users.id` | 创建人 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

约束：同一时间最多一个 `status=active` 且 `is_default=true` 的模型；密钥只在执行调用时按权限解密。

### `model_call_logs`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 调用记录 |
| `model_config_id` | string | FK -> `model_configs.id` | 调用的模型配置 |
| `caller_user_id` | string | FK -> `users.id`, nullable | 触发用户 |
| `purpose` | string | `connection_test/qa_answer` | 调用用途 |
| `related_id` | string | nullable | 问数消息等业务记录 ID |
| `streamed` | boolean | NOT NULL | 是否采用流式调用 |
| `status` | string | `running/succeeded/failed` | 执行状态 |
| `prompt_tokens` | integer | nullable | 服务商返回时保存 |
| `completion_tokens` | integer | nullable | 服务商返回时保存 |
| `total_tokens` | integer | nullable | 服务商返回时保存 |
| `latency_ms` | integer | nullable | 调用耗时 |
| `error_code` | string | nullable | 脱敏错误分类 |
| `started_at` | datetime | NOT NULL | 调用发起时间 |
| `finished_at` | datetime | nullable | 完成时间 |

规则：不保存完整模型密钥；是否保存测试提示词或回答由业务记录负责，调用日志仅记录统计与关联。

## 4. 智能瞭望

### `watch_sources`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 数据源标识 |
| `name` | string | NOT NULL | 来源名称 |
| `source_type` | string | `web_api/web_page` | 来源类型 |
| `entry_url` | string | NOT NULL | 采集入口 |
| `allowed_hosts` | JSON array | NOT NULL | 可访问主机白名单 |
| `status` | string | `active/disabled` | 是否允许创建任务 |
| `auth_ciphertext` | text | nullable, sensitive | 加密认证配置 |
| `auth_mask` | string | nullable | 是否配置凭据的掩码提示 |
| `description` | string | nullable | 管理说明 |
| `created_by` | string | FK -> `users.id` | 创建人 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

### `watch_rules`

一个数据源可以拥有多个规则，但任务执行时仅选择启用规则。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 规则标识 |
| `source_id` | string | FK -> `watch_sources.id` | 所属来源 |
| `name` | string | NOT NULL | 规则名称 |
| `request_method` | string | `GET/POST` | 受支持请求方法 |
| `request_headers` | JSON object | nullable | 非敏感请求头 |
| `request_params` | JSON object | nullable | 请求参数模板 |
| `extractor_type` | string | `json/html` | 解析类型 |
| `extractor_config` | JSON object | NOT NULL | 受校验的字段映射/选择器 |
| `status` | string | `active/disabled` | 规则状态 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

规则：配置仅描述请求和解析，不允许执行代码、命令或任意模板表达式。

### `collection_tasks`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 任务标识 |
| `created_by` | string | FK -> `users.id` | 发起人 |
| `status` | string | `pending/running/succeeded/partial_failed/failed/cancelled` | 生命周期 |
| `trigger_type` | string | `manual` | 首版仅手工发起 |
| `source_count` | integer | NOT NULL | 涉及来源数 |
| `item_success_count` | integer | default 0 | 成功获得内容数 |
| `item_failure_count` | integer | default 0 | 失败数量 |
| `failure_summary` | string | nullable | 脱敏失败摘要 |
| `started_at` | datetime | nullable | 执行开始 |
| `finished_at` | datetime | nullable | 执行结束 |
| `created_at` | datetime | NOT NULL | 创建时间 |

### `collection_task_sources`

记录一次任务中采用的具体数据源与规则，保证可追溯。

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `task_id` | string | FK -> `collection_tasks.id`, composite PK |
| `source_id` | string | FK -> `watch_sources.id`, composite PK |
| `rule_id` | string | FK -> `watch_rules.id`, NOT NULL |
| `status` | string | `pending/running/succeeded/failed` |
| `failure_summary` | string | nullable |
| `started_at` | datetime | nullable |
| `finished_at` | datetime | nullable |

## 5. 数据仓库

### `knowledge_items`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 内容标识 |
| `source_id` | string | FK -> `watch_sources.id` | 内容来源 |
| `task_id` | string | FK -> `collection_tasks.id` | 首次入库任务 |
| `external_key` | string | nullable | 来源侧稳定标识 |
| `canonical_url` | string | nullable | 原始内容链接 |
| `title` | string | nullable | 标题 |
| `content` | text | NOT NULL | 标准化正文 |
| `summary` | text | nullable | 摘要 |
| `published_at` | datetime | nullable | 来源发布时间 |
| `collected_at` | datetime | NOT NULL | 采集时间 |
| `content_hash` | string | NOT NULL | 去重哈希 |
| `status` | string | `available/excluded/archived` | 治理状态 |
| `reviewed_by` | string | FK -> `users.id`, nullable | 最近治理人 |
| `reviewed_at` | datetime | nullable | 最近治理时间 |
| `created_at` | datetime | NOT NULL | 首次写入时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

唯一性：优先约束 `(source_id, external_key)`；无外部标识时约束 `(source_id, content_hash)`。

### `collection_task_items`

记录每次任务发现的内容与数据仓库条目之间的关系，包含去重命中的情况。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `task_id` | string | FK -> `collection_tasks.id`, composite PK | 采集任务 |
| `knowledge_item_id` | string | FK -> `knowledge_items.id`, composite PK | 目标内容 |
| `source_id` | string | FK -> `watch_sources.id` | 来源 |
| `ingest_result` | string | `created/updated/duplicate` | 本次入库处理结果 |
| `created_at` | datetime | NOT NULL | 关系建立时间 |

## 6. 智能问数

### `qa_sessions`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 会话标识 |
| `user_id` | string | FK -> `users.id` | 所属用户 |
| `title` | string | nullable | 会话标题 |
| `status` | string | `active/archived` | 会话状态 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

### `qa_messages`

问题与回答均作为会话消息保存；每个问题后可有一条完成或失败的回答。

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 消息标识 |
| `session_id` | string | FK -> `qa_sessions.id` | 所属会话 |
| `role` | string | `user/assistant` | 消息角色 |
| `reply_to_id` | string | FK -> `qa_messages.id`, nullable | 回答关联的问题 |
| `content` | text | NOT NULL | 问题或完成回答 |
| `status` | string | `completed/streaming/failed` | 回答生命周期；用户消息固定 `completed` |
| `model_call_log_id` | string | FK -> `model_call_logs.id`, nullable | 回答使用的模型调用 |
| `error_summary` | string | nullable | 回答失败摘要 |
| `created_at` | datetime | NOT NULL | 创建时间 |
| `updated_at` | datetime | NOT NULL | 更新时间 |

### `qa_citations`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `answer_message_id` | string | FK -> `qa_messages.id`, composite PK | 回答消息 |
| `knowledge_item_id` | string | FK -> `knowledge_items.id`, composite PK | 被引用内容 |
| `rank` | integer | NOT NULL | 依据展示排序 |
| `excerpt` | text | NOT NULL | 回答时使用的依据摘录 |
| `created_at` | datetime | NOT NULL | 创建时间 |

## 7. 审计

### `audit_logs`

| 字段 | 类型 | 规则 | 用途 |
| --- | --- | --- | --- |
| `id` | string | PK | 审计记录 |
| `actor_user_id` | string | FK -> `users.id`, nullable | 操作者；系统动作可空 |
| `action` | string | NOT NULL | 稳定动作代码 |
| `target_type` | string | NOT NULL | 目标实体类型 |
| `target_id` | string | nullable | 目标标识 |
| `result` | string | `succeeded/failed` | 结果 |
| `detail` | JSON object | nullable, sanitized | 非敏感上下文 |
| `ip_address` | string | nullable | 来源地址 |
| `created_at` | datetime | NOT NULL | 发生时间 |

## 8. 关键索引

- `users(username)` 唯一索引。
- `auth_sessions(token_hash)` 唯一索引和 `auth_sessions(user_id, expires_at)` 查询索引。
- `roles(code)`、`permissions(code)` 唯一索引。
- `functions(code)` 唯一索引与 `functions(parent_id, sort_order)` 导航查询索引。
- `model_configs(is_default)` 对启用默认记录建立唯一约束或等价事务校验。
- `watch_rules(source_id, status)`、`collection_tasks(status, created_at)` 查询索引。
- `knowledge_items(source_id, status, collected_at)` 与去重唯一索引。
- `collection_task_items(task_id)` 与 `collection_task_items(knowledge_item_id, created_at)` 查询索引。
- `qa_sessions(user_id, updated_at)`、`qa_messages(session_id, created_at)` 查询索引。
- `audit_logs(target_type, target_id, created_at)` 与 `audit_logs(actor_user_id, created_at)` 查询索引。
