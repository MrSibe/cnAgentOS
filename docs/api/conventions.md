# API 通用约定

## 1. 适用范围

本文与模块 API 文档共同构成首版正式接口契约。接口基于目标重写系统设计，不兼容原型路由。

## 2. 路径与调用区域

- API 前缀：`/api/v1`。
- 当前用户功能：`/api/v1/auth/*`、`/api/v1/qa/*`。
- 后台管理功能：`/api/v1/admin/*`。
- 路径使用复数资源名和 HTTP 方法表达动作；确需业务命令时使用子资源，如 `/connection-tests`。

## 3. 身份、权限与 CSRF

- 浏览器登录后通过服务端会话 Cookie 访问受保护接口。
- 会话 Cookie 仅保存随机不透明令牌；生产环境 Cookie 名为 `__Host-cnagentos_session`，使用 `HttpOnly`、`Secure`、`SameSite=Lax` 与 `Path=/`。
- 除登录外，本文接口均要求登录；后台接口还要求对应权限代码。
- `POST`、`PUT`、`PATCH`、`DELETE` 请求必须以 `X-CSRF-Token` 请求头携带有效 CSRF token；该值由登录响应或 `GET /api/v1/auth/me` 获取。
- 权限不足返回 HTTP `403`，未登录或会话失效返回 HTTP `401`。
- 列表页面隐藏无权操作按钮不是授权机制，Controller 必须执行权限检查。

## 4. JSON 响应格式

成功响应：

```json
{
  "data": {},
  "meta": {
    "request_id": "uuid"
  }
}
```

分页成功响应：

```json
{
  "data": [],
  "meta": {
    "request_id": "uuid",
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

失败响应：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数无效",
    "details": {
      "field": "原因"
    }
  },
  "meta": {
    "request_id": "uuid"
  }
}
```

## 5. 状态码与错误代码

| HTTP | 典型错误代码 | 含义 |
| --- | --- | --- |
| `400` | `VALIDATION_ERROR` | 字段、状态或过滤条件不合法 |
| `401` | `AUTH_REQUIRED`, `LOGIN_FAILED` | 需要登录或认证失败 |
| `403` | `PERMISSION_DENIED`, `CSRF_INVALID` | 权限或请求保护失败 |
| `404` | `NOT_FOUND` | 资源不存在或不可访问 |
| `409` | `CONFLICT`, `INVALID_STATE` | 唯一冲突或状态迁移不允许 |
| `422` | `SOURCE_UNSAFE`, `MODEL_UNAVAILABLE` | 业务数据可读但无法执行 |
| `500` | `INTERNAL_ERROR` | 未预期服务端错误 |
| `502` | `UPSTREAM_ERROR` | 外部模型或来源调用失败 |

错误消息不得包含密钥、认证头、内部网络信息或上游完整响应正文。

## 6. 字段与分页约定

- ID 均为字符串；时间均为 ISO 8601 UTC 字符串。
- 列表查询使用 `page` 和 `page_size`，默认 `1` 和 `20`，`page_size` 最大 `100`。
- 关键词搜索参数使用 `q`，状态过滤使用 `status`。
- 更新接口采用 `PATCH`，只接受文档声明可修改的字段。
- 敏感字段输入使用独立字段，读取时最多返回 `*_configured` 或 `*_mask`。

## 7. SSE 约定

流式接口响应 `Content-Type: text/event-stream`，事件采用：

```text
event: delta
data: {"content":"回答片段"}

event: completed
data: {"message_id":"uuid","citations":[{"knowledge_item_id":"uuid","rank":1}]}
```

异常完成：

```text
event: error
data: {"code":"UPSTREAM_ERROR","message":"回答生成失败"}
```

- SSE 建立前的校验错误按普通 JSON 错误返回。
- 流式开始后的失败通过 `error` 事件表达，并将数据库中的执行记录标记为失败。
- SSE 响应不得包含提示词、模型凭据或采集敏感配置。

## 8. 审计要求

执行权限配置、模型变更、来源或规则变更、采集任务发起、数据治理状态变更的成功或失败请求，均应写入审计记录。
