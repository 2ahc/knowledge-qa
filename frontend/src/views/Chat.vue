<template>
  <div class="chat-page">
    <!-- 会话侧栏 -->
    <aside class="side">
      <el-button type="primary" class="new-btn" @click="chat.newConversation()">
        <el-icon><Plus /></el-icon>&nbsp;新建对话
      </el-button>
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
        <el-empty v-if="!chat.conversations.length" description="暂无对话" :image-size="60" />
      </div>
    </aside>

    <!-- 主区域 -->
    <section class="main-area">
      <div class="kb-bar">
        <span class="kb-label">知识库：</span>
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
        <el-button text type="primary" @click="$router.push('/knowledge')">管理知识库</el-button>
      </div>

      <div class="messages" ref="messagesEl">
        <el-empty
          v-if="!chat.messages.length"
          description="选择知识库，开始提问吧 🧋"
          :image-size="90"
        />
        <ChatMessage v-for="m in chat.messages" :key="m.id" :message="m" />
      </div>

      <div class="input-bar">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="输入你的问题，Enter 发送，Shift+Enter 换行"
          @keydown="onKeydown"
        />
        <div class="input-actions">
          <el-button v-if="chat.sending" type="danger" plain @click="chat.stop()">
            <el-icon><VideoPause /></el-icon>&nbsp;停止
          </el-button>
          <el-button v-else type="primary" :disabled="!question.trim()" @click="send">
            <el-icon><Promotion /></el-icon>&nbsp;发送
          </el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
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
  question.value = ''
  try {
    await chat.send(q)
  } catch (e: any) {
    ElMessage.warning(e.message)
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function removeConv(id: string) {
  await ElMessageBox.confirm('确定删除该对话？历史消息将一并删除。', '删除对话', {
    type: 'warning',
  }).catch(() => Promise.reject())
  await chat.deleteConversation(id)
}

watch(
  () => chat.messages.length && chat.messages[chat.messages.length - 1]?.content,
  () => nextTick(() => messagesEl.value?.scrollTo({ top: messagesEl.value.scrollHeight }))
)

onMounted(async () => {
  await Promise.all([chat.fetchConversations(), kb.fetchKbs()])
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
.side {
  width: 250px;
  background: #fff;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  padding: 14px;
}
.new-btn {
  margin-bottom: 12px;
}
.conv-list {
  flex: 1;
  overflow-y: auto;
}
.conv-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: background 0.15s;
}
.conv-item:hover {
  background: #f3f6fb;
}
.conv-item.active {
  background: #eaf1ff;
}
.conv-title {
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 16px;
}
.conv-meta {
  font-size: 11px;
  color: var(--sub);
  margin-top: 3px;
}
.conv-del {
  position: absolute;
  right: 8px;
  top: 10px;
  color: var(--sub);
  display: none;
}
.conv-item:hover .conv-del {
  display: block;
}
.conv-del:hover {
  color: #e5484d;
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
  gap: 8px;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid var(--line);
}
.kb-label {
  font-size: 13px;
  color: var(--sub);
  white-space: nowrap;
}
.opt-meta {
  float: right;
  font-size: 12px;
  color: var(--sub);
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.input-bar {
  background: #fff;
  border-top: 1px solid var(--line);
  padding: 14px 20px;
}
.input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>
