<template>
  <div class="msg" :class="message.role">
    <!-- 头像：墨黑圆（AI 为印章「问」，用户为「我」） -->
    <div class="avatar" :class="message.role">{{ message.role === 'user' ? '我' : '问' }}</div>
    <div class="body">
      <div v-if="message.role === 'user'" class="user-text">{{ message.content }}</div>
      <div v-else class="md-body" v-html="rendered"></div>
      <span v-if="message.streaming" class="cursor">▍</span>

      <!-- 回答的引用出处：一行淡墨小字，无标签框；编号与正文 [n] 对应，点击看原文 -->
      <div v-if="message.role === 'assistant' && message.citations?.length" class="cites">
        来源：
        <template v-for="(c, i) in message.citations" :key="c.chunk_id">
          <span v-if="i > 0">，</span>
          <span class="cite-item" @click="openCite(c)">
            [{{ i + 1 }}] {{ c.filename }}{{ c.location ? ' ' + c.location : '' }}
          </span>
        </template>
      </div>
      <!-- 生成耗时：流结束后的一行淡墨小字 -->
      <div
        v-if="message.role === 'assistant' && !message.streaming && message.latency_ms > 0"
        class="latency"
      >
        耗时 {{ (message.latency_ms / 1000).toFixed(1) }} 秒
      </div>
    </div>

    <!-- 出处详情弹窗：细描边、无重投影 -->
    <el-dialog v-model="citeVisible" :title="citeTitle" width="640px">
      <div class="cite-meta">
        <span v-if="activeCite?.location" class="cite-loc">{{ activeCite.location }}</span>
        <span class="cite-score">相关度 {{ citeScore }}%</span>
      </div>
      <pre class="cite-content">{{ activeCite?.content }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// 单条消息组件（水墨文字流，无气泡）：
// - 用户消息墨黑靠右纯文本；AI 消息次墨靠左渲染 Markdown（支持 [编号] 引用标注）
// - AI 消息下方一行淡墨小字展示引用出处，点击弹窗查看切片原文与相关度
import { computed, onUnmounted, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import type { Citation } from '../api/sse'
import type { Message } from '../api/types'

const props = defineProps<{ message: Message & { streaming?: boolean } }>()

// 禁用 html 注入，链接自动识别，换行转 <br>（对话场景更自然）
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

// Markdown 渲染结果：流式生成时做节流（每个 token 都全量渲染会让长回答卡顿），
// 最多每 120ms 渲染一次；流结束后立即渲染最终稿
const rendered = ref(md.render(props.message.content || ''))
let renderTimer: number | null = null
watch(
  () => props.message.content,
  (v) => {
    if (!props.message.streaming) {
      if (renderTimer !== null) {
        clearTimeout(renderTimer)
        renderTimer = null
      }
      rendered.value = md.render(v || '')
      return
    }
    if (renderTimer === null) {
      renderTimer = window.setTimeout(() => {
        renderTimer = null
        rendered.value = md.render(props.message.content || '')
      }, 120)
    }
  }
)
onUnmounted(() => {
  if (renderTimer !== null) clearTimeout(renderTimer)
})

const citeVisible = ref(false)
const activeCite = ref<Citation | null>(null)
const citeTitle = computed(() => (activeCite.value ? `出处：${activeCite.value.filename}` : '出处'))
// 重排得分(0~1)转成百分比展示
const citeScore = computed(() => (((activeCite.value?.score ?? 0) * 100)).toFixed(0))

// 点击引用：打开出处详情弹窗
function openCite(c: Citation) {
  activeCite.value = c
  citeVisible.value = true
}
</script>

<style scoped>
.msg {
  display: flex;
  gap: 14px;
  max-width: 860px;
  margin: 0 auto 30px;
}
.msg.user {
  flex-direction: row-reverse;
}
/* 头像：墨黑圆 */
.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #fdfcfa;
  background: var(--ink-2);
  margin-top: 2px;
}
.avatar.assistant {
  background: var(--ink);
  font-family: var(--font-serif);
}
.body {
  flex: 1;
  min-width: 0;
}
/* 用户问题：墨黑，行距疏朗 */
.msg.user .user-text {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--ink);
  font-weight: 500;
  text-align: right;
}
/* AI 回答：次墨文字流，无卡片包裹（样式见全局 .md-body） */
.msg.assistant .body {
  padding-top: 3px;
}
.cursor {
  display: inline-block;
  animation: blink 1s steps(1) infinite;
  color: var(--ink);
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
/* 引用出处：一行淡墨小字 */
.cites {
  margin-top: 12px;
  font-size: 12px;
  color: var(--ink-3);
  line-height: 1.9;
}
.cite-item {
  cursor: pointer;
  transition: color 0.2s;
}
.cite-item:hover {
  color: var(--ink);
}
/* 耗时：一行淡墨小字 */
.latency {
  margin-top: 8px;
  font-size: 11px;
  color: var(--ink-3);
  font-variant-numeric: tabular-nums;
}
.cite-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--ink-3);
}
.cite-content {
  background: #f2efe8;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 14px 16px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 420px;
  overflow-y: auto;
  line-height: 1.8;
  font-size: 13px;
  color: var(--ink-2);
}
</style>
