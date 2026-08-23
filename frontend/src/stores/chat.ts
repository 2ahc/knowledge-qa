import { defineStore } from 'pinia'
import { http } from '../api/http'
import { streamChat, type Citation } from '../api/sse'
import type { Conversation, Message } from '../api/types'

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
    stop() {
      this.controller?.abort()
      this.controller = null
      this.sending = false
      const last = this.messages[this.messages.length - 1]
      if (last && last.streaming) last.streaming = false
    },
    async send(question: string) {
      if (!question.trim() || this.sending) return
      if (!this.selectedKbIds.length) throw new Error('请先选择至少一个知识库')

      this.messages.push({
        id: `tmp-u-${Date.now()}`,
        role: 'user',
        content: question,
        citations: [],
        latency_ms: 0,
        created_at: new Date().toISOString(),
      })
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
      this.sending = true
      this.controller = new AbortController()

      try {
        await streamChat(
          { question, kb_ids: this.selectedKbIds, conversation_id: this.currentId },
          (ev) => {
            if (ev.type === 'token' && ev.content) {
              assistant.content += ev.content
            } else if (ev.type === 'citations') {
              assistant.citations = ev.citations || []
            } else if (ev.type === 'done') {
              if (ev.conversation_id) {
                this.currentId = ev.conversation_id
                this.fetchConversations()
              }
            } else if (ev.type === 'error') {
              assistant.content += `\n\n> ⚠️ ${ev.message}`
            }
          },
          this.controller.signal
        )
      } catch (e: any) {
        if (e.name !== 'AbortError') {
          assistant.content += `\n\n> ⚠️ 请求失败：${e.message}`
        }
      } finally {
        assistant.streaming = false
        this.sending = false
        this.controller = null
      }
    },
  },
})
