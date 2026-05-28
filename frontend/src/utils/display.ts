import { ApiError } from '@/api/client'

export function errorMessage(error: unknown): string {
  return error instanceof ApiError || error instanceof Error ? error.message : '操作失败，请稍后重试'
}

export function shortTime(value?: string | null): string {
  if (!value) return '-'
  const m = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}/.exec(value)
  return m ? m[0].replace('T', ' ') : value
}

export function statusType(status?: string | null): 'primary' | 'success' | 'info' | 'warning' | 'danger' {
  if (status === 'active' || status === 'available' || status === 'succeeded' || status === 'success') return 'success'
  if (status === 'disabled' || status === 'archived' || status === 'cancelled' || status === 'pending') return 'info'
  if (status === 'excluded' || status === 'partial_failed') return 'warning'
  if (status === 'failed' || status === 'error') return 'danger'
  return 'primary'
}

/**
 * ElMessageBox.confirm rejects with the strings 'cancel' or 'close'
 * when the user dismisses the dialog without confirming.
 */
export function isUserCancelled(error: unknown): boolean {
  return error === 'cancel' || error === 'close'
}
