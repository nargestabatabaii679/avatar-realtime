import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
  type AxiosError,
} from 'axios'
import type {
  User,
  Avatar,
  VoiceModel,
  Video,
  VideoJob,
  Agent,
  KnowledgeBase,
  Document,
  SearchResult,
  AnalyticsSummary,
  TimeSeriesDataPoint,
  AvatarUsageStat,
  ResolutionBreakdown,
  StorageGrowth,
  AgentConversationStat,
  GPUStats,
  SystemHealth,
  AuditLog,
  SystemModel,
  AuthTokens,
  PaginatedResponse,
  PaginationParams,
  CreateAvatarRequest,
  UpdateAvatarRequest,
  CreateVoiceRequest,
  VoiceSynthesisRequest,
  VoiceSynthesisResponse,
  CreateVideoRequest,
  UpdateVideoRequest,
  CreateAgentRequest,
  CreateKnowledgeBaseRequest,
  AddDocumentRequest,
  KnowledgeSearchRequest,
  LoginCredentials,
  RegisterData,
  FileUploadResult,
  Conversation,
} from '@/types'

const BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

// Create the axios instance
export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

// Flag to prevent multiple simultaneous token refreshes
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error)
    } else if (token) {
      resolve(token)
    }
  })
  failedQueue = []
}

// Request interceptor - attach token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Get token from localStorage directly to avoid circular dep with store
    try {
      const authData = localStorage.getItem('auth-storage')
      if (authData) {
        const parsed = JSON.parse(authData)
        const token = parsed?.state?.tokens?.access_token
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`
        }
      }
    } catch {
      // Ignore parse errors
    }

    // Dev logging
    if (import.meta.env.DEV) {
      console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`, config.data)
    }

    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor - handle 401, normalize errors
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    if (import.meta.env.DEV) {
      console.debug(`[API] Response ${response.status}`, response.config.url)
    }
    return response
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token) => {
              originalRequest.headers.Authorization = `Bearer ${token}`
              resolve(apiClient(originalRequest))
            },
            reject,
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const authData = localStorage.getItem('auth-storage')
        if (authData) {
          const parsed = JSON.parse(authData)
          const refreshToken = parsed?.state?.tokens?.refresh_token
          if (refreshToken) {
            const response = await axios.post<{ access_token: string }>(
              `${BASE_URL}/auth/refresh`,
              { refresh_token: refreshToken }
            )
            const newToken = response.data.access_token

            // Update stored token
            parsed.state.tokens.access_token = newToken
            localStorage.setItem('auth-storage', JSON.stringify(parsed))

            processQueue(null, newToken)
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            return apiClient(originalRequest)
          }
        }
      } catch (refreshError) {
        processQueue(refreshError, null)
        // Clear auth state
        localStorage.removeItem('auth-storage')
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Normalize error
    const apiError = {
      status: error.response?.status ?? 0,
      message:
        (error.response?.data as Record<string, string>)?.detail ??
        (error.response?.data as Record<string, string>)?.message ??
        error.message ??
        'An unexpected error occurred',
      detail: error.response?.data,
      code: error.code,
    }

    if (import.meta.env.DEV) {
      console.error('[API] Error:', apiError)
    }

    return Promise.reject(apiError)
  }
)

// ============================================================
// Auth API
// ============================================================

export const authApi = {
  login: (credentials: LoginCredentials) =>
    apiClient.post<AuthTokens>('/auth/login', credentials),

  register: (data: RegisterData) =>
    apiClient.post<AuthTokens>('/auth/register', data),

  logout: () => apiClient.post('/auth/logout'),

  me: () => apiClient.get<User>('/auth/me'),

  refreshToken: (refreshToken: string) =>
    apiClient.post<{ access_token: string }>('/auth/refresh', {
      refresh_token: refreshToken,
    }),

  forgotPassword: (email: string) =>
    apiClient.post('/auth/forgot-password', { email }),

  resetPassword: (token: string, password: string) =>
    apiClient.post('/auth/reset-password', { token, password }),

  changePassword: (current_password: string, new_password: string) =>
    apiClient.post('/auth/change-password', { current_password, new_password }),

  updateProfile: (data: Partial<User>) =>
    apiClient.patch<User>('/auth/me', data),
}

// ============================================================
// Avatar API
// ============================================================

