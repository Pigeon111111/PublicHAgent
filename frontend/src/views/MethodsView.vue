<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMethodFamilies, getMethodVariants, setPreferredVariant } from '@/services/api'
import type { MethodFamilySummary, MethodVariant } from '@/types'

const route = useRoute()
const router = useRouter()

const loadingFamilies = ref(false)
const loadingVariants = ref(false)
const families = ref<MethodFamilySummary[]>([])
const variants = ref<MethodVariant[]>([])
const selectedFamily = ref('')
const selectedVariantName = ref('')

const selectedVariant = computed(() =>
  variants.value.find((item) => item.name === selectedVariantName.value) || null,
)

onMounted(async () => {
  await loadFamilies()
})

watch(
  () => route.query.family,
  async (family) => {
    if (typeof family === 'string' && family && family !== selectedFamily.value) {
      selectedFamily.value = family
      await loadVariants(family)
    }
  },
)

watch(
  () => route.query.variant,
  (variant) => {
    if (typeof variant === 'string' && variant) {
      selectedVariantName.value = variant
    }
  },
)

async function loadFamilies() {
  loadingFamilies.value = true
  try {
    const response = await getMethodFamilies()
    families.value = response.families
    const initialFamily =
      (typeof route.query.family === 'string' && route.query.family) ||
      response.families[0]?.family ||
      ''
    if (initialFamily) {
      selectedFamily.value = initialFamily
      await loadVariants(initialFamily)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载方法家族失败')
  } finally {
    loadingFamilies.value = false
  }
}

async function loadVariants(family: string) {
  loadingVariants.value = true
  try {
    const response = await getMethodVariants(family)
    variants.value = response.variants
    const routeVariant = typeof route.query.variant === 'string' ? route.query.variant : ''
    selectedVariantName.value = routeVariant || response.preferred_variant || response.variants[0]?.name || ''
  } catch (error) {
    variants.value = []
    selectedVariantName.value = ''
    ElMessage.error(error instanceof Error ? error.message : '加载细分方法失败')
  } finally {
    loadingVariants.value = false
  }
}

async function handleSetPreferred(variant: string) {
  if (!selectedFamily.value) return
  try {
    await setPreferredVariant(selectedFamily.value, variant)
    ElMessage.success(variant ? '已设置偏好细分方法' : '已清除偏好细分方法')
    await loadFamilies()
    await loadVariants(selectedFamily.value)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '设置偏好失败')
  }
}

function openEvaluation(analysisId: string) {
  router.push(`/history?analysisId=${analysisId}`)
}

async function selectFamily(family: string) {
  await router.push({ path: '/methods', query: { family } })
}

async function selectVariant(variant: MethodVariant) {
  await router.push({
    path: '/methods',
    query: { family: selectedFamily.value, variant: variant.name },
  })
}
</script>

