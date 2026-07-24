<script setup>
import { ref, reactive, computed } from 'vue'
import { useMessage, NIcon, NButton, NDrawer, NDrawerContent, NInput, NSlider, NTag, NDynamicTags, NSpace, NEmpty, NScrollbar } from 'naive-ui'
import { PersonOutline, SchoolOutline, DocumentTextOutline, CreateOutline, AddOutline, TrashOutline, RibbonOutline, WarningOutline, FlagOutline } from '@vicons/ionicons5'
import { api } from '../api.js'

const props = defineProps({
  profile: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['updated'])

const message = useMessage()

const drawerOpen = ref(false)
const saving = ref(false)

// 编辑表单（抽屉打开时深拷贝初始化）
const form = reactive({
  name: '',
  grade: '',
  subjects: [],   // [{name, level}]
  weak_points: [],
  strengths: [],
  goals: []
})

const isEmpty = computed(() => {
  const p = props.profile || {}
  return !p.name && !(p.subjects && Object.keys(p.subjects).length) &&
    !(p.weak_points && p.weak_points.length) && !(p.strengths && p.strengths.length)
})

function fmtUpdated(t) {
  if (!t) return ''
  try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch (e) { return t }
}

function openEditor() {
  const p = props.profile || {}
  form.name = p.name || ''
  form.grade = p.grade || ''
  form.subjects = Object.entries(p.subjects || {}).map(([name, level]) => ({ name, level: Number(level) || 0 }))
  form.weak_points = (p.weak_points || []).map(String)
  form.strengths = (p.strengths || []).map(String)
  form.goals = (p.goals || []).map(String)
  drawerOpen.value = true
}

function addSubject() {
  form.subjects.push({ name: '', level: 60 })
}
function removeSubject(i) {
  form.subjects.splice(i, 1)
}

function masteryColor(v) {
  if (v >= 80) return '#34c759'
  if (v >= 60) return '#ff9f0a'
  return '#ff453a'
}

// 展示用：档案里的掌握度
const displaySubjects = computed(() => {
  const s = props.profile?.subjects || {}
  return Object.entries(s).map(([name, level]) => ({ name, level: Number(level) || 0 }))
    .sort((a, b) => b.level - a.level)
})

async function save() {
  saving.value = true
  try {
    const subjects = {}
    form.subjects.forEach((s) => {
      const n = (s.name || '').trim()
      if (n) subjects[n] = Number(s.level) || 0
    })
    const payload = {
      replace: true,
      name: form.name.trim(),
      grade: form.grade.trim(),
      subjects,
      weak_points: form.weak_points.map((x) => String(x).trim()).filter(Boolean),
      strengths: form.strengths.map((x) => String(x).trim()).filter(Boolean),
      goals: form.goals.map((x) => String(x).trim()).filter(Boolean)
    }
    const res = await api.updateProfile(payload)
    emit('updated', res.profile || payload)
    message.success('学情档案已更新')
    drawerOpen.value = false
  } catch (e) {
    message.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="profile-card magnetic">
    <div class="pc-head">
      <div class="pc-id">
        <div class="pc-avatar">
          <n-icon size="22" color="var(--accent)"><PersonOutline /></n-icon>
        </div>
        <div class="pc-meta">
          <div class="pc-name">{{ profile?.name || '未命名同学' }}</div>
          <div class="pc-tags">
            <span v-if="profile?.grade" class="pc-chip"><n-icon size="13"><SchoolOutline /></n-icon>{{ profile.grade }}</span>
            <span v-if="profile?.papers_count" class="pc-chip"><n-icon size="13"><DocumentTextOutline /></n-icon>{{ profile.papers_count }} 份试卷</span>
          </div>
        </div>
      </div>
      <n-button size="small" secondary type="primary" @click="openEditor">
        <template #icon><n-icon :component="CreateOutline" /></template>
        编辑档案
      </n-button>
    </div>

    <n-empty v-if="isEmpty" description="AI 还在了解你，对话中透露姓名/年级/薄弱点后会自动建档" class="pc-empty">
      <template #extra>
        <n-button size="small" tertiary @click="openEditor">手动完善档案</n-button>
      </template>
    </n-empty>

    <template v-else>
      <!-- 学科掌握度 -->
      <div v-if="displaySubjects.length" class="pc-section">
        <div class="pc-stitle"><n-icon size="15" color="var(--accent)"><RibbonOutline /></n-icon>学科掌握度</div>
        <div v-for="s in displaySubjects" :key="s.name" class="pc-mastery">
          <div class="pc-mrow">
            <span class="pc-mname">{{ s.name }}</span>
            <span class="pc-mval" :style="{ color: masteryColor(s.level) }">{{ s.level }}</span>
          </div>
          <div class="pc-track">
            <div class="pc-fill" :style="{ width: s.level + '%', background: masteryColor(s.level) }"></div>
          </div>
        </div>
      </div>

      <!-- 薄弱点 / 优势 -->
      <div v-if="(profile?.weak_points && profile.weak_points.length) || (profile?.strengths && profile.strengths.length)" class="pc-tags-area">
        <div v-if="profile?.weak_points && profile.weak_points.length" class="pc-tagblock">
          <div class="pc-stitle warn"><n-icon size="15" color="#ff453a"><WarningOutline /></n-icon>薄弱点</div>
          <div class="pc-tagwrap">
            <n-tag v-for="w in profile.weak_points" :key="w" size="small" :bordered="false" type="error" round>{{ w }}</n-tag>
          </div>
        </div>
        <div v-if="profile?.strengths && profile.strengths.length" class="pc-tagblock">
          <div class="pc-stitle good"><n-icon size="15" color="#34c759"><RibbonOutline /></n-icon>优势</div>
          <div class="pc-tagwrap">
            <n-tag v-for="s in profile.strengths" :key="s" size="small" :bordered="false" type="success" round>{{ s }}</n-tag>
          </div>
        </div>
      </div>

      <!-- 目标 -->
      <div v-if="profile?.goals && profile.goals.length" class="pc-section">
        <div class="pc-stitle"><n-icon size="15" color="var(--accent)"><FlagOutline /></n-icon>学习目标</div>
        <ul class="pc-goals">
          <li v-for="(g, i) in profile.goals" :key="i">{{ g }}</li>
        </ul>
      </div>
    </template>

    <div v-if="profile?.updated_at" class="pc-foot">更新于 {{ fmtUpdated(profile.updated_at) }}</div>

    <!-- 编辑抽屉 -->
    <n-drawer v-model:show="drawerOpen" :width="420" placement="right">
      <n-drawer-content title="编辑学情档案" :native-scrollbar="false">
        <div class="ed-block">
          <label class="ed-label">姓名</label>
          <n-input v-model:value="form.name" placeholder="如：小明" maxlength="20" />
        </div>
        <div class="ed-block">
          <label class="ed-label">年级</label>
          <n-input v-model:value="form.grade" placeholder="如：初二 / 高一" maxlength="20" />
        </div>

        <div class="ed-block">
          <label class="ed-label">学科掌握度（0–100）</label>
          <div v-for="(s, i) in form.subjects" :key="i" class="ed-subject">
            <n-input v-model:value="s.name" placeholder="学科" class="ed-sub-name" />
            <div class="ed-sub-slider">
              <n-slider v-model:value="s.level" :min="0" :max="100" />
              <span class="ed-sub-val" :style="{ color: masteryColor(s.level) }">{{ s.level }}</span>
            </div>
            <n-button text type="error" @click="removeSubject(i)"><n-icon :component="TrashOutline" /></n-button>
          </div>
          <n-button text type="primary" @click="addSubject">
            <template #icon><n-icon :component="AddOutline" /></template>添加学科
          </n-button>
        </div>

        <div class="ed-block">
          <label class="ed-label">薄弱点</label>
          <n-dynamic-tags v-model:value="form.weak_points" type="error" />
        </div>
        <div class="ed-block">
          <label class="ed-label">优势</label>
          <n-dynamic-tags v-model:value="form.strengths" type="success" />
        </div>
        <div class="ed-block">
          <label class="ed-label">学习目标</label>
          <n-dynamic-tags v-model:value="form.goals" type="primary" />
        </div>

        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerOpen = false">取消</n-button>
            <n-button type="primary" :loading="saving" @click="save">保存</n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.profile-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 20px 22px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s;
}
.magnetic:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
}
.pc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.pc-id { display: flex; align-items: center; gap: 12px; min-width: 0; }
.pc-avatar {
  width: 42px; height: 42px; border-radius: 13px;
  background: var(--accent-soft); color: var(--accent);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.pc-name { font-size: 17px; font-weight: 700; letter-spacing: -0.01em; }
.pc-tags { display: flex; gap: 8px; margin-top: 4px; flex-wrap: wrap; }
.pc-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-secondary);
  background: var(--bg-soft, #f2f2f7); padding: 3px 9px; border-radius: 999px;
}
.pc-empty { padding: 28px 0 18px; }
.pc-section { margin-top: 18px; }
.pc-tags-area { margin-top: 18px; display: grid; gap: 14px; }
.pc-stitle {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 10px;
}
.pc-stitle.warn { color: #ff453a; }
.pc-stitle.good { color: #34c759; }
.pc-mastery { margin-bottom: 11px; }
.pc-mrow { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 5px; }
.pc-mname { font-weight: 600; }
.pc-mval { font-weight: 700; font-variant-numeric: tabular-nums; }
.pc-track { height: 7px; border-radius: 999px; background: var(--border); overflow: hidden; }
.pc-fill { height: 100%; border-radius: 999px; transition: width 0.6s cubic-bezier(0.16,1,0.3,1); }
.pc-tagwrap { display: flex; flex-wrap: wrap; gap: 8px; }
.pc-goals { margin: 0; padding-left: 18px; color: var(--text-secondary); font-size: 13px; line-height: 1.9; }
.pc-foot { margin-top: 16px; font-size: 11px; color: var(--text-tertiary); }

/* 编辑抽屉 */
.ed-block { margin-bottom: 18px; }
.ed-label { display: block; font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
.ed-subject { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.ed-sub-name { flex: 0 0 96px; }
.ed-sub-slider { flex: 1; display: flex; align-items: center; gap: 8px; }
.ed-sub-val { width: 28px; text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; font-size: 13px; }
</style>
