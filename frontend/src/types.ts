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
