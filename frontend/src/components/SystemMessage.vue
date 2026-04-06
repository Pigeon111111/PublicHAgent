<script setup lang="ts">
defineProps<{
  content: string
}>()
</script>

<template>
  <div class="system-message">
    <el-icon :size="16"><WarningFilled /></el-icon>
    <span>{{ content }}</span>
  </div>
</template>

<style scoped>
.system-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  margin-bottom: 20px;
  background-color: #fdf6ec;
  color: #e6a23c;
  border-radius: 8px;
  font-size: 14px;
}
</style>
