import axios from 'axios'

const http = axios.create({
  baseURL: '',
  withCredentials: true,
  timeout: 60000
})

function ok(p) {
  return p.then((r) => r.data)
}

export const api = {
  // 认证
  me: () => ok(http.get('/auth/me')),
  login: (username, password) => ok(http.post('/auth/login', { username, password })),
  register: (username, password) => ok(http.post('/auth/register', { username, password })),
  logout: () => ok(http.post('/auth/logout')),

  // 历史会话
  conversations: () => ok(http.get('/conversations')),
  conversation: (sid) => ok(http.get(`/conversations/${sid}`)),
  newConversation: (title) => ok(http.post('/conversations', null, { params: { title } })),
  deleteConversation: (sid) => ok(http.delete(`/conversations/${sid}`)),

  // 文档上传
  upload: (files, url) => {
    const fd = new FormData()
    ;(files || []).forEach((f) => fd.append('files', f))
    if (url) fd.append('url', url)
    return ok(http.post('/upload', fd))
  },

  // 学情档案
  profile: () => ok(http.get('/profile')),
  updateProfile: (p) => ok(http.post('/profile', p)),

  // 错题本
  wrongQuestions: (subject) => ok(http.get('/wrong-questions', { params: { subject } })),
  addWrongQuestion: (p) => ok(http.post('/wrong-questions', p)),
  deleteWrongQuestion: (wid) => ok(http.delete(`/wrong-questions/${wid}`)),
  reviewWrongQuestion: (wid, mastery) => ok(http.patch(`/wrong-questions/${wid}/review`, { mastery })),
  dueWrongQuestions: () => ok(http.get('/wrong-questions/due')),

  // 收藏
  favorites: () => ok(http.get('/favorites')),
  addFavorite: (p) => ok(http.post('/favorites', p)),
  deleteFavorite: (fid) => ok(http.delete(`/favorites/${fid}`)),

  // 试卷 / 计划
  papers: () => ok(http.get('/papers')),
  studyPlan: (goal, days) => ok(http.post('/study-plan', { goal, days })),

  // 账户 / 记忆
  account: () => ok(http.get('/account')),
  setAccount: (name) => ok(http.post('/account', { name })),
  clearMemory: () => ok(http.post('/memory/clear')),

  // 对话（非流式兜底）
  chat: (payload) => ok(http.post('/chat', payload)),

  // 版本
  version: () => ok(http.get('/version'))
}

/**
 * 流式对话（SSE）。payload: {message, session_id, model, persona, style, max_steps}
 * handlers: { onEvent(ev), onError(msg, status), onClose(wasOk) }
 * options: { signal }
 * 返回 { ok: boolean, done: boolean }
 */
export async function streamChat(payload, handlers = {}, options = {}) {
  let resp
  try {
    resp = await fetch('/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
      signal: options.signal
    })
  } catch (e) {
    if (e?.name === 'AbortError') {
      handlers.onClose && handlers.onClose(false)
    } else {
      handlers.onError && handlers.onError('网络异常，请检查连接', 0)
    }
    return { ok: false, done: false }
  }
  if (!resp.ok) {
    let msg = '请求失败'
    try {
      const j = await resp.json()
      msg = j.detail || msg
    } catch (e) {
      /* ignore */
    }
    handlers.onError && handlers.onError(msg, resp.status)
    return { ok: false, done: false }
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let gotDone = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const raw = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const line = raw
          .split('\n')
          .find((l) => l.startsWith('data:'))
        if (!line) continue
        const json = line.slice(5).trim()
        if (!json) continue
        try {
          const ev = JSON.parse(json)
          if (ev.type === 'done') gotDone = true
          handlers.onEvent && handlers.onEvent(ev)
        } catch (e) {
          console.warn('[streamChat] malformed SSE event:', json, e)
        }
      }
    }
  } catch (e) {
    console.warn('[streamChat] read error:', e)
    handlers.onError && handlers.onError('流式连接中断，正在兜底重试…', 0)
    handlers.onClose && handlers.onClose(false)
    return { ok: false, done: gotDone }
  }
  handlers.onClose && handlers.onClose(gotDone)
  return { ok: true, done: gotDone }
}
