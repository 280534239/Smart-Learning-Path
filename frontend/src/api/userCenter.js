import request from './request'

export function getUserCenterSummary() {
  return request.get('/user-center/summary')
}