<template>
  <div class="methods-view">
    <header class="page-header">
      <div>
        <h2>方法库</h2>
        <p>按方法家族浏览细分变体，查看通过率、最近评估和用户偏好。</p>
      </div>
    </header>

    <div class="methods-layout">
      <aside class="family-panel">
        <el-card
          v-loading="loadingFamilies"
          shadow="never"
        >
          <template #header>
            <div class="panel-title">
              方法家族
            </div>
          </template>
          <div class="family-list">
            <button
              v-for="family in families"
              :key="family.family"
              type="button"
              class="family-item"
              :class="{ active: family.family === selectedFamily }"
              @click="selectFamily(family.family)"
            >
              <div class="family-top">
                <strong>{{ family.title || family.family }}</strong>
                <span>{{ family.variant_count }} 个变体</span>
              </div>
              <p>{{ family.description }}</p>
              <div class="family-meta">
                <span>成功率 {{ (family.success_rate * 100).toFixed(0) }}%</span>
                <span>使用 {{ family.recent_usage_count }}</span>
              </div>
            </button>
          </div>
        </el-card>
      </aside>

      <main class="variant-panel">
        <el-card
          v-loading="loadingVariants"
          shadow="never"
        >
          <template #header>
            <div class="panel-title">
              细分方法
            </div>
          </template>

          <el-empty
            v-if="!variants.length && !loadingVariants"
            description="当前方法家族下暂无可用变体"
          />

          <div
            v-else
            class="variant-list"
          >
            <button
              v-for="variant in variants"
              :key="variant.name"
              type="button"
              class="variant-item"
              :class="{ active: variant.name === selectedVariantName }"
              @click="selectVariant(variant)"
            >
              <div class="variant-top">
                <div>
                  <strong>{{ variant.method_variant || variant.name }}</strong>
                  <p>{{ variant.description }}</p>
                </div>
                <el-tag
                  size="small"
                  :type="variant.lifecycle_state === 'active' ? 'success' : variant.lifecycle_state === 'legacy' ? 'info' : 'warning'"
                >
                  {{ variant.lifecycle_state }}
                </el-tag>
              </div>
              <div class="variant-meta">
                <span>通过率 {{ (variant.verifier_pass_rate * 100).toFixed(0) }}%</span>
                <span>使用 {{ variant.usage_count }}</span>
                <span v-if="variant.is_preferred">当前偏好</span>
              </div>
            </button>
          </div>
        </el-card>
      </main>

      <aside class="detail-panel">
        <el-card shadow="never">
          <template #header>
            <div class="panel-title">
              变体详情
            </div>
          </template>

          <el-empty
            v-if="!selectedVariant"
            description="请选择一个细分方法"
          />

          <template v-else>
            <div class="detail-header">
              <div>
                <h3>{{ selectedVariant.method_variant || selectedVariant.name }}</h3>
                <p>{{ selectedVariant.description }}</p>
              </div>
              <el-tag
                :type="selectedVariant.lifecycle_state === 'active' ? 'success' : 'warning'"
              >
                {{ selectedVariant.lifecycle_state }}
              </el-tag>
            </div>

            <div class="detail-grid">
              <div>
                <span>方法家族</span>
                <strong>{{ selectedVariant.method_family }}</strong>
              </div>
              <div>
                <span>验证通过率</span>
                <strong>{{ (selectedVariant.verifier_pass_rate * 100).toFixed(0) }}%</strong>
              </div>
              <div>
                <span>使用次数</span>
                <strong>{{ selectedVariant.usage_count }}</strong>
              </div>
              <div>
                <span>置信度</span>
                <strong>{{ (selectedVariant.confidence_score * 100).toFixed(0) }}%</strong>
              </div>
            </div>

            <section class="detail-section">
              <h4>适用场景</h4>
              <ul>
                <li
                  v-for="item in selectedVariant.applicable_scenarios"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </section>

            <section class="detail-section">
              <h4>关键限制</h4>
              <ul>
                <li
                  v-for="item in selectedVariant.limitations"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </section>

            <section class="detail-section">
              <h4>最近评估</h4>
              <el-empty
                v-if="!selectedVariant.recent_evaluations.length"
                description="暂无最近评估"
                :image-size="60"
              />
              <div
                v-else
                class="evaluation-list"
              >
                <button
                  v-for="item in selectedVariant.recent_evaluations"
                  :key="item.id"
                  type="button"
                  class="evaluation-item"
                  @click="openEvaluation(item.analysis_record_id)"
                >
                  <strong>{{ item.task_family }}</strong>
                  <span>{{ (item.final_score * 100).toFixed(0) }} 分</span>
                  <span>{{ item.review_status }}</span>
                </button>
              </div>
            </section>

            <div class="detail-actions">
              <el-button
                type="primary"
                @click="handleSetPreferred(selectedVariant.name)"
              >
                设为优先
              </el-button>
              <el-button
                v-if="selectedVariant.is_preferred"
                @click="handleSetPreferred('')"
              >
                取消优先
              </el-button>
            </div>
          </template>
        </el-card>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.methods-view {
  min-height: calc(100vh - 60px);
  padding: 24px;
  background: linear-gradient(180deg, #f4f8f5 0%, #eef3f1 100%);
}

.page-header {
  max-width: 1400px;
  margin: 0 auto 18px;
}

.page-header h2 {
  margin: 0 0 8px;
  color: #153126;
  font-size: 28px;
}

.page-header p {
  margin: 0;
  color: #5f6c76;
}

.methods-layout {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 380px;
  gap: 16px;
}

.panel-title {
  font-weight: 700;
  color: #153126;
}

.family-list,
.variant-list,
.evaluation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.family-item,
.variant-item,
.evaluation-item {
  border: 1px solid #d9e5dd;
  border-radius: 14px;
  padding: 14px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.family-item.active,
.variant-item.active {
  border-color: #0f5c3c;
  transform: translateY(-1px);
}

.family-top,
.variant-top,
.variant-meta,
.family-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.family-item p,
.variant-item p {
  margin: 8px 0;
  color: #5f6c76;
  line-height: 1.5;
}

.family-meta,
.variant-meta {
  color: #677581;
  font-size: 12px;
  flex-wrap: wrap;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.detail-header h3 {
  margin: 0 0 8px;
}

.detail-header p {
  margin: 0;
  color: #5f6c76;
  line-height: 1.6;
}

.detail-grid {
  margin: 18px 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-grid div {
  padding: 12px;
  border-radius: 12px;
  background: #f5faf7;
}

.detail-grid span {
  display: block;
  color: #6a7884;
  font-size: 12px;
}

.detail-grid strong {
  display: block;
  margin-top: 6px;
  color: #173327;
}

.detail-section {
  margin-top: 18px;
}

.detail-section h4 {
  margin: 0 0 8px;
}

.detail-section ul {
  padding-left: 18px;
  color: #44545f;
  line-height: 1.6;
}

.evaluation-item {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.detail-actions {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 1200px) {
  .methods-layout {
    grid-template-columns: 1fr;
  }
}
</style>
