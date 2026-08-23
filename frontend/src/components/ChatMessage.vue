<template>
  <div class="msg" :class="message.role">
    <div class="avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
    <div class="bubble">
      <div v-if="message.role === 'user'" class="user-text">{{ message.content }}</div>
      <div v-else class="md-body" v-html="rendered"></div>
      <span v-if="message.streaming" class="cursor">▍</span>

      <!-- citations -->
      <div v-if="message.role === 'assistant' && message.citations?.length" class="cites">
        <span class="cites-label">引用来源：</span>
        <el-tag
          v-for="(c, i) in message.citations"
          :key="c.chunk_id"
          class="cite-tag"
          effect="plain"
          @click="openCite(c)"
        >
          [{{ i + 1 }}] {{ c.filename }}{{ c.location ? ' · ' + c.location : '' }}
        </el-tag>
      </div>
    </div>

    <el-dialog v-model="citeVisible" :title="citeTitle" width="640px">
      <div class="cite-meta">
        <el-tag size="small">相关度 {{ citeScore }}%</el-tag>
        <span v-if="activeCite?.location" class="cite-loc">📍 {{ activeCite.location }}</span>
      </div>
      <pre class="cite-content">{{ activeCite?.content }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import type { Citation } from '../api/sse'
import type { Message } from '../api/types'

const props = defineProps<{ message: Message & { streaming?: boolean } }>()

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const rendered = computed(() => md.render(props.message.content || ''))

const citeVisible = ref(false)
const activeCite = ref<Citation | null>(null)
const citeTitle = computed(() => (activeCite.value ? `出处：${activeCite.value.filename}` : '出处'))
const citeScore = computed(() => (((activeCite.value?.score ?? 0) * 100)).toFixed(0))

function openCite(c: Citation) {
  activeCite.value = c
  citeVisible.value = true
}
</script>

<style scoped>
.msg {
  display: flex;
  gap: 12px;
  margin-bottom: 22px;
}
.msg.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: var(--brand);
}
.msg.user .avatar {
  background: #7c5cff;
}
.bubble {
  max-width: 76%;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 16px;
}
.msg.user .bubble {
  background: #eaf1ff;
  border-color: #d7e4ff;
}
.user-text {
  white-space: pre-wrap;
  line-height: 1.7;
}
.cursor {
  display: inline-block;
  animation: blink 1s steps(1) infinite;
  color: var(--brand);
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.cites {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--line);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.cites-label {
  font-size: 12px;
  color: var(--sub);
}
.cite-tag {
  cursor: pointer;
}
.cite-tag:hover {
  color: var(--brand);
  border-color: var(--brand);
}
.cite-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.cite-loc {
  font-size: 13px;
  color: var(--sub);
}
.cite-content {
  background: #f7f8fa;
  border-radius: 8px;
  padding: 14px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 420px;
  overflow-y: auto;
  line-height: 1.7;
  font-size: 13px;
}
</style>
