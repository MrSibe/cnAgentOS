import { describe, expect, it } from 'vitest'

import { errorMessage, isUserCancelled, shortTime, statusType } from './display'

describe('display helpers', () => {
  it('formats ISO timestamps for compact table display', () => {
    expect(shortTime('2026-05-28T07:00:00Z')).toBe('2026-05-28 07:00:00')
    expect(shortTime('2026-05-28T07:00:00.123Z')).toBe('2026-05-28 07:00:00')
    expect(shortTime('2026-05-28T07:00:00+08:00')).toBe('2026-05-28 07:00:00')
    expect(shortTime(null)).toBe('-')
    expect(shortTime('')).toBe('-')
  })

  it('maps known statuses to Element Plus tag types', () => {
    expect(statusType('active')).toBe('success')
    expect(statusType('disabled')).toBe('info')
    expect(statusType('failed')).toBe('danger')
  })

  it('extracts readable error messages', () => {
    expect(errorMessage(new Error('请求失败'))).toBe('请求失败')
  })

  it('detects ElMessageBox cancel and close rejections', () => {
    expect(isUserCancelled('cancel')).toBe(true)
    expect(isUserCancelled('close')).toBe(true)
    expect(isUserCancelled(new Error('other'))).toBe(false)
  })
})
