<script setup lang="ts">
import { ChatDotRound, ChatDotSquare, Clock, Collection, Cpu, DataAnalysis, Key, Menu, Setting, User } from '@element-plus/icons-vue'
import type { Component } from 'vue'

import type { NavigationItem } from '@/types'

defineOptions({ name: 'AppNavigation' })
defineProps<{ nodes: NavigationItem[] }>()

const icons: Record<string, Component> = {
  users: User,
  key: Key,
  menu: Menu,
  settings: Setting,
  cpu: Cpu,
  activity: DataAnalysis,
  'data-analysis': DataAnalysis,
  history: Clock,
  'file-search': Collection,
  sparkles: ChatDotRound,
  'chat-dot-square': ChatDotSquare,
}

function iconFor(name?: string | null): Component {
  return icons[name ?? ''] ?? Setting
}
</script>

<template>
  <div class="navigation-tree">
    <template v-for="node in nodes" :key="node.id">
      <section v-if="node.children?.length" class="nav-cluster">
        <p class="nav-cluster-title">{{ node.name }}</p>
        <app-navigation :nodes="node.children" />
      </section>
      <router-link v-else-if="node.route_path" :to="node.route_path" class="nav-link">
        <el-icon><component :is="iconFor(node.icon)" /></el-icon>
        <span>{{ node.name }}</span>
      </router-link>
    </template>
  </div>
</template>
