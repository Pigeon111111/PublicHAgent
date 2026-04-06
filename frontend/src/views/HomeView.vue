<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const menuItems = [
  { path: '/chat', icon: 'ChatDotRound', title: '智能对话', desc: '与 AI 助手进行数据分析对话' },
  { path: '/files', icon: 'Folder', title: '文件管理', desc: '上传和管理数据文件' },
  { path: '/history', icon: 'Clock', title: '历史记录', desc: '查看分析历史和结果' },
  { path: '/settings', icon: 'Setting', title: '系统设置', desc: '配置系统参数' },
]
</script>

<template>
  <div class="home-view">
    <div class="home-header">
      <h1>PubHAgent</h1>
      <p>公共卫生数据分析智能体系统</p>
    </div>
    <div class="home-menu">
      <el-card
        v-for="item in menuItems"
        :key="item.path"
        class="menu-card"
        shadow="hover"
        @click="router.push(item.path)"
      >
        <div class="menu-content">
          <el-icon :size="48" class="menu-icon">
            <component :is="item.icon" />
          </el-icon>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 40px;
}

.home-header {
  text-align: center;
  margin-bottom: 60px;
  color: white;
}

.home-header h1 {
  font-size: 48px;
  margin-bottom: 16px;
  font-weight: 600;
}

.home-header p {
  font-size: 20px;
  opacity: 0.9;
}

.home-menu {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
  max-width: 800px;
  width: 100%;
}

.menu-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.menu-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
}

.menu-content {
  text-align: center;
  padding: 20px;
}

.menu-icon {
  color: #667eea;
  margin-bottom: 16px;
}

.menu-content h3 {
  font-size: 20px;
  margin-bottom: 8px;
  color: #303133;
}

.menu-content p {
  font-size: 14px;
  color: #909399;
}

@media (max-width: 600px) {
  .home-menu {
    grid-template-columns: 1fr;
  }
}
</style>
