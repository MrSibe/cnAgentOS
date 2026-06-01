# 智能瞭望与数据仓库 API

## 权限代码

| 权限 | 用途 |
| --- | --- |
| `watch.sources.manage` | 管理数据源和采集规则 |
| `watch.tasks.run` | 发起采集任务 |
| `watch.tasks.view` | 查看任务执行信息 |
| `data.items.view` | 查看沉淀内容 |
| `data.items.manage` | 调整内容治理状态 |

## 数据源

### `GET /api/v1/admin/watch-sources`

权限：`watch.sources.manage`。支持分页、`q`、`status` 与 `source_type` 过滤。

返回来源配置摘要，包括 `auth_configured` 与 `auth_mask`，不得返回认证配置明文或密文。

### `POST /api/v1/admin/watch-sources`

权限：`watch.sources.manage`。

请求：

```json
{
  "name":"公开新闻来源",
  "source_type":"web_page",
  "entry_url":"https://news.example.com/search",
  "allowed_hosts":["news.example.com"],
  "auth_config":{"headers":{"Authorization":"<secret>"}},
  "description":"用于公开信息采集"
}
```

响应 `201`：脱敏数据源对象，初始 `status` 为 `disabled`。

规则：保存前执行 URL/host 安全校验；`auth_config` 加密持久化；校验失败返回 `422 SOURCE_UNSAFE`。

### `PATCH /api/v1/admin/watch-sources/{source_id}`

权限：`watch.sources.manage`。

可修改字段：`name`、`entry_url`、`allowed_hosts`、`auth_config`、`description`。若未提交 `auth_config` 则保留旧值。

### `PATCH /api/v1/admin/watch-sources/{source_id}/status`

权限：`watch.sources.manage`。请求：`{"status":"active"}` 或 `{"status":"disabled"}`。

规则：启用前若存在绑定规则且均为 disabled，可通过 `POST /api/v1/admin/watch-sources/{source_id}/enable-with-rules` 批量启用；禁用不影响历史内容。

### `POST /api/v1/admin/watch-sources/{source_id}/enable-with-rules`

权限：`watch.sources.manage`。

批量启用数据源及其所有采集规则。请求：`{}`（空对象）。

响应 `200`：
```json
{
  "data": {
    "source": { /* 启用后的数据源对象 */ },
    "enabled_rules": [ /* 启用后的规则列表 */ ]
  }
}
```

规则：同时将数据源和所有绑定规则设为 active；安全校验失败返回 `422 SOURCE_UNSAFE`；不存在数据源返回 `404`；已全部启用时返回成功。

## 采集规则

### `GET /api/v1/admin/watch-sources/{source_id}/rules`

权限：`watch.sources.manage`。返回该来源的规则列表和状态。

### `POST /api/v1/admin/watch-sources/{source_id}/rules`

权限：`watch.sources.manage`。

请求：

```json
{
  "name":"新闻列表规则",
  "request_method":"GET",
  "request_headers":{"Accept":"text/html"},
  "request_params":{"keyword":"{{query}}"},
  "extractor_type":"html",
  "extractor_config":{
    "item_selector":".news-item",
    "title_selector":".title",
    "url_selector":"a@href",
    "content_selector":".summary"
  }
}
```

响应 `201`，初始 `status` 为 `disabled`。

规则：模板只允许系统支持的占位字段；解析配置必须通过 schema 校验，不接受脚本或任意表达式。

### `PATCH /api/v1/admin/watch-rules/{rule_id}`

权限：`watch.sources.manage`。允许修改创建时的配置字段及 `status`。

规则：规则必须属于存在的数据源；启用规则前校验配置和来源安全边界。

## 采集任务

### `POST /api/v1/admin/collection-tasks`

权限：`watch.tasks.run`。

请求：

```json
{
  "targets":[
    {"source_id":"uuid","rule_id":"uuid","variables":{"query":"农业"}}
  ]
}
```

响应 `202`：

```json
{"data":{"id":"uuid","status":"pending","created_at":"2026-05-27T00:00:00Z"}}
```

规则：每个来源和规则必须启用且匹配；执行前再次执行 SSRF 校验；任务创建和执行结果写入审计。

### `GET /api/v1/admin/collection-tasks`

权限：`watch.tasks.view`。支持 `status`、时间范围、分页，返回任务统计摘要。

### `GET /api/v1/admin/collection-tasks/{task_id}`

权限：`watch.tasks.view`。

返回任务状态、来源级执行状态、成功/失败数量和脱敏失败摘要。

### `POST /api/v1/admin/collection-tasks/{task_id}/cancel`

权限：`watch.tasks.run`。

规则：仅 `pending` 任务可保证取消；运行中的任务若实现不支持安全中断，返回 `409 INVALID_STATE`。

## 数据仓库

### `GET /api/v1/admin/knowledge-items`

权限：`data.items.view`。

查询参数：`page`、`page_size`、`q`、`source_id`、`status`、`collected_from`、`collected_to`。

返回标题、摘要、来源、原始链接、采集与发布时间、状态等治理信息。

### `GET /api/v1/admin/knowledge-items/{item_id}`

权限：`data.items.view`。

返回标准化内容及追踪信息，不返回来源认证配置或采集敏感请求头。

### `PATCH /api/v1/admin/knowledge-items/{item_id}/status`

权限：`data.items.manage`。

请求：`{"status":"available"}`、`{"status":"excluded"}` 或 `{"status":"archived"}`。

规则：更新治理人和时间并写审计；只有 `available` 内容可以进入问数检索范围。

