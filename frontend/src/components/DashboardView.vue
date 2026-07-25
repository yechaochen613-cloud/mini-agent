<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage, NIcon, NGrid, NGridItem, NCard, NButton, NSpin, NEmpty } from 'naive-ui'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  RadarChart,
  BarChart,
  PieChart,
  LineChart,
  HeatmapChart
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent
} from 'echarts/components'
import {
  BarChartOutline,
  BookmarksOutline,
  ReaderOutline,
  AlarmOutline,
  SchoolOutline,
  AddOutline,
  RefreshOutline
} from '@vicons/ionicons5'
import { api } from '../api.js'
import { switchView } from '../store.js'
import { isDark } from '../theme.js'
import StudyPlanCard from './StudyPlanCard.vue'
import ProfileCard from './ProfileCard.vue'

use([
  CanvasRenderer,
  RadarChart,
  BarChart,
  PieChart,
  LineChart,
  HeatmapChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  VisualMapComponent
])

const message = useMessage()

const loading = ref(true)
const stats = ref({ wrong: 0, due: 0, subjects: 0, favorites: 0 })
const bySubject = ref([]) // {subject, count, mastery}
const allWQ = ref([]) // 完整错题列表（用于趋势/热力计算）
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

const MASTERY_LABELS = ['生疏', '薄弱', '一般', '良好', '扎实', '熟练']

// 近 30 天学习节奏：录入错题数 + 完成复习数（基于真实 created_at / last_review_at）
const lineOption = computed(() => {
  const days = 30
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const labels = []
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    labels.push(`${d.getMonth() + 1}/${d.getDate()}`)
  }
  const added = new Array(days).fill(0)
  const reviewed = new Array(days).fill(0)
  const idxOf = (ts) => {
    if (!ts) return -1
    const dt = new Date(ts * 1000)
    dt.setHours(0, 0, 0, 0)
    const diff = Math.round((today - dt) / 86400000)
    return diff >= 0 && diff < days ? days - 1 - diff : -1
  }
  allWQ.value.forEach((q) => {
    const ca = q.created_at ? new Date(String(q.created_at).replace(' ', 'T')).getTime() / 1000 : 0
    const ai = idxOf(ca)
    if (ai >= 0) added[ai]++
    const ri = idxOf(q.last_review_at)
    if (ri >= 0) reviewed[ri]++
  })
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['录入错题', '完成复习'], bottom: 0, textStyle: { color: axisColor.value }, icon: 'roundRect' },
    grid: { left: 8, right: 16, top: 24, bottom: 36, containLabel: true },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLabel: { color: axisColor.value, fontSize: 10, interval: 4 },
      axisLine: { lineStyle: { color: splitColor.value } }
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: axisColor.value },
      splitLine: { lineStyle: { color: splitColor.value } }
    },
    series: [
      {
        name: '录入错题',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: added,
        itemStyle: { color: accent.value },
        areaStyle: { color: accent.value + '22' },
        lineStyle: { width: 2 }
      },
      {
        name: '完成复习',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: reviewed,
        itemStyle: { color: '#ff9f0a' },
        areaStyle: { color: '#ff9f0a22' },
        lineStyle: { width: 2 }
      }
    ]
  }
})

