import { create } from 'zustand'
import type { NotificationItem } from '@/types'

interface ToastNotification {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
}

interface NotificationState {
  toasts: ToastNotification[]
  notifications: NotificationItem[]
  unreadCount: number
}

interface NotificationActions {
  addToast: (toast: Omit<ToastNotification, 'id'>) => void
  removeToast: (id: string) => void
  clearToasts: () => void
  addNotification: (notification: Omit<NotificationItem, 'id' | 'timestamp' | 'read'>) => void
  markAsRead: (id: string) => void
  markAllAsRead: () => void
  removeNotification: (id: string) => void
  clearNotifications: () => void
  // Convenience methods
  success: (title: string, message?: string, duration?: number) => void
  error: (title: string, message?: string, duration?: number) => void
  warning: (title: string, message?: string, duration?: number) => void
  info: (title: string, message?: string, duration?: number) => void
}

type NotificationStore = NotificationState & NotificationActions

let toastCounter = 0

export const useNotificationStore = create<NotificationStore>()((set, get) => ({
  toasts: [],
  notifications: [],
  unreadCount: 0,

  addToast: (toast) => {
    const id = `toast-${++toastCounter}-${Date.now()}`
    const newToast: ToastNotification = { ...toast, id }
    set((state) => ({ toasts: [...state.toasts, newToast] }))

    // Auto-remove after duration
    const duration = toast.duration ?? 5000
    if (duration > 0) {
      setTimeout(() => {
        get().removeToast(id)
      }, duration)
    }
  },

  removeToast: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
  },

  clearToasts: () => set({ toasts: [] }),

  addNotification: (notification) => {
    const newNotification: NotificationItem = {
      ...notification,
      id: `notif-${Date.now()}`,
      timestamp: new Date().toISOString(),
      read: false,
    }
    set((state) => ({
      notifications: [newNotification, ...state.notifications].slice(0, 100),
      unreadCount: state.unreadCount + 1,
    }))
  },

  markAsRead: (id) => {
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
      unreadCount: Math.max(0, state.unreadCount - 1),
    }))
  },

  markAllAsRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }))
  },

  removeNotification: (id) => {
    set((state) => {
      const notif = state.notifications.find((n) => n.id === id)
      return {
        notifications: state.notifications.filter((n) => n.id !== id),
        unreadCount: notif && !notif.read ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
      }
    })
  },

  clearNotifications: () => set({ notifications: [], unreadCount: 0 }),

  // Convenience helpers
  success: (title, message, duration) => {
    get().addToast({ type: 'success', title, message, duration })
  },
  error: (title, message, duration) => {
    get().addToast({ type: 'error', title, message, duration: duration ?? 8000 })
  },
  warning: (title, message, duration) => {
    get().addToast({ type: 'warning', title, message, duration })
  },
  info: (title, message, duration) => {
    get().addToast({ type: 'info', title, message, duration })
  },
}))
