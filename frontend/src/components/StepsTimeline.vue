<script setup>
import { NIcon, NSpin } from 'naive-ui'
import { ConstructOutline, CheckmarkCircleOutline, EllipsisHorizontalOutline } from '@vicons/ionicons5'

const props = defineProps({
  steps: { type: Array, default: () => [] }
})

function argStr(args) {
  if (!args) return ''
  try {
    const s = JSON.stringify(args)
    return s.length > 80 ? s.slice(0, 80) + '…' : s
  } catch (e) {
    return ''
  }
}
function resStr(r) {
  if (r == null) return ''
  const s = typeof r === 'string' ? r : JSON.stringify(r)
  return s.length > 120 ? s.slice(0, 120) + '…' : s
}
</script>

<template>
  <div class="steps">
    <div v-for="(s, i) in steps" :key="i" class="step" :class="s.status">
      <div class="step-rail">
        <div class="step-dot">
          <n-spin v-if="s.status === 'running'" size="small" />
          <n-icon v-else-if="s.status === 'done'" size="15" color="var(--success)">
            <CheckmarkCircleOutline />
          </n-icon>
          <n-icon v-else size="15" color="var(--text-tertiary)">
            <ConstructOutline />
          </n-icon>
        </div>
        <div v-if="i < steps.length - 1" class="step-line"></div>
      </div>
      <div class="step-body">
        <div class="step-name">
          <span class="tool">{{ s.tool }}</span>
          <span v-if="s.status === 'running'" class="step-state running">执行中</span>
          <span v-else-if="s.status === 'done'" class="step-state done">完成</span>
          <span v-else class="step-state"><n-icon size="13"><EllipsisHorizontalOutline /></n-icon></span>
        </div>
        <div v-if="argStr(s.args)" class="step-args">{{ argStr(s.args) }}</div>
        <div v-if="resStr(s.result)" class="step-result">{{ resStr(s.result) }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.steps {
  display: flex;
  flex-direction: column;
  margin-top: 10px;
}
.step {
  display: flex;
  gap: 10px;
}
.step-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}
.step-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
}
.step-line {
  width: 2px;
  flex: 1;
  background: var(--border);
  margin: 2px 0;
  min-height: 14px;
}
.step-body {
  padding-bottom: 12px;
  min-width: 0;
}
.step-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tool {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text);
}
.step-state {
  font-size: 11px;
  color: var(--text-tertiary);
}
.step-state.running {
  color: var(--accent);
}
.step-state.done {
  color: var(--success);
}
.step-args {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 11.5px;
  color: var(--text-secondary);
  margin-top: 3px;
  word-break: break-all;
}
.step-result {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 3px;
  background: var(--bg-hover);
  border-radius: 8px;
  padding: 6px 9px;
  word-break: break-all;
  max-height: 120px;
  overflow: auto;
}
</style>