// 薄弱点分布：学科 × 掌握度等级 矩阵热力图（越红=该学科在该等级错题越多=越薄弱）
const heatLabelColor = computed(() => (isDark.value ? 'rgba(255,255,255,0.92)' : 'rgba(0,0,0,0.72)'))
const heatOption = computed(() => {
  const subs = bySubject.value.map((s) => s.subject)
  const cnt = {}
  let max = 1
  allWQ.value.forEach((q) => {
    const s = q.subject || '其他'
    const lvl = Math.max(0, Math.min(5, Number(q.mastery || 0)))
    const k = `${s}|${lvl}`
    cnt[k] = (cnt[k] || 0) + 1
    if (cnt[k] > max) max = cnt[k]
  })
  const data = []
  subs.forEach((s, yi) => {
    for (let lvl = 0; lvl <= 5; lvl++) {
      data.push([lvl, yi, cnt[`${s}|${lvl}`] || 0])
    }
  })
  return {
    backgroundColor: 'transparent',
    tooltip: {
      position: 'top',
      formatter: (p) => `${subs[p.data[1]]} · ${MASTERY_LABELS[p.data[0]]}：<b>${p.data[2]}</b> 道`
    },
    grid: { left: 8, right: 16, top: 8, bottom: 56, containLabel: true },
    xAxis: {
      type: 'category',
      data: MASTERY_LABELS,
      splitArea: { show: true },
      axisLabel: { color: axisColor.value, fontSize: 11 },
      axisLine: { lineStyle: { color: splitColor.value } }
    },
    yAxis: {
      type: 'category',
      data: subs,
      splitArea: { show: true },
      axisLabel: { color: axisColor.value, fontSize: 11 },
      axisLine: { lineStyle: { color: splitColor.value } }
    },
    visualMap: {
      min: 0,
      max,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 12,
      itemHeight: 88,
      textStyle: { color: axisColor.value },
      inRange: { color: ['#f2f2f7', '#ffd60a', '#ff9f0a', '#ff453a'] }
    },
    series: [
      {
        type: 'heatmap',
        data,
        label: { show: true, color: heatLabelColor.value, fontSize: 11 },
        itemStyle: { borderColor: 'rgba(255,255,255,0.45)', borderWidth: 1, borderRadius: 4 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.3)' } }
      }
    ]
  }
})

// 近 30 天是否有任何录入/复习活动（决定是否显示折线，否则空态）
const hasTrend = computed(() => {
  const t0 = new Date(); t0.setHours(0, 0, 0, 0)
  return allWQ.value.some((q) => {
    const ca = q.created_at ? new Date(String(q.created_at).replace(' ', 'T')).getTime() : 0
    if (ca) {
      const dt = new Date(ca); dt.setHours(0, 0, 0, 0)
      if (Math.round((t0 - dt) / 86400000) < 30) return true
    }
    if (q.last_review_at) {
      const dt = new Date(q.last_review_at * 1000); dt.setHours(0, 0, 0, 0)
      if (Math.round((t0 - dt) / 86400000) < 30) return true
    }
    return false
  })
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
    allWQ.value = list
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

      <!-- 今日复习行动条 -->
      <div v-if="stats.due" class="review-cta">
        <div class="rc-ic"><n-icon size="18"><RefreshOutline /></n-icon></div>
        <div class="rc-text">今日有 <b>{{ stats.due }}</b> 道错题待复习，间隔复习能显著巩固记忆</div>
        <n-button type="primary" size="small" @click="switchView('review')">去复习</n-button>
      </div>

      <!-- 图表区 -->
      <n-grid cols="2" :x-gap="16" :y-gap="16" responsive="screen" item-responsive class="charts">
        <n-grid-item span="2 m:1">
          <n-card title="学科掌握度" :bordered="true">
            <v-chart v-if="bySubject.length" :option="radarOption" autoresize style="height: 280px" />
            <n-empty v-else description="暂无错题数据" style="padding: 64px 0" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="错题分布" :bordered="true">
            <v-chart v-if="bySubject.length" :option="barOption" autoresize style="height: 280px" />
            <n-empty v-else description="暂无错题数据" style="padding: 64px 0" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="复习安排" :bordered="true">
            <v-chart v-if="stats.wrong" :option="pieOption" autoresize style="height: 280px" />
            <n-empty v-else description="暂无复习安排" style="padding: 64px 0" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="近 30 天学习节奏" :bordered="true">
            <template #header-extra><span class="card-hint">录入 vs 复习</span></template>
            <v-chart v-if="hasTrend" :option="lineOption" autoresize style="height: 280px" />
            <n-empty v-else description="近 30 天暂无学习记录" style="padding: 64px 0" />
          </n-card>
        </n-grid-item>
        <n-grid-item span="2 m:1">
          <n-card title="薄弱点分布" :bordered="true">
            <template #header-extra><span class="card-hint">学科 × 掌握度</span></template>
            <v-chart v-if="bySubject.length" :option="heatOption" autoresize style="height: 280px" />
            <n-empty v-else description="暂无错题数据" style="padding: 64px 0" />
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
.review-cta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--accent-soft);
  border: 1px solid var(--accent);
}
.rc-ic {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.rc-text {
  flex: 1;
  font-size: 14px;
  color: var(--text);
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
.card-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-tertiary);
}

@media (max-width: 860px) {
  .panel {
    padding: 64px 16px 40px;
  }
}
</style>
