<script setup>
import { ref, watch, onMounted, nextTick, computed } from 'vue'
import { useMessage, NIcon } from 'naive-ui'
import {
  SunnyOutline,
  MoonOutline,
  ContrastOutline,
  SparklesOutline,
  DocumentTextOutline,
  SchoolOutline,
  BulbOutline
} from '@vicons/ionicons5'
import { store, refreshConversations } from '../store.js'
import { api, streamChat } from '../api.js'
import { themeMode, setTheme } from '../theme.js'
import { TEACHERS } from '../teachers.js'
import MessageBubble from './MessageBubble.vue'
import Composer from './Composer.vue'
import BotAvatar from './BotAvatar.vue'

const message = useMessage()

const messages = ref([])
const streaming = ref(false)
const botMsg = ref(null)
const scrollRef = ref(null)
const loadingHist = ref(false)

const title = computed(() => {
  if (!store.currentSessionId) return '新对话'
  const c = store.conversations.find((x) => x.id === store.currentSessionId)
  return c?.title || '对话'
})

const themeIcon = computed(() => {
  if (themeMode.value === 'dark') return MoonOutline
  if (themeMode.value === 'light') return SunnyOutline
  return ContrastOutline
})

const suggestions = [
  { icon: SchoolOutline, text: '帮我讲解一道数学题' },
  { icon: DocumentTextOutline, text: '上传一份试卷并分析薄弱点' },
  { icon: BulbOutline, text: '为我制定两周学习计划' },
  { icon: SparklesOutline, text: '用生活中的例子解释牛顿第二定律' }
]

function nowTime() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadConversation() {
  loadingHist.value = true
  if (store.currentSessionId) {
    try {
      const c = await api.conversation(store.currentSessionId)
      messages.value = (c.messages || []).map((m) => ({
        role: m.role,
        text: m.text || '',
        steps: m.steps || [],
        reasoning: m.reasoning || '',
        streaming: false
      }))
      store.currentTeacher = null
    } catch (e) {
      messages.value = []
    }
  } else {
    messages.value = []
  }
  loadingHist.value = false
  scrollToBottom()
  // 召唤老师后的待发提示
  if (store.pendingPrompt) {
    const p = store.pendingPrompt
    store.pendingPrompt = null
    send(p)
  }
}

function handleEvent(ev, bot) {
  switch (ev.type) {
    case 'token':
      bot.text += ev.text
      scrollToBottom()
      break
    case 'reasoning':
      bot.reasoning += ev.text
      break
    case 'step_start':
      bot.steps.push({ id: ev.id, tool: ev.tool, args: ev.args, result: '', status: 'running' })
      break
    case 'step_end': {
      const s = bot.steps.find((x) => x.id === ev.id)
      if (s) {
        s.result = ev.result
        s.status = 'done'
      } else {
        bot.steps.push({ id: ev.id, tool: ev.tool, args: ev.args, result: ev.result, status: 'done' })
      }
      break
    }
    case 'done':
      bot.text = ev.reply ?? bot.text
      bot.streaming = false
      streaming.value = false
      if (ev.session_id) store.currentSessionId = ev.session_id
      if (ev.needs_review && ev.review) bot.review = ev.review
      refreshConversations()
      scrollToBottom()
      break
    case 'error':
      bot.streaming = false
      streaming.value = false
      bot.error = ev.message
      message.error(ev.message || '出错了')
      break
  }
}

async function send(text) {
  if (streaming.value) return
  messages.value.push({ role: 'user', text, time: nowTime() })
  const bot = { role: 'bot', text: '', steps: [], reasoning: '', streaming: true, time: nowTime() }
  messages.value.push(bot)
  botMsg.value = bot
  streaming.value = true
  scrollToBottom()

  const payload = {
    message: text,
    session_id: store.currentSessionId,
    model: store.settings.model,
    persona: store.currentTeacher || store.settings.persona,
    style: store.settings.style,
    max_steps: 6
  }
  await streamChat(payload, {
    onEvent: (ev) => handleEvent(ev, bot),
    onError: (msg) => {
      bot.streaming = false
      streaming.value = false
      bot.error = msg
      message.error(msg || '网络异常')
    }
  })
}

function onSummon(t) {
  store.currentTeacher = t.subject
  send(t.prompt)
}

function onClearTeacher() {
  store.currentTeacher = null
}

async function onAttach(files) {
  try {
    const res = await api.upload(Array.from(files))
    const n = res.uploaded || 0
    message.success(`已上传 ${n} 篇文档，已加入知识库`)
  } catch (e) {
    message.error('文档上传失败')
  }
}

