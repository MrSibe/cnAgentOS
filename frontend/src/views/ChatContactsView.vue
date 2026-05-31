<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { get, patch, post } from '@/api/client'
import { useChatStore } from '@/stores/chat'
import { errorMessage } from '@/utils/display'
import type { ContactItem } from '@/types'

const router = useRouter()
const chat = useChatStore()

const activeTab = ref<'contacts' | 'requests' | 'search'>('contacts')
const searchQuery = ref('')
const searchResults = ref<{ user_id: string; username: string; display_name: string }[]>([])
const loading = ref(false)

async function doSearch(): Promise<void> {
  if (!searchQuery.value) return
  loading.value = true
  try {
    const data = await get<{ user_id: string; username: string; display_name: string }[]>(
      '/api/v1/chat/users/search?q=' + encodeURIComponent(searchQuery.value) + '&page_size=20'
    )
    searchResults.value = data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function doSendRequest(username: string): Promise<void> {
  try {
    await post('/api/v1/chat/friend-requests', { username })
    ElMessage.success('好友请求已发送')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function handleReq(requestId: string, action: 'accept' | 'reject'): Promise<void> {
  try {
    await patch('/api/v1/chat/friend-requests/' + requestId, { action })
    await chat.loadFriendRequests()
    if (action === 'accept') await chat.loadContacts()
    ElMessage.success(action === 'accept' ? '已添加好友' : '已拒绝')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function chatWith(_contact: ContactItem): void {
  router.push('/chat')
}

onMounted(() => {
  chat.loadContacts()
  chat.loadFriendRequests()
})
</script>

<template>
  <section class="contacts-page">
    <header class="contacts-head">
      <h2>通讯录</h2>
      <div class="contacts-tabs">
        <el-radio-group v-model="activeTab" size="small">
          <el-radio-button value="contacts">联系人</el-radio-button>
          <el-radio-button value="requests">
            请求
            <el-badge :value="chat.incomingRequests.length" :hidden="!chat.incomingRequests.length" />
          </el-radio-button>
          <el-radio-button value="search">查找用户</el-radio-button>
        </el-radio-group>
      </div>
    </header>

    <!-- Contacts list -->
    <div v-if="activeTab === 'contacts'" class="contacts-list">
      <div v-if="chat.contacts.length === 0" class="empty">暂无联系人</div>
      <div
        v-for="c in chat.contacts"
        :key="c.user_id"
        class="contact-card"
        @click="chatWith(c)"
      >
        <div class="contact-avatar">{{ (c.remark || c.display_name)[0] }}</div>
        <div class="contact-body">
          <strong>{{ c.remark || c.display_name }}</strong>
          <span class="contact-username">@{{ c.username }}</span>
        </div>
      </div>
    </div>

    <!-- Requests -->
    <div v-else-if="activeTab === 'requests'" class="requests-list">
      <div v-if="chat.incomingRequests.length === 0" class="empty">暂无待处理请求</div>
      <div v-for="req in chat.incomingRequests" :key="req.id" class="request-card">
        <div class="request-body">
          <strong>{{ req.from_user_name }}</strong>
          <p v-if="req.message" class="request-msg">{{ req.message }}</p>
        </div>
        <div class="request-actions">
          <el-button type="success" size="small" @click="handleReq(req.id, 'accept')">接受</el-button>
          <el-button size="small" @click="handleReq(req.id, 'reject')">拒绝</el-button>
        </div>
      </div>
    </div>

    <!-- Search users -->
    <div v-else class="search-panel">
      <div class="search-bar">
        <el-input v-model="searchQuery" placeholder="输入用户名搜索" @keyup.enter="doSearch" />
        <el-button type="primary" :loading="loading" @click="doSearch">搜索</el-button>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <div v-for="u in searchResults" :key="u.user_id" class="search-item">
          <span>{{ u.display_name }} (@{{ u.username }})</span>
          <el-button size="small" type="primary" @click="doSendRequest(u.username)">添加好友</el-button>
        </div>
      </div>
      <div v-else-if="searchQuery && !loading" class="empty">未找到用户</div>
    </div>
  </section>
</template>

<style scoped>
.contacts-page {
  padding: 1rem;
  max-width: 600px;
  margin: 0 auto;
}
.contacts-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}
.contacts-head h2 { font-size: 1.25rem; font-weight: 600; margin: 0; }
.contacts-list, .requests-list, .search-panel { display: flex; flex-direction: column; gap: 0.5rem; }
.contact-card, .request-card {
  display: flex; align-items: center; padding: 0.75rem; border-radius: 8px;
  border: 1px solid var(--el-border-color-light); cursor: pointer; gap: 0.75rem;
}
.contact-card:hover { background: var(--el-color-primary-light-9); }
.contact-avatar {
  width: 40px; height: 40px; border-radius: 50%; background: var(--el-color-primary-light-5);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-weight: 600; flex-shrink: 0;
}
.contact-body, .request-body { flex: 1; }
.contact-body strong, .request-body strong { display: block; font-size: 0.9375rem; }
.contact-username { font-size: 0.8125rem; color: var(--el-text-color-secondary); }
.request-msg { font-size: 0.8125rem; color: var(--el-text-color-secondary); margin: 0.25rem 0 0; }
.request-actions { display: flex; gap: 0.5rem; flex-shrink: 0; }
.search-bar { display: flex; gap: 0.5rem; }
.search-results, .search-item { display: flex; flex-direction: column; gap: 0.5rem; }
.search-item {
  flex-direction: row; align-items: center; justify-content: space-between;
  padding: 0.5rem; border-bottom: 1px solid var(--el-border-color-light);
}
.empty { text-align: center; padding: 2rem; color: var(--el-text-color-secondary); }
</style>