export const avatarApi = {
  list: (params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<Avatar>>('/avatars', { params }),

  get: (id: string) => apiClient.get<Avatar>(`/avatars/${id}`),

  create: (data: CreateAvatarRequest) =>
    apiClient.post<Avatar>('/avatars', data),

  update: (id: string, data: UpdateAvatarRequest) =>
    apiClient.patch<Avatar>(`/avatars/${id}`, data),

  delete: (id: string) => apiClient.delete(`/avatars/${id}`),

  uploadSource: (id: string, formData: FormData, onProgress?: (pct: number) => void) =>
    apiClient.post<Avatar>(`/avatars/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      },
    }),

  getPublic: (params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<Avatar>>('/avatars/public', { params }),

  startProcessing: (id: string) =>
    apiClient.post<VideoJob>(`/avatars/${id}/process`),
}

// ============================================================
// Voice API
// ============================================================

export const voiceApi = {
  list: (params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<VoiceModel>>('/voices', { params }),

  get: (id: string) => apiClient.get<VoiceModel>(`/voices/${id}`),

  create: (data: CreateVoiceRequest) =>
    apiClient.post<VoiceModel>('/voices', data),

  update: (id: string, data: Partial<CreateVoiceRequest>) =>
    apiClient.patch<VoiceModel>(`/voices/${id}`, data),

  delete: (id: string) => apiClient.delete(`/voices/${id}`),

  uploadSample: (id: string, formData: FormData, onProgress?: (pct: number) => void) =>
    apiClient.post(`/voices/${id}/samples`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      },
    }),

  startTraining: (id: string) =>
    apiClient.post<VideoJob>(`/voices/${id}/train`),

  synthesize: (data: VoiceSynthesisRequest) =>
    apiClient.post<VoiceSynthesisResponse>('/voices/synthesize', data),

  getSystemVoices: (lang?: string) =>
    apiClient.get<VoiceModel[]>('/voices/system', { params: { lang } }),
}

// ============================================================
// Video API
// ============================================================

export const videoApi = {
  list: (params?: PaginationParams & { status?: string; avatar_id?: string }) =>
    apiClient.get<PaginatedResponse<Video>>('/videos', { params }),

  get: (id: string) => apiClient.get<Video>(`/videos/${id}`),

  create: (data: CreateVideoRequest) =>
    apiClient.post<Video>('/videos', data),

  update: (id: string, data: UpdateVideoRequest) =>
    apiClient.patch<Video>(`/videos/${id}`, data),

  delete: (id: string) => apiClient.delete(`/videos/${id}`),

  getJob: (videoId: string) =>
    apiClient.get<VideoJob>(`/videos/${videoId}/job`),

  cancelJob: (videoId: string) =>
    apiClient.post(`/videos/${videoId}/cancel`),

  retryJob: (videoId: string) =>
    apiClient.post<Video>(`/videos/${videoId}/retry`),

  download: (id: string) => apiClient.get(`/videos/${id}/download`, { responseType: 'blob' }),

  getTemplates: () => apiClient.get<Array<{ id: string; name: string; preview_url: string }>>('/videos/templates'),
}

// ============================================================
// Job API
// ============================================================

export const jobApi = {
  get: (id: string) => apiClient.get<VideoJob>(`/jobs/${id}`),

  list: (params?: PaginationParams & { status?: string; type?: string }) =>
    apiClient.get<PaginatedResponse<VideoJob>>('/jobs', { params }),

  cancel: (id: string) => apiClient.post(`/jobs/${id}/cancel`),

  retry: (id: string) => apiClient.post<VideoJob>(`/jobs/${id}/retry`),
}

// ============================================================
// Agent API
// ============================================================

export const agentApi = {
  list: (params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<Agent>>('/agents', { params }),

  get: (id: string) => apiClient.get<Agent>(`/agents/${id}`),

  create: (data: CreateAgentRequest) =>
    apiClient.post<Agent>('/agents', data),

  update: (id: string, data: Partial<CreateAgentRequest>) =>
    apiClient.patch<Agent>(`/agents/${id}`, data),

  delete: (id: string) => apiClient.delete(`/agents/${id}`),

  getEmbedCode: (id: string) =>
    apiClient.get<{ code: string; script_url: string }>(`/agents/${id}/embed`),

  chat: (id: string, message: string, sessionId?: string) =>
    apiClient.post<{ response: string; session_id: string; audio_url?: string }>(
      `/agents/${id}/chat`,
      { message, session_id: sessionId }
    ),

  getConversations: (id: string, params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<Conversation>>(`/agents/${id}/conversations`, { params }),
}

// ============================================================
// Knowledge Base API
// ============================================================

export const knowledgeApi = {
  list: (params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<KnowledgeBase>>('/knowledge-bases', { params }),

  get: (id: string) => apiClient.get<KnowledgeBase>(`/knowledge-bases/${id}`),

  create: (data: CreateKnowledgeBaseRequest) =>
    apiClient.post<KnowledgeBase>('/knowledge-bases', data),

  update: (id: string, data: Partial<CreateKnowledgeBaseRequest>) =>
    apiClient.patch<KnowledgeBase>(`/knowledge-bases/${id}`, data),

  delete: (id: string) => apiClient.delete(`/knowledge-bases/${id}`),

  listDocuments: (kbId: string, params?: PaginationParams) =>
    apiClient.get<PaginatedResponse<Document>>(`/knowledge-bases/${kbId}/documents`, { params }),

  addDocument: (data: AddDocumentRequest) =>
    apiClient.post<Document>(`/knowledge-bases/${data.knowledge_base_id}/documents`, data),

  uploadDocument: (
    kbId: string,
    formData: FormData,
    onProgress?: (pct: number) => void
  ) =>
    apiClient.post<Document>(`/knowledge-bases/${kbId}/documents/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      },
    }),

  deleteDocument: (kbId: string, docId: string) =>
    apiClient.delete(`/knowledge-bases/${kbId}/documents/${docId}`),

  search: (data: KnowledgeSearchRequest) =>
    apiClient.post<SearchResult[]>('/knowledge-bases/search', data),
}

