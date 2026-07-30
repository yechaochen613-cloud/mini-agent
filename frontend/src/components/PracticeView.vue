<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  useMessage,
  NIcon,
  NRadioGroup,
  NRadio,
  NProgress,
  NTag,
  NSpin
} from 'naive-ui'
import {
  BookOutline,
  PlayOutline,
  RefreshOutline,
  CheckmarkDoneOutline,
  CheckmarkCircleOutline,
  CloseOutline,
  SchoolOutline,
  BarChartOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'
import { switchView } from '../store.js'

const message = useMessage()

const phase = ref('setup') // setup | practice | summary
const subject = ref('数学')
const grade = ref('八年级')
const count = ref(6)

const supported = ref([{ subject: '数学', grade: '八年级' }])
const chapters = ref([])
const pointsCount = ref(0)

const generating = ref(false)
const questions = ref([])
const answers = reactive({}) // { [questionId]: choiceIndex }
const focusSel = reactive({}) // 选中的薄弱点：{ [pointName]: true }
const weakFromProfile = ref([]) // 诊断档案里的薄弱点（用于展示）
const showManual = ref(false)

const isAnswered = (q) => answers[q.id] !== undefined && answers[q.id] !== null
const answeredCount = computed(() => questions.value.filter((q) => isAnswered(q)).length)
const total = computed(() => questions.value.length)
const allAnswered = computed(() => total.value > 0 && answeredCount.value === total.value)

const focusList = computed(() => Object.keys(focusSel))

const correctCount = computed(() => {
  let c = 0
  for (const q of questions.value) if (answers[q.id] === q.answer) c++
  return c
})

const summary = computed(() => {
  const perTopic = {}
  let correct = 0
  for (const q of questions.value) {
    const right = answers[q.id] === q.answer
    if (right) correct++
    const d = perTopic[q.topic_id] || (perTopic[q.topic_id] = { topic: q.topic, right: 0, total: 0 })
    d.total++
    if (right) d.right++
  }
  const t = questions.value.length
  return {
    perTopic: Object.values(perTopic),
    correct,
    total: t,
    accuracy: t ? Math.round((100 * correct) / t) : 0
  }
})

onMounted(loadSetup)

async function loadSetup() {
  try {
    const data = await api.curriculum(subject.value, grade.value)
    supported.value = data.supported || supported.value
    pointsCount.value = data.points_count || 0
    chapters.value = data.chapters || []
    // 解析档案薄弱点，自动选入与知识点图谱匹配的项
    const names = new Set()
    for (const ch of chapters.value) for (const p of ch.points) names.add(p.name)
    try {
      const prof = await api.profile()
      const weak = (prof.profile?.weak_points || []).filter((w) => {
        const ww = String(w).trim()
        if (!ww) return false
        if (names.has(ww)) return true
        for (const n of names) if (n.includes(ww) || ww.includes(n)) return true
        return false
      })
      weakFromProfile.value = weak
      for (const w of weak) focusSel[w] = true
    } catch (e) {
      /* 忽略：拿不到档案就不预选 */
    }
  } catch (e) {
    /* ignore */
  }
}

function selectSubjectGrade(s, g) {
  subject.value = s
  grade.value = g
  loadSetup()
}

function toggleFocus(name) {
  if (focusSel[name]) delete focusSel[name]
  else focusSel[name] = true
}

function clearFocus() {
  for (const k of Object.keys(focusSel)) delete focusSel[k]
}

async function startPractice() {
  generating.value = true
  try {
    const data = await api.practice({
      subject: subject.value,
      grade: grade.value,
      focus_points: focusList.value,
      count: count.value
    })
    questions.value = data.questions || []
    for (const k of Object.keys(answers)) delete answers[k]
    phase.value = 'practice'
  } catch (e) {
    message.error(e?.detail || '生成练习失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

function finish() {
  if (!allAnswered.value) {
    message.warning(`还有 ${total.value - answeredCount.value} 题未作答`)
    return
  }
  phase.value = 'summary'
}

function restart() {
  questions.value = []
  for (const k of Object.keys(answers)) delete answers[k]
  phase.value = 'setup'
  // 保留已选薄弱点，方便再练一轮
}

function optState(q, oi) {
  const answered = isAnswered(q)
  const isCorrect = q.answer === oi
  const isChosen = answers[q.id] === oi
  return {
    revealed: answered,
    correct: answered && isCorrect,
    wrong: answered && isChosen && !isCorrect
  }
}

function topicColor(right, total) {
  const pct = total ? right / total : 0
  return pct >= 0.6 ? 'var(--success)' : 'var(--danger)'
}

function accuracyColor(a) {
  if (a >= 80) return 'var(--success)'
  if (a >= 60) return 'var(--accent)'
  return 'var(--danger)'
}
</script>

<template>
  <div class="prac-wrap">
    <!-- 顶部标题 -->
    <header class="prac-head">
      <div class="ph-left">
        <div class="ph-icon"><n-icon size="22"><BookOutline /></n-icon></div>
        <div>
          <h1>针对性练习</h1>
          <p class="ph-sub">测 → 学 → 再测：做一题，立刻看名师分步讲解，薄弱点当场巩固</p>
        </div>
      </div>
      <div class="ph-step">
        <span :class="{ on: phase === 'setup' }">1 选目标</span>
        <span class="dot">·</span>
        <span :class="{ on: phase === 'practice' }">2 练+讲</span>
        <span class="dot">·</span>
        <span :class="{ on: phase === 'summary' }">3 总结</span>
      </div>
    </header>

    <!-- ===== 阶段一：选择目标 ===== -->
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
      </div>

      <div class="setup-block">
        <div class="block-label">练习目标（薄弱点）</div>

        <template v-if="weakFromProfile.length">
          <div class="sub-label">基于诊断薄弱点（已自动选入）</div>
          <div class="chip-row">
            <button
              v-for="w in weakFromProfile"
              :key="'w-' + w"
              class="chip small"
              :class="{ active: focusSel[w] }"
              @click="toggleFocus(w)"
            >
              <n-icon size="14"><CheckmarkDoneOutline v-if="focusSel[w]" /><BookOutline v-else /></n-icon>
              <span>{{ w }}</span>
            </button>
          </div>
        </template>
        <p class="hint" v-else>
          暂无诊断薄弱点，可直接手动选择知识点，或留空由系统随机抽取练习。
        </p>

        <button class="manual-toggle" @click="showManual = !showManual">
          <n-icon size="15"><BookOutline /></n-icon>
          <span>{{ showManual ? '收起知识点列表' : '手动选择知识点' }}</span>
          <span class="caret" :class="{ open: showManual }">▾</span>
        </button>

        <div v-if="showManual" class="manual-panel">
          <div v-for="ch in chapters" :key="ch.chapter" class="ch-block">
            <div class="ch-name">{{ ch.chapter }}</div>
            <div class="chip-row">
              <button
                v-for="p in ch.points"
                :key="p.id"
                class="chip small"
                :class="{ active: focusSel[p.name] }"
                @click="toggleFocus(p.name)"
              >
                <span>{{ p.name }}</span>
              </button>
            </div>
          </div>
        </div>

        <div class="focus-bar" v-if="focusList.length">
          <span class="fb-k">已选 {{ focusList.length }} 个目标</span>
          <button class="fb-clear" @click="clearFocus">清空</button>
        </div>
        <p class="hint" v-else>未选择目标，将随机抽取知识点练习。</p>
      </div>

      <div class="setup-block">
        <div class="block-label">题量</div>
        <div class="chip-row">
          <button
            v-for="c in [4, 6, 8]"
            :key="c"
            class="chip small"
            :class="{ active: count === c }"
            @click="count = c"
          >
            {{ c }} 题
          </button>
        </div>
      </div>

      <button class="primary-btn magnetic" :disabled="generating" @click="startPractice">
        <n-spin v-if="generating" size="small" />
        <template v-else>
          <n-icon size="18"><PlayOutline /></n-icon>
          <span>开始练习</span>
        </template>
      </button>
    </section>

    <!-- ===== 阶段二：练 + 讲 ===== -->
    <section v-else-if="phase === 'practice'" class="practice">
      <div class="quiz-bar glass-card">
        <div class="qb-info">
          进度 <b>{{ answeredCount }}</b> / {{ total }}　·　正确 <b class="ok">{{ correctCount }}</b>
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
                :class="[optState(q, oi).correct ? 'opt-correct' : '', optState(q, oi).wrong ? 'opt-wrong' : '', isAnswered(q) && !optState(q, oi).correct && !optState(q, oi).wrong ? 'opt-dim' : '']"
              >
                <span class="opt-key">{{ 'ABCD'[oi] }}</span>
                <span class="opt-txt">{{ opt }}</span>
                <span class="opt-mark" v-if="optState(q, oi).correct"><n-icon size="16"><CheckmarkCircleOutline /></n-icon></span>
                <span class="opt-mark" v-else-if="optState(q, oi).wrong"><n-icon size="16"><CloseOutline /></n-icon></span>
              </n-radio>
            </div>
          </n-radio-group>

          <!-- 名师讲解：作答后揭示 -->
          <div v-if="isAnswered(q)" class="explain">
            <div class="ex-head">
              <n-icon size="16"><SchoolOutline /></n-icon>
              <span>名师讲解</span>
              <span class="ex-badge" :class="answers[q.id] === q.answer ? 'good' : 'bad'">
                <n-icon size="14"><CheckmarkCircleOutline v-if="answers[q.id] === q.answer" /><CloseOutline v-else /></n-icon>
                {{ answers[q.id] === q.answer ? '答对了' : '正确答案 ' + 'ABCD'[q.answer] }}
              </span>
            </div>
            <p class="ex-text">{{ q.explanation }}</p>
          </div>
        </div>
      </div>

      <div class="submit-bar">
        <button class="primary-btn magnetic" :disabled="!allAnswered" @click="finish">
          <n-icon size="18"><CheckmarkDoneOutline /></n-icon>
          <span>查看总结</span>
        </button>
        <span class="submit-hint" v-if="!allAnswered">请答完所有题目</span>
      </div>
    </section>

    <!-- ===== 阶段三：总结 ===== -->
    <section v-else-if="phase === 'summary'" class="result">
      <div class="glass-card result-top">
        <div class="score-ring">
          <n-progress
            type="circle"
            :percentage="summary.accuracy"
            :color="accuracyColor(summary.accuracy)"
            :rail-color="summary.accuracy >= 60 ? 'var(--accent-soft)' : 'rgba(224,36,36,0.12)'"
            :stroke-width="10"
            :show-indicator="false"
            :size="148"
          >
          </n-progress>
          <div class="ring-center">
            <div class="ring-score" :style="{ color: accuracyColor(summary.accuracy) }">{{ summary.accuracy }}%</div>
            <div class="ring-label">正确率</div>
          </div>
        </div>
        <div class="result-meta">
          <div class="rm-title">{{ subject }} · {{ grade }} 练习总结</div>
          <p class="rm-sub">
            共 {{ summary.total }} 题，答对 {{ summary.correct }} 题。
            <template v-if="focusList.length">本次针对 <b>{{ focusList.length }}</b> 个薄弱点巩固。</template>
          </p>
          <div class="rm-weak" v-if="focusList.length">
            <span class="rm-k">练习目标</span>
            <n-tag
              v-for="f in focusList"
              :key="f"
              size="small"
              type="warning"
              :bordered="false"
              class="wk-tag"
            >{{ f }}</n-tag>
          </div>
        </div>
      </div>

      <div class="glass-card mastery-card">
        <div class="block-label">各薄弱点掌握情况</div>
        <div class="mastery-list">
          <div v-for="m in summary.perTopic" :key="m.topic" class="m-row">
            <div class="m-name">{{ m.topic }}</div>
            <div class="m-bar">
              <div
                class="m-fill"
                :style="{ width: (m.total ? Math.round((m.right / m.total) * 100) : 0) + '%', background: topicColor(m.right, m.total) }"
              ></div>
            </div>
            <div class="m-pct" :style="{ color: topicColor(m.right, m.total) }">
              {{ m.total ? Math.round((m.right / m.total) * 100) : 0 }}%
            </div>
            <div class="m-right">{{ m.right }}/{{ m.total }}</div>
          </div>
        </div>
      </div>

      <div class="result-actions">
        <button class="primary-btn magnetic" @click="switchView('diagnosis')">
          <n-icon size="18"><BarChartOutline /></n-icon>
          <span>去重新诊断，检验进步</span>
        </button>
        <button class="ghost-btn lg" @click="restart">
          <n-icon size="16"><RefreshOutline /></n-icon>
          <span>再练一轮</span>
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.prac-wrap {
  height: 100%;
  overflow-y: auto;
  padding: 26px clamp(16px, 4vw, 48px) 48px;
  max-width: 880px;
  margin: 0 auto;
}
.prac-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
  flex-wrap: wrap;
}
.ph-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.ph-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: linear-gradient(135deg, #6a5cff, #0071e3);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 18px rgba(106, 92, 255, 0.35);
  flex-shrink: 0;
}
.ph-left h1 {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}
.ph-sub {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.ph-step {
  font-size: 13px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.ph-step .on {
  color: var(--accent);
  font-weight: 700;
}
.ph-step .dot {
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
.sub-label {
  font-size: 12.5px;
  color: var(--text-tertiary);
  margin-bottom: 10px;
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
.chip.small span {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.manual-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  height: 38px;
  padding: 0 14px;
  border-radius: 11px;
  border: 1px dashed var(--border-strong);
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.16s;
}
.manual-toggle:hover {
  border-color: var(--accent);
  color: var(--text);
}
.caret {
  transition: transform 0.2s;
}
.caret.open {
  transform: rotate(180deg);
}
.manual-panel {
  margin-top: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--bg-input);
  display: flex;
  flex-direction: column;
  gap: 16px;
  animation: rise 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.ch-block .ch-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.focus-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  padding: 10px 14px;
  border-radius: 11px;
  background: var(--accent-soft);
}
.fb-k {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--accent);
}
.fb-clear {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 13px;
  cursor: pointer;
  text-decoration: underline;
}
.fb-clear:hover {
  color: var(--danger);
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
  background: linear-gradient(135deg, #6a5cff, #0071e3);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 8px 22px rgba(106, 92, 255, 0.38);
  transition: transform 0.16s cubic-bezier(0.16, 1, 0.3, 1), filter 0.16s, box-shadow 0.16s;
}
.primary-btn:hover:not(:disabled) {
  filter: brightness(1.05);
  box-shadow: 0 10px 28px rgba(106, 92, 255, 0.46);
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
.qb-info b.ok {
  color: var(--success);
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
  position: relative;
}
.opt:hover {
  border-color: var(--accent);
}
.opt-correct {
  border-color: var(--success) !important;
  background: rgba(52, 199, 89, 0.12) !important;
}
.opt-wrong {
  border-color: var(--danger) !important;
  background: rgba(224, 36, 36, 0.1) !important;
}
.opt-dim {
  opacity: 0.62;
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
.opt-correct .opt-key {
  background: var(--success);
  color: #fff;
}
.opt-wrong .opt-key {
  background: var(--danger);
  color: #fff;
}
.opt-txt {
  font-size: 14.5px;
  line-height: 1.4;
}
.opt-mark {
  margin-left: auto;
  color: var(--success);
  display: inline-flex;
  align-items: center;
}
.opt-wrong .opt-mark {
  color: var(--danger);
}

/* 名师讲解 */
.explain {
  margin-top: 14px;
  padding: 14px 16px;
  border-left: 3px solid var(--accent);
  border-radius: 0 12px 12px 0;
  background: var(--bg-input);
  animation: rise 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
}
.ex-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  color: var(--accent);
  font-weight: 700;
  font-size: 14px;
}
.ex-badge {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  padding: 2px 9px;
  border-radius: 8px;
  font-weight: 700;
}
.ex-badge.good {
  color: var(--success);
  background: rgba(52, 199, 89, 0.14);
}
.ex-badge.bad {
  color: var(--danger);
  background: rgba(224, 36, 36, 0.12);
}
.ex-text {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--text);
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
.mastery-card {
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
.result-actions {
  display: flex;
  gap: 14px;
  margin-top: 6px;
  flex-wrap: wrap;
}
</style>
