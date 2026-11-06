import { USER_STORAGE_KEY } from '../api/request'

export function getStoredUserId() {
  try {
    const user = JSON.parse(
      localStorage.getItem(USER_STORAGE_KEY) || 'null',
    )
    return user?.id ? String(user.id) : 'guest'
  } catch {
    return 'guest'
  }
}

export function getUserScopedStorageKey(baseKey) {
  return `${baseKey}:${getStoredUserId()}`
}
