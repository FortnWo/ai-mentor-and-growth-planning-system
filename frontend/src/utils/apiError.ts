import { isAxiosError } from 'axios'

export function getApiErrorMessage(caughtError: unknown, fallback: string): string {
  if (isAxiosError(caughtError)) {
    if (caughtError.code === 'ECONNABORTED') {
      return '请求超时，请稍后重试。'
    }

    if (!caughtError.response) {
      return '网络异常，请检查连接后重试。'
    }

    const status = caughtError.response.status
    if (status === 502 || status === 503 || status === 504) {
      return '服务暂时不可用，请稍后重试。'
    }
    if (status === 429) {
      return '请求过于频繁，请稍后再试。'
    }

    const detail = caughtError.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }

    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => {
          const location = Array.isArray(item?.loc) ? item.loc.slice(1).join('.') : ''
          const message = typeof item?.msg === 'string' ? item.msg : 'Validation error'
          return location ? `${location}: ${message}` : message
        })
        .join('; ')
    }
  }

  return fallback
}