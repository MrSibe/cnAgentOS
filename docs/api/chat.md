# 即时通信 API

## 基础信息

- **Base URL**: `/api/v1/chat`
- **认证方式**: Cookie-based 会话认证（`cnagentos_session`）
- **CSRF**: 所有变更型请求（POST/PATCH）需附带 `X-CSRF-Token` 请求头
- **权限守卫**: 每个端点声明所需权限代码

## 端点总览

### 联系人

| 方法 | 路径 | 权限 | CSRF | 说明 |
| --- | --- | --- | --- | --- |
| `GET` | `/contacts` | `chat.contacts.view` | - | 获取联系人列表 |
| `GET` | `/users/search` | `chat.contacts.view` | - | 搜索用户 |

### 好友请求

| 方法 | 路径 | 权限 | CSRF | 说明 |
| --- | --- | --- | --- | --- |
| `POST` | `/friend-requests` | `chat.friends.request` | ✓ | 发送好友请求 |
| `GET` | `/friend-requests/incoming` | `chat.friends.request` | - | 收到的请求列表 |
| `GET` | `/friend-requests/outgoing` | `chat.friends.request` | - | 发出的请求列表 |
| `PATCH` | `/friend-requests/{id}` | `chat.friends.request` | ✓ | 接受/拒绝请求 |

### 会话

| 方法 | 路径 | 权限 | CSRF | 说明 |
| --- | --- | --- | --- | --- |
| `GET` | `/conversations` | `chat.messages.send` | - | 会话列表（含未读计数） |
| `POST` | `/conversations` | `chat.groups.create` | ✓ | 创建群聊 |
| `GET` | `/conversations/{id}/members` | `chat.messages.send` | - | 群成员列表 |
| `POST` | `/conversations/{id}/leave` | `chat.messages.send` | ✓ | 退出群聊 |

### 消息

| 方法 | 路径 | 权限 | CSRF | 说明 |
| --- | --- | --- | --- | --- |
| `GET` | `/messages` | `chat.messages.send` | - | 获取消息历史 |
| `POST` | `/messages` | `chat.messages.send` | ✓ | 发送文本消息 |
| `POST` | `/messages/mark-read` | `chat.messages.send` | ✓ | 标记已读 |

## 请求/响应示例

### 搜索用户

```
GET /api/v1/chat/users/search?q=alice&page=1&page_size=20
```

```json
{
  "data": [
    { "user_id": "...", "username": "alice", "display_name": "Alice" }
  ],
  "meta": { "request_id": "...", "page": 1, "page_size": 20, "total": 1 }
}
```

### 发送好友请求

```
POST /api/v1/chat/friend-requests
X-CSRF-Token: ...
```

```json
{
  "data": {
    "id": "...",
    "from_user_id": "...",
    "from_user_name": "bob",
    "to_user_id": "...",
    "to_user_name": "alice",
    "status": "pending",
    "message": "你好",
    "created_at": "2026-05-31T12:00:00"
  },
  "meta": { "request_id": "..." }
}
```

### 获取会话列表

```
GET /api/v1/chat/conversations
```

```json
{
  "data": [
    {
      "id": "...",
      "type": "private",
      "name": "Alice",
      "unread_count": 3,
      "last_message": {
        "content": "你好",
        "sender_name": "alice",
        "created_at": "2026-05-31T12:00:00"
      },
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "meta": { "request_id": "..." }
}
```

### 发送消息

```
POST /api/v1/chat/messages
X-CSRF-Token: ...
```

```json
{
  "conversation_id": "...",
  "content_type": "text",
  "content": "你好！",
  "reply_to_id": null
}
```

### 获取消息历史

```
GET /api/v1/chat/messages?conversation_id=xxx&before=msg_id&limit=50
```

支持 `before`（向前翻页）和 `after`（断线重连后补拉新消息）两个翻页参数。

## WebSocket 实时通信

协议细节见 [WebSocket 聊天协议](ws-chat.md)。

## 注册

| 方法 | 路径 | CSRF | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | - | 自助注册（公开端点） |

```
POST /api/v1/auth/register
```

```json
{
  "username": "newuser",
  "display_name": "新用户",
  "password": "securepassword123"
}
```

限流：每 IP 每小时最多 3 次。
