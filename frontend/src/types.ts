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
  model_name: string
  purpose: string
  streamed: boolean
  status: string
  total_tokens?: number | null
  latency_ms?: number | null
  started_at?: string
}
