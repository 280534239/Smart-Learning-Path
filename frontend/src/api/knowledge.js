import request, { LLM_REQUEST_TIMEOUT_MS } from './request'

export function getKnowledgeGraph(subject) {
  return request.get(`/knowledge/graph/${subject}`)
}

export function getLearningSubjects() {
  return request.get('/knowledge/subjects')
}

export function generateLearningSubject(payload) {
  return request.post('/knowledge/subjects/generate', payload, {
    timeout: LLM_REQUEST_TIMEOUT_MS,
  })
}

export function deleteLearningSubject(subject) {
  return request.delete(
    `/knowledge/subjects/${encodeURIComponent(subject)}`,
  )
}

export function getKnowledgePoint(knowledgePointId) {
  return request.get(`/knowledge/point/${knowledgePointId}`)
}

export function generateKnowledgePointResources(knowledgePointId) {
  return request.post(
    `/knowledge/point/${encodeURIComponent(knowledgePointId)}/resources`,
    {},
    { timeout: LLM_REQUEST_TIMEOUT_MS },
  )
}

export function getKnowledgeCategories(subject) {
  return request.get(`/knowledge/categories/${subject}`)
}
