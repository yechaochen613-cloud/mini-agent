<script setup>
import { ref, nextTick, computed, onBeforeUnmount } from 'vue'
import { NIcon, useMessage } from 'naive-ui'
import { AttachOutline, SendOutline, CloseOutline, MicOutline } from '@vicons/ionicons5'
import { findTeacher } from '../teachers.js'
import { store } from '../store.js'
import { api } from '../api.js'

const emit = defineEmits(['send', 'summon', 'clearTeacher', 'attach'])
const message = useMessage()

const text = ref('')
const textareaRef = ref(null)
const fileInputRef = ref(null)
const sending = ref(false)

// 语音输入状态
const recording = ref(false)
let recognition = null
let mediaRecorder = null
let audioChunks = []

const activeTeacher = computed(() =>
  store.currentTeacher ? findTeacher(store.currentTeacher) : null
)

function autoGrow() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 180) + 'px'
}

function appendText(s) {
  if (!s) return
  const t = text.value
  text.value = t && !/\s$/.test(t) ? t + ' ' + s : t + s
  nextTick(autoGrow)
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

// ===== 语音输入（Web Speech API，回退到录音 + /stt） =====
function toggleVoice() {
  if (recording.value) stopVoice()
  else startVoice()
}

function startVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (SR) {
    try {
      recognition = new SR()
      recognition.lang = 'zh-CN'
      recognition.continuous = true
      recognition.interimResults = true
      recognition.onresult = (e) => {
        let finalStr = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i]
          if (r.isFinal) finalStr += r[0].transcript
        }
        if (finalStr) appendText(finalStr)
      }
      recognition.onerror = (ev) => {
        stopVoice()
        message.error('语音识别出错：' + (ev?.error || '未知错误'))
      }
      recognition.onend = () => {
        recording.value = false
      }
      recognition.start()
      recording.value = true
      return
    } catch (e) {
      // 落到录音回退
    }
  }
  fallbackRecord()
}

async function fallbackRecord() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    message.warning('当前浏览器不支持语音输入')
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream)
    audioChunks = []
    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size) audioChunks.push(e.data)
    }
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      if (!blob.size) return
      try {
        const res = await api.stt(blob)
        if (res && res.text) appendText(res.text)
        else message.warning('未识别到语音内容')
      } catch (err) {
        const detail = err?.response?.data?.detail || err?.message || '请检查网络'
        message.error('语音识别失败：' + detail)
      }
    }
    mediaRecorder.start()
    recording.value = true
  } catch (e) {
    message.error('无法访问麦克风：' + (e?.message || e))
  }
}

function stopVoice() {
  if (recognition) {
    try {
      recognition.stop()
    } catch (e) {
      /* ignore */
    }
    recognition = null
  }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try {
      mediaRecorder.stop()
    } catch (e) {
      /* ignore */
    }
  }
  recording.value = false
}

onBeforeUnmount(stopVoice)
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
      <button
        class="mic-btn"
        :class="{ recording }"
        :title="recording ? '点击结束录音' : '语音输入'"
        :aria-label="recording ? '结束录音' : '语音输入'"
        @click="toggleVoice"
      >
        <span v-if="recording" class="eq" aria-hidden="true"><i></i><i></i><i></i></span>
        <n-icon v-else size="20"><MicOutline /></n-icon>
      </button>
      <textarea
        ref="textareaRef"
        v-model="text"
        class="composer-input"
        rows="1"
        placeholder="问我一道题，或先告诉我你的年级和想学的科目…（也可点麦克风语音输入）"
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
.mic-btn,
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
.mic-btn {
  background: transparent;
  color: var(--text-secondary);
}
.mic-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.mic-btn.recording {
  background: var(--accent);
  color: #fff;
  animation: micPulse 1.1s ease-in-out infinite;
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

/* 录音中脉冲 + 声波 */
@keyframes micPulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 var(--accent-soft);
  }
  50% {
    box-shadow: 0 0 0 9px rgba(0, 113, 227, 0);
  }
}
.eq {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 2.5px;
  height: 20px;
}
.eq i {
  width: 3px;
  height: 6px;
  background: #fff;
  border-radius: 2px;
  animation: eqbar 0.8s ease-in-out infinite;
}
.eq i:nth-child(2) {
  animation-delay: 0.18s;
}
.eq i:nth-child(3) {
  animation-delay: 0.36s;
}
@keyframes eqbar {
  0%,
  100% {
    height: 5px;
  }
  50% {
    height: 17px;
  }
}
</style>
