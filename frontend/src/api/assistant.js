import { TOKEN_STORAGE_KEY } from './request'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || '/api'
).replace(/\/$/, '')

export async function streamAssistantQuestion(
  payload,
  { signal, onEvent } = {},
) {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  const response = await fetch(`${API_BASE_URL}/assistant/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let message = '助手暂时无法回答，请稍后重试'
    try {
      const errorBody = await response.json()
      message = errorBody.detail || errorBody.message || message
    } catch {
      // 非 JSON 错误响应使用通用提示。
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式回答')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    buffer = consumeEvents(buffer, onEvent)
  }

  buffer += decoder.decode()
  consumeEvents(`${buffer}\n\n`, onEvent)
}

function consumeEvents(buffer, onEvent) {
  const blocks = buffer.split(/\r?\n\r?\n/)
  let remainder = blocks.pop() || ''
  for (const block of blocks) {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (!data) continue
    try {
      onEvent?.(JSON.parse(data))
    } catch {
      // 忽略无法解析的心跳或非业务事件。
    }
  }
  return remainder
}
