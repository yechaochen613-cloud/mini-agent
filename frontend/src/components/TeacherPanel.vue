<script setup>
import { NIcon } from 'naive-ui'
import { PeopleOutline, ArrowForwardOutline } from '@vicons/ionicons5'
import { TEACHERS } from '../teachers.js'
import { summonTeacher } from '../store.js'
</script>

<template>
  <div class="panel">
    <header class="panel-head">
      <div class="ph-icon"><n-icon size="22" color="var(--accent)"><PeopleOutline /></n-icon></div>
      <div>
        <h1 class="ph-title">名师分诊台</h1>
        <p class="ph-sub">选择学科名师，进入针对性的辅导对话——每位老师都有专属性格与教学风格</p>
      </div>
    </header>

    <div class="teacher-grid">
      <div
        v-for="t in TEACHERS"
        :key="t.id"
        class="teacher-card"
        :style="{ '--c1': t.color1, '--c2': t.color2 }"
        v-motion="{
          initial: { opacity: 0, y: 16 },
          enter: { opacity: 1, y: 0, transition: { duration: 380, ease: 'easeOut' } }
        }"
      >
        <div class="tc-top">
          <div class="tc-avatar"><n-icon size="24" color="#1d1d1f"><component :is="t.icon" /></n-icon></div>
          <div class="tc-info">
            <div class="tc-name">
              {{ t.name }}
              <span class="tc-subject">{{ t.subject }}</span>
            </div>
            <div class="tc-personality">{{ t.personality }}</div>
          </div>
        </div>

        <div class="tc-bio">{{ t.bio }}</div>

        <div class="tc-row">
          <span class="tc-label">教学风格</span>
          <span class="tc-style">{{ t.style }}</span>
        </div>

        <div class="tc-skills">
          <span v-for="s in t.skills" :key="s" class="tc-skill">{{ s }}</span>
        </div>

        <button class="tc-call" @click="summonTeacher(t)">
          <span>召唤老师</span>
          <n-icon size="16"><ArrowForwardOutline /></n-icon>
        </button>
      </div>
    </div>
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
  margin-bottom: 26px;
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
.teacher-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 16px;
  max-width: 1180px;
}
.teacher-card {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 18px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.18s, box-shadow 0.18s;
  display: flex;
  flex-direction: column;
}
.teacher-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}
.tc-top {
  display: flex;
  align-items: center;
  gap: 12px;
}
.tc-avatar {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  background: linear-gradient(135deg, var(--c1), var(--c2));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tc-info {
  min-width: 0;
}
.tc-name {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: baseline;
  gap: 7px;
}
.tc-subject {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
}
.tc-personality {
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  font-size: 11.5px;
  font-weight: 600;
  color: #1d1d1f;
  background: linear-gradient(135deg, var(--c1), var(--c2));
  border-radius: 7px;
  padding: 2px 9px;
  width: fit-content;
}
.tc-bio {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.62;
  margin: 14px 0 10px;
}
.tc-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.55;
  margin-bottom: 12px;
}
.tc-label {
  flex-shrink: 0;
  font-weight: 700;
  color: var(--text-tertiary);
  font-size: 11px;
  padding-top: 1px;
}
.tc-style {
  color: var(--text);
}
.tc-skills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}
.tc-skill {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 7px;
  padding: 3px 9px;
}
.tc-call {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--c1), var(--c2));
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: filter 0.16s, transform 0.12s;
}
.tc-call:hover {
  filter: brightness(1.04);
}
.tc-call:active {
  transform: scale(0.98);
}

@media (max-width: 860px) {
  .panel {
    padding: 64px 16px 40px;
  }
}
</style>
