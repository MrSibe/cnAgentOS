import { defineStore } from 'pinia'
import { ref } from 'vue'

import { get, patch, post } from '@/api/client'
import type {
  ContactItem,
  ConversationItem,
  FriendRequestItem,
  MessageItem,
} from '@/types'

export const useChatStore = defineStore('chat', () => {
  // --- State ---
  const conversations = ref<ConversationItem[]>([])
  const contacts = ref<ContactItem[]>([])
  const incomingRequests = ref<FriendRequestItem[]>([])
  const activeConversationId = ref<string | null>(null)
  const messages = ref<MessageItem[]>([])
  const loadingMessages = ref(false)
  const connected = ref(false)
  const wsConnected = ref(false)

  // WebSocket instance reference
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  // Track last received message ID for offline pull
  const lastMessageId = ref<string | null>(null)

  // --- REST API helpers ---

  async function loadConversations(): Promise<void> {
    conversations.value = await get<ConversationItem[]>('/api/v1/chat/conversations')
  }

  async function loadContacts(): Promise<void> {
    contacts.value = await get<ContactItem[]>('/api/v1/chat/contacts')
  }

  async function loadFriendRequests(): Promise<void> {
    incomingRequests.value = await get<FriendRequestItem[]>('/api/v1/chat/friend-requests/incoming')
  }

  async function searchUsers(query: string): Promise<{ user_id: string; username: string; display_name: string }[]> {
    return get('/api/v1/chat/users/search?q=' + encodeURIComponent(query) + '&page_size=20')
  }

  async function sendFriendRequest(username: string, message?: string): Promise<void> {
    await post('/api/v1/chat/friend-requests', { username, message })
    await loadFriendRequests()
  }

  async function handleFriendRequest(requestId: string, action: 'accept' | 'reject'): Promise<void> {
    await patch('/api/v1/chat/friend-requests/' + requestId, { action })
    await loadFriendRequests()
    if (action === 'accept') {
      await loadContacts()
    }
  }

  async function createGroup(name: string | null, memberUsernames: string[]): Promise<ConversationItem> {
    const conv = await post<ConversationItem>('/api/v1/chat/conversations', { name, member_usernames: memberUsernames })
    await loadConversations()
    return conv
  }

  async function loadMessages(conversationId: string, before?: string, after?: string, limit = 50): Promise<void> {
    loadingMessages.value = true
    try {
      const params = new URLSearchParams({ conversation_id: conversationId, limit: String(limit) })
      if (before) params.set('before', before)
      if (after) params.set('after', after)
      const data = await get<MessageItem[]>('/api/v1/chat/messages?' + params.toString())
      messages.value = data
      if (data.length > 0) {
        lastMessageId.value = data[data.length - 1].id
      }
    } finally {
      loadingMessages.value = false
    }
  }

  async function leaveGroup(conversationId: string): Promise<void> {
    await post('/api/v1/chat/conversations/' + conversationId + '/leave')
    await loadConversations()
    if (activeConversationId.value === conversationId) {
      activeConversationId.value = null
      messages.value = []
    }
  }

  function setActiveConversation(id: string | null): void {
    activeConversationId.value = id
    if (id) {
      loadMessages(id)
    } else {
      messages.value = []
    }
  }

  // --- WebSocket ---

  function getWsUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}/api/v1/ws`
  }

  function connectWs(): void {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return
    ws = new WebSocket(getWsUrl())

    ws.onopen = () => {
      wsConnected.value = true
      reconnectAttempts = 0
      connected.value = true
    }

    ws.onclose = () => {
      wsConnected.value = false
      ws = null
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws?.close()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const frame = JSON.parse(event.data)
        handleWsFrame(frame)
      } catch {
        // ignore malformed frames
      }
    }
  }

  function scheduleReconnect(): void {
    if (reconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      reconnectAttempts++
      connectWs()
    }, delay)
  }

  function disconnectWs(): void {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.onclose = null
      ws.close()
      ws = null
    }
    wsConnected.value = false
    connected.value = false
    reconnectAttempts = 0
  }

  function wsSend(type: string, payload: Record<string, unknown>, id?: string): void {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload, ...(id ? { id } : {}) }))
    }
  }

  function handleWsFrame(frame: { type: string; payload: any }): void {
    switch (frame.type) {
      case 'connected':
        wsConnected.value = true
        break

      case 'new_message': {
        const msg = frame.payload as MessageItem
        if (msg.conversation_id === activeConversationId.value) {
          // Append to current messages list if viewing this conversation
          messages.value = [...messages.value, msg]
          lastMessageId.value = msg.id
        } else {
          // Different conversation — increment unread count
          const conv = conversations.value.find(c => c.id === msg.conversation_id)
          if (conv) {
            conv.unread_count = (conv.unread_count || 0) + 1
            conv.last_message = {
              content: msg.content,
              sender_name: msg.sender_name,
              created_at: msg.created_at || '',
            }
          }
        }
        break
      }

      case 'message_read':
        // Optionally update UI for read receipts (Phase 7 enhancement)
        break

      case 'friend_request':
        // A new friend request arrived — refresh
        loadFriendRequests()
        break

      case 'presence':
        // Could update contact online status (Phase 7 enhancement)
        break

      case 'error':
        console.warn('[WS error]', frame.payload)
        break
    }
  }

  // --- Lifecycle ---

  function init(): void {
    loadConversations()
    loadContacts()
    loadFriendRequests()
    connectWs()
  }

  function destroy(): void {
    disconnectWs()
  }

  return {
    // State
    conversations,
    contacts,
    incomingRequests,
    activeConversationId,
    messages,
    loadingMessages,
    connected,
    wsConnected,
    lastMessageId,
    // REST
    loadConversations,
    loadContacts,
    loadFriendRequests,
    searchUsers,
    sendFriendRequest,
    handleFriendRequest,
    createGroup,
    loadMessages,
    leaveGroup,
    setActiveConversation,
    // WebSocket
    connectWs,
    disconnectWs,
    wsSend,
    // Lifecycle
    init,
    destroy,
  }
})
