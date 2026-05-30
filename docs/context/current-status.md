# 当前状态

**更新时间**：2026-05-30

## 当前阶段

正式产品处于 **Phase 4（MVP 集成验收与交付）后端与 C 端集成验收收口** 阶段。

Phase 0 工程底座已落地并调整为单仓前后端分离结构：`backend/` 承载 FastAPI + SQLAlchemy AsyncSession + Alembic + PostgreSQL 后端 API，`frontend/` 承载 Vite Vue TypeScript + Pinia + Vue Router + Element Plus 前端；Docker Compose 继续在根目录提供开发数据库。后端进程只提供 API、健康检查和 OpenAPI 文档，不托管前端页面或构建产物。

Phase 1 A 已完成认证/RBAC/导航/审计后端实现和集成测试。Phase 1 B 已完成模型配置、凭据加密脱敏、连接测试、流式测试和调用统计，并由管理端页面调用正式 `/api/v1` 接口。Phase 2 A/B/C 已收口：采集安全组件、数据源/规则/采集任务/知识库治理后端 API、系统导航入口和 Vue 管理端页面均已实现，并通过后端全量 pytest、前端构建和前端单元测试验证。Phase 3 A/B/C 已完成问数安全地基、问数后端 API、SSE 回答、引用持久化和智能问数页面，进入 MVP 端到端验收修复阶段。

早期示例原型仅被用于提取需求，已经从正式开发上下文中废弃；它不作为功能完成状态，也不要求新实现保持兼容。后续开发应按 `docs/product/`、`docs/architecture/`、`docs/database/` 和 `docs/api/` 中的新契约建设。

## 文档建设状态

| 内容 | 状态 |
| --- | --- |
| 产品愿景与首版需求 | 已定义 |
| MVP 边界与验收脚本 | 已定义 |
| 模块化 MVC 架构与安全基线 | 已定义 |
| 首版数据库契约与数据规则 | 已定义 |
| 首版 API 契约 | 已定义 |
| AI 开发流程与可复用 SOP | 已定义 |
| `uv` 依赖与项目环境工作流 | 已定义 |
| `pnpm` 前端依赖、Vite 脚手架与组件库选择 | 已定义 |
| Git 分支、约定式提交与 Code Review 流程 | 已定义 |
| 三人并行开发 Phase 计划 | 已定义 |

## 首版实现状态

| 模块 | 目标 | 正式实现状态 |
| --- | --- | --- |
| 认证与基础 RBAC | 登录、用户、角色、权限、功能导航和访问控制 | 已实现并通过集成测试；Vue 管理端已对接登录、导航、用户、角色、权限、功能导航和审计接口，支持现有管理 API 的主要写操作 |
| 模型引擎 | 脱敏配置、默认模型、测试与调用统计 | 已实现并通过集成测试；管理端已对接模型配置、启停、设默认、连接测试、流式测试和调用记录 |
| 智能瞭望 | 数据源、规则和采集任务 | Phase 2 已实现并通过集成测试；包含 SSRF/规则安全校验、数据源 CRUD、规则 CRUD、采集任务创建/取消/执行和脱敏审计 |
| 数据仓库 | 标准化入库、去重和内容治理 | Phase 2 已实现并通过集成测试；包含内容入库、SHA-256 去重、列表/详情查询和治理状态更新 |
| 智能问数 | 检索依据、流式回答与引用 | Phase 3 A/B/C 已实现；Phase 4 A/B 已补齐安全与后端稳定性验收，进入 MVP 端到端演示收口 |
| 安全与审计 | 秘密保护、SSRF 防护与高风险动作审计 | Phase 1 覆盖认证/RBAC/CSRF/审计基础和模型凭据加密；Phase 2 覆盖采集 SSRF 校验、规则安全校验和 watch/data 脱敏审计 |

## 下一里程碑

Phase 4 进入 MVP 集成验收与交付收口，待完成：
- A：复核权限矩阵、安全边界、审计完整性和发布配置。
- B：复核迁移初始化、外部依赖失败策略和问数后端稳定性（已完成，待评审）。
- C：执行 MVP 演示脚本、补齐端到端验证、修复界面/集成问题并汇总评审材料。

## Phase 4 B 实现摘要

**分支**：`feat/phase-4-b-backend-stabilization`

**已实现能力**：
- 新增 Alembic 迁移验收测试，使用隔离测试库执行 `upgrade head`、初始化系统管理员/reference data、校验 Phase 1-3 权限和导航项，再执行 `downgrade base` 验证回滚链。
- 补强 QA 流式回答外部依赖失败测试，覆盖上游 HTTP 错误、超时、连接失败和未知 provider 异常，确保回答、`qa_answer` 调用日志和脱敏审计均稳定落库。
- 修复 QA SSE 客户端提前关闭时的运行态残留：回答消息和模型调用日志会标记为 `failed`，错误码记录为 `CLIENT_DISCONNECTED`。

