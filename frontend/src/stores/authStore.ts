import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User, AuthTokens, LoginCredentials, RegisterData } from '@/types'

interface AuthState {
  user: User | null
  tokens: AuthTokens | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
}

interface AuthActions {
  setUser: (user: User | null) => void
  setTokens: (tokens: AuthTokens | null) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  login: (credentials: LoginCredentials) => Promise<void>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<string | null>
  updateUser: (updates: Partial<User>) => void
  clearError: () => void
}

type AuthStore = AuthState & AuthActions

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // State
      user: null,
      tokens: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setTokens: (tokens) => set({ tokens }),
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),

      updateUser: (updates) => {
        const { user } = get()
        if (user) {
          set({ user: { ...user, ...updates } })
        }
      },

      login: async (credentials) => {
        set({ isLoading: true, error: null })
        try {
          // Import api lazily to avoid circular deps
          const { apiClient } = await import('@/services/api')
          const response = await apiClient.post<AuthTokens>('/auth/login', credentials)
          const tokens = response.data

          // Fetch user profile
          const userResponse = await apiClient.get<User>('/auth/me', {
            headers: { Authorization: `Bearer ${tokens.access_token}` },
          })

          set({
            tokens,
            user: userResponse.data,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        } catch (err: unknown) {
          const message =
            err instanceof Error ? err.message : 'Login failed. Please check your credentials.'
          set({ isLoading: false, error: message, isAuthenticated: false })
          throw err
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null })
        try {
          const { apiClient } = await import('@/services/api')
          const response = await apiClient.post<AuthTokens>('/auth/register', data)
          const tokens = response.data

          const userResponse = await apiClient.get<User>('/auth/me', {
            headers: { Authorization: `Bearer ${tokens.access_token}` },
          })

          set({
            tokens,
            user: userResponse.data,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'Registration failed.'
          set({ isLoading: false, error: message })
          throw err
        }
      },

      logout: () => {
        // Attempt server-side logout (fire and forget)
        const { tokens } = get()
        if (tokens?.access_token) {
          import('@/services/api').then(({ apiClient }) => {
            apiClient.post('/auth/logout').catch(() => {})
          })
        }
        set({
          user: null,
          tokens: null,
          isAuthenticated: false,
          error: null,
        })
      },

      refreshToken: async (): Promise<string | null> => {
        const { tokens } = get()
        if (!tokens?.refresh_token) return null

        try {
          const { apiClient } = await import('@/services/api')
          const response = await apiClient.post<{ access_token: string }>('/auth/refresh', {
            refresh_token: tokens.refresh_token,
          })
          const newAccessToken = response.data.access_token

          set({
            tokens: {
              ...tokens,
              access_token: newAccessToken,
            },
          })

          return newAccessToken
        } catch {
          // Refresh failed - logout
          set({ user: null, tokens: null, isAuthenticated: false })
          return null
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
