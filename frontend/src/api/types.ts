export interface User {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
}

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

export interface Conversation {
  id: string
  title: string
  kb_ids: string[]
  created_at: string
  message_count: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: any[]
  latency_ms: number
  created_at: string
}
