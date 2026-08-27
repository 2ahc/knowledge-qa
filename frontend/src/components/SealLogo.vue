<template>
  <!-- 品牌印章：墨黑方形 + 反白「问」字，登录页与导航复用 -->
  <svg :width="size" :height="size" viewBox="0 0 40 40" aria-label="问 印章" role="img">
    <rect x="1" y="1" width="38" height="38" rx="5" fill="#2b2a28" />
    <text
      x="20"
      y="28.5"
      text-anchor="middle"
      font-size="23"
      font-weight="700"
      fill="#fdfcfa"
      style="font-family: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', 'SimSun', serif"
    >问</text>
  </svg>
</template>

<script setup lang="ts">
// 品牌印章组件：全站唯一的品牌图形，尺寸由外部指定
withDefaults(defineProps<{ size?: number }>(), { size: 28 })
</script>
