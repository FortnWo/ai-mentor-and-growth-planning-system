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
    console.error('[API Error]', error.response?.data ?? error.message)
    return Promise.reject(error)
  },
)

export default apiClient
