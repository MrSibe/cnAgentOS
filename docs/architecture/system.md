# 目标系统架构

## 架构选择

首版采用单仓前后端分离开发的 Python 模块化 MVC 单体应用。`backend/` 承载 FastAPI API、认证、权限、安全审计和业务持久化；`frontend/` 承载 Vite Vue 前端，通过正式 `/api/v1` 与后端交互。

此选择面向当前目标：尽快跑通采集到问数的闭环，保持调试、部署和 AI 辅助开发的可控性。首版不承担微服务引入的网关、跨服务鉴权、分布式事务和多服务运维成本。

MVP 阶段不拆分为两个 Git 仓库，但运行职责分离：后端进程只提供 API、健康检查和 OpenAPI 文档，不托管前端页面或构建产物；前端由 Vite 开发服务负责。开发期由 Vite 代理 API 到 FastAPI。

## 系统视图

```mermaid
flowchart TD
    Browser["浏览器 - 管理端与用户端"] --> View["View 层<br/>Vue 页面与交互"]
    View --> Controller["Controller 层<br/>FastAPI 请求/认证/校验/响应"]
    Controller --> Model["Model 层<br/>业务规则与应用编排"]
    Model --> Store["数据存储<br/>业务数据与审计"]
    Model --> LLM["OpenAI 兼容模型服务"]
    Model --> External["允许访问的外部数据源"]

    subgraph Modules["单体内业务模块"]
      Auth["认证、RBAC 与功能导航"]
      Engine["模型引擎"]
      Watch["智能瞭望"]
      Data["数据仓库"]
      QA["智能问数"]
    end
    Model --- Modules
```

## 主业务流

```mermaid
sequenceDiagram
    participant A as 管理员
    participant W as 瞭望模块
    participant D as 数据仓库
    participant U as 用户
    participant Q as 问数模块
    participant M as 模型引擎
    A->>W: 配置数据源和规则
    A->>W: 发起采集任务
    W->>D: 写入采集内容与来源信息
    A->>D: 审核内容可用状态
    U->>Q: 提交问题
    Q->>D: 检索可用依据
    Q->>M: 调用默认模型并传入依据
    M-->>Q: 流式生成回答
    Q-->>U: 返回回答与引用
```

## MVC 约束

- Controller 不直接拼接数据库操作或采集/AI 业务流程。
- Model 包含领域规则和持久化编排；实现时可在 `models` 范围内拆分实体、仓储和业务服务。
- View 位于 `frontend/`，只承载展示、状态管理和用户交互；所有权限和数据范围由服务端最终判定。
- 前端不得绕过 `/api/v1` 契约直接访问数据库、拼接后端内部路径或复制后端授权规则作为最终判断。
- 模块通过明确的业务能力协作，不通过复制数据规则或绕过安全控制耦合。

## 拆分评估触发条件

只有出现独立扩缩容、采集执行影响主站稳定性、独立团队交付边界或强隔离合规要求时，才评估拆分仓库或相关模块服务拆分方案。