**验证结果**：
- `uv run pytest tests/test_qa_engine.py tests/test_migrations.py -q` 通过（20 passed）。

## Phase 4 C 实现摘要

**分支**：`feat/phase4-c-mvp-validation`

**当前收口点**：
- 发现并修复流式问数提问接口缺少服务端 CSRF 依赖的问题；前端原本已通过 `postStream` 发送 `X-CSRF-Token`，后端现同步强制校验。
- 补充 QA 集成测试，确保 `POST /api/v1/qa/sessions/{session_id}/questions/stream` 无 CSRF token 时返回 `403`，已有正常提问、模型不可用和归档会话测试改为显式携带 CSRF token。
- 继续以 `docs/product/mvp.md` 的四条用户旅程作为 Phase 4 C 验收基线。

## Phase 3 A 实现摘要

**分支**：`feat/phase-3-qa-security`

**已实现能力**：
- 新增 `qa_sessions`、`qa_messages`、`qa_citations` 基础数据表和 Alembic 迁移，承接两个 Phase 2 迁移头。
- 新增 `qa_security` 服务 helper：按查询条件执行会话/回答所有权过滤，外部会话与不存在会话统一返回 `404`。
- 新增问数问题文本规范化、可用知识依据状态校验和 QA 审计脱敏写入能力。
- 不新增对用户开放的 QA HTTP API、不实现检索、模型编排、SSE 或前端页面；这些仍属于 Phase 3 B/C。

**技术细节**：
- 所有权检查必须使用 `session_id + current_user.id` 或 answer message join 当前用户会话的查询级过滤。
- QA 审计支持 `succeeded/failed/rejected`，并对 prompt、question、headers、token、secret、URL query 等敏感信息脱敏。
- 集成测试覆盖自己的会话可访问、他人/不存在会话统一不可见、assistant 回答归属检查、问题校验、非 `available` 依据拒绝和审计脱敏。

## Phase 4 A 实现摘要

**分支**：`feat/phase-4-a-security-acceptance`

**已实现能力**：
- 补齐 QA 流式提问入口的 CSRF 校验，确保所有变更型浏览器请求均需 `X-CSRF-Token`。
- 固化无可用依据回答策略：返回固定说明、保存空引用，不调用模型 provider，也不伪造引用。
- 补齐 QA 审计完整性：问题提交、回答完成、回答失败和引用查看均写入脱敏审计并在流式响应结束后提交。
- 增加生产发布配置守卫测试，验证生产环境必须显式设置 CSRF secret、加密密钥，并使用 `__Host-cnagentos_session` 与 secure cookie。

**技术细节**：
- `qa_security.get_owned_answer_message` 预加载引用、知识内容和来源，避免引用查看时异步懒加载越界。
- `qa_knowledge.RetrievedKnowledge` 保留检索结果的治理状态，供 QA 安全校验复核。
- 验证命令覆盖后端定向测试、后端全量测试、前端单元测试和前端构建。

## Phase 3 C 实现摘要

**分支**：`feat/phase3-c-qa-ui`

**管理端/用户端页面**（对接 `docs/api/question-answering.md` 契约）：

| 页面 | 路由 | 状态 |
| --- | --- | --- |
| 智能问数工作台 | `/qa` | 已补页面骨架、会话列表、新建/重命名/归档、历史消息、SSE 提问回答、引用抽屉 |

**技术细节**：
- 前端只提交用户问题，不提交 `knowledge_item_id` 或手工依据；引用由服务端完成检索并通过 SSE completed 事件或引用接口返回。
- 新增系统导航入口 `qa`，关联 `qa.use` 权限，已有库通过 Alembic 迁移补齐入口。
- Phase 3 B 后端接口尚未实现，当前页面按正式契约先行，待 `/api/v1/qa/*` 落地后联调。

## Phase 2 B 实现摘要

**分支**：`feat/phase-2-watch-data-v2`

**已实现能力**：
- 数据源 CRUD、状态管理（active/disabled）
- 采集规则 CRUD、状态管理
- 采集任务 CRUD、取消、执行（后台异步）
- 知识库内容列表、详情、状态更新
- Phase 2 A 采集安全组件复用（`validate_source_policy`、`validate_fetch_target`、`validate_rule_security`）
- `watch_audit.write_watch_audit` 审计日志（含敏感信息脱敏）
- 采集内容 HTML/JSON 提取、重复检测（SHA-256）
- SSRF 校验：HTTPS 强制、私网 IP 拒绝、DNS rebinding 防护、精确 host 白名单

