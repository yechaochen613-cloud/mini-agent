<script setup>
import { ref, computed, onMounted } from 'vue'
import { NIcon, NEmpty, NPopconfirm, useMessage } from 'naive-ui'
import {
  FolderOutline,
  LinkOutline,
  CloudUploadOutline,
  TrashOutline,
  DocumentOutline,
  SearchOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'

const message = useMessage()

const docs = ref([])
const loading = ref(false)
const urlText = ref('')
const importingUrl = ref(false)
const fileInputRef = ref(null)
const searchText = ref('')
const isDragging = ref(false)
let dragCounter = 0

const TYPE_LABEL = {
  pdf: 'PDF', docx: 'Word', xlsx: 'Excel', pptx: 'PPT',
  csv: 'CSV', html: '网页', md: 'Markdown', txt: '文本',
  json: 'JSON', image: '图片'
}

const filteredDocs = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return docs.value
  return docs.value.filter((d) => (d.name || '').toLowerCase().includes(q))
})

async function loadDocs() {
  loading.value = true
  try {
    const data = await api.documents()
    docs.value = data.documents || []
  } catch (e) {
    docs.value = []
  } finally {
    loading.value = false
  }
}

function fmtSize(n) {
  if (!n && n !== 0) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function handleFiles(files) {
  if (!files || !files.length) return
  try {
    const res = await api.upload(Array.from(files))
    const n = res.uploaded || 0
    message.success(`已上传 ${n} 篇文档，已加入知识库`)
    await loadDocs()
  } catch (err) {
    message.error('文档上传失败')
  }
}

async function onImportUrl() {
  const url = urlText.value.trim()
  if (!url) {
    message.warning('请先粘贴网页链接')
    return
  }
  importingUrl.value = true
  try {
    const res = await api.upload(null, url)
    const n = res.uploaded || 0
    message.success(`已导入 ${n} 篇网页文档，已加入知识库`)
    urlText.value = ''
    await loadDocs()
  } catch (e) {
    message.error('网页导入失败，请检查链接是否有效')
  } finally {
    importingUrl.value = false
  }
}

function triggerFile() {
  fileInputRef.value?.click()
}

async function onPickFiles(e) {
  const files = e.target.files
  await handleFiles(files)
  e.target.value = ''
}

function onDragEnter(e) {
  e.preventDefault()
  dragCounter++
  isDragging.value = true
}

function onDragLeave(e) {
  e.preventDefault()
  dragCounter--
  if (dragCounter <= 0) {
    dragCounter = 0
    isDragging.value = false
  }
}

function onDrop(e) {
  e.preventDefault()
  dragCounter = 0
  isDragging.value = false
  const files = e.dataTransfer?.files
  handleFiles(files)
}

async function onDelete(id) {
  try {
    await api.deleteDocument(id)
    message.success('已删除文档')
    await loadDocs()
  } catch (e) {
    message.error('删除失败')
  }
}

onMounted(loadDocs)
</script>

<template>
  <div class="kb-wrap">
    <header class="kb-head">
      <div class="kb-title">
        <n-icon size="22" class="kb-title-icon"><FolderOutline /></n-icon>
        <div>
          <h2>知识库</h2>
          <p>上传文档或导入网页，对话时自动检索引用</p>
        </div>
      </div>
    </header>

    <!-- 导入区（支持拖拽） -->
    <section
      class="kb-import kb-glass"
      :class="{ 'drag-over': isDragging }"
      @dragenter="onDragEnter"
      @dragleave="onDragLeave"
      @dragover.prevent
      @drop="onDrop"
    >
      <div class="import-row">
        <n-icon size="18" class="import-ico"><LinkOutline /></n-icon>
        <input
          v-model="urlText"
          class="url-input"
          type="url"
          placeholder="粘贴网页链接，按回车或点「导入」抓取进知识库"
          @keydown.enter="onImportUrl"
        />
        <button class="import-btn" :disabled="importingUrl" @click="onImportUrl">
          {{ importingUrl ? '导入中…' : '导入' }}
        </button>
      </div>
      <div class="import-row alt">
        <span class="import-hint">或把文件拖到这里 / 点击选择：PDF · Word · Excel · PPT · CSV · Markdown · 图片 等</span>
        <button class="upload-btn" @click="triggerFile">
          <n-icon size="16"><CloudUploadOutline /></n-icon>
          <span>选择文件</span>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          multiple
          class="hidden-file"
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.tsv,.html,.md,.txt,.json,.png,.jpg,.jpeg,.gif,.webp"
          @change="onPickFiles"
        />
      </div>
      <div v-if="isDragging" class="drop-hint">松手即可上传到知识库</div>
    </section>

    <!-- 工具栏：搜索 + 计数 -->
    <div class="kb-toolbar">
      <div class="search-box">
        <n-icon size="16" class="search-ico"><SearchOutline /></n-icon>
        <input
          v-model="searchText"
          class="search-input"
          type="text"
          placeholder="按文档名搜索…"
        />
      </div>
      <span class="kb-count">{{ filteredDocs.length }} 篇</span>
    </div>

    <!-- 列表 -->
    <section class="kb-list">
      <n-empty
        v-if="!loading && filteredDocs.length === 0"
        :description="searchText ? '没有匹配的文档' : '知识库还是空的，先上传或导入一些资料吧'"
        class="kb-empty"
      />
      <div v-else class="doc-grid">
        <div v-for="d in filteredDocs" :key="d.id" class="doc-row kb-glass">
          <div class="doc-icon"><n-icon size="20"><DocumentOutline /></n-icon></div>
          <div class="doc-main">
            <div class="doc-name" :title="d.name">{{ d.name }}</div>
            <div class="doc-meta">
              <span class="tag">{{ TYPE_LABEL[d.type] || d.type }}</span>
              <span>{{ d.chunks }} 块</span>
              <span>{{ d.chars }} 字</span>
              <span v-if="d.size">· {{ fmtSize(d.size) }}</span>
              <span v-if="d.refs" class="refs">· 被引用 {{ d.refs }} 次</span>
            </div>
          </div>
          <n-popconfirm
            :show-icon="false"
            positive-text="删除"
            negative-text="取消"
            @positive-click="onDelete(d.id)"
          >
            <template #trigger>
              <button class="doc-del" title="删除文档">
                <n-icon size="17"><TrashOutline /></n-icon>
              </button>
            </template>
            确定删除《{{ d.name }}》？此操作不可恢复。
          </n-popconfirm>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.kb-wrap {
  max-width: 880px;
  margin: 0 auto;
  padding: 28px 22px 60px;
}
.kb-head {
  margin-bottom: 18px;
}
.kb-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.kb-title-icon {
  color: var(--accent);
  background: var(--accent-soft);
  padding: 10px;
  border-radius: 14px;
}
.kb-title h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.kb-title p {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.kb-glass {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.05);
}

.kb-import {
  position: relative;
  padding: 16px 18px;
  margin-bottom: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}
.kb-import.drag-over {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  background: var(--accent-soft);
}
.drop-hint {
  position: absolute;
  inset: auto 0 8px 0;
  text-align: center;
  font-size: 12.5px;
  color: var(--accent);
  font-weight: 600;
  pointer-events: none;
}
.import-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.import-row.alt {
  justify-content: space-between;
}
.import-ico {
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.url-input {
  flex: 1;
  min-width: 0;
  height: 40px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.url-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.import-btn {
  flex-shrink: 0;
  height: 40px;
  padding: 0 20px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--accent);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
}
.import-btn:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
}
.import-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.import-hint {
  font-size: 13px;
  color: var(--text-secondary);
}
.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.upload-btn:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.hidden-file {
  display: none;
}

.kb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 12px;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  max-width: 320px;
  height: 38px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-input);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.search-box:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.search-ico {
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 14px;
  outline: none;
}
.kb-count {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}

.kb-empty {
  padding: 70px 0;
}
.doc-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 14px;
}
.doc-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.18s;
}
.doc-row:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.09);
}
.doc-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--accent-soft);
  color: var(--accent);
}
.doc-main {
  flex: 1;
  min-width: 0;
}
.doc-name {
  font-size: 14.5px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.doc-meta {
  margin-top: 4px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}
.doc-meta .tag {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  font-weight: 600;
}
.doc-meta .refs {
  color: var(--accent);
  font-weight: 600;
}
.doc-del {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: background 0.18s, color 0.18s;
}
.doc-del:hover {
  background: rgba(255, 59, 48, 0.12);
  color: #ff3b30;
}

@media (max-width: 640px) {
  .doc-grid {
    grid-template-columns: 1fr;
  }
  .import-row.alt {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .upload-btn {
    justify-content: center;
  }
  .search-box {
    max-width: none;
  }
}
</style>