function onReview(decision) {
  const bot = botMsg.value
  if (!bot || !bot.review) return
  const actions = bot.review.actions || []
  const ids = actions.map((a) => a.id)
  const review_decision =
    decision === 'approve_all'
      ? { decision, approved: ids, rejected: [] }
      : { decision, approved: [], rejected: ids }
  bot.review = null
  bot.streaming = true
  streaming.value = true
  scrollToBottom()
  const payload = {
    session_id: store.currentSessionId,
    review_decision,
    model: store.settings.model,
    persona: store.currentTeacher || store.settings.persona,
    style: store.settings.style
  }
  streamChat(payload, {
    onEvent: (ev) => handleEvent(ev, bot),
    onError: (msg) => {
      bot.streaming = false
      streaming.value = false
      message.error(msg || '审批处理失败')
    }
  })
}

function cycleTheme() {
  const next = themeMode.value === 'light' ? 'dark' : themeMode.value === 'dark' ? 'system' : 'light'
  setTheme(next)
}

function onSuggestion(text) {
  send(text)
}

onMounted(loadConversation)
watch(
  () => store.loadNonce,
  () => loadConversation()
)
</script>

<template>
  <div class="chat-view">
    <!-- 顶部条 -->
    <header class="chat-header">
      <div class="ch-title">{{ title }}</div>
      <button class="theme-toggle" :title="`主题：${themeMode}`" @click="cycleTheme">
        <n-icon size="19"><component :is="themeIcon" /></n-icon>
      </button>
    </header>

    <!-- 消息区 -->
    <div ref="scrollRef" class="chat-scroll">
      <div v-if="loadingHist" class="hist-skeleton">
        <div v-for="n in 3" :key="n" class="sk-row" :class="{ right: n % 2 === 0 }">
          <div class="ma-skeleton" style="width: 60%; height: 60px; border-radius: 18px"></div>
        </div>
      </div>

      <template v-else-if="messages.length">
        <MessageBubble
          v-for="(m, i) in messages"
          :key="i"
          :message="m"
          :time="m.time"
          @review="onReview"
        />
      </template>

      <!-- 空状态 -->
      <div v-else class="empty-state">
        <div class="empty-avatar"><BotAvatar :size="64" /></div>
        <h2 class="empty-title">我是你的智能学习助手</h2>
        <p class="empty-sub">可以问我任何学科问题，上传资料让我帮你分析，或召唤专属名师。</p>
        <div class="suggest-grid">
          <button v-for="(s, i) in suggestions" :key="i" class="suggest-card" @click="onSuggestion(s.text)">
            <n-icon size="20" color="var(--accent)"><component :is="s.icon" /></n-icon>
            <span>{{ s.text }}</span>
          </button>
        </div>
        <div class="teacher-hint">
          <n-icon size="15"><SchoolOutline /></n-icon>
          <span>提示：在下方选择学科老师，可获得针对性的辅导</span>
        </div>
      </div>
    </div>

    <!-- 合成器 -->
    <div class="chat-footer">
      <Composer
        @send="send"
        @summon="onSummon"
        @clearTeacher="onClearTeacher"
        @attach="onAttach"
      />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-sidebar);
  backdrop-filter: saturate(180%) blur(20px);
  flex-shrink: 0;
}
.ch-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.theme-toggle {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 10px;
  background: var(--bg-hover);
  color: var(--text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.16s;
}
.theme-toggle:hover {
  background: var(--border-strong);
}
.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px 12px;
  min-height: 0;
}
.hist-skeleton {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.sk-row {
  display: flex;
}
.sk-row.right {
  justify-content: flex-end;
}
.empty-state {
  max-width: 680px;
  margin: 4vh auto 0;
  text-align: center;
}
.empty-avatar {
  display: inline-flex;
  padding: 10px;
  border-radius: 50%;
  background: var(--bg-elevated);
  box-shadow: var(--shadow-md);
  margin-bottom: 18px;
}
.empty-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 0 0 8px;
}
.empty-sub {
  font-size: 15px;
  color: var(--text-secondary);
  margin: 0 auto 28px;
  max-width: 460px;
  line-height: 1.6;
}
.suggest-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  text-align: left;
}
.suggest-card {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 15px 16px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: var(--bg-elevated);
  color: var(--text);
  font-size: 14px;
  cursor: pointer;
  transition: transform 0.16s, box-shadow 0.16s, border-color 0.16s;
}
.suggest-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--accent);
}
.teacher-hint {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-top: 24px;
  font-size: 12.5px;
  color: var(--text-tertiary);
}
.chat-footer {
  flex-shrink: 0;
  padding: 12px 20px 18px;
  border-top: 1px solid var(--border);
  background: var(--bg);
}

@media (max-width: 860px) {
  .suggest-grid {
    grid-template-columns: 1fr;
  }
  .chat-scroll {
    padding-top: 56px;
  }
}
</style>
