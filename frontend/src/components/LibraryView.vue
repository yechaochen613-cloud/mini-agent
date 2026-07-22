<script setup>
import { ref, onMounted } from 'vue'
import {
  useMessage,
  NIcon,
  NCard,
  NTabs,
  NTabPane,
  NButton,
  NModal,
  NInput,
  NForm,
  NFormItem,
  NSkeleton,
  NEmpty,
  NTag
} from 'naive-ui'
import {
  LibraryOutline,
  BookmarksOutline,
  AddOutline,
  TrashOutline,
  CheckmarkDoneOutline,
  ReaderOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'

const message = useMessage()

const loading = ref(true)
const wrong = ref([])
const favorites = ref([])

// 错题弹窗
const showWQ = ref(false)
const wqForm = ref({ subject: '', question: '', my_answer: '', correct_answer: '', explanation: '' })
const savingWQ = ref(false)

// 收藏弹窗
const showFav = ref(false)
const favForm = ref({ title: '', content: '' })
const savingFav = ref(false)

async function load() {
  loading.value = true
  try {
    const [w, f] = await Promise.all([api.wrongQuestions(), api.favorites()])
    wrong.value = w.wrong_questions || []
    favorites.value = f.favorites || []
  } catch (e) {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

function openWQ() {
  wqForm.value = { subject: '', question: '', my_answer: '', correct_answer: '', explanation: '' }
  showWQ.value = true
}
async function saveWQ() {
  if (!wqForm.value.question.trim()) {
    message.warning('请填写题目')
    return
  }
  savingWQ.value = true
  try {
    await api.addWrongQuestion(wqForm.value)
    message.success('已加入错题本')
    showWQ.value = false
    load()
  } catch (e) {
    message.error('添加失败')
  } finally {
    savingWQ.value = false
  }
}

function openFav() {
  favForm.value = { title: '', content: '' }
  showFav.value = true
}
async function saveFav() {
  if (!favForm.value.content.trim()) {
    message.warning('请填写内容')
    return
  }
  savingFav.value = true
  try {
    await api.addFavorite(favForm.value)
    message.success('已收藏')
    showFav.value = false
    load()
  } catch (e) {
    message.error('添加失败')
  } finally {
    savingFav.value = false
  }
}

async function delWQ(id) {
  try {
    await api.deleteWrongQuestion(id)
    wrong.value = wrong.value.filter((x) => x.id !== id)
  } catch (e) {
    message.error('删除失败')
  }
}
async function reviewWQ(id, mastery) {
  try {
    await api.reviewWrongQuestion(id, Math.min(mastery + 1, 5))
    load()
  } catch (e) {
    message.error('操作失败')
  }
}
async function delFav(id) {
  try {
    await api.deleteFavorite(id)
    favorites.value = favorites.value.filter((x) => x.id !== id)
  } catch (e) {
    message.error('删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <header class="panel-head">
      <div class="ph-icon"><n-icon size="22" color="var(--accent)"><LibraryOutline /></n-icon></div>
      <div>
        <h1 class="ph-title">学习库</h1>
        <p class="ph-sub">错题本与收藏，沉淀你的学习资产</p>
      </div>
    </header>

    <n-tabs type="line" animated>
      <!-- 错题本 -->
      <n-tab-pane name="wq">
        <template #tab>
          <span class="tab-label"><n-icon size="16"><ReaderOutline /></n-icon> 错题本</span>
        </template>
        <div class="tab-head">
          <span class="count">{{ wrong.length }} 条</span>
          <n-button type="primary" size="small" @click="openWQ">
            <template #icon><n-icon :component="AddOutline" /></template>
            添加错题
          </n-button>
        </div>

        <div v-if="loading" class="sk-list">
          <n-skeleton v-for="n in 3" :key="n" height="90px" style="border-radius: 16px; margin-bottom: 12px" />
        </div>
        <n-empty v-else-if="!wrong.length" description="还没有错题，添加一道试试" />
        <div v-else class="cards">
          <div v-for="q in wrong" :key="q.id" class="lib-card">
            <div class="lc-top">
              <n-tag size="small" :bordered="false" type="info">{{ q.subject || '其他' }}</n-tag>
              <span class="mastery">掌握度 {{ q.mastery || 0 }}/5</span>
            </div>
            <div class="lc-q">{{ q.question }}</div>
            <div class="lc-actions">
              <n-button size="tiny" quaternary type="success" @click="reviewWQ(q.id, q.mastery || 0)">
                <template #icon><n-icon :component="CheckmarkDoneOutline" /></template>
                复习
              </n-button>
              <n-button size="tiny" quaternary type="error" @click="delWQ(q.id)">
                <template #icon><n-icon :component="TrashOutline" /></template>
                删除
              </n-button>
            </div>
          </div>
        </div>
      </n-tab-pane>

      <!-- 收藏 -->
      <n-tab-pane name="fav">
        <template #tab>
          <span class="tab-label"><n-icon size="16"><BookmarksOutline /></n-icon> 收藏</span>
        </template>
        <div class="tab-head">
          <span class="count">{{ favorites.length }} 条</span>
          <n-button type="primary" size="small" @click="openFav">
            <template #icon><n-icon :component="AddOutline" /></template>
            添加收藏
          </n-button>
        </div>

        <div v-if="loading" class="sk-list">
          <n-skeleton v-for="n in 3" :key="n" height="90px" style="border-radius: 16px; margin-bottom: 12px" />
        </div>
        <n-empty v-else-if="!favorites.length" description="还没有收藏" />
        <div v-else class="cards">
          <div v-for="f in favorites" :key="f.id" class="lib-card">
            <div class="lc-q">{{ f.title || '收藏' }}</div>
            <div class="lc-content">{{ f.content }}</div>
            <div class="lc-actions">
              <n-button size="tiny" quaternary type="error" @click="delFav(f.id)">
                <template #icon><n-icon :component="TrashOutline" /></template>
                删除
              </n-button>
            </div>
          </div>
        </div>
      </n-tab-pane>
    </n-tabs>

    <!-- 错题弹窗 -->
    <n-modal v-model:show="showWQ" preset="card" title="添加错题" style="max-width: 520px">
      <n-form>
        <n-form-item label="学科">
          <n-input v-model:value="wqForm.subject" placeholder="如：数学" />
        </n-form-item>
        <n-form-item label="题目">
          <n-input v-model:value="wqForm.question" type="textarea" :autosize="{ minRows: 2 }" />
        </n-form-item>
        <n-form-item label="我的答案">
          <n-input v-model:value="wqForm.my_answer" type="textarea" :autosize="{ minRows: 2 }" />
        </n-form-item>
        <n-form-item label="正确答案">
          <n-input v-model:value="wqForm.correct_answer" type="textarea" :autosize="{ minRows: 2 }" />
        </n-form-item>
        <n-form-item label="解析">
          <n-input v-model:value="wqForm.explanation" type="textarea" :autosize="{ minRows: 2 }" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-foot">
          <n-button @click="showWQ = false">取消</n-button>
          <n-button type="primary" :loading="savingWQ" @click="saveWQ">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 收藏弹窗 -->
    <n-modal v-model:show="showFav" preset="card" title="添加收藏" style="max-width: 520px">
      <n-form>
        <n-form-item label="标题">
          <n-input v-model:value="favForm.title" placeholder="如：重要公式" />
        </n-form-item>
        <n-form-item label="内容">
          <n-input v-model:value="favForm.content" type="textarea" :autosize="{ minRows: 3 }" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-foot">
          <n-button @click="showFav = false">取消</n-button>
          <n-button type="primary" :loading="savingFav" @click="saveFav">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.panel {
  height: 100%;
  overflow-y: auto;
  padding: 32px 36px 48px;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}
.ph-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ph-title {
  margin: 0;
  font-size: 23px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.ph-sub {
  margin: 3px 0 0;
  font-size: 14px;
  color: var(--text-tertiary);
}
.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tab-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 6px 0 16px;
}
.count {
  font-size: 13px;
  color: var(--text-tertiary);
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lib-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow: var(--shadow-sm);
}
.lc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.mastery {
  font-size: 12px;
  color: var(--text-tertiary);
}
.lc-q {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.5;
}
.lc-content {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-top: 6px;
  max-height: 120px;
  overflow: auto;
  white-space: pre-wrap;
}
.lc-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  justify-content: flex-end;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 860px) {
  .panel {
    padding: 64px 16px 40px;
  }
}
</style>
