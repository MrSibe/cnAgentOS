import { describe, expect, it } from 'vitest'

import type { QaCitationItem, QaMessageItem } from '@/types'

import { applyQaStreamEvent, extractQaDeltaContent, inlineQaCitations } from './qa'

function answerMessage(): QaMessageItem {
  return {
    id: 'local-answer',
    role: 'assistant',
    content: '',
    status: 'streaming',
    citations: [],
  }
}

describe('qa helpers', () => {
  it('extracts delta content from supported stream payloads', () => {
    expect(extractQaDeltaContent({ content: '正文' })).toBe('正文')
    expect(extractQaDeltaContent({ delta: '片段' })).toBe('片段')
    expect(extractQaDeltaContent({ choices: [{ delta: { content: '模型片段' } }] })).toBe('模型片段')
    expect(extractQaDeltaContent({ choices: [{ text: '文本片段' }] })).toBe('文本片段')
  })

  it('appends delta stream events', () => {
    const message = answerMessage()
    applyQaStreamEvent(message, 'delta', { content: '第一段' })
    applyQaStreamEvent(message, 'delta', { content: '第二段' })
    expect(message.content).toBe('第一段第二段')
    expect(message.status).toBe('streaming')
  })

  it('marks completed stream events and attaches citations', () => {
    const message = answerMessage()
    const citations: QaCitationItem[] = [{ knowledge_item_id: 'item-1', rank: 1, excerpt: '引用' }]
    applyQaStreamEvent(message, 'completed', { message_id: 'answer-1', citations })
    expect(message.id).toBe('answer-1')
    expect(message.status).toBe('completed')
    expect(message.citations).toEqual(citations)
  })

  it('renders stream errors as failed answers', () => {
    const message = answerMessage()
    applyQaStreamEvent(message, 'error', { error: { message: '模型失败' } })
    expect(message.status).toBe('failed')
    expect(message.error_summary).toBe('模型失败')
    expect(message.content).toBe('模型失败')
  })

  it('uses inline citations when available', () => {
    const citations: QaCitationItem[] = [{ knowledge_item_id: 'item-1', rank: 1, excerpt: '引用' }]
    expect(inlineQaCitations({ ...answerMessage(), citations })).toEqual(citations)
    expect(inlineQaCitations(answerMessage())).toEqual([])
  })
})
