<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  useMessage,
  NIcon,
  NTag,
  NSpin
} from 'naive-ui'
import {
  ClipboardOutline,
  BookOutline,
  SchoolOutline,
  BarChartOutline,
  TrendingUpOutline,
  CheckmarkDoneOutline,
  PlayOutline,
  ArrowForwardOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'
import { store, switchView } from '../store.js'

const message = useMessage()

// 当前仅开放数学·八年级，直接作为只读标签展示
const SUBJECT = '数学'
const GRADE = '八年级'

const loading = ref(true)
const weakPoints = ref([])       // 诊断写回的薄弱点
const practiceMastery = reactive({}) // 练习巩固度 { topic: {attempts, correct, last_pct} }
const hasDiagnosed = computed(() => weakPoints.value.length > 0)
const hasPracticed = computed(() => Object.keys(practiceMastery).length > 0)

// 巩固度排序：掌握率升序（最弱在前）
const masteryRows = computed(() =>
  Object.entries(practiceMastery)
    .map(([topic, v]) => ({ topic, ...v }))
    .sort((a, b) => (a.last_pct ?? 0) - (b.last_pct ?? 0))
)

const subjectLabel = `${SUBJECT} · ${GRADE}`

onMounted(() => {
  loadProfile()
  maybeShowWelcome()
})

async function loadProfile() {
  loading.value = true
  try {
    const prof = await api.profile()
    const p = prof.profile || {}
    weakPoints.value = p.weak_points || []
    const pm = p.practice_mastery || {}
    for (const k of Object.keys(practiceMastery)) delete practiceMastery[k]
    Object.assign(practiceMastery, pm)
  } catch (e) {
    weakPoints.value = []
  } finally {
    loading.value = false
  }
}

function startDiagnosis() {
  switchView('diagnosis')
}

async function startPractice() {
  store.practiceAutoStart = true
  switchView('practice')
}

function goDashboard() {
  switchView('dashboard')
}

function masteryColor(pct) {
  if (pct >= 85) return 'var(--success)'
  if (pct >= 60) return 'var(--accent)'
  return 'var(--danger)'
}

// ===== 欢迎引导弹窗（首次进入学习主页）=====
const showWelcome = ref(false)
const WELCOME_KEY = 'ma_welcome_v1'
function maybeShowWelcome() {
  if (!localStorage.getItem(WELCOME_KEY)) showWelcome.value = true
}
function startNow() {
  // 看过即标记，之后进入不再打扰；并引导到聊天输入学习问题
  localStorage.setItem(WELCOME_KEY, '1')
  showWelcome.value = false
  switchView('chat')
}
function closeWelcome() {
  localStorage.setItem(WELCOME_KEY, '1')
  showWelcome.value = false
}
</script>

<template>
  <div class="learn-wrap">
    <!-- 顶部标题 -->
    <header class="learn-head">
      <div class="lh-left">
        <div class="lh-icon"><n-icon size="22"><SchoolOutline /></n-icon></div>
        <div>
          <h1>学习空间</h1>
          <p class="lh-sub">先测出薄弱点，再针对性练习巩固 —— 一条清晰的学习闭环</p>
        </div>
      </div>
      <div class="subj-badge">
        <n-icon size="15"><SchoolOutline /></n-icon>
        <span>{{ subjectLabel }}</span>
      </div>
    </header>

    <n-spin v-if="loading" size="medium" style="display:flex;justify-content:center;padding:60px 0" />

    <template v-else>
      <!-- ===== 路径说明：测 → 学 → 练 ===== -->
      <section class="glass-card path-card">
        <div class="path-step">
          <div class="ps-ico"><n-icon size="18"><ClipboardOutline /></n-icon></div>
          <div class="ps-tx"><b>测</b> · 诊断</div>
          <div class="ps-desc">8–16 题定位薄弱点，生成学情画像</div>
        </div>
        <div class="path-arrow"><n-icon size="16"><ArrowForwardOutline /></n-icon></div>
        <div class="path-step">
          <div class="ps-ico alt"><n-icon size="18"><BookOutline /></n-icon></div>
          <div class="ps-tx"><b>学</b> · 练习</div>
          <div class="ps-desc">针对薄弱点出题，做完即看名师讲解</div>
        </div>
        <div class="path-arrow"><n-icon size="16"><ArrowForwardOutline /></n-icon></div>
        <div class="path-step">
          <div class="ps-ico good"><n-icon size="18"><TrendingUpOutline /></n-icon></div>
          <div class="ps-tx"><b>练</b> · 巩固</div>
          <div class="ps-desc">进度写回档案，再诊断检验进步</div>
        </div>
      </section>

      <!-- ===== 状态区 ===== -->
      <section v-if="!hasDiagnosed" class="glass-card empty-card">
        <div class="ec-emoji">🧭</div>
        <div class="ec-title">还没有诊断记录</div>
        <p class="ec-sub">
          先做一次学情诊断，系统会自动找出你的薄弱点，然后就能针对性练习巩固。
        </p>
        <button class="primary-btn magnetic" @click="startDiagnosis">
          <n-icon size="18"><PlayOutline /></n-icon>
          <span>开始诊断</span>
        </button>
      </section>

      <template v-else>
        <!-- 薄弱点 + 主操作 -->
        <section class="glass-card status-card">
          <div class="sc-head">
            <div class="block-label">诊断薄弱点 <span class="count">({{ weakPoints.length }})</span></div>
            <span class="sc-hint">已自动选入练习目标</span>
          </div>
          <div class="wk-list">
            <n-tag
              v-for="w in weakPoints"
              :key="w"
              size="small"
              type="error"
              :bordered="false"
              class="wk-tag"
            >{{ w }}</n-tag>
          </div>
          <div class="sc-actions">
            <button class="primary-btn magnetic" @click="startPractice">
              <n-icon size="18"><BookOutline /></n-icon>
              <span>针对性练习</span>
            </button>
            <button class="ghost-btn lg" @click="startDiagnosis">
              <n-icon size="16"><ClipboardOutline /></n-icon>
              <span>重新诊断</span>
            </button>
            <button class="ghost-btn lg" @click="goDashboard">
              <n-icon size="16"><BarChartOutline /></n-icon>
              <span>学情看板</span>
            </button>
          </div>
        </section>

        <!-- 练习巩固度（双向画像） -->
        <section v-if="hasPracticed" class="glass-card mastery-card">
          <div class="block-label">练习巩固度 <span class="count">({{ masteryRows.length }})</span></div>
          <div class="mastery-list">
            <div v-for="m in masteryRows" :key="m.topic" class="m-row">
              <div class="m-name">{{ m.topic }}</div>
              <div class="m-bar">
                <div
                  class="m-fill"
                  :style="{ width: (m.last_pct ?? 0) + '%', background: masteryColor(m.last_pct ?? 0) }"
                ></div>
              </div>
              <div class="m-pct" :style="{ color: masteryColor(m.last_pct ?? 0) }">{{ m.last_pct ?? 0 }}%</div>
              <div class="m-right">{{ m.correct }}/{{ m.attempts }}</div>
            </div>
          </div>
        </section>
      </template>
    </template>
  </div>

  <!-- 欢迎引导弹窗：首次进入学习主页弹出 -->
  <teleport to="body">
    <transition name="welcome-fade">
      <div v-if="showWelcome" class="welcome-mask" @click.self="closeWelcome">
        <div class="welcome-card">
          <button class="welcome-close" @click="closeWelcome" aria-label="关闭">×</button>
          <div class="welcome-emoji">🎓</div>
          <div class="welcome-title">智伴私教 · 学习引导</div>
          <div class="welcome-lines">
            <p>我可以帮你梳理知识、讲解题目、规划学习</p>
            <p>学习过程我会引导思考，鼓励你主动推导</p>
          </div>
          <div class="welcome-hint">试试输入你的学习问题...</div>
          <button class="welcome-btn" @click="startNow">立即开始</button>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.learn-wrap {
  height: 100%;
  overflow-y: auto;
  padding: 26px clamp(16px, 4vw, 48px) 48px;
  max-width: 880px;
  margin: 0 auto;
}
.learn-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
  flex-wrap: wrap;
}
.lh-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.lh-icon {
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
.lh-left h1 {
  font-size: 22px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.01em;
}
.lh-sub {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.subj-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 16px;
  border-radius: 11px;
  background: var(--bg-input);
  border: 1px solid var(--border-strong);
  color: var(--text-secondary);
  font-size: 14px;
  font-weight: 600;
}

.glass-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
}

