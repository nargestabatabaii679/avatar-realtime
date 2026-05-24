import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import { wsService } from '@/services/websocket'
import type { LoginCredentials, RegisterData, User } from '@/types'
import { UserRole } from '@/types'

export function useAuth() {
  const navigate = useNavigate()
  const { user, tokens, isAuthenticated, isLoading, error, login, register, logout, clearError, updateUser } =
    useAuthStore()
  const { success, error: notifyError } = useNotificationStore()

  const handleLogin = useCallback(
    async (credentials: LoginCredentials) => {
      try {
        await login(credentials)
        success('Welcome back!', `Logged in successfully`)
        // Connect WebSocket
        const { tokens: newTokens } = useAuthStore.getState()
        if (newTokens?.access_token) {
          wsService.connect(newTokens.access_token)
        }
        navigate('/dashboard')
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Login failed'
        notifyError('Login Failed', message)
      }
    },
    [login, navigate, success, notifyError]
  )

  const handleRegister = useCallback(
    async (data: RegisterData) => {
      try {
        await register(data)
        success('Account Created!', 'Welcome to AvatarAI Platform')
        navigate('/dashboard')
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Registration failed'
        notifyError('Registration Failed', message)
      }
    },
    [register, navigate, success, notifyError]
  )

  const handleLogout = useCallback(() => {
    wsService.disconnect()
    logout()
    navigate('/login')
    success('Logged Out', 'See you next time!')
  }, [logout, navigate, success])

  // Role checks
  const isSuperAdmin = user?.role === UserRole.SUPER_ADMIN
  const isAdmin = user?.role === UserRole.SUPER_ADMIN || user?.role === UserRole.ADMIN
  const isEditor = isAdmin || user?.role === UserRole.EDITOR

  const hasRole = useCallback(
    (role: UserRole): boolean => {
      if (!user) return false
      const roleHierarchy: Record<UserRole, number> = {
        [UserRole.SUPER_ADMIN]: 4,
        [UserRole.ADMIN]: 3,
        [UserRole.EDITOR]: 2,
        [UserRole.VIEWER]: 1,
      }
      return roleHierarchy[user.role] >= roleHierarchy[role]
    },
    [user]
  )

  const canManageUsers = isAdmin
  const canCreateContent = isEditor

  // Storage helpers
  const storageUsedPct = user
    ? Math.min(100, (user.storage_used / user.storage_limit) * 100)
    : 0

  const apiCallsUsedPct = user
    ? Math.min(100, (user.api_calls_today / user.api_calls_limit) * 100)
    : 0

  return {
    user,
    tokens,
    isAuthenticated,
    isLoading,
    error,
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
    clearError,
    updateUser: (updates: Partial<User>) => updateUser(updates),
    isSuperAdmin,
    isAdmin,
    isEditor,
    hasRole,
    canManageUsers,
    canCreateContent,
    storageUsedPct,
    apiCallsUsedPct,
  }
}
