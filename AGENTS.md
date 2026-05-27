# cnAgentOS AI 开发指引

## 项目目标

cnAgentOS 是 AI 智能瞭望与智能问数系统。首版要跑通：

`认证/RBAC/功能导航 -> 模型配置 -> 数据源与采集 -> 数据仓库 -> 智能问数与引用`

## 重要事实

- 旧示例原型已被废弃，不是正式实现基线；新系统可以重写。
- 旧材料仅用于已完成的需求提取，不提供可复用的 API 或数据库设计。
- 正式开发契约位于 `docs/`。
- 首版采用 Python 模块化 MVC 单体应用，不主动引入微服务。
- Python 依赖、虚拟环境和锁文件统一由 `uv` 管理；`pyproject.toml` 与 `uv.lock` 应保持同步并提交。
- 候选扩展不得在未明确要求时进入首版范围。

## 开始任务前阅读

1. `docs/product/requirements.md`
2. `docs/product/mvp.md`
3. `docs/planning/development-plan.md`
4. `docs/context/current-status.md`
5. `docs/context/decisions.md`
6. 与任务相关的 `docs/architecture/`、`docs/database/` 和 `docs/api/` 文档
7. `docs/workflow/development.md`
8. `docs/workflow/git.md`

## 实现约束

- Controller 负责请求解析、认证入口、校验和响应编排。
- Model 负责业务规则、持久化与外部能力编排；可在 Model 内拆分服务和仓储代码。
- View 负责页面和交互展示，不在前端绕过后端权限判断。
- 权限、安全、敏感配置和采集目标校验是首版功能的一部分。
- 不在代码、文档、日志或测试样例中提交真实密钥。
- 新增或移除 Python 依赖使用 `uv add` / `uv remove`，不得自行维护另一套依赖真源。
- 运行 Python 程序、测试和工程工具时优先使用 `uv run ...`；验证依赖一致性使用 `uv lock --check`。
- 数据库与 API 变更必须先同步或同时更新正式契约文档。
- 提交信息采用 Conventional Commits。
- 不直接在 `main`、`master` 或受保护主分支提交变更；使用工作分支。
- 未经项目负责人 Code Review 和明确同意，不合并至主分支。

## 完成任务后

- 按需求验收并运行可用的验证命令。
- 更新 `docs/context/current-status.md`。
- 若形成长期有效选择，更新 `docs/context/decisions.md`。
- 若发现风险或未完成事项，更新 `docs/context/issues.md`。
- 将可复用经验记入 `docs/context/ai-memory.md`。
- 若用户要求提交或交付评审，说明工作分支、提交与验证结果。

## 文档地图

- 产品：`docs/product/`
- 架构与安全：`docs/architecture/`
- 数据契约：`docs/database/`
- API 契约：`docs/api/`
- 计划：`docs/planning/`
- 当前上下文：`docs/context/`
- 开发流程：`docs/workflow/`
