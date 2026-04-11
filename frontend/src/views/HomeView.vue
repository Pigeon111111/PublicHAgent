<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const menuItems = [
  { path: '/chat', icon: 'ChatDotRound', title: '智能对话', desc: '发起分析、恢复中断任务并查看实时评估卡片' },
  { path: '/files', icon: 'Folder', title: '文件管理', desc: '上传和管理输入数据文件，供工作流自动装载' },
  { path: '/history', icon: 'Clock', title: '历史记录', desc: '查看分析详情、审阅评估、触发重跑与新变体学习' },
  { path: '/methods', icon: 'Collection', title: '方法库', desc: '浏览方法家族与细分变体，设置偏好并追踪最近效果' },
  { path: '/settings', icon: 'Setting', title: '系统设置', desc: '配置模型、沙箱与基础运行参数' },
]
</script>

<template>
  <div class="home-view">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">
          PubHAgent
        </p>
        <h1>公共卫生数据分析智能体工作台</h1>
        <p class="subtitle">
          统一管理计划执行、结果评估、方法家族和可学习的细分分析路径。
        </p>
      </div>
    </section>

    <section class="menu-grid">
      <el-card
        v-for="item in menuItems"
        :key="item.path"
        class="menu-card"
        shadow="hover"
        @click="router.push(item.path)"
      >
        <div class="menu-content">
          <el-icon
            :size="42"
            class="menu-icon"
          >
            <component :is="item.icon" />
          </el-icon>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
        </div>
      </el-card>
    </section>
  </div>
</template>

<style scoped>
.home-view {
  min-height: calc(100vh - 60px);
  padding: 40px;
  background:
    radial-gradient(circle at top left, rgba(15, 92, 60, 0.18), transparent 34%),
    radial-gradient(circle at bottom right, rgba(196, 230, 211, 0.55), transparent 28%),
    linear-gradient(180deg, #f6fbf7 0%, #edf4f0 100%);
}

.hero {
  max-width: 1100px;
  margin: 0 auto 28px;
  padding: 32px 36px;
  border: 1px solid rgba(15, 92, 60, 0.12);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
}

.eyebrow {
  margin: 0 0 10px;
  color: #0f5c3c;
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero h1 {
  margin: 0 0 12px;
  color: #163126;
  font-size: clamp(32px, 6vw, 52px);
  line-height: 1.08;
}

.subtitle {
  max-width: 720px;
  margin: 0;
  color: #44545f;
  font-size: 16px;
  line-height: 1.7;
}

.menu-grid {
  max-width: 1100px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 18px;
}

.menu-card {
  cursor: pointer;
  border-radius: 22px;
  border: 1px solid rgba(15, 92, 60, 0.1);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.menu-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 40px rgba(16, 24, 40, 0.1);
}

.menu-content {
  min-height: 190px;
  padding: 8px 4px;
}

.menu-icon {
  color: #0f5c3c;
  margin-bottom: 18px;
}

.menu-content h3 {
  margin: 0 0 10px;
  color: #102a22;
  font-size: 20px;
}

.menu-content p {
  margin: 0;
  color: #5f6c76;
  font-size: 14px;
  line-height: 1.7;
}
</style>
