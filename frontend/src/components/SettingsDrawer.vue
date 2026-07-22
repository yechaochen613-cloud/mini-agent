<script setup>
import { ref, watch } from 'vue'
import {
  useMessage,
  useDialog,
  NDrawer,
  NDrawerContent,
  NIcon,
  NInput,
  NButton,
  NRadioGroup,
  NRadioButton,
  NDivider,
  NTag
} from 'naive-ui'
import { PersonOutline, TrashOutline, SaveOutline } from '@vicons/ionicons5'
import { store, setSetting } from '../store.js'
import { api } from '../api.js'
import { themeMode, setTheme } from '../theme.js'

const props = defineProps({ show: { type: Boolean, default: false } })
const emit = defineEmits(['update:show'])

const message = useMessage()
const dialog = useDialog()

const accountName = ref('')
const savingName = ref(false)

const models = [
  { label: '标准 1.0', value: '1.0' },
  { label: '轻量', value: 'lite' },
  { label: '专业', value: 'pro' }
]
const personas = [
  { label: '家教模式', value: 'tutor' },
  { label: '严谨', value: 'strict' },
  { label: '幽默', value: 'funny' },
  { label: '温柔', value: 'gentle' }
]
const styles = [
  { label: '简洁', value: 'concise' },
  { label: '详细', value: 'detailed' },
  { label: '分步', value: 'step' },
  { label: '举例', value: 'example' }
]
const themes = [
  { label: '浅色', value: 'light' },
  { label: '深色', value: 'dark' },
  { label: '跟随系统', value: 'system' }
]

watch(
  () => props.show,
  async (v) => {
    if (v) {
      try {
        const a = await api.account()
        accountName.value = a.name || ''
      } catch (e) {
        accountName.value = ''
      }
    }
  }
)

function close() {
  emit('update:show', false)
}

async function saveName() {
  if (!accountName.value.trim()) {
    message.warning('名字不能为空')
    return
  }
  savingName.value = true
  try {
    await api.setAccount(accountName.value.trim())
    message.success('已保存')
  } catch (e) {
    message.error('保存失败')
  } finally {
    savingName.value = false
  }
}

function clearMemory() {
  dialog.warning({
    title: '清空长期记忆',
    content: '这将删除助手记住的你的偏好与历史上下文，确定继续吗？',
    positiveText: '清空',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.clearMemory()
        message.success('长期记忆已清空')
      } catch (e) {
        message.error('操作失败')
      }
    }
  })
}
</script>

<template>
  <n-drawer :show="show" :width="360" placement="right" @update:show="emit('update:show', $event)">
    <n-drawer-content title="设置" :native-scrollbar="false">
      <div class="settings">
        <!-- 账户 -->
        <section class="sec">
          <div class="sec-title"><n-icon size="16"><PersonOutline /></n-icon> 账户</div>
          <div class="row">
            <n-input v-model:value="accountName" placeholder="你的昵称" size="medium" @keyup.enter="saveName" />
            <n-button type="primary" :loading="savingName" @click="saveName">
              <template #icon><n-icon :component="SaveOutline" /></template>
              保存
            </n-button>
          </div>
          <div class="hint">当前登录：{{ store.user?.username }}</div>
        </section>

        <n-divider />

        <!-- 模型 -->
        <section class="sec">
          <div class="sec-title">模型档位</div>
          <n-radio-group
            :value="store.settings.model"
            @update:value="(v) => setSetting('model', v)"
            size="small"
          >
            <n-radio-button v-for="m in models" :key="m.value" :value="m.value">{{ m.label }}</n-radio-button>
          </n-radio-group>
        </section>

        <n-divider />

        <!-- 人设 -->
        <section class="sec">
          <div class="sec-title">回答人设</div>
          <n-radio-group
            :value="store.settings.persona"
            @update:value="(v) => setSetting('persona', v)"
            size="small"
          >
            <n-radio-button v-for="p in personas" :key="p.value" :value="p.value">{{ p.label }}</n-radio-button>
          </n-radio-group>
        </section>

        <n-divider />

        <!-- 风格 -->
        <section class="sec">
          <div class="sec-title">回答风格</div>
          <n-radio-group
            :value="store.settings.style"
            @update:value="(v) => setSetting('style', v)"
            size="small"
          >
            <n-radio-button v-for="s in styles" :key="s.value" :value="s.value">{{ s.label }}</n-radio-button>
          </n-radio-group>
        </section>

        <n-divider />

        <!-- 主题 -->
        <section class="sec">
          <div class="sec-title">外观主题</div>
          <n-radio-group :value="themeMode" @update:value="setTheme" size="small">
            <n-radio-button v-for="t in themes" :key="t.value" :value="t.value">{{ t.label }}</n-radio-button>
          </n-radio-group>
        </section>

        <n-divider />

        <!-- 记忆 -->
        <section class="sec">
          <div class="sec-title">记忆管理</div>
          <n-button block strong secondary type="error" @click="clearMemory">
            <template #icon><n-icon :component="TrashOutline" /></template>
            清空长期记忆
          </n-button>
        </section>

        <div class="foot">
          <n-tag :bordered="false" type="default" size="small">Mini Agent · 智能学习助手</n-tag>
        </div>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
}
.sec-title {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  margin-bottom: 11px;
}
.row {
  display: flex;
  gap: 8px;
}
.hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 8px;
}
.foot {
  margin-top: 18px;
  text-align: center;
}
</style>
