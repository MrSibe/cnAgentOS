<script setup lang="ts">
defineProps<{ title: string; description: string }>()
</script>

<template>
  <header class="page-heading">
    <div>
      <p class="page-eyebrow">CNAGENTOS / OPERATIONS</p>
      <h1>{{ title }}</h1>
      <p class="page-description">{{ description }}</p>
    </div>
    <div class="page-actions">
      <slot />
    </div>
  </header>
</template>
