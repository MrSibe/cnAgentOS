import { ApiError } from '@/api/client'

export function errorMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof Error ? error.message : '操作失败，请稍后重试'
}

export function shortTime(value?: string | null): string {
  return value ? value.replace('T', ' ').replace('Z', '') : '-'
}

export function statusType(status?: string | null): 'primary' | 'success' | 'info' | 'warning' | 'danger' {
  if (status === 'active' || status === 'succeeded' || status === 'success') return 'success'
  if (status === 'disabled') return 'info'
  if (status === 'failed' || status === 'error') return 'danger'
  return 'primary'
}
