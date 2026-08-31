// 问答状态（Pinia）：会话列表、当前消息流、发送与停止。
// 核心是 send()：乐观地先插入"用户消息 + 空的 AI 消息占位"，
// 再用 SSE 流把回答逐字填进占位消息，实现打字机效果。
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { http } from '../api/http'
import { streamChat, type Citation } from '../api/sse'
import type { Conversation, Message } from '../api/types'

// UI 消息 = 后端 Message + streaming 标记（正在流式生成中）
interface UiMessage extends Message {
  streaming?: boolean
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [] as Conversation[],
    currentId: null as string | null,
    messages: [] as UiMessage[],
    sending: false,
    selectedKbIds: [] as string[],
    controller: null as AbortController | null,
  }),
  actions: {
    async fetchConversations() {
      const { data } = await http.get('/conversations')
      this.conversations = data
    },
    // 切换会话：加载历史消息，并恢复该会话绑定的知识库选择
    async selectConversation(id: string) {
      this.currentId = id
      const { data } = await http.get(`/conversations/${id}/messages`)
      this.messages = data
      const conv = this.conversations.find((c) => c.id === id)
      if (conv && conv.kb_ids?.length) this.selectedKbIds = conv.kb_ids
    },
    newConversation() {
      this.currentId = null
      this.messages = []
    },
    async deleteConversation(id: string) {
      await http.delete(`/conversations/${id}`)
      if (this.currentId === id) this.newConversation()
      await this.fetchConversations()
    },
    // 停止生成：中断 SSE 连接，已收到的部分内容保留展示
    stop() {
      this.controller?.abort()
      this.controller = null
      this.sending = false
      const last = this.messages[this.messages.length - 1]
      if (last && last.streaming) last.streaming = false
    },
    // 重新生成：丢弃末尾的 AI 回答（失败/中断/不满意时），重发最近一次提问
    async regenerate() {
      if (this.sending) return
      const lastUser = [...this.messages].reverse().find((m) => m.role === 'user')
      if (!lastUser) return
      const last = this.messages[this.messages.length - 1]
      if (last && last.role === 'assistant') this.messages.pop()
      try {
        await this.send(lastUser.content, { skipUserEcho: true })
      } catch (e: any) {
        ElMessage.warning(e.message)
      }
    },
    // 发送提问：乐观更新 + SSE 流式填充
    // opts.skipUserEcho：重新生成场景下不再重复插入用户消息
    async send(question: string, opts: { skipUserEcho?: boolean } = {}) {
      if (!question.trim() || this.sending) return
      if (!this.selectedKbIds.length) throw new Error('请先选择至少一个知识库')

      // 1) 乐观插入用户消息（用临时 ID，稍后以服务端数据为准）
      if (!opts.skipUserEcho) {
        this.messages.push({
          id: `tmp-u-${Date.now()}`,
          role: 'user',
          content: question,
          citations: [],
          latency_ms: 0,
          created_at: new Date().toISOString(),
        })
      }
      // 2) 插入空的 AI 消息占位，SSE 事件到达时逐字填充它
      const assistant: UiMessage = {
        id: `tmp-a-${Date.now()}`,
        role: 'assistant',
        content: '',
        citations: [],
        latency_ms: 0,
        created_at: new Date().toISOString(),
        streaming: true,
      }
      this.messages.push(assistant)
      // 关键：必须取回数组里的"响应式代理"引用来改消息内容。
      // Vue 3 的响应性靠 Proxy 拦截读写 —— 直接修改上面那个原始对象（raw）
      // 会绕过 Proxy 的 setter，不触发任何界面更新，
      // 表现就是"回答生成完了页面却不动，必须刷新才显示"。
      const live = this.messages[this.messages.length - 1]
      this.sending = true
      this.controller = new AbortController()

      try {
        await streamChat(
          { question, kb_ids: this.selectedKbIds, conversation_id: this.currentId },
          (ev) => {
            // 3) 按事件类型分发（协议见 api/sse.ts）
            if (ev.type === 'token' && ev.content) {
              live.content += ev.content // 增量文本 → 打字机效果
            } else if (ev.type === 'citations') {
              live.citations = ev.citations || [] // 引用卡片数据
            } else if (ev.type === 'done') {
              // 结束事件：回填耗时；新会话此时才拿到真实 ID，刷新左侧会话列表
              if (ev.latency_ms) live.latency_ms = ev.latency_ms
              if (ev.conversation_id) {
                this.currentId = ev.conversation_id
                this.fetchConversations()
              }
            } else if (ev.type === 'error') {
              live.content += `\n\n> ${ev.message}`
            }
          },
          this.controller.signal
        )
      } catch (e: any) {
        // 主动停止（AbortError）不算错误，其余异常展示给用户
        if (e.name !== 'AbortError') {
          live.content += `\n\n> 请求失败：${e.message}`
        }
      } finally {
        live.streaming = false
        this.sending = false
        this.controller = null
      }
    },
  },
})
