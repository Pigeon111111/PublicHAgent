<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMenu, ElMenuItem, ElIcon, ElBreadcrumb, ElBreadcrumbItem } from 'element-plus'
import { ChatDotRound, Document, Clock, Setting, HomeFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const activeIndex = computed(() => {
  return route.path
})

const breadcrumbItems = computed(() => {
  const items: { name: string; path: string }[] = []

  if (route.path === '/') {
    items.push({ name: '首页', path: '/' })
  } else {
    items.push({ name: '首页', path: '/' })

    const routeNameMap: Record<string, string> = {
      '/chat': '智能对话',
      '/files': '文件管理',
      '/history': '历史记录',
      '/settings': '系统设置',
    }

    const name = routeNameMap[route.path]
    if (name) {
      items.push({ name, path: route.path })
    }
  }

  return items
})

function handleSelect(index: string) {
  router.push(index)
}

function goBack() {
  router.back()
}

function canGoBack() {
  return route.path !== '/'
}
</script>

<template>
  <div class="nav-container">
    <div class="nav-header">
      <div class="nav-brand">
        <h1 class="nav-title">
          PubHAgent
        </h1>
        <span class="nav-subtitle">公共卫生数据分析智能体</span>
      </div>

      <el-menu
        :default-active="activeIndex"
        mode="horizontal"
        class="nav-menu"
        @select="handleSelect"
      >
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能对话</span>
        </el-menu-item>
        <el-menu-item index="/files">
          <el-icon><Document /></el-icon>
          <span>文件管理</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <span>历史记录</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </div>

    <div
      v-if="route.path !== '/'"
      class="nav-breadcrumb"
    >
      <el-button
        v-if="canGoBack()"
        type="text"
        size="small"
        class="back-button"
        @click="goBack"
      >
        ← 返回
      </el-button>
      <el-breadcrumb separator="/">
        <el-breadcrumb-item
          v-for="item in breadcrumbItems"
          :key="item.path"
          :to="item.path"
        >
          {{ item.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>
  </div>
</template>

<style scoped>
.nav-container {
  background-color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
  border-bottom: 1px solid #f0f0f0;
}

.nav-brand {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.nav-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.nav-subtitle {
  font-size: 12px;
  color: #909399;
}

.nav-menu {
  border-bottom: none;
  background: transparent;
}

.nav-menu .el-menu-item {
  height: 60px;
  line-height: 60px;
}

.nav-breadcrumb {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  background-color: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.back-button {
  padding: 0;
  font-size: 13px;
  color: #606266;
}

.back-button:hover {
  color: #409eff;
}
</style>
