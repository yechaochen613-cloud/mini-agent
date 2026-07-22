<script setup>
import { computed } from 'vue'
import { useDialog, NIcon, NPopconfirm } from 'naive-ui'
import {
  SchoolOutline,
  ChatbubbleOutline,
  PeopleOutline,
  BarChartOutline,
  LibraryOutline,
  CreateOutline,
  SettingsOutline,
  LogOutOutline,
  TrashOutline,
  TimeOutline
} from '@vicons/ionicons5'
import { store, switchView, openConversation, newChat, refreshConversations } from '../store.js'
import { api } from '../api.js'

const emit = defineEmits(['logout', 'navigate'])

const dialog = useDialog()

const navItems = [
  { key: 'chat', label: '对话', icon: ChatbubbleOutline },
  { key: 'teachers', label: '名师', icon: PeopleOutline },
  { key: 'dashboard', label: '学情看板', icon: BarChartOutline },
  { key: 'library', label: '学习库', icon: LibraryOutline }
]

const initial = computed(() => (store.user?.username || '?').slice(0, 1).toUpperCase())

function fmtTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d)) return ''
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `${hh}:${mm}`
  const mo = d.getMonth() + 1
  const day = d.getDate()
  return `${mo}/${day} ${hh}:${mm}`
}

async function onNewChat() {
  newChat()
  emit('navigate')
}

async function onSelect(sid) {
  openConversation(sid)
  emit('navigate')
}

async function onDelete(sid) {
  try {
    await api.deleteConversation(sid)
    if (store.currentSessionId === sid) newChat()
    await refreshConversations()
  } catch (e) {
    /* ignore */
  }
}

function openSettings() {
  store.showSettings = true
  emit('navigate')
}
</script>

<template>
  <div class="side">
    <!-- 品牌 -->
    <div class="brand">
      <div class="brand-logo">
        <n-icon size="22" color="#fff"><SchoolOutline /></n-icon>
      </div>
      <div class="brand-text">
        <div class="brand-name">Mini Agent</div>
        <div class="brand-sub">智能学习助手</div>
      </div>
    </div>

    <!-- 新对话 -->
    <button class="new-chat" @click="onNewChat">
      <n-icon size="18"><CreateOutline /></n-icon>
      <span>新建对话</span>
    </button>

    <!-- 主导航 -->
    <nav class="nav">
      <button
        v-for="item in navItems"
        :key="item.key"
        class="nav-item"
        :class="{ active: store.view === item.key }"
        @click="switchView(item.key); emit('navigate')"
      >
        <n-icon size="19"><component :is="item.icon" /></n-icon>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <!-- 历史对话 -->
    <div class="hist-head">
      <n-icon size="15"><TimeOutline /></n-icon>
      <span>历史对话</span>
    </div>
    <div class="hist-list">
      <template v-if="store.conversationsLoading">
        <div v-for="n in 5" :key="n" class="hist-skel">
          <div class="ma-skeleton" style="height: 14px; width: 70%"></div>
          <div class="ma-skeleton" style="height: 11px; width: 40%; margin-top: 6px"></div>
        </div>
      </template>
      <template v-else-if="store.conversations.length">
        <div
          v-for="c in store.conversations"
          :key="c.id"
          class="hist-item"
          :class="{ active: store.currentSessionId === c.id }"
          @click="onSelect(c.id)"
        >
          <div class="hist-info">
            <div class="hist-title">{{ c.title || '新对话' }}</div>
            <div class="hist-time">{{ fmtTime(c.updated_at) }}</div>
          </div>
          <n-popconfirm
            placement="right"
            message="删除这条对话？"
            @positive-click="onDelete(c.id)"
          >
            <template #trigger>
              <button class="hist-del" @click.stop aria-label="删除">
                <n-icon size="15"><TrashOutline /></n-icon>
              </button>
            </template>
          </n-popconfirm>
        </div>
      </template>
      <div v-else class="hist-empty">还没有对话记录</div>
    </div>

    <!-- 底部用户区 -->
    <div class="side-foot">
      <div class="user-chip" @click="openSettings">
        <div class="avatar">{{ initial }}</div>
        <div class="u-name">{{ store.user?.username }}</div>
      </div>
      <button class="foot-btn" title="设置" @click="openSettings">
        <n-icon size="18"><SettingsOutline /></n-icon>
      </button>
      <button class="foot-btn" title="退出登录" @click="emit('logout')">
        <n-icon size="18"><LogOutOutline /></n-icon>
      </button>
    </div>
  </div>
</template>

<style scoped>
.side {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-sidebar);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  overflow: hidden;
}
.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 6px 8px 14px;
}
.brand-logo {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(135deg, #0071e3, #42a5f5);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 113, 227, 0.35);
}
.brand-name {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: -0.01em;
}
.brand-sub {
  font-size: 11.5px;
  color: var(--text-tertiary);
  margin-top: 1px;
}
.new-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 42px;
  border: none;
  border-radius: 12px;
  background: var(--accent);
  color: #fff;
  font-size: 14.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
}
.new-chat:hover {
  background: var(--accent-hover);
}
.new-chat:active {
  transform: scale(0.98);
}
.nav {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin: 14px 0 8px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  height: 40px;
  padding: 0 11px;
  border: none;
  border-radius: 11px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14.5px;
  cursor: pointer;
  transition: background 0.18s, color 0.18s;
}
.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.hist-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px 11px 8px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}
.hist-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-right: 2px;
  margin-right: -2px;
}
.hist-skel {
  padding: 10px 11px;
}
.hist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 11px;
  border-radius: 11px;
  cursor: pointer;
  transition: background 0.16s;
}
.hist-item:hover {
  background: var(--bg-hover);
}
.hist-item.active {
  background: var(--accent-soft);
}
.hist-info {
  flex: 1;
  min-width: 0;
}
.hist-title {
  font-size: 13.5px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hist-time {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.hist-del {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
}
.hist-item:hover .hist-del {
  display: inline-flex;
}
.hist-del:hover {
  background: rgba(224, 36, 36, 0.12);
  color: var(--danger);
}
.hist-empty {
  padding: 16px 11px;
  font-size: 13px;
  color: var(--text-tertiary);
}
.side-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 6px 4px;
  border-top: 1px solid var(--border);
  margin-top: 8px;
}
.user-chip {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 8px;
  border-radius: 10px;
  cursor: pointer;
  min-width: 0;
}
.user-chip:hover {
  background: var(--bg-hover);
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #8e8e93, #636366);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}
.u-name {
  font-size: 13.5px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.foot-btn {
  width: 34px;
  height: 34px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.16s, color 0.16s;
}
.foot-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}
</style>
