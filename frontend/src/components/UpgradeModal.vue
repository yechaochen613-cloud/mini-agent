<script setup>
import { computed } from 'vue'
import { NModal, NIcon, useMessage } from 'naive-ui'
import { DiamondOutline, StarOutline, RocketOutline, CloseOutline } from '@vicons/ionicons5'
import { store } from '../store.js'

const props = defineProps({ show: Boolean })
const emit = defineEmits(['update:show'])
const message = useMessage()

const plans = [
  {
    key: 'free',
    name: '免费版',
    price: 0,
    icon: StarOutline,
    highlight: false,
    features: ['基础对话辅导', '学情档案与错题本', '每周学习节奏看板']
  },
  {
    key: 'std',
    name: '标准版',
    price: 99,
    icon: DiamondOutline,
    highlight: true,
    features: ['包含免费版全部功能', '名师分科深度讲解', '间隔复习与学情报告导出']
  },
  {
    key: 'pro',
    name: '尊享版',
    price: 299,
    icon: RocketOutline,
    highlight: false,
    features: ['包含标准版全部功能', '无限试卷智能解析', '1对1 定制学习路径 · 优先响应']
  }
]

const currentPlan = computed(() => localStorage.getItem('ma_plan') || 'free')

function close() {
  emit('update:show', false)
}

function choose(plan) {
  localStorage.setItem('ma_plan', plan.key)
  message.success(`已选择「${plan.name}」（演示环境，未接入支付）`)
  close()
}
</script>

<template>
  <n-modal
    :show="props.show"
    @update:show="emit('update:show', $event)"
    :auto-focus="false"
    transform-origin="center"
    :mask-closable="true"
  >
    <div class="upgrade-panel">
      <button class="up-close" @click="close" aria-label="关闭">
        <n-icon size="18"><CloseOutline /></n-icon>
      </button>

      <div class="up-head">
        <div class="up-title">升级智伴私教</div>
        <div class="up-sub">选择适合你的会员方案，解锁更聪明的 AI 陪练</div>
      </div>

      <div class="plans">
        <div
          v-for="p in plans"
          :key="p.key"
          class="plan-card"
          :class="{ hl: p.highlight, current: currentPlan === p.key }"
        >
          <div class="plan-top">
            <n-icon size="22" class="plan-ico" :class="{ hi: p.highlight }">
              <component :is="p.icon" />
            </n-icon>
            <div class="plan-name">{{ p.name }}</div>
            <span v-if="currentPlan === p.key" class="cur-badge">当前</span>
          </div>
          <div class="plan-price">
            <span class="num">{{ p.price }}</span>
            <span class="unit">元/月</span>
          </div>
          <ul class="plan-feats">
            <li v-for="f in p.features" :key="f">
              <span class="tick">✓</span><span>{{ f }}</span>
            </li>
          </ul>
          <button
            class="plan-cta"
            :class="{ primary: p.highlight }"
            :disabled="currentPlan === p.key"
            @click="choose(p)"
          >
            {{ currentPlan === p.key ? '当前套餐' : p.price === 0 ? '免费使用' : '选择此方案' }}
          </button>
        </div>
      </div>

      <div class="up-tip">演示环境暂未接入支付，选择套餐会记录偏好并提示。</div>
    </div>
  </n-modal>
</template>

<style scoped>
.upgrade-panel {
  position: relative;
  width: min(820px, 92vw);
  padding: 28px 26px 22px;
  border-radius: var(--radius-lg);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-lg);
  backdrop-filter: saturate(160%) blur(24px);
  -webkit-backdrop-filter: saturate(160%) blur(24px);
}
.up-close {
  position: absolute;
  top: 14px;
  right: 14px;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.16s, color 0.16s;
}
.up-close:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.up-head {
  text-align: center;
  margin-bottom: 22px;
}
.up-title {
  font-size: 22px;
  font-weight: 750;
  letter-spacing: -0.01em;
}
.up-sub {
  margin-top: 6px;
  font-size: 13.5px;
  color: var(--text-secondary);
}
.plans {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.plan-card {
  display: flex;
  flex-direction: column;
  padding: 18px 16px 16px;
  border-radius: var(--radius-md);
  background: var(--bg-input);
  border: 1px solid var(--border);
  transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s;
}
.plan-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}
.plan-card.hl {
  border-color: transparent;
  background: linear-gradient(160deg, var(--accent-soft), var(--bg-elevated));
  box-shadow: 0 10px 30px rgba(0, 113, 227, 0.22);
  position: relative;
}
.plan-card.hl::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--radius-md);
  padding: 1.5px;
  background: linear-gradient(135deg, #6a5cff, #0071e3);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}
.plan-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.plan-ico {
  color: var(--text-secondary);
}
.plan-ico.hi {
  color: var(--accent);
}
.plan-name {
  font-size: 15.5px;
  font-weight: 700;
}
.cur-badge {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 2px 7px;
  border-radius: 7px;
}
.plan-price {
  margin: 12px 0 14px;
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.plan-price .num {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.plan-price .unit {
  font-size: 12.5px;
  color: var(--text-tertiary);
}
.plan-feats {
  list-style: none;
  margin: 0 0 16px;
  padding: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.plan-feats li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
}
.tick {
  flex-shrink: 0;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: var(--success);
  color: #fff;
  font-size: 11px;
  line-height: 17px;
  text-align: center;
  margin-top: 1px;
}
.plan-cta {
  width: 100%;
  height: 38px;
  border: 1px solid var(--border-strong);
  border-radius: 11px;
  background: transparent;
  color: var(--text);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, filter 0.15s, background 0.18s;
}
.plan-cta.primary {
  border: none;
  color: #fff;
  background: linear-gradient(135deg, #6a5cff, #0071e3);
  box-shadow: 0 6px 16px rgba(0, 113, 227, 0.32);
}
.plan-cta:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.05);
}
.plan-cta:disabled {
  opacity: 0.55;
  cursor: default;
}
.up-tip {
  margin-top: 18px;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

@media (max-width: 680px) {
  .plans {
    grid-template-columns: 1fr;
  }
}
</style>
