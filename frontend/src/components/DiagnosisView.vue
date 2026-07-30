<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  useMessage,
  NIcon,
  NButton,
  NRadioGroup,
  NRadio,
  NProgress,
  NTag,
  NSpin
} from 'naive-ui'
import {
  ClipboardOutline,
  PlayOutline,
  CheckmarkDoneOutline,
  RefreshOutline,
  BarChartOutline,
  SchoolOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'
import { switchView } from '../store.js'

const message = useMessage()

const phase = ref('setup') // setup | quiz | result
const subject = ref('数学')
const grade = ref('八年级')
const count = ref(12)

const supported = ref([{ subject: '数学', grade: '八年级' }])
const pointsCount = ref(0)

const generating = ref(false)
const submitting = ref(false)
const questions = ref([])
const answers = reactive({}) // { [questionId]: choiceIndex }
const result = ref(null)

const answeredCount = computed(() => Object.keys(answers).filter((k) => answers[k] !== null && answers[k] !== undefined).length)
const total = computed(() => questions.value.length)
const allAnswered = computed(() => total.value > 0 && answeredCount.value === total.value)

onMounted(loadCurriculum)

async function loadCurriculum() {
  try {
    const data = await api.curriculum(subject.value, grade.value)
    supported.value = data.supported || supported.value
    pointsCount.value = data.points_count || 0
  } catch (e) {
    /* ignore */
  }
}

function selectSubjectGrade(s, g) {
  subject.value = s
  grade.value = g
  loadCurriculum()
}

async function startDiagnosis() {
  generating.value = true
  try {
    const data = await api.diagnose(subject.value, grade.value, count.value)
    questions.value = data.questions || []
    for (const k of Object.keys(answers)) delete answers[k]
    phase.value = 'quiz'
  } catch (e) {
    message.error(e?.detail || '生成诊断卷失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

async function submitDiagnosis() {
  if (!allAnswered.value) {
    message.warning(`还有 ${total.value - answeredCount.value} 题未作答`)
    return
  }
  submitting.value = true
  try {
    const payload = {
      subject: subject.value,
      grade: grade.value,
      questions: questions.value,
      answers: questions.value.map((q) => ({ id: q.id, choice: answers[q.id] }))
    }
    const res = await api.submitDiagnosis(payload)
    result.value = res
    phase.value = 'result'
  } catch (e) {
    message.error(e?.detail || '批改失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

function restart() {
  result.value = null
  questions.value = []
  for (const k of Object.keys(answers)) delete answers[k]
  phase.value = 'setup'
}

function masteryColor(pct) {
  if (pct >= 85) return 'var(--success)'
  if (pct >= 60) return 'var(--accent)'
  return 'var(--danger)'
}

function scoreColor(score) {
  if (score >= 85) return 'var(--success)'
  if (score >= 60) return 'var(--accent)'
  return 'var(--danger)'
}

function levelText(score) {
  if (score >= 85) return '优秀'
  if (score >= 60) return '良好'
  return '待加强'
}
</script>

<template>
  <div class="diag-wrap">
    <!-- 顶部标题 -->
    <header class="diag-head">
      <div class="dh-left">
        <div class="dh-icon"><n-icon size="22"><ClipboardOutline /></n-icon></div>
        <div>
          <h1>学情诊断</h1>
          <p class="dh-sub">一次闭环：出题 → 作答 → 批改 → 薄弱点画像，自动写入学情档案</p>
        </div>
      </div>
      <div class="dh-step">
        <span :class="{ on: phase === 'setup' }">1 选择</span>
        <span class="dot">·</span>
        <span :class="{ on: phase === 'quiz' }">2 作答</span>
        <span class="dot">·</span>
        <span :class="{ on: phase === 'result' }">3 画像</span>
      </div>
    </header>

    <!-- ===== 阶段一：选择 ===== -->
    <section v-if="phase === 'setup'" class="glass-card setup">
      <div class="setup-block">
        <div class="block-label">学科 · 年级</div>
        <div class="chip-row">
          <button
            v-for="s in supported"
            :key="s.subject + s.grade"
            class="chip"
            :class="{ active: subject === s.subject && grade === s.grade }"
            @click="selectSubjectGrade(s.subject, s.grade)"
          >
            <n-icon size="16"><SchoolOutline /></n-icon>
            <span>{{ s.subject }} · {{ s.grade }}</span>
          </button>
        </div>
        <p class="hint" v-if="pointsCount">
          本次诊断覆盖 <b>{{ pointsCount }}</b> 个核心知识点，将从中抽取 {{ count }} 题。
        </p>
      </div>

      <div class="setup-block">
        <div class="block-label">题量</div>
        <div class="chip-row">
          <button
            v-for="c in [8, 12, 16]"
            :key="c"
            class="chip small"
            :class="{ active: count === c }"
            @click="count = c"
          >
            {{ c }} 题
          </button>
        </div>
      </div>

      <button class="primary-btn magnetic" :disabled="generating" @click="startDiagnosis">
        <n-spin v-if="generating" size="small" />
        <template v-else>
          <n-icon size="18"><PlayOutline /></n-icon>
          <span>开始诊断</span>
        </template>
      </button>
    </section>

    <!-- ===== 阶段二：作答 ===== -->
    <section v-else-if="phase === 'quiz'" class="quiz">
      <div class="quiz-bar glass-card">
        <div class="qb-info">
          进度 <b>{{ answeredCount }}</b> / {{ total }}
        </div>
        <n-progress
          type="line"
          :percentage="total ? Math.round((answeredCount / total) * 100) : 0"
          :height="8"
          :border-radius="8"
          color="var(--accent)"
          rail-color="var(--bg-hover)"
          style="flex: 1; max-width: 320px"
        />
        <button class="ghost-btn" @click="restart"><n-icon size="15"><RefreshOutline /></n-icon> 重选</button>
      </div>

      <div class="q-list">
        <div v-for="(q, i) in questions" :key="q.id" class="glass-card q-card">
          <div class="q-top">
            <span class="q-no">Q{{ i + 1 }}</span>
            <n-tag size="small" :bordered="false" type="info">{{ q.topic }}</n-tag>
          </div>
          <p class="q-stem">{{ q.stem }}</p>
          <n-radio-group :value="answers[q.id]" @update:value="(v) => (answers[q.id] = v)">
            <div class="opt-grid">
              <n-radio
                v-for="(opt, oi) in q.options"
                :key="oi"
                :value="oi"
                class="opt"
                :class="{ chosen: answers[q.id] === oi }"
              >
                <span class="opt-key">{{ 'ABCD'[oi] }}</span>
                <span class="opt-txt">{{ opt }}</span>
              </n-radio>
            </div>
          </n-radio-group>
        </div>
      </div>

      <div class="submit-bar">
        <button class="primary-btn magnetic" :disabled="submitting || !allAnswered" @click="submitDiagnosis">
          <n-spin v-if="submitting" size="small" />
          <template v-else>
            <n-icon size="18"><CheckmarkDoneOutline /></n-icon>
            <span>提交并生成画像</span>
          </template>
        </button>
        <span class="submit-hint" v-if="!allAnswered">请答完所有题目</span>
      </div>
    </section>

    <!-- ===== 阶段三：画像 ===== -->
    <section v-else-if="phase === 'result'" class="result">
      <div class="glass-card result-top">
        <div class="score-ring">
          <n-progress
            type="circle"
            :percentage="result.score"
            :color="scoreColor(result.score)"
            :rail-color="result.score >= 60 ? 'var(--accent-soft)' : 'rgba(224,36,36,0.12)'"
            :stroke-width="10"
            :show-indicator="false"
            :size="148"
          >
          </n-progress>
          <div class="ring-center">
            <div class="ring-score" :style="{ color: scoreColor(result.score) }">{{ result.score }}</div>
            <div class="ring-label">分 · {{ levelText(result.score) }}</div>
          </div>
        </div>
        <div class="result-meta">
          <div class="rm-title">{{ result.subject }} · {{ result.grade }} 学情画像</div>
          <p class="rm-sub">
            共 {{ result.total }} 题，答对 {{ result.correct }} 题。
            已自动更新学情档案，可在「学情看板」查看趋势。
          </p>
          <div class="rm-weak" v-if="result.weak_points.length">
            <span class="rm-k">薄弱点</span>
            <n-tag
              v-for="w in result.weak_points"
              :key="w"
              size="small"
              type="error"
              :bordered="false"
              class="wk-tag"
            >{{ w }}</n-tag>
          </div>
          <div class="rm-weak" v-else>
            <span class="rm-k">薄弱点</span>
            <span class="rm-none">暂无显著薄弱点 🎉</span>
          </div>
        </div>
      </div>

      <div class="glass-card mastery-card">
        <div class="block-label">知识点掌握度</div>
        <div class="mastery-list">
          <div v-for="m in result.mastery" :key="m.topic_id" class="m-row">
            <div class="m-name">{{ m.topic }}</div>
            <div class="m-bar">
              <div class="m-fill" :style="{ width: m.pct + '%', background: masteryColor(m.pct) }"></div>
            </div>
            <div class="m-pct" :style="{ color: masteryColor(m.pct) }">{{ m.pct }}%</div>
            <div class="m-right">{{ m.right }}/{{ m.total }}</div>
          </div>
        </div>
      </div>

      <div class="glass-card sugg-card">
        <div class="block-label">提升建议</div>
        <ul class="sugg-list">
          <li v-for="(s, i) in result.suggestions" :key="i">{{ s }}</li>
        </ul>
      </div>

      <div class="result-actions">
        <button class="primary-btn magnetic" @click="switchView('dashboard')">
          <n-icon size="18"><BarChartOutline /></n-icon>
          <span>查看学情看板</span>
        </button>
        <button class="ghost-btn lg" @click="restart">
          <n-icon size="16"><RefreshOutline /></n-icon>
          <span>再测一次</span>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.diag-wrap {
  height: 100%;
  overflow-y: auto;
  padding: 26px clamp(16px, 4vw, 48px) 48px;
  max-width: 880px;
  margin: 0 auto;
}
.diag-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
  flex-wrap: wrap;
}
.dh-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.dh-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: linear-gradient(135deg, #0071e3, #42a5f5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 18px rgba(0, 113, 227, 0.35);
  flex-shrink: 0;
}
.dh-left h1 {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}
.dh-sub {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.dh-step {
  font-size: 13px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.dh-step .on {
  color: var(--accent);
  font-weight: 700;
}
.dh-step .dot {
  opacity: 0.5;
}

.glass-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
}

/* ===== 阶段一 ===== */
.setup {
  padding: 26px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.setup-block .block-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  margin-bottom: 12px;
  letter-spacing: 0.02em;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 42px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid var(--border-strong);
  background: var(--bg-input);
  color: var(--text);
  font-size: 14.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
}
.chip.small {
  height: 38px;
  padding: 0 18px;
}
.chip:hover {
  border-color: var(--accent);
  transform: translateY(-1px);
}
.chip.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  box-shadow: 0 6px 16px rgba(0, 113, 227, 0.3);
}
.hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.hint b {
  color: var(--accent);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  height: 50px;
  padding: 0 26px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #0071e3, #0a84ff);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 22px rgba(0, 113, 227, 0.38);
  transition: transform 0.16s cubic-bezier(0.16, 1, 0.3, 1), filter 0.16s, box-shadow 0.16s;
}
.primary-btn:hover:not(:disabled) {
  filter: brightness(1.05);
  box-shadow: 0 10px 28px rgba(0, 113, 227, 0.46);
}
.primary-btn:active:not(:disabled) {
  transform: scale(0.98);
}
.primary-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.magnetic {
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), filter 0.16s, box-shadow 0.16s;
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 14px;
  border: 1px solid var(--border-strong);
  border-radius: 11px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.16s;
}
.ghost-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.ghost-btn.lg {
  height: 50px;
  padding: 0 22px;
  font-size: 15px;
}

/* ===== 阶段二 ===== */
.quiz-bar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.qb-info {
  font-size: 14px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.qb-info b {
  color: var(--accent);
  font-size: 16px;
}
.q-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.q-card {
  padding: 18px 20px;
  animation: rise 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.q-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.q-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 26px;
  padding: 0 8px;
  border-radius: 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 700;
  font-size: 13px;
}
.q-stem {
  font-size: 15.5px;
  line-height: 1.6;
  margin: 0 0 14px;
  color: var(--text);
}
.opt-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
@media (max-width: 600px) {
  .opt-grid {
    grid-template-columns: 1fr;
  }
}
.opt {
  display: flex !important;
  align-items: center;
  gap: 10px;
  padding: 12px 14px !important;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.16s ease;
  background: var(--bg-input);
}
.opt:hover {
  border-color: var(--accent);
}
.opt.chosen {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.opt-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: var(--bg-hover);
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
  color: var(--text-secondary);
}
.opt.chosen .opt-key {
  background: var(--accent);
  color: #fff;
}
.opt-txt {
  font-size: 14.5px;
  line-height: 1.4;
}
.submit-bar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 20px;
}
.submit-hint {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ===== 阶段三 ===== */
.result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.result-top {
  display: flex;
  align-items: center;
  gap: 26px;
  padding: 24px;
}
@media (max-width: 560px) {
  .result-top {
    flex-direction: column;
    text-align: center;
  }
}
.score-ring {
  position: relative;
  width: 148px;
  height: 148px;
  flex-shrink: 0;
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ring-score {
  font-size: 44px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.02em;
}
.ring-label {
  font-size: 12.5px;
  color: var(--text-tertiary);
  margin-top: 4px;
}
.result-meta {
  flex: 1;
  min-width: 0;
}
.rm-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}
.rm-sub {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 14px;
}
.rm-weak {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.rm-k {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-tertiary);
}
.wk-tag {
  font-weight: 600;
}
.rm-none {
  font-size: 13.5px;
  color: var(--success);
  font-weight: 600;
}

.mastery-card,
.sugg-card {
  padding: 22px 24px;
}
.block-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 16px;
  letter-spacing: 0.01em;
}
.mastery-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.m-row {
  display: grid;
  grid-template-columns: 1fr 200px 48px 44px;
  align-items: center;
  gap: 12px;
}
@media (max-width: 560px) {
  .m-row {
    grid-template-columns: 1fr 120px 44px;
  }
  .m-right {
    display: none;
  }
}
.m-name {
  font-size: 14px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.m-bar {
  height: 10px;
  border-radius: 6px;
  background: var(--bg-hover);
  overflow: hidden;
}
.m-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.7s cubic-bezier(0.16, 1, 0.3, 1);
}
.m-pct {
  font-size: 13.5px;
  font-weight: 700;
  text-align: right;
}
.m-right {
  font-size: 12.5px;
  color: var(--text-tertiary);
  text-align: right;
}
.sugg-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.sugg-list li {
  font-size: 14.5px;
  line-height: 1.6;
  color: var(--text);
}
.result-actions {
  display: flex;
  gap: 14px;
  margin-top: 6px;
  flex-wrap: wrap;
}
</style>
