// 与后端接口对应的 TypeScript 类型定义（出参形状）。
// 后端字段为 snake_case，这里保持一致，避免来回转换。
import type { Citation } from './sse'

// 用户
export interface User {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
}

// 知识库（含实时统计）
export interface KnowledgeBase {
  id: string
  name: string
  description: string
  owner_id: string
  visibility: 'private' | 'shared' | 'public'
  doc_count: number
  chunk_count: number
  created_at: string
}

// 文档（status 为索引状态机的当前状态）
export interface DocumentItem {
  id: string
  kb_id: string
  filename: string
  filetype: string
  size_bytes: number
  status: 'pending' | 'parsing' | 'embedding' | 'done' | 'failed'
  error: string
  chunk_count: number
  created_at: string
}

// 会话
export interface Conversation {
  id: string
  title: string
  kb_ids: string[]
  created_at: string
  message_count: number
}

// 消息（assistant 消息的 citations 携带引用来源）
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  latency_ms: number
  created_at: string
}
