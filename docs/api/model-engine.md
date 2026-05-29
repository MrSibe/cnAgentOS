# 模型引擎 API

## 权限代码

| 权限 | 用途 |
| --- | --- |
| `models.view` | 查看模型配置和调用统计 |
| `models.manage` | 新增、编辑、启停和设置默认模型 |
| `models.test` | 执行连接或对话测试 |

## 模型配置

### `GET /api/v1/admin/models`

权限：`models.view`。支持 `page`、`page_size`、`q`、`status`。

列表项响应字段：

```json
{
  "id":"uuid",
  "name":"主模型",
  "provider_type":"openai_compatible",
  "model_name":"model-name",
  "base_url":"https://provider.example/v1",
  "credential_configured":true,
  "credential_mask":"****abcd",
  "status":"active",
  "is_default":true,
  "timeout_seconds":60,
  "updated_at":"2026-05-27T00:00:00Z"
}
```

不得返回 `credential_ciphertext` 或任何可用密钥。

### `POST /api/v1/admin/models`

权限：`models.manage`。

请求：

```json
{
  "name":"主模型",
  "provider_type":"openai_compatible",
  "model_name":"model-name",
  "base_url":"https://provider.example/v1",
  "api_key":"<secret>",
  "timeout_seconds":60,
  "description":"用于智能问数"
}
```

响应 `201`：返回脱敏后的配置，初始 `status` 为 `disabled`、`is_default` 为 `false`。

规则：服务地址必须为允许的 HTTPS URL；凭据加密后写入；审计不包含 `api_key`。

### `PATCH /api/v1/admin/models/{model_id}`

权限：`models.manage`。

可修改：`name`、`model_name`、`base_url`、`api_key`、`timeout_seconds`、`description`。未提交 `api_key` 时保留原凭据。

规则：影响连接的字段改变后，界面应提示重新测试；返回值保持脱敏。

### `PATCH /api/v1/admin/models/{model_id}/status`

权限：`models.manage`。请求：`{"status":"active"}` 或 `{"status":"disabled"}`。

规则：停用当前默认模型前必须已有替代默认模型，或由业务显式处理问数不可用状态；不合法状态返回 `409 INVALID_STATE`。

### `PUT /api/v1/admin/models/{model_id}/default`

权限：`models.manage`。响应 `200` 返回新的默认模型摘要。

规则：目标模型必须启用；操作原子替换旧默认；无可用凭据返回 `422 MODEL_UNAVAILABLE`。

## 测试调用

### `POST /api/v1/admin/models/{model_id}/connection-tests`

权限：`models.test`。

请求：

```json
{"message":"请回复连接正常","stream":false}
```

响应：

```json
{
  "data": {
    "call_log_id":"uuid",
    "reply":"连接正常",
    "usage":{"prompt_tokens":10,"completion_tokens":4,"total_tokens":14},
    "latency_ms":320
  }
}
```

规则：创建用途为 `connection_test` 的调用记录；上游 HTTP 状态失败返回脱敏 `502 UPSTREAM_ERROR`，连接失败返回 `502 CONNECTION_ERROR`，超时返回 `504 TIMEOUT`。

### `POST /api/v1/admin/models/{model_id}/connection-tests/stream`

权限：`models.test`。请求：`{"message":"请回复连接正常"}`。

响应：遵循 SSE 通用约定，`completed` 事件附带 `call_log_id` 与可获得的 usage 数据；流开始后的失败通过 `error` 事件返回脱敏错误码与消息。

## 统计

### `GET /api/v1/admin/model-calls`

权限：`models.view`。

查询参数：`page`、`page_size`、`model_id`、`purpose`、`status`、`started_from`、`started_to`。

返回调用时间、用途、状态、耗时和 token 统计；不返回请求原文、回答正文或秘密配置。

### `GET /api/v1/admin/model-calls/summary`

权限：`models.view`。

返回过滤时间范围内的总调用数、成功/失败数、总 token 与平均耗时；未提供 token 的上游调用不伪造计数。
