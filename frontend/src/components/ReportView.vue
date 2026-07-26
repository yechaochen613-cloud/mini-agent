<script setup>
import { ref, computed, onMounted } from 'vue'
import { NButton, NTag, NSpin, NEmpty, useMessage } from 'naive-ui'
import { DocumentTextOutline, DownloadOutline, RefreshOutline, SchoolOutline } from '@vicons/ionicons5'
import { api } from '../api.js'
import StudyPlanCard from './StudyPlanCard.vue'

const message = useMessage()

const loading = ref(true)
const profile = ref(null)
const wrong = ref([])
const plan = ref(null)
const planLoading = ref(false)

const MASTERY_LABELS = ['生疏', '薄弱', '一般', '良好', '扎实', '熟练']

const studentName = computed(() => profile.value?.name || '同学')
const grade = computed(() => profile.value?.grade || '—')
const papersCount = computed(() => profile.value?.papers_count ?? 0)
const goals = computed(() => profile.value?.goals || [])
const weakPoints = computed(() => profile.value?.weak_points || [])
const strengths = computed(() => profile.value?.strengths || [])
const subjects = computed(() => {
  const s = profile.value?.subjects || {}
  return Object.entries(s)
    .map(([name, lvl]) => ({ name, level: Number(lvl) || 0 }))
    .sort((a, b) => b.level - a.level)
})

function masteryColor(level) {
  if (level >= 4) return '#34c759'
  if (level >= 3) return '#30b0c7'
  if (level >= 2) return '#ff9f0a'
  return '#ff3b30'
}

// 错题统计
const wrongTotal = computed(() => wrong.value.length)
const bySubject = computed(() => {
  const m = {}
  for (const w of wrong.value) {
    const s = w.subject || '未分类'
    if (!m[s]) m[s] = { subject: s, count: 0, sum: 0 }
    m[s].count += 1
    m[s].sum += Number(w.mastery) || 0
  }
  return Object.values(m)
    .map((x) => ({ ...x, avg: x.count ? Math.round((x.sum / x.count) * 10) / 10 : 0 }))
    .sort((a, b) => b.count - a.count)
})
const recentWrong = computed(() => wrong.value.slice(0, 8))

