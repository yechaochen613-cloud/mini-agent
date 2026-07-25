<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  useMessage,
  NIcon,
  NButton,
  NSkeleton,
  NEmpty,
  NTag
} from 'naive-ui'
import { RefreshOutline, ReaderOutline, LibraryOutline, CheckmarkDoneOutline } from '@vicons/ionicons5'
import { api } from '../api.js'
import { switchView } from '../store.js'

const message = useMessage()

const loading = ref(true)
const mode = ref('due') // 'due' = 今日待复习；'all' = 全部错题
const list = ref([])
const total = ref(0)
const idx = ref(0)
const revealed = ref(false)
const done = ref(false)
const submitting = ref(false)
const finished = ref(false)
const lastResult = ref(null) // { mastery, nextDate, nextDays, label }

const cur = computed(() => list.value[idx.value] || null)
const doneCount = computed(() => Math.max(0, total.value - list.value.length))
const progress = computed(() => (total.value ? Math.round((doneCount.value / total.value) * 100) : 0))
const currentNo = computed(() => doneCount.value + 1)

// 回忆质量档位（对应 SM-2 的 recall quality）
const QUALITY = [
  { key: 0, label: '完全忘了', desc: '没想起来', cls: 'q-forgot' },
  { key: 1, label: '有点模糊', desc: '有印象但不确定', cls: 'q-fuzzy' },
  { key: 3, label: '记得了', desc: '基本能回忆', cls: 'q-ok' },
  { key: 5, label: '很熟练', desc: '脱口而出', cls: 'q-master' }
]

async function load() {
  loading.value = true
  finished.value = false
  idx.value = 0
  revealed.value = false
  done.value = false
  lastResult.value = null
  try {
    if (mode.value === 'due') {
      const r = await api.dueWrongQuestions()
      list.value = r.due || []
    } else {
      const r = await api.wrongQuestions()
      list.value = r.wrong_questions || []
    }
    total.value = list.value.length
  } catch (e) {
    message.error('加载失败')
  } finally {
    loading.value = false
  }
}

function setMode(m) {
  if (m === mode.value) return
  mode.value = m
  load()
}

function reveal() {
  revealed.value = true
}

// 回忆质量 → 新掌握度（0~5）
// 完全忘了：重置为 0（间隔重置为 1 天）
// 有点模糊：压到 <=1（间隔 2 天）
// 记得了：+1（间隔按表递增）
// 很熟练：+2（跳级，间隔更长）
function nextMastery(qLevel) {
  const m = cur.value?.mastery || 0
  if (qLevel === 0) return 0
  if (qLevel === 1) return Math.max(0, Math.min(m, 1))
  if (qLevel === 3) return Math.min(m + 1, 5)
  if (qLevel === 5) return Math.min(m + 2, 5)
  return m
}

function fmtNext(ts) {
  if (!ts) return { date: '', days: 0 }
  const d = new Date(ts * 1000)
  const now = new Date()
  const days = Math.max(0, Math.round((d - now) / 86400000))
  const mo = d.getMonth() + 1
  const day = d.getDate()
  return { date: `${mo}月${day}日`, days }
}

async function submit(qLevel) {
  if (!cur.value || submitting.value || done.value) return
  submitting.value = true
  const newM = nextMastery(qLevel)
  try {
    const res = await api.reviewWrongQuestion(cur.value.id, newM)
    const info = fmtNext(res.next_review_at)
    lastResult.value = {
      mastery: newM,
      nextDate: info.date,
      nextDays: info.days,
      label: QUALITY.find((q) => q.key === qLevel)?.label || ''
    }
    done.value = true
  } catch (e) {
    message.error('提交失败')
  } finally {
    submitting.value = false
  }
}

function nextCard() {
  if (!list.value.length) {
    finished.value = true
    return
  }
  list.value.splice(idx.value, 1)
  done.value = false
  lastResult.value = null
  revealed.value = false
  if (idx.value >= list.value.length) finished.value = true
}

