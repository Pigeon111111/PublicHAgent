<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useFileStore } from '@/stores'
import FileUpload from '@/components/FileUpload.vue'
import { getFiles, deleteFile } from '@/services/api'

const fileStore = useFileStore()
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)

onMounted(() => {
  loadFiles()
})

async function loadFiles() {
  loading.value = true
  try {
    const response = await getFiles(currentPage.value, pageSize.value)
    fileStore.setFiles(response.files, response.total)
  } catch (error) {
    ElMessage.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(fileId: string) {
  try {
    await deleteFile(fileId)
    fileStore.removeFile(fileId)
    ElMessage.success('文件已删除')
  } catch {
    ElMessage.error('删除文件失败')
  }
}

function handleUploadSuccess(file: unknown) {
  fileStore.addFile(file as Parameters<typeof fileStore.addFile>[0])
  ElMessage.success('文件上传成功')
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadFiles()
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}
</script>

<template>
  <div class="files-view">
    <el-container>
      <el-header class="files-header">
        <h2>文件管理</h2>
      </el-header>
      <el-main class="files-main">
        <el-row :gutter="24">
          <el-col :span="8">
            <FileUpload @success="handleUploadSuccess" />
          </el-col>
          <el-col :span="16">
            <el-card class="file-list-card">
              <template #header>
                <div class="card-header">
                  <span>已上传文件</span>
                  <el-button type="primary" text @click="loadFiles">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </div>
              </template>
              <el-table :data="fileStore.files" v-loading="loading" stripe>
                <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
                <el-table-column label="大小" width="120">
                  <template #default="{ row }">
                    {{ formatFileSize(row.size) }}
                  </template>
                </el-table-column>
                <el-table-column prop="content_type" label="类型" width="180" show-overflow-tooltip />
                <el-table-column label="上传时间" width="180">
                  <template #default="{ row }">
                    {{ new Date(row.upload_time).toLocaleString() }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                  <template #default="{ row }">
                    <el-popconfirm
                      title="确定要删除此文件吗？"
                      @confirm="handleDelete(row.id)"
                    >
                      <template #reference>
                        <el-button type="danger" text>
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </template>
                    </el-popconfirm>
                  </template>
                </el-table-column>
              </el-table>
              <div class="pagination-container">
                <el-pagination
                  v-model:current-page="currentPage"
                  :page-size="pageSize"
                  :total="fileStore.totalFiles"
                  layout="total, prev, pager, next"
                  @current-change="handlePageChange"
                />
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<style scoped>
.files-view {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.files-header {
  display: flex;
  align-items: center;
  background-color: white;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
}

.files-header h2 {
  font-size: 20px;
  color: #303133;
}

.files-main {
  padding: 24px;
}

.file-list-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