**已实现接口**：

| 模块 | 端点 | 状态 |
| --- | --- | --- |
| 数据源 | `GET/POST /api/v1/admin/watch-sources`、`GET/PATCH /watch-sources/{id}`、`PATCH /watch-sources/{id}/status` | 已实现 |
| 采集规则 | `GET/POST /api/v1/admin/watch-sources/{id}/rules`、`PATCH /watch-rules/{id}` | 已实现 |
| 采集任务 | `POST /api/v1/admin/collection-tasks`、`GET /collection-tasks`、`GET /collection-tasks/{id}`、`POST /collection-tasks/{id}/cancel`、`POST /collection-tasks/{id}/execute` | 已实现 |
| 知识库 | `GET /api/v1/admin/knowledge-items`、`GET /knowledge-items/{id}`、`PATCH /knowledge-items/{id}/status` | 已实现 |

**技术细节**：
- 后台任务执行（`/execute`）使用 `asyncio.create_task` + `sessionmaker` 确保独立 session
- 集成测试覆盖 22 条：SSRF 策略、HTTPS 强制、私网 IP 拒绝、DNS rebinding、端点存在性、CSRF 校验、审计日志

## Phase 3 B 实现摘要

**分支**：`feat/phase-3-qa-engine`

**已实现能力**：
- 会话 CRUD：创建、获取、列表、更新会话标题和状态（active/archived）
- 消息管理：保存用户问题和助手回答，包含状态追踪
- 引用管理：保存并获取回答与知识内容的关联关系
- 内容检索：基于关键词从 `status=available` 的知识内容中检索相关条目
- 流式问答：使用 SSE 流式返回模型回答，支持增量片段和完成事件
- 模型编排：调用默认模型（`qa_answer` 用途），错误状态记录到 `model_call_log`
- 权限隔离：用户只能访问自己的会话、消息和引用
- 审计日志：记录会话创建和问数动作

**已实现接口**：

| 模块 | 端点 | 状态 |
| --- | --- | --- |
| 会话 | `GET/POST /api/v1/qa/sessions`、`GET/PATCH /qa/sessions/{id}` | 已实现 |
| 消息 | `GET /api/v1/qa/sessions/{id}/messages` | 已实现 |
| 流式问答 | `POST /api/v1/qa/sessions/{id}/questions/stream` | 已实现 |
| 引用 | `GET /api/v1/qa/messages/{id}/citations` | 已实现 |

**技术细节**：
- 使用 `StreamingResponse` + `text/event-stream` 返回 SSE 流式响应
- 检索策略：提取问题关键词，从 `available` 状态知识内容中按相关度排序
- 提示词构建：外部采集内容按不可信处理，在提示词中声明参考资料限制
- 模型调用通过 `ModelProviderClient.stream_chat` 实现，调用日志含 `qa_answer` 用途
- 集成测试覆盖：权限隔离、会话隔离、CSRF 保护、模型可用性、流式响应、错误处理

**代码修复记录**：
- 修复 `qa_engine.py` 中 `selectinload` 链式加载重复问题
- 修复 `qa_engine.py` 中空值检查逻辑不清晰问题
- 修复 `qa_knowledge.py` 中查询条件逻辑错误（移除了错误的 or_ 条件）
- 修复 `entities.py` 中注释格式问题
- 修复 `qa_engine.py` 中缺少 `KnowledgeItem` 导入问题
- 修复 `model_engine.py` 中设置默认模型时的数据库约束冲突问题（添加 flush）
- 修复 `qa.py` 中 `require_permission` 依赖使用方式不正确导致权限检查失效问题
- 修复 `qa.py` 中 `require_csrf` 依赖使用方式不正确导致请求验证失败问题
- 集成测试全部通过（12/12）：权限检查、会话隔离、CSRF 保护、模型可用性、流式响应、错误处理

**Phase 2 A 实现摘要**

**分支**：`phase-2-collection-security`

**已实现能力**：
- 新增采集安全组件，支持数据源保存前和任务执行/重定向前的 HTTPS、精确 host 白名单、URL userinfo、本地域名、非公网 IP 与 DNS 解析结果校验。
- 新增采集规则安全校验，拒绝敏感请求头、换行注入、未知模板变量、脚本型解析配置和任意表达式。
- 新增 watch/data 审计 helper，约定数据源、规则、任务和内容治理动作代码，并对 URL 查询串、认证配置、请求头、Cookie、token、secret 等敏感信息脱敏。
- 不新增可见导航入口，也不交付数据源 CRUD、任务执行器、内容入库或前端页面；Phase 2 B 必须在真实业务路径中调用本安全组件。

