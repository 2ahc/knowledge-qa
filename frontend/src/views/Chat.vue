<template>
  <div class="chat-page">
    <!-- 会话侧栏：无按钮框，纯文字列表，当前项墨黑加粗 + 左侧细竖线 -->
    <aside class="side">
      <button class="new-btn" @click="chat.newConversation()">
        <el-icon><Plus /></el-icon>新建对话
      </button>
      <div class="conv-list">
        <div
          v-for="conv in chat.conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === chat.currentId }"
          @click="chat.selectConversation(conv.id)"
        >
          <div class="conv-title">{{ conv.title || '新对话' }}</div>
          <div class="conv-meta">
            {{ formatTime(conv.created_at) }} · {{ conv.message_count }} 条
          </div>
          <el-icon class="conv-del" @click.stop="removeConv(conv.id)"><Delete /></el-icon>
        </div>
        <div v-if="!chat.conversations.length" class="conv-empty">暂无对话</div>
      </div>
    </aside>

    <!-- 主区域 -->
    <section class="main-area">
      <div class="kb-bar">
        <span class="kb-label">知识库</span>
        <el-select
          v-model="chat.selectedKbIds"
          multiple
          collapse-tags
          collapse-tags-tooltip
          placeholder="选择要提问的知识库"
          style="width: 340px"
        >
          <el-option v-for="kb in kb.kbs" :key="kb.id" :label="kb.name" :value="kb.id">
            <span>{{ kb.name }}</span>
            <span class="opt-meta">{{ kb.doc_count }} 篇</span>
          </el-option>
        </el-select>
        <button class="link-btn" @click="$router.push('/knowledge')">管理知识库</button>
      </div>

      <div class="messages" ref="messagesEl">
        <div v-if="!chat.messages.length" class="chat-empty">
          <p class="empty-title">选择知识库，开始提问</p>
          <p class="empty-sub">回答将基于所选知识库的内容生成，并附引用出处</p>
        </div>
        <ChatMessage v-for="m in chat.messages" :key="m.id" :message="m" />
        <div v-if="canRegenerate" class="regen-bar">
          <button class="regen-btn" @click="chat.regenerate()">重新生成</button>
        </div>
      </div>

      <div class="input-bar">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          resize="none"
          class="ink-textarea"
          placeholder="输入你的问题，Enter 发送"
          @keydown="onKeydown"
        />
        <div class="input-actions">
          <button v-if="chat.sending" class="stop-btn" @click="chat.stop()">
            <el-icon><VideoPause /></el-icon>停止
          </button>
          <button v-else class="send-dot" :disabled="!question.trim()" @click="send" aria-label="发送">
            <el-icon><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// 智能问答页：左侧会话列表 + 右侧知识库选择、消息流、底部输入线。
// 发送逻辑在 chat store（SSE 流式），这里只负责交互细节。
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Plus, Promotion, VideoPause } from '@element-plus/icons-vue'
import { useChatStore } from '../stores/chat'
import { useKbStore } from '../stores/kb'
import ChatMessage from '../components/ChatMessage.vue'

const chat = useChatStore()
const kb = useKbStore()
const question = ref('')
const messagesEl = ref<HTMLElement>()

function formatTime(s: string) {
  const d = new Date(s)
  return `${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(
    d.getMinutes()
  ).padStart(2, '0')}`
}

async function send() {
  const q = question.value.trim()
  if (!q) return
  question.value = '' // 先清空输入框，发送中禁用重复提交（由 store 控制）
  try {
    await chat.send(q)
  } catch (e: any) {
    ElMessage.warning(e.message)
  }
}

// 快捷键：Enter 发送，Shift+Enter 换行
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function removeConv(id: string) {
  // 用户点"取消"会 reject：用 try/catch 安静返回，避免未处理的 rejection
  try {
    await ElMessageBox.confirm('确定删除该对话？历史消息将一并删除。', '删除对话', {
      type: 'warning',
    })
  } catch {
    return
  }
  await chat.deleteConversation(id)
}

// 最后一条是 AI 回答且空闲时，允许"重新生成"（失败/中断/不满意都能一键重来）
const canRegenerate = computed(() => {
  const last = chat.messages[chat.messages.length - 1]
  return !chat.sending && !!last && last.role === 'assistant'
})

// 消息内容变化（流式增量）时自动滚动到底部，保证最新内容可见
watch(
  () => chat.messages.length && chat.messages[chat.messages.length - 1]?.content,
  () => nextTick(() => messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight }))
)

