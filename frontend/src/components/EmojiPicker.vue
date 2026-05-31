<template>
  <el-popover trigger="click" :width="280" popper-class="emoji-picker-popover">
    <template #reference>
      <el-button size="small" circle><span style="font-size: 16px">😊</span></el-button>
    </template>
    <div class="emoji-grid">
      <button v-for="emoji in emojis" :key="emoji" class="emoji-item" @click="selectEmoji(emoji)">
        {{ emoji }}
      </button>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
const emit = defineEmits<{ select: [emoji: string] }>()

const emojis = [
  '😊', '😂', '🤣', '❤️', '😍', '🥰', '😘', '😎',
  '👍', '👏', '🙌', '🎉', '🔥', '💪', '🤝', '✨',
  '😀', '😃', '😄', '😁', '😅', '🤗', '🤔', '😌',
  '😢', '😭', '😤', '😡', '🥺', '😳', '😱', '🤯',
  '🙏', '💯', '⭐', '🌈', '🎶', '🎵', '💡', '📚',
  '🐶', '🐱', '🐼', '🌸', '🌺', '🍀', '🌻', '☀️',
  '🍎', '🍕', '🍺', '☕', '🎂', '🍰', '🎁', '💎',
  '🚀', '✈️', '🏠', '🌍', '📱', '💻', '⌚', '📷',
]

function selectEmoji(emoji: string): void {
  emit('select', emoji)
}
</script>

<style scoped>
.emoji-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 4px; }
.emoji-item {
  background: transparent; border: none; font-size: 20px;
  cursor: pointer; padding: 4px; border-radius: 4px; transition: background 0.2s;
}
.emoji-item:hover { background: #f0f0f0; }
</style>