function goLibrary() {
  switchView('library')
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <header class="panel-head">
      <div class="ph-icon"><n-icon size="22" color="var(--accent)"><RefreshOutline /></n-icon></div>
      <div>
        <h1 class="ph-title">间隔复习</h1>
        <p class="ph-sub">基于艾宾浩斯记忆曲线，记住则拉长间隔、忘了则重置</p>
      </div>
    </header>

    <!-- 模式切换 -->
    <div class="mode-switch">
      <button class="mode-btn" :class="{ active: mode === 'due' }" @click="setMode('due')">
        <n-icon size="15"><ReaderOutline /></n-icon> 今日待复习
      </button>
      <button class="mode-btn" :class="{ active: mode === 'all' }" @click="setMode('all')">
        <n-icon size="15"><LibraryOutline /></n-icon> 全部错题
      </button>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="sk-list">
      <n-skeleton v-for="n in 2" :key="n" height="180px" style="border-radius: 20px; margin-bottom: 16px" />
    </div>

    <!-- 空状态 -->
    <div v-else-if="!list.length && !finished" class="empty-wrap">
      <n-empty v-if="mode === 'due'" description="今天没有待复习的题，状态很棒">
        <template #extra>
          <div class="empty-actions">
            <n-button tertiary @click="setMode('all')">浏览全部错题</n-button>
            <n-button type="primary" @click="goLibrary">去学习库</n-button>
          </div>
        </template>
      </n-empty>
      <n-empty v-else description="错题本还是空的">
        <template #extra>
          <n-button type="primary" @click="goLibrary">去添加错题</n-button>
        </template>
      </n-empty>
    </div>

    <!-- 完成页 -->
    <div v-else-if="finished" class="done-wrap">
      <div class="done-emoji">🎉</div>
      <h2 class="done-title">今日复习完成</h2>
      <p class="done-sub">本轮共复习 {{ total }} 道，保持节奏，记忆更牢固</p>
      <div class="done-actions">
        <n-button v-if="mode === 'due'" tertiary @click="setMode('all')">再刷一遍全部错题</n-button>
        <n-button type="primary" @click="goLibrary">返回学习库</n-button>
      </div>
    </div>

    <!-- 复习卡 -->
    <div v-else-if="cur" class="rev-wrap">
      <div class="rev-progress">
        <div class="rp-bar"><div class="rp-fill" :style="{ width: progress + '%' }"></div></div>
        <span class="rp-text">第 {{ currentNo }} / {{ total }} 题 · 已完成 {{ doneCount }}</span>
      </div>

      <div class="rev-card">
        <div class="rc-top">
          <n-tag size="small" :bordered="false" type="info">{{ cur.subject || '其他' }}</n-tag>
          <span class="rc-mastery">掌握度 {{ cur.mastery || 0 }}/5</span>
        </div>

        <div class="rc-q">{{ cur.question }}</div>

        <!-- 答案区：未揭示 -->
        <div v-if="!revealed" class="rc-hidden">
          <p class="rc-tip">先在脑中回忆答案，再点下方按钮核对 👇</p>
          <n-button type="primary" size="large" @click="reveal">
            <template #icon><n-icon :component="CheckmarkDoneOutline" /></template>
            显示答案
          </n-button>
        </div>

        <!-- 答案区：已揭示 -->
        <div v-else class="rc-answer">
          <div v-if="cur.my_answer" class="rc-row">
            <span class="rc-label mine">我的答案</span>
            <span class="rc-val">{{ cur.my_answer }}</span>
          </div>
          <div v-if="cur.correct_answer" class="rc-row">
            <span class="rc-label correct">正确答案</span>
            <span class="rc-val">{{ cur.correct_answer }}</span>
          </div>
          <div v-if="cur.explanation" class="rc-row">
            <span class="rc-label exp">解析</span>
            <span class="rc-val">{{ cur.explanation }}</span>
          </div>

          <!-- 回忆质量选择 -->
          <div v-if="!done" class="rc-quality">
            <p class="rq-title">你回忆得怎么样？</p>
            <div class="rq-grid">
              <button
                v-for="q in QUALITY"
                :key="q.key"
                class="rq-btn"
                :class="q.cls"
                :disabled="submitting"
                @click="submit(q.key)"
              >
                <span class="rq-label">{{ q.label }}</span>
                <span class="rq-desc">{{ q.desc }}</span>
              </button>
            </div>
          </div>

          <!-- 提交反馈 -->
          <div v-else class="rc-feedback">
            <div class="fb-row">
              <span class="fb-badge" :class="lastResult.mastery >= 3 ? 'good' : 'weak'">
                掌握度 {{ lastResult.mastery }}/5
              </span>
              <span class="fb-text">
                已记录「{{ lastResult.label }}」· 下次复习：<b>{{ lastResult.nextDate }}</b>
                （{{ lastResult.nextDays }} 天后）
              </span>
            </div>
            <n-button type="primary" block size="large" @click="nextCard">
              下一道 →
            </n-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  height: 100%;
  overflow-y: auto;
  padding: 32px 36px 48px;
  max-width: 760px;
  margin: 0 auto;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
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
.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
}
.mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 16px;
  border-radius: 11px;
  border: 1px solid var(--border);
  background: var(--bg-elevated);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s;
}
.mode-btn:hover {
  border-color: var(--accent);
  color: var(--text);
}
.mode-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.sk-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.empty-wrap,
.done-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  text-align: center;
}
.empty-actions,
.done-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 8px;
}
.done-emoji {
  font-size: 56px;
  margin-bottom: 8px;
}
.done-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
}
.done-sub {
  margin: 8px 0 18px;
  color: var(--text-tertiary);
  font-size: 14.5px;
}
.rev-progress {
  margin-bottom: 16px;
}
.rp-bar {
  height: 8px;
  border-radius: 99px;
  background: var(--bg-elevated);
  overflow: hidden;
}
.rp-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #42a5f5);
  border-radius: 99px;
  transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.rp-text {
  display: block;
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--text-tertiary);
}
.rev-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 22px 24px;
  box-shadow: var(--shadow-sm);
}
.rc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.rc-mastery {
  font-size: 12.5px;
  color: var(--text-tertiary);
}
.rc-q {
  font-size: 17px;
  font-weight: 700;
  line-height: 1.6;
  color: var(--text);
  white-space: pre-wrap;
}
.rc-hidden {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}
.rc-tip {
  margin: 0;
  font-size: 14px;
  color: var(--text-tertiary);
}
.rc-answer {
  margin-top: 18px;
  border-top: 1px dashed var(--border);
  padding-top: 16px;
  animation: fadeIn 0.35s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
.rc-row {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  align-items: flex-start;
}
.rc-label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 7px;
  margin-top: 2px;
}
.rc-label.mine { background: rgba(255, 159, 10, 0.16); color: #ff9f0a; }
.rc-label.correct { background: rgba(52, 199, 89, 0.16); color: #34c759; }
.rc-label.exp { background: var(--accent-soft); color: var(--accent); }
.rc-val {
  font-size: 14.5px;
  line-height: 1.65;
  color: var(--text);
  white-space: pre-wrap;
}
.rc-quality {
  margin-top: 18px;
}
.rq-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
}
.rq-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}
.rq-btn {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  border-radius: 13px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.2s, border-color 0.2s;
  text-align: left;
}
.rq-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}
.rq-btn:disabled { opacity: 0.6; cursor: default; }
.rq-label { font-size: 14.5px; font-weight: 700; }
.rq-desc { font-size: 12px; color: var(--text-tertiary); }
.q-forgot { border-left: 3px solid #ff3b30; }
.q-forgot:hover:not(:disabled) { border-color: #ff3b30; }
.q-fuzzy { border-left: 3px solid #ff9f0a; }
.q-fuzzy:hover:not(:disabled) { border-color: #ff9f0a; }
.q-ok { border-left: 3px solid #0a84ff; }
.q-ok:hover:not(:disabled) { border-color: #0a84ff; }
.q-master { border-left: 3px solid #34c759; }
.q-master:hover:not(:disabled) { border-color: #34c759; }
.rc-feedback {
  margin-top: 18px;
  animation: fadeIn 0.35s ease;
}
.fb-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.fb-badge {
  font-size: 12.5px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 8px;
}
.fb-badge.good { background: rgba(52, 199, 89, 0.16); color: #34c759; }
.fb-badge.weak { background: rgba(255, 59, 48, 0.16); color: #ff3b30; }
.fb-text {
  font-size: 13.5px;
  color: var(--text-secondary);
}

@media (max-width: 860px) {
  .panel { padding: 64px 16px 40px; }
  .rq-grid { grid-template-columns: 1fr; }
}
</style>
