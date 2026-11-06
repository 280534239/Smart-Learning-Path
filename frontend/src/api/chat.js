import request, { LLM_REQUEST_TIMEOUT_MS } from './request'

export function askQuestion(payload) {
  return request.post('/chat/ask', payload, {
    timeout: LLM_REQUEST_TIMEOUT_MS,
  })
}

export function getChatHistory(sessionId) {
  return request.get(`/chat/history/${sessionId}`, {
    params: { allow_missing: true },
    suppressNotFound: true,
  })
}

export function deleteChatSession(sessionId) {
  return request.delete(`/chat/history/${sessionId}`)
}