/* ===== 路径说明 ===== */
.path-card {
  display: flex;
  align-items: stretch;
  gap: 8px;
  padding: 22px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.path-step {
  flex: 1;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ps-ico {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 113, 227, 0.12);
  color: var(--accent);
}
.ps-ico.alt {
  background: rgba(106, 92, 255, 0.14);
  color: #6a5cff;
}
.ps-ico.good {
  background: rgba(52, 199, 89, 0.14);
  color: var(--success);
}
.ps-tx {
  font-size: 15px;
  font-weight: 700;
}
.ps-tx b {
  font-size: 16px;
}
.ps-desc {
  font-size: 12.5px;
  color: var(--text-tertiary);
  line-height: 1.5;
}
.path-arrow {
  display: flex;
  align-items: center;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
@media (max-width: 620px) {
  .path-arrow {
    transform: rotate(90deg);
  }
}

/* ===== 空状态 ===== */
.empty-card {
  padding: 40px 26px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 10px;
}
.ec-emoji {
  font-size: 40px;
}
.ec-title {
  font-size: 18px;
  font-weight: 700;
}
.ec-sub {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 460px;
  margin: 0 0 12px;
}

/* ===== 状态区 ===== */
.status-card {
  padding: 22px 24px;
  margin-bottom: 16px;
}
.sc-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.block-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: 0.01em;
}
.block-label .count {
  color: var(--text-tertiary);
  font-weight: 600;
}
.sc-hint {
  font-size: 12.5px;
  color: var(--text-tertiary);
}
.wk-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}
.wk-tag {
  font-weight: 600;
}
.sc-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* ===== 巩固度 ===== */
.mastery-card {
  padding: 22px 24px;
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

/* ===== 按钮 ===== */
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

/* ===== 欢迎引导弹窗 ===== */
.welcome-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.welcome-card {
  position: relative;
  width: 100%;
  max-width: 420px;
  padding: 34px 30px 30px;
  border-radius: 22px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.42);
  backdrop-filter: saturate(180%) blur(24px);
  -webkit-backdrop-filter: saturate(180%) blur(24px);
  text-align: center;
}
.welcome-close {
  position: absolute;
  top: 14px;
  right: 16px;
  width: 30px;
  height: 30px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.16s, color 0.16s;
}
.welcome-close:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.welcome-emoji {
  font-size: 46px;
  margin-bottom: 12px;
}
.welcome-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 18px;
  letter-spacing: 0.02em;
}
.welcome-lines {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.welcome-lines p {
  margin: 0;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text);
}
.welcome-hint {
  font-size: 13.5px;
  color: var(--text-tertiary);
  margin-bottom: 24px;
  font-style: italic;
}
.welcome-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 50px;
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
.welcome-btn:hover:not(:disabled) {
  filter: brightness(1.05);
  box-shadow: 0 10px 28px rgba(0, 113, 227, 0.46);
}
.welcome-btn:active:not(:disabled) {
  transform: scale(0.98);
}
.welcome-fade-enter-active,
.welcome-fade-leave-active {
  transition: opacity 0.28s ease;
}
.welcome-fade-enter-from,
.welcome-fade-leave-to {
  opacity: 0;
}
</style>
