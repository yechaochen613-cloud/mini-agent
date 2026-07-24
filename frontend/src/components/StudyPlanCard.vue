<script setup>
import { computed } from 'vue'
import { NTag } from 'naive-ui'

const props = defineProps({
  plan: { type: [Object, String], default: null }
})

// 兼容两套可能的 schema：
// 我们后端实际：{ goal, days, focus[], schedule[{day, theme, tasks[]}], tips[] }
// 指南假设：    { goal, total_days, days[{day, phase, topic, knowledge_points[], exercises[]}], advice }
const isObj = computed(() => props.plan && typeof props.plan === 'object')

const goal = computed(() => (isObj.value ? props.plan.goal : ''))
const days = computed(() => {
  if (!isObj.value) return 0
  return props.plan.days || props.plan.total_days || 0
})
const focusList = computed(() => {
  if (!isObj.value) return []
  return props.plan.focus || props.plan.focus_points || []
})
const schedule = computed(() => {
  if (!isObj.value) return []
  return props.plan.schedule || props.plan.days || []
})
const tips = computed(() => {
  if (!isObj.value) return []
  if (Array.isArray(props.plan.tips)) return props.plan.tips
  if (props.plan.advice) return [props.plan.advice]
  return []
})
const rawText = computed(() =>
  typeof props.plan === 'string' ? props.plan : JSON.stringify(props.plan, null, 2)
)

function dayNum(d) {
  return d.day ?? d.day_index ?? ''
}
function dayTitle(d) {
  return d.theme || d.topic || d.phase || (dayNum(d) ? `第 ${dayNum(d)} 天` : '当日安排')
}
function dayTasks(d) {
  return (
    d.tasks ||
    d.knowledge_points ||
    d.exercises ||
    (d.content ? [d.content] : []) ||
    []
  ).filter(Boolean)
}
</script>

<template>
  <div class="sp">
    <!-- 目标摘要 -->
    <div v-if="goal" class="sp-goal">
      <span class="sp-goal-label">总目标</span>
      <span class="sp-goal-text">{{ goal }}</span>
      <span v-if="days" class="sp-days">共 {{ days }} 天</span>
    </div>

    <!-- 重点薄弱点 -->
    <div v-if="focusList.length" class="sp-focus">
      <span class="sp-focus-label">重点薄弱点</span>
      <NTag v-for="f in focusList" :key="f" size="small" :bordered="false" type="warning" round>
        {{ f }}
      </NTag>
    </div>

    <!-- 时间轴 -->
    <div v-if="schedule.length" class="sp-timeline">
      <div v-for="(d, i) in schedule" :key="i" class="sp-day">
        <div class="sp-node">
          <span class="sp-dot">{{ dayNum(d) }}</span>
        </div>
        <div class="sp-card">
          <div class="sp-card-head">{{ dayTitle(d) }}</div>
          <ul v-if="dayTasks(d).length" class="sp-tasks">
            <li v-for="(t, j) in dayTasks(d)" :key="j">{{ t }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- 陪伴建议 -->
    <div v-if="tips.length" class="sp-tips">
      <div class="sp-tips-label">陪伴建议</div>
      <ul>
        <li v-for="(t, i) in tips" :key="i">{{ t }}</li>
      </ul>
    </div>

    <!-- 兜底：未知结构直接展示原文 -->
    <pre v-if="!goal && !schedule.length && !tips.length" class="sp-raw">{{ rawText }}</pre>
  </div>
</template>

<style scoped>
.sp {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.sp-goal {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 14px;
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  border-radius: 10px;
}
.sp-goal-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 0.04em;
}
.sp-goal-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.sp-days {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-tertiary);
}
.sp-focus {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sp-focus-label {
  font-size: 12px;
  color: var(--text-tertiary);
}
.sp-timeline {
  position: relative;
  padding-left: 30px;
}
.sp-timeline::before {
  content: '';
  position: absolute;
  left: 13px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  background: var(--border);
}
.sp-day {
  position: relative;
  margin-bottom: 12px;
}
.sp-node {
  position: absolute;
  left: -30px;
  top: 2px;
}
.sp-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 113, 227, 0.3);
}
.sp-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 11px 14px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.sp-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
}
.sp-card-head {
  font-size: 14px;
  font-weight: 650;
  color: var(--text-primary);
  margin-bottom: 6px;
}
.sp-tasks {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sp-tasks li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.sp-tips {
  padding: 11px 14px;
  background: rgba(64, 132, 255, 0.08);
  border-left: 3px solid #4084ff;
  border-radius: 10px;
}
.sp-tips-label {
  font-size: 12px;
  font-weight: 700;
  color: #4084ff;
  margin-bottom: 5px;
}
.sp-tips ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sp-tips li {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.sp-raw {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-tertiary);
}
</style>
