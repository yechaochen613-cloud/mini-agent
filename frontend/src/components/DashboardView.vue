<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage, NIcon, NGrid, NGridItem, NCard, NButton, NSpin } from 'naive-ui'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  RadarChart,
  BarChart,
  PieChart,
  LineChart
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import {
  BarChartOutline,
  BookmarksOutline,
  ReaderOutline,
  AlarmOutline,
  SchoolOutline,
  AddOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'
import { isDark } from '../theme.js'
import StudyPlanCard from './StudyPlanCard.vue'
import ProfileCard from './ProfileCard.vue'

use([
  CanvasRenderer,
  RadarChart,
  BarChart,
  PieChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const message = useMessage()

const loading = ref(true)
const stats = ref({ wrong: 0, due: 0, subjects: 0, favorites: 0 })
const bySubject = ref([]) // {subject, count, mastery}
const due = ref(0)
const plan = ref(null)
const planLoading = ref(false)
const profile = ref({})

const axisColor = computed(() => (isDark.value ? '#86868b' : '#6e6e73'))
const splitColor = computed(() => (isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'))
const accent = computed(() => (isDark.value ? '#0a84ff' : '#0071e3'))

const radarOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {},
  radar: {
    radius: '66%',
    indicator: bySubject.value.map((s) => ({ name: s.subject, max: 5 })),
    axisName: { color: axisColor.value, fontSize: 12 },
    splitLine: { lineStyle: { color: splitColor.value } },
    splitArea: { areaStyle: { color: ['transparent', 'transparent'] } },
    axisLine: { lineStyle: { color: splitColor.value } }
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: bySubject.value.map((s) => s.mastery),
          name: '掌握度',
          areaStyle: { color: accent.value + '33' },
          lineStyle: { color: accent.value, width: 2 },
          itemStyle: { color: accent.value }
        }
      ]
    }
  ]
}))

const barOption = computed(() => ({
  backgroundColor: 'transparent',
  grid: { left: 8, right: 14, top: 20, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: bySubject.value.map((s) => s.subject),
    axisLabel: { color: axisColor.value, fontSize: 11 },
    axisLine: { lineStyle: { color: splitColor.value } }
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: axisColor.value },
    splitLine: { lineStyle: { color: splitColor.value } }
  },
  series: [
    {
      type: 'bar',
      data: bySubject.value.map((s) => s.count),
      itemStyle: { color: accent.value, borderRadius: [6, 6, 0, 0] },
      barWidth: '52%'
    }
  ]
}))

const pieOption = computed(() => {
  const total = stats.value.wrong || 0
  const d = due.value || 0
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: axisColor.value }, icon: 'circle' },
    series: [
      {
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: false,
        label: { show: false },
        data: [
          { value: d, name: '待复习', itemStyle: { color: '#ff9f0a' } },
          { value: Math.max(total - d, 0), name: '已安排', itemStyle: { color: accent.value } }
        ]
      }
    ]
  }
})

const statCards = computed(() => [
  { label: '错题总数', value: stats.value.wrong, icon: BarChartOutline },
  { label: '待复习', value: stats.value.due, icon: AlarmOutline },
  { label: '覆盖学科', value: stats.value.subjects, icon: SchoolOutline },
  { label: '收藏', value: stats.value.favorites, icon: BookmarksOutline }
])

async function load() {
  loading.value = true
  try {
    const [wq, dueRes, fav, pRes] = await Promise.all([
      api.wrongQuestions(),
      api.dueWrongQuestions(),
      api.favorites(),
      api.profile()
    ])
    const list = wq.wrong_questions || []
    stats.value.wrong = list.length
    due.value = dueRes.count || 0
    stats.value.due = dueRes.count || 0
    stats.value.favorites = (fav.favorites || []).length
    profile.value = pRes.profile || {}

    const map = {}
    list.forEach((q) => {
      const s = q.subject || '其他'
      if (!map[s]) map[s] = { subject: s, count: 0, sum: 0, n: 0 }
      map[s].count++
      map[s].sum += Number(q.mastery || 0)
      map[s].n++
    })
    const arr = Object.values(map).map((m) => ({
      subject: m.subject,
      count: m.count,
      mastery: Math.round((m.sum / m.n) * 10) / 10 || 0
    }))
    bySubject.value = arr
    stats.value.subjects = arr.length
  } catch (e) {
    message.error('看板数据加载失败')
  } finally {
    loading.value = false
  }
}

async function genPlan() {
  planLoading.value = true
  try {
    const res = await api.studyPlan('巩固薄弱学科，提升综合成绩', 14)
    plan.value = res.plan
  } catch (e) {
    message.error('生成计划失败')
  } finally {
    planLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="panel">
    <header class="panel-head">
      <div class="ph-icon"><n-icon size="22" color="var(--accent)"><ReaderOutline /></n-icon></div>
      <div>
        <h1 class="ph-title">学情看板</h1>
        <p class="ph-sub">你的学习数据一目了然</p>
      </div>
    </header>

    <n-spin :show="loading">
      <!-- 学情档案 -->
      <ProfileCard :profile="profile" @updated="profile = $event" class="pc-slot" />

      <!-- 统计卡 -->
      <n-grid cols="4" :x-gap="14" :y-gap="14" responsive="screen" item-responsive>
        <n-grid-item v-for="(c, i) in statCards" :key="i" span="4 m:1">
          <div class="stat-card">
            <div class="stat-ic"><n-icon size="18"><component :is="c.icon" /></n-icon></div>
            <div class="stat-val">{{ c.value }}</div>
            <div class="stat-label">{{ c.label }}</div>
          </div>
        </n-grid-item>
      </n-grid>

      <!-- 图表区 -->
      <n-grid cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive class="charts">
        <n-grid-item span="2 m:1">
          <n-card title="学科掌握度" :bordered="true">
            <v-chart :option="radarOption" autoresize style="height: 280px" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="错题分布" :bordered="true">
            <v-chart :option="barOption" autoresize style="height: 280px" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="复习安排" :bordered="true">
            <v-chart :option="pieOption" autoresize style="height: 280px" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="学习计划" :bordered="true">
            <template #header-extra>
              <n-button size="small" type="primary" :loading="planLoading" @click="genPlan">
                <template #icon><n-icon :component="AddOutline" /></template>
                生成
              </n-button>
            </template>
            <StudyPlanCard v-if="plan" :plan="plan" />
            <div v-else class="plan-empty">点击「生成」基于学情档案制定专属提升计划</div>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-spin>
  </div>
</template>

<style scoped>
.panel {
  height: 100%;
  overflow-y: auto;
  padding: 32px 36px 48px;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}
.ph-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: var(--accent-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ph-title {
  margin: 0;
  font-size: 23px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.ph-sub {
  margin: 3px 0 0;
  font-size: 14px;
  color: var(--text-tertiary);
}
.stat-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 18px;
  box-shadow: var(--shadow-sm);
}
.stat-ic {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  background: var(--accent-soft);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}
.stat-val {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
}
.stat-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-top: 6px;
}
.charts {
  margin-top: 16px;
}
.pc-slot {
  margin-bottom: 16px;
}
.plan-empty {
  font-size: 13px;
  color: var(--text-tertiary);
  padding: 20px 0;
  text-align: center;
}

@media (max-width: 860px) {
  .panel {
    padding: 64px 16px 40px;
  }
}
</style>
