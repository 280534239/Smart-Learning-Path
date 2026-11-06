import axios from 'axios'
import { ElMessage } from 'element-plus'

export const TOKEN_STORAGE_KEY = 'slp_token'
export const USER_STORAGE_KEY = 'slp_user'
export const LLM_REQUEST_TIMEOUT_MS = 180_000

function getErrorMessage(payload) {
  const detail = payload?.detail ?? payload?.message
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg)
      .filter((item) => typeof item === 'string' && item.trim())
    if (messages.length) return messages.join('；')
  }
  return ''
}

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const payload = response.data
    if (payload && typeof payload.code === 'number') {
      if (payload.code !== 200) {
        const message = payload.message || '请求失败'
        ElMessage.error(message)
        return Promise.reject(new Error(message))
      }
      return payload.data
    }
    return payload
  },
  (error) => {
    const status = error.response?.status
    const payload = error.response?.data
    const ignoreNotFound =
      status === 404 && error.config?.suppressNotFound
    const isLoginRequest =
      error.config?.url?.includes('/auth/login') ||
      error.config?.url?.includes('/auth/register')
    const message =
      getErrorMessage(payload) ||
      (['ECONNABORTED', 'ETIMEDOUT'].includes(error.code)
        ? '请求超时，请稍后重试'
        : status === 502
          ? '模型生成失败，请稍后重试'
          : status === 503
            ? '模型服务暂不可用，请稍后重试'
            : status === 504
              ? '模型响应超时，请稍后重试'
              : '网络连接异常，请检查后端服务')

    if (status === 401 && !isLoginRequest) {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      localStorage.removeItem(USER_STORAGE_KEY)
      if (window.location.pathname !== '/login') {
        const redirect = `${window.location.pathname}${window.location.search}`
        window.location.assign(
          `/login?redirect=${encodeURIComponent(redirect)}`,
        )
      }
    }

    if (!ignoreNotFound) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)

export default request
