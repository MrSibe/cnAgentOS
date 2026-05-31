<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { get, post } from '@/api/client'
import { useChatStore } from '@/stores/chat'
import { useSessionStore } from '@/stores/session'
import { errorMessage } from '@/utils/display'
import type { ConversationMemberItem } from '@/types'
import type { ConversationItem } from '@/types'

const session = useSessionStore()
const chat = useChatStore()

// --- Tab state ---
const activeTab = ref<'chats' | 'contacts'>('chats')
const chatSearch = ref('')
const contactSearch = ref('')

// --- Dialogs ---
const showAddFriend = ref(false)
const friendSearch = ref('')
const searchResults = ref<{ user_id: string; username: string; display_name: string }[]>([])
const showFriendRequests = ref(false)
const showMembers = ref(false)
const memberList = ref<ConversationMemberItem[]>([])
const showCreateGroup = ref(false)
const groupName = ref('')
const groupMembers = ref('')

// --- Composer ---
const newMessage = ref('')
const messagePane = ref<HTMLElement | null>(null)

// --- Computed ---
const activeConversation = computed(() =>
  chat.conversations.find(c => c.id === chat.activeConversationId)
)

const conversationTitle = computed(() => {
  const conv = activeConversation.value
  if (!conv) return ''
  if (conv.type === 'group') return conv.name || '群聊'
  return conv.name || '私聊'
})

const filteredConversations = computed(() => {
  if (!chatSearch.value) return chat.conversations
  const q = chatSearch.value.toLowerCase()
  return chat.conversations.filter(c => (c.name || '').toLowerCase().includes(q))
})

const filteredContacts = computed(() => {
  if (!contactSearch.value) return chat.contacts
  const q = contactSearch.value.toLowerCase()
  return chat.contacts.filter(
    c => c.display_name.toLowerCase().includes(q) || c.username.toLowerCase().includes(q)
  )
})

// --- Methods ---

function openConversation(conv: ConversationItem): void {
  chat.setActiveConversation(conv.id)
  conv.unread_count = 0
}

function startPrivateChat(contact: { user_id: string }): void {
  const existing = chat.conversations.find(
    c => c.type === 'private' && c.id === contact.user_id
  )
  if (existing) {
    openConversation(existing)
    return
  }
  ElMessage.info('请先给联系人发送一条消息以创建聊天')
}

