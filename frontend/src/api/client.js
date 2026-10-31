const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

/**
 * 调用后端接口并解包统一响应。
 * @param {string} path 接口路径
 * @param {RequestInit} options fetch 配置
 * @returns {Promise<unknown>} 业务数据
 */
async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  const payload = await response.json()

  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || '请求失败')
  }

  return payload.data
}

/**
 * 获取后端健康状态。
 * @returns {Promise<object>} 健康检查数据
 */
export function getHealth() {
  return request('/api/health')
}