onMounted(async () => {
  await Promise.all([chat.fetchConversations(), kb.fetchKbs()])
  // 默认选中第一个知识库，减少用户操作步骤
  if (!chat.selectedKbIds.length && kb.kbs.length) {
    chat.selectedKbIds = [kb.kbs[0].id]
  }
})
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
}
/* 侧栏：与纸底同色，仅一条极细线分隔 */
.side {
  width: 250px;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  padding: 18px 14px;
}
/* 新建对话：文字按钮，无框 */
.new-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 6px 10px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: opacity 0.2s;
}
.new-btn:hover {
  opacity: 0.65;
}
.conv-list {
  flex: 1;
  overflow-y: auto;
}
.conv-item {
  position: relative;
  padding: 9px 12px 9px 14px;
  border-left: 2px solid transparent;
  cursor: pointer;
  margin-bottom: 4px;
  transition: border-color 0.2s;
}
/* 当前会话：墨黑加粗 + 左侧墨黑细竖线，不用高亮块 */
.conv-item.active {
  border-left-color: var(--ink);
}
.conv-item.active .conv-title {
  color: var(--ink);
  font-weight: 600;
}
.conv-title {
  font-size: 13px;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 16px;
}
.conv-meta {
  font-size: 11px;
  color: var(--ink-3);
  margin-top: 3px;
  font-variant-numeric: tabular-nums;
}
.conv-del {
  position: absolute;
  right: 8px;
  top: 11px;
  color: var(--ink-3);
  display: none;
  transition: color 0.2s;
}
.conv-item:hover .conv-del {
  display: block;
}
.conv-del:hover {
  color: var(--ink);
}
.conv-empty {
  color: var(--ink-3);
  font-size: 12px;
  padding: 12px 14px;
}
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.kb-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 28px;
  border-bottom: 1px solid var(--line);
}
.kb-label {
  font-size: 13px;
  color: var(--ink-3);
  white-space: nowrap;
  letter-spacing: 0.06em;
}
.opt-meta {
  float: right;
  font-size: 12px;
  color: var(--ink-3);
}
.link-btn {
  background: none;
  border: none;
  color: var(--ink-3);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.2s;
}
.link-btn:hover {
  color: var(--ink);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 36px 48px;
}
/* 空状态：两行小字，克制留白 */
.chat-empty {
  max-width: 640px;
  margin: 12vh auto 0;
  text-align: center;
}
.empty-title {
  font-family: var(--font-serif);
  font-size: 18px;
  color: var(--ink-2);
  letter-spacing: 0.1em;
  margin: 0 0 10px;
}
.empty-sub {
  font-size: 13px;
  color: var(--ink-3);
  margin: 0;
}
/* 底部输入：一条极细线 + 下划线输入 + 墨黑小圆发送点 */
.input-bar {
  border-top: 1px solid var(--line);
  padding: 16px 48px 18px;
  display: flex;
  align-items: flex-end;
  gap: 14px;
}
.ink-textarea {
  flex: 1;
}
.ink-textarea :deep(.el-textarea__inner) {
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  border-bottom: 1px solid var(--ink-3);
  padding: 6px 2px;
  color: var(--ink);
  transition: border-color 0.25s;
}
.ink-textarea :deep(.el-textarea__inner:focus) {
  border-bottom-color: var(--ink);
}
.input-actions {
  display: flex;
  align-items: center;
  padding-bottom: 4px;
}
/* 发送：墨黑小圆点 */
.send-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: var(--ink);
  color: #fdfcfa;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
}
.send-dot:hover:not(:disabled) {
  opacity: 0.82;
}
.send-dot:active:not(:disabled) {
  transform: scale(0.94);
}
.send-dot:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.stop-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--ink-2);
  font-size: 13px;
  cursor: pointer;
  padding: 8px 4px;
  transition: color 0.2s;
}
.stop-btn:hover {
  color: var(--ink);
}
/* 重新生成：居中一行淡墨文字按钮 */
.regen-bar {
  max-width: 860px;
  margin: 0 auto 8px;
  text-align: center;
}
.regen-btn {
  background: none;
  border: none;
  color: var(--ink-3);
  font-size: 12px;
  letter-spacing: 0.1em;
  cursor: pointer;
  padding: 4px 10px;
  transition: color 0.2s;
}
.regen-btn:hover {
  color: var(--ink);
}
</style>
