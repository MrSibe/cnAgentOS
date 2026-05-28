<script setup lang="ts">
import { computed } from 'vue'

import { statusType } from '@/utils/display'

const props = defineProps<{ value?: string | null }>()
const tagType = computed(() => statusType(props.value))
</script>

<template>
  <el-tag :type="tagType" effect="plain" round>{{ value || '-' }}</el-tag>
</template>
