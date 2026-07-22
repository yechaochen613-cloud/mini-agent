<script setup>
import { computed, ref } from 'vue'
import { NIcon } from 'naive-ui'
import {
  ConstructOutline,
  BulbOutline,
  ChevronDownOutline,
  ShieldCheckmarkOutline,
  BanOutline,
  AlertCircleOutline
} from '@vicons/ionicons5'
import { renderMarkdown } from '../markdown.js'
import BotAvatar from './BotAvatar.vue'
import StepsTimeline from './StepsTimeline.vue'

const props = defineProps({
  message: { type: Object, required: true },
  time: { type: String, default: '' }
})

const emit = defineEmits(['review'])

const showSteps = ref(false)
const showReason = ref(false)

function reviewActions() {
  const r = props.message.review
  if (!r || !Array.isArray(r.actions)) return []
  return r.actions
}
function argStr(args) {
  if (!args) return ''
  try {
    const s = JSON.stringify(args)
    return s.length > 90 ? s.slice(0, 90) + '…' : s
  } catch (e) {
    return ''
  }
}

const rendered = computed(() => renderMarkdown(props.message.text || ''))
const reasonRendered = computed(() => renderMarkdown(props.message.reasoning || ''))
const hasSteps = computed(() => (props.message.steps || []).length > 0)
const isEmpty = computed(() => !props.message.text && !hasSteps.value && !(props.message.reasoning))
</script>

<template>
  <!-- 用户 -->
  <div v-if="message.role === 'user'" class="msg user">
    <div class="bubble user-bubble">{{ message.text }}</div>
  </div>

  <!-- 助手 -->
  <div v-else class="msg bot" v-motion="{
    initial: { opacity: 0, y: 12 },
    enter: { opacity: 1, y: 0, transition: { duration: 320, ease: 'easeOut' } }
  }">
    <div class="avatar"><BotAvatar :size="34" /></div>
    <div class="msg-col">
      <div class="msg-head">
        <span class="model-badge"><span class="mb-dot"></span>智伴私教</span>
        <span class="msg-time">{{ time }}</span>
      </div>
      <div class="bubble bot-bubble">
        <!-- 思考过程 -->
        <div v-if="message.reasoning" class="reason-block">
          <button class="collapse-head" @click="showReason = !showReason">
            <n-icon size="15" color="var(--warning)"><BulbOutline /></n-icon>
            <span>思考过程</span>
            <n-icon size="14" class="caret" :class="{ open: showReason }"><ChevronDownOutline /></n-icon>
          </button>
          <div v-show="showReason" class="reason-body md" v-html="reasonRendered"></div>
        </div>

        <!-- 类型中（空内容） -->
        <div v-if="isEmpty && message.streaming" class="typing">
          <span></span><span></span><span></span>
        </div>

        <!-- 正文 -->
        <div v-if="message.text" class="md" v-html="rendered"></div>

        <!-- 执行步骤 -->
        <div v-if="hasSteps" class="steps-block">
          <button class="collapse-head" @click="showSteps = !showSteps">
            <n-icon size="15" color="var(--accent)"><ConstructOutline /></n-icon>
            <span>执行步骤</span>
            <span class="step-count">{{ message.steps.length }}</span>
            <n-icon size="14" class="caret" :class="{ open: showSteps }"><ChevronDownOutline /></n-icon>
          </button>
          <div v-show="showSteps" class="steps-body">
            <StepsTimeline :steps="message.steps" />
          </div>
        </div>

        <!-- 人工审批 -->
        <div v-if="message.review" class="review-block">
          <div class="review-head">
            <n-icon size="16" color="var(--warning)"><AlertCircleOutline /></n-icon>
            <span>需要你的审批</span>
          </div>
          <div v-for="(a, i) in reviewActions()" :key="i" class="review-action">
            <span class="ra-tool">{{ a.tool }}</span>
            <span class="ra-args">{{ argStr(a.args) }}</span>
          </div>
          <div class="review-btns">
            <button class="rb approve" @click="emit('review', 'approve_all')">
              <n-icon size="15"><ShieldCheckmarkOutline /></n-icon> 全部通过
            </button>
            <button class="rb reject" @click="emit('review', 'reject_all')">
              <n-icon size="15"><BanOutline /></n-icon> 全部拒绝
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg {
  display: flex;
  gap: 12px;
  max-width: 760px;
  margin: 0 auto 22px;
  width: 100%;
}
.msg.user {
  justify-content: flex-end;
}
.avatar {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  margin-top: 22px;
}
.msg-col {
  min-width: 0;
  flex: 1;
}
.msg.user .msg-col {
  flex: 0 1 auto;
  display: flex;
  justify-content: flex-end;
}
.msg-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.mb-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
}
.msg-time {
  font-size: 11px;
  color: var(--text-tertiary);
}
.bubble {
  border-radius: 18px;
  padding: 13px 17px;
  font-size: 15px;
  line-height: 1.7;
}
.user-bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 6px;
  max-width: 80%;
  white-space: pre-wrap;
  word-break: break-word;
}
.bot-bubble {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-bottom-left-radius: 6px;
  box-shadow: var(--shadow-sm);
  width: 100%;
}
.collapse-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 0;
}
.step-count {
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 20px;
  padding: 0 8px;
  font-size: 11px;
}
.caret {
  transition: transform 0.2s;
}
.caret.open {
  transform: rotate(180deg);
}
.reason-block {
  margin-bottom: 10px;
  border-left: 3px solid var(--warning);
  background: rgba(255, 159, 10, 0.08);
  border-radius: 10px;
  padding: 8px 12px;
}
.reason-body {
  margin-top: 6px;
  font-size: 13.5px;
  color: var(--text-secondary);
}
.reason-body :deep(p) {
  margin: 0 0 6px;
}
.typing {
  display: inline-flex;
  gap: 5px;
  padding: 4px 0;
}
.typing span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: blink 1.3s infinite ease-in-out;
}
.typing span:nth-child(2) {
  animation-delay: 0.2s;
}
.typing span:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%,
  60%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
.review-block {
  margin-top: 12px;
  border: 1px solid rgba(255, 159, 10, 0.4);
  background: rgba(255, 159, 10, 0.06);
  border-radius: 12px;
  padding: 12px 14px;
}
.review-head {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 700;
  color: var(--warning);
  margin-bottom: 8px;
}
.review-action {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: 12.5px;
  padding: 4px 0;
  border-top: 1px solid var(--border);
}
.ra-tool {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-weight: 600;
  color: var(--text);
}
.ra-args {
  color: var(--text-secondary);
  word-break: break-all;
}
.review-btns {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.rb {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  border-radius: 11px;
  border: none;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.15s, transform 0.12s;
}
.rb:active {
  transform: scale(0.98);
}
.rb.approve {
  background: var(--success);
  color: #fff;
}
.rb.reject {
  background: var(--bg-hover);
  color: var(--text-secondary);
}
.rb:hover {
  filter: brightness(1.05);
}
</style>
