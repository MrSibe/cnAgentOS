# cnAgentOS - AI智能瞭望与智能问数系统

## 项目定位

cnAgentOS 是一个面向信息采集、数据沉淀和智能问答的 Web 应用。系统通过可配置的数据源采集信息，将有效内容纳入数据仓库，再由 AI 基于这些内容回答用户问题并提供依据。

仓库曾包含早期示例原型，其有效功能需求已提取到正式文档中。原型实现不代表正式产品已经实现，也不限制后续重写方案。

## 首版目标

首版聚焦完整业务闭环：

1. 管理员通过认证与基础 RBAC 管理系统能力。
2. 管理员维护后台功能导航及其访问权限配置。
3. 管理员配置可调用的 OpenAI 兼容模型服务。
4. 管理员维护瞭望数据源和采集规则，发起采集任务。
5. 系统将有效采集内容沉淀为可治理、可查询的数据。
6. 用户针对已有数据发起问题，获得 AI 回答和引用依据。

即时通讯、数字员工、舆情大屏、语音/手势、多数据库切换等均属于后续候选方向，不纳入首版验收。

## 目标架构

- 后端语言：Python，使用 FastAPI 与 SQLAlchemy 异步数据层。
- 前端语言：Vue 3 + TypeScript，使用 Vite、Pinia、Vue Router 与 Element Plus。
- 架构形态：单仓前后端分离开发的模块化 MVC 单体应用。
- 数据库：PostgreSQL，迁移由 Alembic 管理。
- 设计原则：先完成可靠的业务闭环，再根据真实规模评估服务拆分。
- 开发契约：新的数据库与 API 设计以 `docs/` 内文档为准，不继承原型代码中的技术细节。

## 开发环境与包管理

项目统一使用 [uv](https://docs.astral.sh/uv/) 管理 Python 版本、依赖、项目虚拟环境和锁文件。`pyproject.toml` 与 `uv.lock` 是依赖契约的一部分，均应提交到 Git；本地 `.venv/` 不提交。

```bash
# 首次拉取或依赖变化后同步环境
cd backend
uv sync

# 启动本地 PostgreSQL 并执行迁移
cd ..
docker compose up -d postgres
cd backend
uv run alembic upgrade head

# 一次性创建首个系统管理员（密码通过交互输入或环境变量提供）
uv run cnagentos create-system-admin --username admin --display-name "系统管理员"

# 运行 API 服务
uv run main.py

# 检查依赖声明与锁文件是否一致
uv lock --check

# 运行后端自动化测试
uv run pytest
```

本地配置可从 `.env.example` 开始设置，示例值只用于本地开发，不用于部署。依赖新增或调整应使用 `uv add` / `uv remove`，并在同一次变更中提交更新后的 `pyproject.toml` 与 `uv.lock`。

## 前端开发

前端位于 `frontend/`，使用 `pnpm` 管理依赖和锁文件。后端进程只提供 API，不托管前端页面或构建产物；开发时由 Vite 代理 API 到后端：

```bash
pnpm --dir frontend install
pnpm --dir frontend dev
pnpm --dir frontend build
```

后端 API 本地默认运行在 `http://127.0.0.1:8080`，前端开发服务运行在 `http://127.0.0.1:5173`。前端请求使用 `/api/...` 相对路径，由 Vite 代理到后端。

## Phase 1 管理端界面

管理端前端由 `frontend/` 运行，调用 `/api/v1` 接口。开发时分别启动后端 API 与前端 Vite 服务：

```bash
cd backend
uv run python main.py

cd ..
pnpm --dir frontend dev
```

启动后访问 `http://127.0.0.1:5173`。登录页、后台框架、用户/角色/权限/导航、审计、模型配置、调用记录、数据源与规则、采集任务和数据仓库治理页面均调用正式 `/api/v1` 接口。

## 文档导航

| 内容 | 文档 |
| --- | --- |
| AI 编程入口 | [AGENTS.md](AGENTS.md) |
| 产品愿景 | [docs/product/vision.md](docs/product/vision.md) |
| 首版正式需求 | [docs/product/requirements.md](docs/product/requirements.md) |
| MVP 验收边界 | [docs/product/mvp.md](docs/product/mvp.md) |
| 路线图 | [docs/product/roadmap.md](docs/product/roadmap.md) |
| 系统架构 | [docs/architecture/system.md](docs/architecture/system.md) |
| 模块边界 | [docs/architecture/modules.md](docs/architecture/modules.md) |
| 安全原则 | [docs/architecture/security.md](docs/architecture/security.md) |
| 数据库契约 | [docs/database/schema.md](docs/database/schema.md) |
| API 契约 | [docs/api/conventions.md](docs/api/conventions.md) |
| 当前状态 | [docs/context/current-status.md](docs/context/current-status.md) |
| 开发工作流 | [docs/workflow/development.md](docs/workflow/development.md) |
| Git 与评审流程 | [docs/workflow/git.md](docs/workflow/git.md) |
| 三人开发计划 | [docs/planning/development-plan.md](docs/planning/development-plan.md) |

## 开发状态

正式版本目前已完成 Phase 2 智能瞭望采集与数据仓库治理能力，下一阶段进入 Phase 3 智能问数闭环。开始实现任何首版功能前，应先阅读需求、MVP 验收边界、开发计划、架构、数据库和对应 API 文档；实现完成后，应同步更新动态上下文文档。

正式变更采用约定式提交，必须通过工作分支交付并由项目负责人 Code Review 后合并；不得直接向主分支提交变更。

## 原型处理原则

旧原型资料仅用于本次需求提取，已不作为项目文档组成部分。正式开发不得从旧原型复用路由、表结构、凭据或完成状态；需要实现的行为以 `docs/` 中的正式契约为准。
