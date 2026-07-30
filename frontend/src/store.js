import { reactive } from 'vue'
import { api } from './api.js'

// 轻量全局状态（跨组件共享）
export const store = reactive({
  user: null, // { username, id }
  view: 'chat', // chat | teachers | dashboard | library | review | report | docs | diagnosis
  conversations: [],
  conversationsLoading: false,
  currentSessionId: null,
  currentTeacher: null, // 名师 id or null
  showSettings: false,
  showUpgrade: false,
  loadNonce: 0, // 每次切换/加载会话自增，通知 ChatView 重新拉取
  pendingPrompt: null, // 待发送的提示
  teacherGreetingPending: false, // 召唤老师后需要自动插入老师开场白
  settings: {
    model: localStorage.getItem('ma_model') || '1.0',
    persona: localStorage.getItem('ma_persona') || 'tutor',
    style: localStorage.getItem('ma_style') || 'detailed'
  }
})

export function setSetting(key, val) {
  store.settings[key] = val
  localStorage.setItem('ma_' + key, val)
}

export function switchView(v) {
  store.view = v
}

export function openConversation(sid) {
  store.currentSessionId = sid
  store.currentTeacher = null
  store.view = 'chat'
  store.loadNonce++
}

export function newChat() {
  store.currentSessionId = null
  store.currentTeacher = null
  store.view = 'chat'
  store.loadNonce++
}

export function summonTeacher(teacher) {
  // 存名师 id（传给后端 persona 时命中 teachers.py 的具体人设），并开启新对话
  store.currentSessionId = null
  store.currentTeacher = teacher.id
  store.pendingPrompt = null
  store.teacherGreetingPending = true
  store.view = 'chat'
  store.loadNonce++
}

export async function refreshConversations() {
  try {
    store.conversationsLoading = true
    const data = await api.conversations()
    store.conversations = data.conversations || []
  } catch (e) {
    /* 忽略 */
  } finally {
    store.conversationsLoading = false
  }
}
