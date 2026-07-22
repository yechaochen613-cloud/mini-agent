<script setup>
// 常驻 bot 头像：中国老师卡通形象（静态 SVG，沿用产品品牌视觉）
defineProps({ size: { type: Number, default: 36 } })
</script>

<template>
  <svg
    class="bot-avatar"
    :width="size"
    :height="size"
    viewBox="0 0 100 100"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <circle cx="50" cy="50" r="50" fill="#fde7d3" />
    <path
      d="M22 54 Q20 22 50 20 Q80 22 78 54 Q82 70 73 78 L73 52 Q73 40 50 38 Q27 40 27 52 L27 78 Q18 70 22 54 Z"
      fill="#222"
    />
    <circle cx="50" cy="56" r="24" fill="#ffd6b0" />
    <circle cx="40" cy="55" r="3.2" fill="#222" />
    <circle cx="60" cy="55" r="3.2" fill="#222" />
    <circle cx="40" cy="55" r="8" fill="none" stroke="#222" stroke-width="2.2" />
    <circle cx="60" cy="55" r="8" fill="none" stroke="#222" stroke-width="2.2" />
    <line x1="48" y1="55" x2="52" y2="55" stroke="#222" stroke-width="2.2" />
    <path d="M43 66 Q50 72 57 66" fill="none" stroke="#c0392b" stroke-width="2.6" stroke-linecap="round" />
    <path d="M27 86 Q50 76 73 86 L75 100 L25 100 Z" fill="#c0392b" />
    <path d="M50 82 L42 90 L48 94 L50 90 L52 94 L58 90 Z" fill="#fdf8ef" />
  </svg>
</template>

<style scoped>
.bot-avatar {
  display: block;
  border-radius: 50%;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
}
</style>
