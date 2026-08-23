export interface Citation {
  chunk_id: string
  document_id: string
  filename: string
  location: string
  content: string
  score: number
}

export interface ChatEvent {
  type: 'token' | 'citations' | 'done' | 'error'
  content?: string
  citations?: Citation[]
  conversation_id?: string
  message_id?: string
  message?: string
}

export async function streamChat(
  payload: { question: string; kb_ids: string[]; conversation_id?: string | null },
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const resp = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('access_token')}`,
    },
    body: JSON.stringify(payload),
    signal,
  })
  if (!resp.ok || !resp.body) {
    let detail = `HTTP ${resp.status}`
    try {
      const j = await resp.json()
      if (typeof j.detail === 'string') detail = j.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)) as ChatEvent)
          } catch {
            /* skip malformed event */
          }
        }
      }
    }
  }
}