// ============================================================
// Analytics API
// ============================================================

export const analyticsApi = {
  getSummary: (params: { from: string; to: string }) =>
    apiClient.get<AnalyticsSummary>('/analytics/summary', { params }),

  getVideosTimeSeries: (params: { from: string; to: string; interval?: string }) =>
    apiClient.get<TimeSeriesDataPoint[]>('/analytics/videos/time-series', { params }),

  getAvatarUsage: (params: { from: string; to: string; limit?: number }) =>
    apiClient.get<AvatarUsageStat[]>('/analytics/avatars/usage', { params }),

  getResolutionBreakdown: (params: { from: string; to: string }) =>
    apiClient.get<ResolutionBreakdown[]>('/analytics/videos/resolutions', { params }),

  getStorageGrowth: (params: { from: string; to: string }) =>
    apiClient.get<StorageGrowth[]>('/analytics/storage/growth', { params }),

  getAgentStats: (params: { from: string; to: string }) =>
    apiClient.get<AgentConversationStat[]>('/analytics/agents/conversations', { params }),

  getGPUStats: () => apiClient.get<GPUStats>('/analytics/gpu'),

  exportCSV: (params: { from: string; to: string; type: string }) =>
    apiClient.get('/analytics/export', { params, responseType: 'blob' }),
}

// ============================================================
// Admin API
// ============================================================

export const adminApi = {
  // Users
  listUsers: (params?: PaginationParams & { role?: string; status?: string }) =>
    apiClient.get<PaginatedResponse<User>>('/admin/users', { params }),

  getUser: (id: string) => apiClient.get<User>(`/admin/users/${id}`),

  updateUser: (id: string, data: Partial<User>) =>
    apiClient.patch<User>(`/admin/users/${id}`, data),

  suspendUser: (id: string) => apiClient.post(`/admin/users/${id}/suspend`),

  activateUser: (id: string) => apiClient.post(`/admin/users/${id}/activate`),

  // Jobs
  listJobs: (params?: PaginationParams & { status?: string; type?: string }) =>
    apiClient.get<PaginatedResponse<VideoJob>>('/admin/jobs', { params }),

  retryJob: (id: string) => apiClient.post(`/admin/jobs/${id}/retry`),

  cancelJob: (id: string) => apiClient.post(`/admin/jobs/${id}/cancel`),

  // System
  getSystemHealth: () => apiClient.get<SystemHealth>('/admin/system/health'),

  getModels: () => apiClient.get<SystemModel[]>('/admin/models'),

  reloadModel: (id: string) => apiClient.post(`/admin/models/${id}/reload`),

  // Audit Logs
  getAuditLogs: (params?: PaginationParams & { action?: string; user_id?: string }) =>
    apiClient.get<PaginatedResponse<AuditLog>>('/admin/audit-logs', { params }),
}

// ============================================================
// File Upload API
// ============================================================

export const fileApi = {
  upload: (formData: FormData, onProgress?: (pct: number) => void, config?: AxiosRequestConfig) =>
    apiClient.post<FileUploadResult>('/files/upload', formData, {
      ...config,
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      },
    }),
}

// Convenience alias used by page components
export const api = apiClient