const today = new Date()
const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`

async function loadPlan() {
  if (!goals.value.length) {
    plan.value = null
    return
  }
  planLoading.value = true
  try {
    const r = await api.studyPlan(goals.value.join('、'), 14)
    plan.value = r.plan || null
  } catch (e) {
    plan.value = null
  } finally {
    planLoading.value = false
  }
}

async function onGeneratePlan() {
  await loadPlan()
  if (plan.value) message.success('已生成学习计划')
  else message.warning('暂无法生成，请先在学情档案中设置学习目标')
}

async function load() {
  loading.value = true
  try {
    const [p, w] = await Promise.all([api.profile(), api.wrongQuestions()])
    profile.value = p.profile || null
    wrong.value = (w.wrong_questions || []).slice().sort(
      (a, b) => (b.created_at || '').localeCompare(a.created_at || '')
    )
    await loadPlan()
  } finally {
    loading.value = false
  }
}

function exportPdf() {
  const prev = document.title
  document.title = `智伴私教-学情报告-${studentName.value}-${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, '0')}${String(today.getDate()).padStart(2, '0')}`
  const restore = () => {
    document.title = prev
    window.removeEventListener('afterprint', restore)
  }
  window.addEventListener('afterprint', restore)
  window.print()
}

onMounted(load)
</script>

<template>
  <div class="report-wrap">
    <!-- 工具栏（打印时隐藏） -->
    <div class="report-toolbar no-print">
      <div class="rt-title">
        <n-icon size="20" color="#0071e3"><DocumentTextOutline /></n-icon>
        <span>学情报告</span>
      </div>
      <div class="rt-actions">
        <n-button v-if="!plan && goals.length" size="small" @click="onGeneratePlan" :loading="planLoading">
          <template #icon><n-icon :component="RefreshOutline" /></template>
          生成学习计划
        </n-button>
        <n-button type="primary" size="small" @click="exportPdf">
          <template #icon><n-icon :component="DownloadOutline" /></template>
          导出 PDF
        </n-button>
      </div>
    </div>

    <n-spin :show="loading">
      <div class="report-document" v-if="profile">
        <!-- 品牌头 -->
        <header class="rp-header">
          <div class="rp-brand">
            <div class="rp-logo"><n-icon size="20" color="#fff"><SchoolOutline /></n-icon></div>
            <div>
              <div class="rp-brand-name">智伴私教</div>
              <div class="rp-brand-sub">智能学习助手 · 学情报告</div>
            </div>
          </div>
          <div class="rp-meta">
            <div class="rp-meta-row"><span class="rp-meta-k">学生</span><span class="rp-meta-v">{{ studentName }}</span></div>
            <div class="rp-meta-row"><span class="rp-meta-k">年级</span><span class="rp-meta-v">{{ grade }}</span></div>
            <div class="rp-meta-row"><span class="rp-meta-k">生成时间</span><span class="rp-meta-v">{{ dateStr }}</span></div>
          </div>
        </header>

        <!-- 学情概览 -->
        <section class="rp-section">
          <h2 class="rp-h2">一、学情概览</h2>
          <div class="rp-facts">
            <div class="rp-fact">
              <div class="rp-fact-num">{{ papersCount }}</div>
              <div class="rp-fact-label">已分析试卷</div>
            </div>
            <div class="rp-fact">
              <div class="rp-fact-num">{{ wrongTotal }}</div>
              <div class="rp-fact-label">累计错题</div>
            </div>
            <div class="rp-fact">
              <div class="rp-fact-num">{{ subjects.length }}</div>
              <div class="rp-fact-label">追踪学科</div>
            </div>
          </div>

          <div class="rp-block" v-if="goals.length">
            <div class="rp-block-label">学习目标</div>
            <div class="rp-tags">
              <NTag v-for="g in goals" :key="g" size="small" :bordered="false" type="info" round>{{ g }}</NTag>
            </div>
          </div>

          <div class="rp-grid2">
            <div class="rp-block" v-if="weakPoints.length">
              <div class="rp-block-label rp-bad">薄弱点</div>
              <div class="rp-tags">
                <NTag v-for="w in weakPoints" :key="w" size="small" :bordered="false" type="error" round>{{ w }}</NTag>
              </div>
            </div>
            <div class="rp-block" v-if="strengths.length">
              <div class="rp-block-label rp-good">优势</div>
              <div class="rp-tags">
                <NTag v-for="s in strengths" :key="s" size="small" :bordered="false" type="success" round>{{ s }}</NTag>
              </div>
            </div>
          </div>

          <div class="rp-block" v-if="subjects.length">
            <div class="rp-block-label">学科掌握度</div>
            <div class="rp-subjects">
              <div class="rp-subj" v-for="s in subjects" :key="s.name">
                <div class="rp-subj-name">{{ s.name }}</div>
                <div class="rp-bar">
                  <div class="rp-bar-fill" :style="{ width: (s.level / 5 * 100) + '%', background: masteryColor(s.level) }"></div>
                </div>
                <div class="rp-subj-val">{{ MASTERY_LABELS[s.level] || s.level }}</div>
              </div>
            </div>
          </div>
        </section>

        <!-- 学习计划 -->
        <section class="rp-section">
          <h2 class="rp-h2">二、学习计划</h2>
          <StudyPlanCard v-if="plan" :plan="plan" />
          <n-empty v-else-if="planLoading" description="正在生成学习计划…" />
          <div v-else class="rp-empty-note">
            暂无学习计划。可在对话中让私教为你制定，或点击右上角「生成学习计划」。
          </div>
        </section>

        <!-- 错题本概览 -->
        <section class="rp-section">
          <h2 class="rp-h2">三、错题本概览</h2>
          <div class="rp-block" v-if="bySubject.length">
            <div class="rp-block-label">按学科分布</div>
            <table class="rp-table">
              <thead>
                <tr><th>学科</th><th>错题数</th><th>平均掌握度</th></tr>
              </thead>
              <tbody>
                <tr v-for="x in bySubject" :key="x.subject">
                  <td>{{ x.subject }}</td>
                  <td>{{ x.count }}</td>
                  <td>
                    <span class="rp-pill" :style="{ background: masteryColor(x.avg) + '22', color: masteryColor(x.avg) }">
                      {{ MASTERY_LABELS[Math.round(x.avg)] || x.avg }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="rp-block" v-if="recentWrong.length">
            <div class="rp-block-label">近期错题明细（最近 {{ recentWrong.length }} 题）</div>
            <div class="rp-wq" v-for="(w, i) in recentWrong" :key="w.id">
              <div class="rp-wq-q">
                <span class="rp-wq-idx">{{ i + 1 }}</span>
                <span class="rp-wq-subj">{{ w.subject }}</span>
                <span class="rp-wq-text">{{ w.question }}</span>
              </div>
              <div class="rp-wq-ans">
                <div class="rp-ans"><span class="rp-ans-k rp-bad">我的答案</span>{{ w.my_answer || '—' }}</div>
                <div class="rp-ans"><span class="rp-ans-k rp-good">正确答案</span>{{ w.correct_answer || '—' }}</div>
              </div>
              <div class="rp-wq-exp" v-if="w.explanation">
                <span class="rp-ans-k">解析</span>{{ w.explanation }}
              </div>
              <div class="rp-wq-foot">
                <span class="rp-pill" :style="{ background: masteryColor(w.mastery) + '22', color: masteryColor(w.mastery) }">
                  掌握度：{{ MASTERY_LABELS[w.mastery] || w.mastery }}
                </span>
                <span class="rp-wq-date" v-if="w.created_at">{{ w.created_at.slice(0, 10) }}</span>
              </div>
            </div>
          </div>
          <div v-if="!wrongTotal" class="rp-empty-note">暂无错题记录。遇到问题随时问私教，答错的题会自动归集到这里。</div>
        </section>

        <footer class="rp-footer">
          本报告由「智伴私教」自动生成 · 数据截至 {{ dateStr }} · 仅供学习参考
        </footer>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.report-wrap {
  max-width: 860px;
  margin: 0 auto;
  padding: 18px 20px 40px;
}
.report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  position: sticky;
  top: 0;
  z-index: 5;
}
.rt-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 17px;
}
.rt-actions {
  display: flex;
  gap: 10px;
}
.report-document {
  background: #ffffff;
  color: #1d1d1f;
  border: 1px solid #e6e6e9;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
  padding: 32px 36px 28px;
}
/* 品牌头 */
.rp-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 3px solid #0071e3;
}
.rp-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.rp-logo {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0071e3, #42a5f5);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0, 113, 227, 0.35);
}
.rp-brand-name {
  font-weight: 800;
  font-size: 20px;
  color: #1d1d1f;
  letter-spacing: -0.01em;
}
.rp-brand-sub {
  font-size: 12px;
  color: #86868b;
  margin-top: 2px;
}
.rp-meta {
  text-align: right;
  font-size: 13px;
}
.rp-meta-row {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  line-height: 1.7;
}
.rp-meta-k {
  color: #86868b;
}
.rp-meta-v {
  font-weight: 600;
  color: #1d1d1f;
}
/* 区块 */
.rp-section {
  margin-top: 24px;
}
.rp-h2 {
  font-size: 16px;
  font-weight: 700;
  color: #0071e3;
  margin: 0 0 14px;
  padding-left: 10px;
  border-left: 4px solid #0071e3;
}
.rp-facts {
  display: flex;
  gap: 14px;
  margin-bottom: 16px;
}
.rp-fact {
  flex: 1;
  background: #f5f5f7;
  border-radius: 12px;
  padding: 14px;
  text-align: center;
}
.rp-fact-num {
  font-size: 26px;
  font-weight: 800;
  color: #0071e3;
  line-height: 1.1;
}
.rp-fact-label {
  font-size: 12px;
  color: #86868b;
  margin-top: 4px;
}
.rp-block {
  margin-bottom: 14px;
}
.rp-block-label {
  font-size: 13px;
  font-weight: 700;
  color: #1d1d1f;
  margin-bottom: 8px;
}
.rp-bad {
  color: #d70015;
}
.rp-good {
  color: #248a3d;
}
.rp-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}
.rp-grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 560px) {
  .rp-grid2 {
    grid-template-columns: 1fr;
  }
  .rp-facts {
    flex-direction: column;
  }
}
/* 学科掌握度 */
.rp-subjects {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.rp-subj {
  display: flex;
  align-items: center;
  gap: 12px;
}
.rp-subj-name {
  width: 72px;
  font-size: 13px;
  font-weight: 600;
  color: #1d1d1f;
  flex-shrink: 0;
}
.rp-bar {
  flex: 1;
  height: 8px;
  background: #ececf0;
  border-radius: 6px;
  overflow: hidden;
}
.rp-bar-fill {
  height: 100%;
  border-radius: 6px;
  transition: width 0.4s ease;
}
.rp-subj-val {
  width: 40px;
  font-size: 12px;
  color: #86868b;
  text-align: right;
  flex-shrink: 0;
}
/* 表格 */
.rp-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.rp-table th,
.rp-table td {
  text-align: left;
  padding: 9px 12px;
  border-bottom: 1px solid #ececf0;
}
.rp-table th {
  background: #f5f5f7;
  font-weight: 700;
  color: #1d1d1f;
}
.rp-table td {
  color: #1d1d1f;
}
.rp-pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
/* 错题明细 */
.rp-wq {
  border: 1px solid #ececf0;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 10px;
  page-break-inside: avoid;
}
.rp-wq-q {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13.5px;
  color: #1d1d1f;
  line-height: 1.5;
}
.rp-wq-idx {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  border-radius: 6px;
  background: #0071e3;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.rp-wq-subj {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  color: #0071e3;
  background: #e8f1fe;
  padding: 1px 7px;
  border-radius: 6px;
}
.rp-wq-ans {
  display: flex;
  gap: 18px;
  margin-top: 8px;
  font-size: 13px;
  color: #1d1d1f;
}
.rp-ans-k {
  font-size: 11px;
  font-weight: 700;
  margin-right: 6px;
}
.rp-wq-exp {
  margin-top: 6px;
  font-size: 12.5px;
  color: #515154;
  line-height: 1.5;
}
.rp-wq-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.rp-wq-date {
  font-size: 11px;
  color: #86868b;
}
.rp-empty-note {
  font-size: 13px;
  color: #86868b;
  padding: 14px 0;
  line-height: 1.6;
}
.rp-footer {
  margin-top: 26px;
  padding-top: 14px;
  border-top: 1px solid #ececf0;
  font-size: 11px;
  color: #a1a1a6;
  text-align: center;
}
</style>
