<script setup>
import { ref, nextTick, computed } from 'vue'
import { NIcon } from 'naive-ui'
import { AttachOutline, SendOutline, CloseOutline } from '@vicons/ionicons5'
import { findTeacher } from '../teachers.js'
import { store } from '../store.js'

const emit = defineEmits(['send', 'summon', 'clearTeacher', 'attach'])

const text = ref('')
const textareaRef = ref(null)
const fileInputRef = ref(null)
const sending = ref(false)

const activeTeacher = computed(() =>
  store.currentTeacher ? findTeacher(store.currentTeacher) : null
)

function autoGrow() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

function submit() {
  const v = text.value.trim()
  if (!v || sending.value) return
  emit('send', v)
  text.value = ''
  nextTick(autoGrow)
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

function onPickFiles(e) {
  const files = e.target.files
  if (files && files.length) emit('attach', files)
  e.target.value = ''
}

function triggerAttach() {
  fileInputRef.value?.click()
}
</script>

<template>
  <div class="composer-wrap">
    <!-- 已选学科老师 -->
    <div v-if="activeTeacher" class="teacher-bar">
      <div class="tc-chip active" :style="{ '--c1': activeTeacher.color1, '--c2': activeTeacher.color2 }">
        <n-icon size="16"><component :is="activeTeacher.icon" /></n-icon>
        <span>{{ activeTeacher.subject }}老师</span>
        <button class="tc-exit" @click="emit('clearTeacher')" aria-label="退出学科">
          <n-icon size="13"><CloseOutline /></n-icon>
        </button>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="composer">
      <button class="attach-btn" title="上传文档" @click="triggerAttach">
        <n-icon size="20"><AttachOutline /></n-icon>
      </button>
      <textarea
        ref="textareaRef"
        v-model="text"
        class="composer-input"
        rows="1"
        placeholder="问我一道题，或先告诉我你的年级和想学的科目…"
        @input="autoGrow"
        @keydown="onKeydown"
      ></textarea>
      <button class="send-btn" :disabled="!text.trim()" @click="submit">
        <n-icon size="20"><SendOutline /></n-icon>
      </button>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        class="hidden-file"
        @change="onPickFiles"
      />
    </div>
  </div>
</template>

<style scoped>
.composer-wrap {
  width: 100%;
  max-width: 820px;
  margin: 0 auto;
}
.teacher-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
  justify-content: flex-start;
}
.tc-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: linear-gradient(135deg, var(--c1, #eef), var(--c2, #e7e7ff));
  color: #1d1d1f;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.tc-chip:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
.tc-chip.active {
  padding-right: 8px;
}
.tc-exit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  margin-left: 2px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.12);
  color: #1d1d1f;
  cursor: pointer;
}
.tc-exit:hover {
  background: rgba(0, 0, 0, 0.22);
}
.composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 8px 8px 8px 12px;
  backdrop-filter: blur(12px);
  box-shadow: var(--shadow-md);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.composer:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.attach-btn,
.send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.18s, transform 0.15s, opacity 0.18s;
}
.attach-btn {
  background: transparent;
  color: var(--text-secondary);
}
.attach-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.send-btn {
  background: var(--accent);
  color: #fff;
}
.send-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.send-btn:active:not(:disabled) {
  transform: scale(0.94);
}
.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.composer-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--text);
  font-family: inherit;
  font-size: 15px;
  line-height: 1.5;
  padding: 9px 4px;
  max-height: 180px;
}
.composer-input::placeholder {
  color: var(--text-tertiary);
}
.hidden-file {
  display: none;
}
</style>
