import axios from 'axios'

const ACCESS_TOKEN_STORAGE_KEY = 'ai_mentor_access_token'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10_000,
})

apiClient.interceptors.request.use((config) => {
  const url = config.url ?? ''
  if (url.includes('/auth/login')) {
    return config
  }

  const token = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }

  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      const requestUrl = String(error.config?.url ?? '')
      const isLoginRequest = requestUrl.includes('/auth/login')

      if (!isLoginRequest) {
        void import('../stores/auth').then(({ clearAuthSession }) => {
          clearAuthSession()
        })
      }
    }
    console.error('[API Error]', error.response?.data ?? error.message)
    return Promise.reject(error)
  },
)

export default apiClient
