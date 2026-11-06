import request, { LLM_REQUEST_TIMEOUT_MS } from './request'

export function getPracticeQuestions(
  knowledgePointId,
  { difficulty, count = 5 } = {},
) {
  return request.get(`/practice/questions/${knowledgePointId}`, {
    params: { difficulty, count },
    timeout: LLM_REQUEST_TIMEOUT_MS,
  })
}

export function submitAnswer(payload) {
  return request.post('/practice/submit', payload)
}

export function getErrorBook(
  subject,
  knowledgePointId = null,
) {
  return request.get('/practice/error-book', {
    params: {
      subject,
      knowledge_point_id: knowledgePointId,
    },
  })
}

export function reviewError(payload) {
  return request.post('/practice/error-book/review', payload)
}