async function doSearchUsers(): Promise<void> {
  if (!friendSearch.value) return
  try {
    const data = await get<{ user_id: string; username: string; display_name: string }[]>(
      '/api/v1/chat/users/search?q=' + encodeURIComponent(friendSearch.value) + '&page_size=20'
    )
    searchResults.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function doSendRequest(username: string): Promise<void> {
  try {
    await chat.sendFriendRequest(username)
    ElMessage.success('好友请求已发送')
    showAddFriend.value = false
    friendSearch.value = ''
    searchResults.value = []
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleFriendReq(requestId: string, action: 'accept' | 'reject'): Promise<void> {
  try {
    await chat.handleFriendRequest(requestId, action)
    ElMessage.success(action === 'accept' ? '已添加好友' : '已拒绝')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function loadMembers(): Promise<void> {
  if (!chat.activeConversationId) return
  try {
    memberList.value = await get<ConversationMemberItem[]>(
      '/api/v1/chat/conversations/' + chat.activeConversationId + '/members'
    )
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function showMemberDialog(): void {
  showMembers.value = true
  loadMembers()
}

async function confirmLeaveGroup(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定退出群聊？', '退出群聊')
    await chat.leaveGroup(chat.activeConversationId!)
    ElMessage.success('已退出群聊')
    showMembers.value = false
  } catch (error) {
    if (!errorMessage(error).includes('cancel')) {
      ElMessage.error(errorMessage(error))
    }
  }
}

async function createGroup(): Promise<void> {
  if (!groupMembers.value.trim()) {
    ElMessage.warning('请输入群成员用户名')
    return
  }
  const usernames = groupMembers.value.split(/[,，\s]+/).filter(Boolean)
  try {
    await chat.createGroup(groupName.value || null, usernames)
    ElMessage.success('群聊已创建')
    showCreateGroup.value = false
    groupName.value = ''
    groupMembers.value = ''
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleSend(): Promise<void> {
  const content = newMessage.value.trim()
  if (!content || !chat.activeConversationId) return
  newMessage.value = ''

  try {
    // Send via REST (WebSocket also sends, but REST is the reliable path)
    await post('/api/v1/chat/messages', {
      conversation_id: chat.activeConversationId,
      content,
      content_type: 'text',
    })
    // Also send via WebSocket for real-time push to other users
    chat.wsSend('send_message', {
      conversation_id: chat.activeConversationId,
      content,
    })
    await chat.loadMessages(chat.activeConversationId)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

// Auto-scroll on new messages
watch(() => chat.messages.length, async () => {
  await nextTick()
  if (messagePane.value) {
    messagePane.value.scrollTop = messagePane.value.scrollHeight
  }
})

// Lifecycle
onMounted(() => {
  chat.init()
})

onUnmounted(() => {
  chat.destroy()
})
</script>

<template>
  <section class="chat-workbench">
    <!-- Left sidebar -->
    <aside class="chat-sidebar">
      <div class="chat-sidebar-head">
        <div class="chat-tabs">
          <button :class="{ active: activeTab === 'chats' }" @click="activeTab = 'chats'">聊天</button>
          <button :class="{ active: activeTab === 'contacts' }" @click="activeTab = 'contacts'">通讯录</button>
        </div>
        <div class="chat-actions">
          <el-badge :value="chat.incomingRequests.length" :hidden="!chat.incomingRequests.length">
            <el-button size="small" @click="showFriendRequests = true">
              <el-icon><Bell /></el-icon>
            </el-button>
          </el-badge>
          <el-button size="small" @click="showAddFriend = true">
            <el-icon><Plus /></el-icon>
          </el-button>
          <el-button size="small" @click="showCreateGroup = true">
            <el-icon><ChatDotSquare /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- Chats tab -->
      <div v-show="activeTab === 'chats'" class="chat-list">
        <el-input v-model="chatSearch" placeholder="搜索聊天" size="small" clearable />
        <div v-if="filteredConversations.length === 0" class="empty-hint">
          <p>暂无聊天</p>
        </div>
        <div
          v-for="conv in filteredConversations"
          :key="conv.id"
          class="chat-list-item"
          :class="{ active: conv.id === chat.activeConversationId }"
          @click="openConversation(conv)"
        >
          <div class="chat-list-item-info">
            <strong class="conv-name">{{ conv.name || (conv.type === 'group' ? '群聊' : '私聊') }}</strong>
            <span class="last-message">{{ conv.last_message?.content || '' }}</span>
          </div>
          <div class="chat-list-item-meta">
            <span class="conv-time">{{ conv.last_message?.created_at ? new Date(conv.last_message.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '' }}</span>
            <el-badge :value="conv.unread_count" :hidden="!conv.unread_count" />
          </div>
        </div>
      </div>

      <!-- Contacts tab -->
      <div v-show="activeTab === 'contacts'" class="contact-list">
        <el-input v-model="contactSearch" placeholder="搜索联系人" size="small" clearable />
        <div v-if="filteredContacts.length === 0" class="empty-hint">
          <p>暂无联系人</p>
        </div>
        <div
          v-for="contact in filteredContacts"
          :key="contact.user_id"
          class="contact-list-item"
          @click="startPrivateChat(contact)"
        >
          <div class="contact-avatar">{{ (contact.remark || contact.display_name)[0] }}</div>
          <div class="contact-info">
            <strong>{{ contact.remark || contact.display_name }}</strong>
            <span class="contact-username">@{{ contact.username }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main message panel -->
    <main class="chat-panel">
      <template v-if="activeConversation">
        <header class="chat-panel-head">
          <h2>{{ conversationTitle }}</h2>
          <el-button v-if="activeConversation.type === 'group'" size="small" @click="showMemberDialog">群成员</el-button>
        </header>

        <section ref="messagePane" class="chat-messages" v-loading="chat.loadingMessages">
          <div v-for="msg in chat.messages" :key="msg.id" class="chat-message" :class="msg.sender_id === session.user?.id ? 'own' : 'other'">
            <div v-if="activeConversation.type === 'group' && msg.sender_id !== session.user?.id" class="message-sender">
              {{ msg.sender_name }}
            </div>
            <div class="message-bubble">
              {{ msg.content }}
            </div>
            <div class="message-time">{{ msg.created_at ? new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '' }}</div>
          </div>
        </section>

        <footer class="chat-composer">
          <el-input
            v-model="newMessage"
            type="textarea"
            :autosize="{ minRows: 2, maxRows: 4 }"
            placeholder="输入消息..."
            @keyup.enter.prevent="handleSend"
          />
          <el-button type="primary" @click="handleSend">发送</el-button>
        </footer>
      </template>

      <el-empty v-else description="选择一个聊天开始对话" />
    </main>

    <!-- Add friend dialog -->
    <el-dialog v-model="showAddFriend" title="添加好友" width="400px">
      <el-input v-model="friendSearch" placeholder="搜索用户名" @keyup.enter="doSearchUsers" />
      <el-button type="primary" size="small" style="margin-top:8px" @click="doSearchUsers">搜索</el-button>
      <div v-for="user in searchResults" :key="user.user_id" class="search-result-item">
        <span>{{ user.display_name }} (@{{ user.username }})</span>
        <el-button size="small" type="primary" @click="doSendRequest(user.username)">添加</el-button>
      </div>
      <div v-if="searchResults.length === 0 && friendSearch" class="search-empty">
        未找到用户
      </div>
    </el-dialog>

    <!-- Friend requests dialog -->
    <el-dialog v-model="showFriendRequests" title="好友请求" width="400px">
      <div v-if="chat.incomingRequests.length === 0" class="search-empty">
        暂无待处理请求
      </div>
      <div v-for="req in chat.incomingRequests" :key="req.id" class="friend-request-item">
        <div class="friend-request-info">
          <strong>{{ req.from_user_name }}</strong>
          <p v-if="req.message" class="request-message">{{ req.message }}</p>
        </div>
        <div class="friend-request-actions">
          <el-button type="success" size="small" @click="handleFriendReq(req.id, 'accept')">接受</el-button>
          <el-button size="small" @click="handleFriendReq(req.id, 'reject')">拒绝</el-button>
        </div>
      </div>
    </el-dialog>

    <!-- Create group dialog -->
    <el-dialog v-model="showCreateGroup" title="创建群聊" width="400px">
      <el-form label-position="top">
        <el-form-item label="群名称">
          <el-input v-model="groupName" placeholder="群聊名称（可选）" />
        </el-form-item>
        <el-form-item label="群成员">
          <el-input v-model="groupMembers" placeholder="输入用户名，用逗号分隔" type="textarea" :rows="3" />
          <p class="member-hint">仅限已经是联系人的用户</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateGroup = false">取消</el-button>
        <el-button type="primary" @click="createGroup">创建</el-button>
      </template>
    </el-dialog>

    <!-- Members dialog -->
    <el-dialog v-model="showMembers" title="群成员" width="350px">
      <div v-for="member in memberList" :key="member.user_id" class="member-item">
        <span>{{ member.display_name }} (@{{ member.username }})</span>
        <el-tag v-if="member.role === 'owner'" size="small" type="warning">群主</el-tag>
      </div>
      <template #footer>
        <el-button type="danger" size="small" @click="confirmLeaveGroup">退出群聊</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.chat-workbench {
  display: flex;
  height: calc(100vh - 120px);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-bg-color);
}
.chat-sidebar {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--el-border-color-light);
  background: var(--el-bg-color-page);
}
.chat-sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem;
  border-bottom: 1px solid var(--el-border-color-light);
}
.chat-tabs { display: flex; gap: 0.25rem; }
.chat-tabs button {
  padding: 0.375rem 0.75rem;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
}
.chat-tabs button.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}
.chat-actions { display: flex; gap: 0.25rem; }
.chat-list, .contact-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
.chat-list-item, .contact-list-item {
  display: flex;
  align-items: center;
  padding: 0.625rem;
  border-radius: 6px;
  cursor: pointer;
  gap: 0.5rem;
}
.chat-list-item:hover, .contact-list-item:hover { background: var(--el-color-primary-light-9); }
.chat-list-item.active { background: var(--el-color-primary-light-8); }
.chat-list-item-info { flex: 1; min-width: 0; }
.conv-name { display: block; font-size: 0.875rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.last-message { display: block; font-size: 0.75rem; color: var(--el-text-color-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-list-item-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem; }
.conv-time { font-size: 0.6875rem; color: var(--el-text-color-secondary); white-space: nowrap; }
.contact-avatar {
  width: 36px; height: 36px; border-radius: 50%; background: var(--el-color-primary-light-5);
  color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 600;
  font-size: 0.875rem; flex-shrink: 0;
}
.contact-info { flex: 1; min-width: 0; }
.contact-info strong { display: block; font-size: 0.875rem; }
.contact-username { font-size: 0.75rem; color: var(--el-text-color-secondary); }
.empty-hint { text-align: center; padding: 2rem 0; color: var(--el-text-color-secondary); font-size: 0.875rem; }

/* Message panel */
.chat-panel { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-panel-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.75rem 1rem; border-bottom: 1px solid var(--el-border-color-light);
}
.chat-panel-head h2 { font-size: 1rem; font-weight: 600; margin: 0; }
.chat-messages { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: 0.75rem; }
.chat-message { max-width: 70%; display: flex; flex-direction: column; gap: 0.25rem; }
.chat-message.own { align-self: flex-end; align-items: flex-end; }
.chat-message.other { align-self: flex-start; align-items: flex-start; }
.message-sender { font-size: 0.75rem; color: var(--el-text-color-secondary); margin-bottom: 0.125rem; }
.message-bubble {
  padding: 0.5rem 0.75rem; border-radius: 8px; font-size: 0.875rem; line-height: 1.4; word-break: break-word;
}
.chat-message.own .message-bubble { background: var(--el-color-primary); color: #fff; border-bottom-right-radius: 2px; }
.chat-message.other .message-bubble { background: var(--el-fill-color-light); border-bottom-left-radius: 2px; }
.message-time { font-size: 0.6875rem; color: var(--el-text-color-placeholder); }
.chat-composer {
  display: flex; align-items: flex-end; gap: 0.5rem;
  padding: 0.75rem 1rem; border-top: 1px solid var(--el-border-color-light);
}
.chat-composer .el-textarea { flex: 1; }

/* Dialogs */
.search-result-item, .friend-request-item, .member-item {
  display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0;
  border-bottom: 1px solid var(--el-border-color-light);
}
.friend-request-info { flex: 1; }
.request-message { font-size: 0.8125rem; color: var(--el-text-color-secondary); margin: 0.25rem 0 0; }
.friend-request-actions { display: flex; gap: 0.5rem; flex-shrink: 0; }
.search-empty { text-align: center; color: var(--el-text-color-secondary); padding: 1rem; }
.member-hint { font-size: 0.75rem; color: var(--el-text-color-secondary); margin-top: 4px; }

@media (max-width: 768px) {
  .chat-sidebar { width: 100%; }
  .chat-panel { display: none; }
}
</style>
