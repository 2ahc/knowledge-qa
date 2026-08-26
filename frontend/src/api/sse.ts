// SSE 流式问答客户端：用 fetch + ReadableStream 手动解析 SSE 流。
// 为什么不用 EventSource：EventSource 只支持 GET 且无法自定义请求头，
// 而问答接口是 POST 且需要 Authorization 头。

// 引用来源：与后端 RetrievedChunk 对应
export interface Citation {
  chunk_id: string
  document_id: string
  filename: string
  location: string
  content: string
  score: number
}

// SSE 事件：协议与后端 chat.py 定义一致
//   token     —— 回答增量文本（逐块到达，打字机效果）
//   citations —— 引用来源列表（先于回答到达）
//   done      —— 结束，携带会话与消息 ID
//   error     —— 过程出错
export interface ChatEvent {
  type: 'token' | 'citations' | 'done' | 'error'
  content?: string
  citations?: Citation[]
  conversation_id?: string
  message_id?: string
  message?: string
}

// 发起流式问答。每解析出一个完整事件就回调 onEvent；
// signal 支持中途取消（用户点"停止生成"）。
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
    // 非流式错误（如 401/422）：尝试读后端返回的中文错误信息
    let detail = `HTTP ${resp.status}`
    try {
      const j = await resp.json()
      if (typeof j.detail === 'string') detail = j.detail
    } catch {
      /* 忽略 */
    }
    throw new Error(detail)
  }
  // 逐块读取流，按 SSE 协议（事件之间以空行 \n\n 分隔）切分并解析
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    // 一个事件帧以 \n\n 结尾；缓冲区里可能有多个完整帧，循环取出
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)) as ChatEvent)
          } catch {
            /* 跳过格式错误的事件 */
          }
        }
      }
    }
  }
}
