import type { QaCitationItem, QaMessageItem } from '@/types'

export function extractQaDeltaContent(data: Record<string, unknown>): string {
  if (typeof data.content === 'string') return data.content
  if (typeof data.delta === 'string') return data.delta
  const choices = data.choices as Array<{ delta?: { content?: string }; text?: string }> | undefined
  return choices?.[0]?.delta?.content ?? choices?.[0]?.text ?? ''
}

export function applyQaStreamEvent(message: QaMessageItem, event: string, data: Record<string, unknown>): void {
  if (event === 'delta') {
    message.content += extractQaDeltaContent(data)
  }
  if (event === 'completed') {
    message.status = 'completed'
    if (typeof data.message_id === 'string') message.id = data.message_id
    message.citations = Array.isArray(data.citations) ? (data.citations as QaCitationItem[]) : []
  }
  if (event === 'error') {
    message.status = 'failed'
    const streamError = data.error as { message?: string } | undefined
    message.error_summary = String(streamError?.message ?? data.message ?? '回答生成失败')
    if (!message.content) message.content = message.error_summary
  }
}

export function inlineQaCitations(message: QaMessageItem): QaCitationItem[] {
  return message.citations?.length ? message.citations : []
}
