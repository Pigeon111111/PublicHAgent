<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadFile } from '@/services/api'
import type { FileInfo } from '@/types'

const emit = defineEmits<{
  success: [file: FileInfo]
}>()

const fileList = ref<File[]>([])
const uploading = ref(false)
const dragOver = ref(false)

const allowedExtensions = ['csv', 'xlsx', 'xls', 'json', 'txt', 'parquet', 'feather', 'pdf', 'docx', 'doc']
const maxSize = 50 * 1024 * 1024

function validateFile(file: File): boolean {
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !allowedExtensions.includes(ext)) {
    ElMessage.error(`不支持的文件类型: ${ext}`)
    return false
  }
  if (file.size > maxSize) {
    ElMessage.error('文件大小超过 50MB 限制')
    return false
  }
  return true
}

function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  const validFiles = files.filter(validateFile)
  if (validFiles.length > 0) {
    fileList.value = validFiles
  }
}

function handleDragOver() {
  dragOver.value = true
}

function handleDragLeave() {
  dragOver.value = false
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  const files = Array.from(target.files || [])
  const validFiles = files.filter(validateFile)
  fileList.value = validFiles
}

async function handleUpload() {
  if (fileList.value.length === 0) return
  
  uploading.value = true
  try {
    for (const file of fileList.value) {
      const result = await uploadFile(file)
      emit('success', result)
    }
    fileList.value = []
    ElMessage.success('文件上传成功')
  } catch {
    ElMessage.error('文件上传失败')
  } finally {
    uploading.value = false
  }
}

function removeFile(index: number) {
  fileList.value.splice(index, 1)
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function getFileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase()
  const iconMap: Record<string, string> = {
    csv: 'Document',
    xlsx: 'Document',
    xls: 'Document',
    json: 'Document',
    txt: 'Document',
    pdf: 'Document',
    docx: 'Document',
    doc: 'Document',
  }
  return iconMap[ext || ''] || 'Document'
}
</script>

<template>
  <el-card class="upload-card">
    <template #header>
      <span>文件上传</span>
    </template>
    <div
      class="upload-area"
      :class="{ 'drag-over': dragOver }"
      @drop.prevent="handleDrop"
      @dragover.prevent="handleDragOver"
      @dragleave="handleDragLeave"
    >
      <el-icon
        :size="48"
        class="upload-icon"
      >
        <Upload />
      </el-icon>
      <p>拖拽文件到此处上传</p>
      <p class="upload-hint">
        支持 CSV, XLSX, JSON, PDF, Word 等格式，最大 50MB
      </p>
      <input
        type="file"
        multiple
        class="file-input"
        accept=".csv,.xlsx,.xls,.json,.txt,.parquet,.feather,.pdf,.docx,.doc"
        @change="handleFileChange"
      >
    </div>

    <div
      v-if="fileList.length > 0"
      class="file-preview"
    >
      <div
        v-for="(file, index) in fileList"
        :key="index"
        class="preview-item"
      >
        <el-icon class="file-icon">
          <component :is="getFileIcon(file.name)" />
        </el-icon>
        <div class="file-info">
          <span class="file-name">{{ file.name }}</span>
          <span class="file-size">{{ formatFileSize(file.size) }}</span>
        </div>
        <el-button
          type="danger"
          text
          @click="removeFile(index)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <el-button
      type="primary"
      :disabled="fileList.length === 0"
      :loading="uploading"
      class="upload-btn"
      @click="handleUpload"
    >
      <el-icon><Upload /></el-icon>
      上传文件
    </el-button>
  </el-card>
</template>

<style scoped>
.upload-card {
  height: 100%;
}

.upload-area {
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  position: relative;
}

.upload-area:hover,
.upload-area.drag-over {
  border-color: #409eff;
  background-color: #f5f7fa;
}

.upload-icon {
  color: #c0c4cc;
  margin-bottom: 16px;
}

.upload-area p {
  color: #606266;
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 12px;
  color: #909399;
}

.file-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.file-preview {
  margin-top: 16px;
  max-height: 200px;
  overflow-y: auto;
}

.preview-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 8px;
}

.file-icon {
  color: #409eff;
  font-size: 20px;
}

.file-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #909399;
}

.upload-btn {
  width: 100%;
  margin-top: 16px;
}
</style>
