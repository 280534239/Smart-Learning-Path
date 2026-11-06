import request from './request'

export function login(payload) {
  return request.post('/auth/login', payload)
}

export function register(payload) {
  return request.post('/auth/register', payload)
}

export function getProfile() {
  return request.get('/auth/profile')
}

export function updateProfile(payload) {
  return request.patch('/auth/profile', payload)
}

export function changePassword(payload) {
  return request.post('/auth/password', payload)
}

export function uploadAvatar(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/auth/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,
  })
}
