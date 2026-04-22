import { isAxiosError } from 'axios'

export function getApiErrorMessage(caughtError: unknown, fallback: string): string {
  if (isAxiosError(caughtError)) {
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