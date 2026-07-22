<script setup>
import { ref } from 'vue'
import { useMessage, NIcon, NInput, NButton } from 'naive-ui'
import { SchoolOutline, PersonOutline, LockClosedOutline, LogInOutline } from '@vicons/ionicons5'
import { api } from '../api.js'

const emit = defineEmits(['authenticated'])
const message = useMessage()

const mode = ref('login') // login | register
const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) {
    message.warning('请输入用户名和密码')
    return
  }
  if (password.value.length < 4) {
    message.warning('密码至少 4 位')
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await api.login(username.value.trim(), password.value)
    } else {
      await api.register(username.value.trim(), password.value)
    }
    const me = await api.me()
    message.success(mode.value === 'login' ? '登录成功' : '注册成功')
    emit('authenticated', me)
  } catch (e) {
    const detail = e?.response?.data?.detail || (mode.value === 'login' ? '登录失败' : '注册失败')
    message.error(detail)
  } finally {
    loading.value = false
  }
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
}
</script>

<template>
  <div class="auth-screen">
    <div class="auth-bg"></div>
    <div class="auth-card" v-motion="{
      initial: { opacity: 0, y: 24, scale: 0.98 },
      enter: { opacity: 1, y: 0, scale: 1, transition: { duration: 500, ease: 'easeOut' } }
    }">
      <div class="auth-logo">
        <n-icon size="30" color="#fff"><SchoolOutline /></n-icon>
      </div>
      <h1 class="auth-title">Mini Agent</h1>
      <p class="auth-sub">
        {{ mode === 'login' ? '欢迎回来，继续你的学习之旅' : '创建账户，开启智能辅导' }}
      </p>

      <div class="auth-form">
        <n-input
          v-model:value="username"
          placeholder="用户名"
          size="large"
          round
          clearable
          @keyup.enter="submit"
        >
          <template #prefix>
            <n-icon :component="PersonOutline" />
          </template>
        </n-input>

        <n-input
          v-model:value="password"
          type="password"
          placeholder="密码"
          size="large"
          round
          show-password-on="click"
          @keyup.enter="submit"
        >
          <template #prefix>
            <n-icon :component="LockClosedOutline" />
          </template>
        </n-input>

        <n-button
          type="primary"
          size="large"
          round
          block
          :loading="loading"
          @click="submit"
        >
          <template #icon>
            <n-icon :component="LogInOutline" />
          </template>
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </n-button>
      </div>

      <div class="auth-switch">
        <span>{{ mode === 'login' ? '还没有账户？' : '已有账户？' }}</span>
        <button class="link-btn" @click="toggleMode">
          {{ mode === 'login' ? '立即注册' : '去登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-screen {
  position: relative;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.auth-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(1100px 600px at 12% -10%, rgba(0, 113, 227, 0.16), transparent 60%),
    radial-gradient(900px 500px at 110% 110%, rgba(120, 80, 220, 0.14), transparent 55%),
    var(--bg);
}
.auth-card {
  position: relative;
  width: 380px;
  max-width: calc(100vw - 40px);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 26px;
  box-shadow: var(--shadow-lg);
  padding: 38px 34px 30px;
  text-align: center;
}
.auth-logo {
  width: 60px;
  height: 60px;
  margin: 0 auto 16px;
  border-radius: 18px;
  background: linear-gradient(135deg, #0071e3, #42a5f5);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 22px rgba(0, 113, 227, 0.4);
}
.auth-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.auth-sub {
  margin: 6px 0 26px;
  font-size: 13.5px;
  color: var(--text-tertiary);
}
.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.auth-switch {
  margin-top: 22px;
  font-size: 13.5px;
  color: var(--text-secondary);
}
.link-btn {
  border: none;
  background: none;
  color: var(--accent);
  font-weight: 600;
  cursor: pointer;
  padding: 0 2px;
  font-size: 13.5px;
}
.link-btn:hover {
  text-decoration: underline;
}
</style>
