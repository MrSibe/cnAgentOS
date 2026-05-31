export interface SessionUser {
  id: string
  username: string
  display_name: string
}

export interface NavigationItem {
  id: string
  code: string
  name: string
  icon?: string | null
  route_path?: string | null
  children?: NavigationItem[]
}

export interface BootPayload {
  user: SessionUser
  permissions: string[]
  csrf_token: string
  navigation: NavigationItem[]
}

export interface UserItem extends SessionUser {
  status: string
  is_system_admin: boolean
  roles: RoleSummary[]
  updated_at?: string
}

export interface RoleSummary {
  id: string
  code: string
  name: string
}

export interface RoleItem extends RoleSummary {
  description?: string | null
  permissions: string[]
  status: string
  is_system: boolean
}

export interface PermissionItem {
  id: string
  code: string
  name: string
  module: string
  description?: string | null
}

export interface FunctionItem {
  id: string
  code: string
  name: string
  parent_id?: string | null
  route_path?: string | null
  icon?: string | null
  required_permission_code?: string | null
  sort_order: number
  status: string
  is_system?: boolean
}

export interface AuditLogItem {
  id: string
  actor?: SessionUser | null
  action: string
  target_type: string
  target_id?: string | null
  result: string
  created_at: string
}

export interface ModelItem {
  id: string
  name: string
  provider_type: string
  model_name: string
  base_url: string
  credential_configured: boolean
  credential_mask?: string | null
  status: string
  is_default: boolean
  timeout_seconds: number
  description?: string | null
  updated_at?: string
}

export interface ModelCallItem {
  id: string
  model?: {
    id: string
    name: string
  } | null
  purpose: string
  streamed: boolean
  status: string
  total_tokens?: number | null
  latency_ms?: number | null
  started_at?: string
}

export interface WatchSourceItem {
  id: string
  name: string
  source_type: string
  entry_url: string
  allowed_hosts: string[]
  status: string
  auth_configured?: boolean
  auth_mask?: string | null
  description?: string | null
  updated_at?: string
}

export interface WatchRuleItem {
  id: string
  source_id: string
  name: string
  request_method: string
  request_headers?: Record<string, unknown> | null
  request_params?: Record<string, unknown> | null
  extractor_type: string
  extractor_config: Record<string, unknown>
  status: string
  updated_at?: string
}

export interface CollectionTaskItem {
  id: string
  status: string
  trigger_type?: string
  source_count: number
  item_success_count: number
  item_failure_count: number
  failure_summary?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at: string
}

export interface CollectionTaskSourceItem {
  source_id: string
  rule_id: string
  source_name?: string | null
  rule_name?: string | null
  status: string
  failure_summary?: string | null
  started_at?: string | null
  finished_at?: string | null
}

export interface CollectionTaskDetail extends CollectionTaskItem {
  sources?: CollectionTaskSourceItem[]
}

export interface KnowledgeItem {
  id: string
  source_id: string
  source_name?: string | null
  task_id?: string | null
  title?: string | null
  summary?: string | null
  canonical_url?: string | null
  status: string
  collected_at: string
  published_at?: string | null
}

export interface KnowledgeItemDetail extends KnowledgeItem {
  content: string
  external_key?: string | null
  content_hash?: string | null
  reviewed_by?: SessionUser | null
  reviewed_at?: string | null
}

export interface QaSessionItem {
  id: string
  title?: string | null
  status: string
  updated_at?: string
  created_at?: string
}

export interface QaCitationItem {
  knowledge_item_id: string
  rank: number
  title?: string | null
  source_name?: string | null
  excerpt: string
  status?: string | null
  current_status?: string | null
}

export interface QaMessageItem {
  id: string
  session_id?: string
  role: 'user' | 'assistant'
  reply_to_id?: string | null
  content: string
  status: string
  error_summary?: string | null
  citations?: QaCitationItem[]
  created_at?: string
  updated_at?: string
}

// =============================================================================
// Chat (Phase 6)
// =============================================================================

export interface ContactItem {
  user_id: string
  username: string
  display_name: string
  remark?: string | null
  status: string
  created_at?: string
}

export interface FriendRequestItem {
  id: string
  from_user_id: string
  from_user_name: string
  to_user_id: string
  to_user_name: string
  status: string
  message?: string | null
  created_at?: string
}

export interface ConversationItem {
  id: string
  type: 'private' | 'group'
  name?: string | null
  unread_count: number
  last_message?: {
    content: string
    sender_name: string
    created_at: string
  } | null
  created_at?: string
  updated_at?: string
}

export interface ConversationMemberItem {
  user_id: string
  username: string
  display_name: string
  role: string
}

export interface MessageItem {
  id: string
  conversation_id: string
  sender_id: string
  sender_name: string
  content_type: string
  content: string
  reply_to_id?: string | null
  created_at?: string
}

// =============================================================================
// Phase 7 — 数字员工、工具、服务器与群增强
// =============================================================================

export interface DigitalEmployeeItem {
  id: string
  code: string
  name: string
  avatar?: string | null
  description?: string | null
  system_prompt?: string | null
  model_config_id?: string | null
  model_name?: string | null
  trigger_type: string
  max_turns: number
  status: string
  created_by?: string | null
  created_at?: string
  updated_at?: string
}

export interface ToolItem {
  id: string
  code: string
  name: string
  description?: string | null
  tool_type: string
  config: Record<string, unknown>
  config_mask?: string | null
  invocation_limit: number
  invocation_window_seconds: number
  status: string
  created_by?: string | null
  created_at?: string
  updated_at?: string
}

export interface ToolInvocationLogItem {
  id: string
  tool_name?: string | null
  employee_name?: string | null
  caller_name?: string | null
  status: string
  error_code?: string | null
  latency_ms?: number | null
  created_at?: string
}

export interface ChatServerItem {
  id: string
  name: string
  base_url: string
  health_check_url?: string | null
  auth_mask?: string | null
  priority: number
  status: string
  last_health_check_at?: string | null
  last_health_check_result?: string | null
  created_by?: string | null
  created_at?: string
  updated_at?: string
}

export interface GroupDetailItem {
  id: string
  name?: string | null
  type: string
  is_disbanded: boolean
  member_count: number
  members: Array<{
    user_id: string
    username: string
    display_name: string
    role: string
    banned_at?: string | null
  }>
  created_by?: string | null
  created_by_id?: string
  created_at?: string
  updated_at?: string
}

export interface GroupAnnouncementItem {
  id: string
  conversation_id: string
  title?: string | null
  content: string
  is_pinned: boolean
  created_by_id?: string
  created_at?: string
}

export interface FileStatsItem {
  total_files: number
  total_blobs: number
  total_size_bytes: number
  saved_bytes: number
  dedup_ratio: number
}

export interface AdminFileItem {
  id: string
  filename: string
  mime_type?: string | null
  size_bytes: number
  sha256?: string | null
  uploaded_by?: string | null
  uploaded_by_id?: string
  created_at?: string
}
