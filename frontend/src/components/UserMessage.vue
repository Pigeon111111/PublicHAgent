<script setup lang="ts">
defineProps<{
  content: string
}>()
</script>

<template>
  <div class="user-message">
    <div class="message-avatar">
      <el-icon :size="24"><User /></el-icon>
    </div>
    <div class="message-content">
      <div class="message-bubble">
        {{ content }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.user-message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  justify-content: flex-end;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: 12px 16px;
  background-color: #409eff;
  color: white;
  border-radius: 8px;
  word-wrap: break-word;
  white-space: pre-wrap;
}
</style>
