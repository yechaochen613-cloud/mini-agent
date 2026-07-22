<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NLoadingBarProvider,
  NDrawer,
  NDrawerContent,
  darkTheme,
  NIcon
} from 'naive-ui'
import { MenuOutline } from '@vicons/ionicons5'
import { isDark } from './theme.js'
import { store, refreshConversations } from './store.js'
import { api } from './api.js'
import Sidebar from './components/Sidebar.vue'
import AuthView from './components/AuthView.vue'
import ChatView from './components/ChatView.vue'
import TeacherPanel from './components/TeacherPanel.vue'
import DashboardView from './components/DashboardView.vue'
import LibraryView from './components/LibraryView.vue'
import SettingsDrawer from './components/SettingsDrawer.vue'

const drawerOpen = ref(false)

const themeOverrides = computed(() => ({
  common: {
    primaryColor: isDark.value ? '#0a84ff' : '#0071e3',
    primaryColorHover: isDark.value ? '#409cff' : '#0077ed',
    primaryColorPressed: isDark.value ? '#0a6cf0' : '#006edb',
    primaryColorSuppl: isDark.value ? '#409cff' : '#0077ed',
    borderRadius: '12px',
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "SF Pro Display", "PingFang SC", "Helvetica Neue", Helvetica, Arial, sans-serif'
  }
}))

async function boot() {
  try {
    const me = await api.me()
    store.user = me
    await refreshConversations()
  } catch (e) {
    store.user = null
  }
  // 版本自刷新：后端 DEPLOY_TAG 变化则静默重载
  try {
    const v = await api.version()
    const seen = localStorage.getItem('ma_seen_tag')
    if (seen && seen !== v.deploy_tag) {
      localStorage.setItem('ma_seen_tag', v.deploy_tag)
      location.reload()
      return
    }
    localStorage.setItem('ma_seen_tag', v.deploy_tag)
  } catch (e) {
    /* ignore */
  }
}

function onAuthenticated(user) {
  store.user = user
  refreshConversations()
}

function onLogout() {
  store.user = null
  store.conversations = []
  store.currentSessionId = null
  store.currentTeacher = null
  store.view = 'chat'
}

function openDrawer() {
  drawerOpen.value = true
}
function onNavigate() {
  drawerOpen.value = false
}

onMounted(boot)
</script>

<template>
  <n-config-provider :theme="isDark ? darkTheme : null" :theme-overrides="themeOverrides">
    <n-message-provider placement="top">
      <n-dialog-provider>
        <n-notification-provider>
          <n-loading-bar-provider>
            <!-- 未登录：认证页 -->
            <AuthView v-if="!store.user" @authenticated="onAuthenticated" />

            <!-- 已登录：应用外壳 -->
            <div v-else class="app-shell">
              <!-- 桌面侧栏 -->
              <aside class="sidebar desktop-only">
                <Sidebar @logout="onLogout" @navigate="onNavigate" />
              </aside>

              <!-- 移动端顶部条 + 抽屉 -->
              <div class="mobile-topbar mobile-only">
                <button class="menu-btn" @click="openDrawer" aria-label="菜单">
                  <n-icon size="22"><MenuOutline /></n-icon>
                </button>
                <span class="mobile-title">Mini Agent</span>
              </div>
              <n-drawer v-model:show="drawerOpen" :width="280" placement="left">
                <n-drawer-content :native-scrollbar="false" :body-content-style="{ padding: 0 }">
                  <Sidebar @logout="onLogout" @navigate="onNavigate" />
                </n-drawer-content>
              </n-drawer>

              <!-- 主区域 -->
              <main class="main-area">
                <ChatView v-if="store.view === 'chat'" />
                <TeacherPanel v-else-if="store.view === 'teachers'" />
                <DashboardView v-else-if="store.view === 'dashboard'" />
                <LibraryView v-else-if="store.view === 'library'" />
              </main>
            </div>

            <SettingsDrawer v-model:show="store.showSettings" />
          </n-loading-bar-provider>
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped>
.sidebar {
  width: 284px;
  flex-shrink: 0;
  height: 100vh;
}
.desktop-only {
  display: block;
}
.mobile-only {
  display: none;
}
.mobile-topbar {
  display: none;
}

@media (max-width: 860px) {
  .desktop-only {
    display: none;
  }
  .mobile-only {
    display: flex;
    align-items: center;
    gap: 12px;
    height: 52px;
    padding: 0 14px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
    backdrop-filter: saturate(180%) blur(20px);
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    z-index: 20;
  }
  .app-shell {
    flex-direction: column;
  }
  .main-area {
    padding-top: 52px;
  }
  .menu-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border-radius: 10px;
    border: none;
    background: var(--bg-hover);
    color: var(--text);
    cursor: pointer;
  }
  .mobile-title {
    font-weight: 600;
    font-size: 16px;
  }
}
</style>