## Phase 1 A 实现摘要

**分支**：`feat/phase-1-auth-rbac`

**已实现接口**（符合 `docs/api/auth-and-rbac.md`）：

| 模块 | 端点 | 状态 |
| --- | --- | --- |
| 认证 | `POST /api/v1/auth/login`、`POST /api/v1/auth/logout`、`GET /api/v1/auth/me`、`GET /api/v1/auth/boot`、`GET /api/v1/auth/navigation` | 已实现 |
| 用户管理 | `GET/POST /api/v1/admin/users`、`PATCH /users/{id}`、`PATCH /users/{id}/status`、`POST /users/{id}/password-reset` | 已实现 |
| 角色权限 | `GET /api/v1/admin/permissions`、`GET/POST/PATCH/DELETE /api/v1/admin/roles` | 已实现 |
| 导航管理 | `GET/POST/PATCH/DELETE /api/v1/admin/functions` | 已实现 |
| 审计 | `GET /api/v1/admin/audit-logs` | 已实现 |

**技术细节**：
- 密码 Argon2id 慢哈希、会话令牌 SHA-256 存储、CSRF 双令牌（HMAC 派生）
- 管理端初始化可通过 `/api/v1/auth/boot` 聚合读取用户与导航；接口鉴权仍实时依据当前角色和权限关联，撤权后续请求立即生效
- 权限字典 13 项覆盖 platform/models/watch/data/qa/audit 六个模块
- Bootstrap 数据：系统管理员角色、5 项系统导航（初始 disabled）
- `create-system-admin` CLI 支持 `--username` / `--display-name` 和交互式或环境变量密码输入
- 集成测试覆盖 15 条：CRUD、CSRF 校验、导航过滤、审计脱敏、权限拒绝、即时撤权、并发管理员保护、循环层级保护、系统角色保护

## Phase 1 B 实现摘要

**分支**：`feat/phase-1-model-engine`

**已实现接口**（符合 `docs/api/model-engine.md`）：

| 模块 | 端点 | 状态 |
| --- | --- | --- |
| 模型配置 | `GET/POST /api/v1/admin/models`、`GET/PATCH /models/{id}`、`PATCH /models/{id}/status`、`PUT /models/{id}/default` | 已实现 |
| 模型测试 | `POST /models/{id}/connection-tests`、`POST /models/{id}/connection-tests/stream` | 已实现 |
| 调用统计 | `GET /api/v1/admin/model-calls`、`GET /model-calls/summary` | 已实现 |

**技术细节**：
- API 密钥使用 Fernet (AES-128-CBC + HMAC-SHA256) 加密存储，凭据掩码只显示 `****xxxx` 格式
- 模型调用通过 OpenAI Python SDK 的 AsyncOpenAI 适配 OpenAI-compatible Chat Completions，连接测试支持普通响应和 SSE 流式响应
- 模型调用记录包含耗时、token 使用量和脱敏错误分类
- 集成测试覆盖 15 条：CRUD、列表过滤、脱敏验证、默认模型保护、权限控制、SDK 调用成功、上游错误映射、SSE 成功和流式错误处理

## Phase 2 C 实现摘要

**分支**：`feat/phase2-c-watch-data-ui`

**管理端页面**（对接 `docs/api/watch-and-data.md` 契约）：

| 页面 | 路由 | 状态 |
| --- | --- | --- |
| 数据源与规则 | `/admin/watch-sources` | 已补页面、创建/编辑/启停数据源、创建/编辑规则、手动发起采集任务入口 |
| 采集任务 | `/admin/collection-tasks` | 已补任务列表、状态/时间过滤、详情抽屉和取消入口 |
| 数据仓库治理 | `/admin/knowledge-items` | 已补内容列表、来源/状态过滤、详情抽屉和治理状态调整入口 |

**技术细节**：
- 新增 Vue 类型定义与路由懒加载页面，继续使用统一 API client、CSRF 令牌和后端权限判定。
- Bootstrap 与 Alembic 迁移新增 Phase 2 系统导航项，确保新库和已有库都能看到对应菜单。
- 页面不内置 mock 数据；已对接 Phase 2 B 后端接口，并通过 `pnpm --dir frontend build` 与单元测试验证。

## 维护要求

- 完成一个正式模块或验收项后，更新本文件对应状态。
- 若实现改变正式数据库或 API 契约，先更新相应设计文档并记录决策。
- 不因旧原型曾存在同名页面或功能而将本表标记为完成。
