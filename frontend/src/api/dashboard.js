
import request from './request'

export function getLearningProgress(subject) {
  return request.get('/dashboard/progress', {
    params: { subject },
  })
}

export function analyzeLearning(subject) {
  return request.post('/recommend/analyze', {
    subject,
  })
}
