import { reactive } from 'vue'
import { api } from './api.js'

// 轻量全局状态（跨组件共享）
export const store = reactive({
  user: null, // { username, id }
  view: 'chat', // chat | teachers | dashboard | library
  conversations: [],
  conversationsLoading: false,
  currentSessionId: null,
  currentTeacher: null, // 学科名 or null
  showSettings: false,
  loadNonce: 0, // 每次切换/加载会话自增，通知 ChatView 重新拉取
  pendingPrompt: null, // 召唤老师后待发送的提示
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
  store.currentTeacher = teacher.subject
  store.pendingPrompt = teacher.prompt
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
