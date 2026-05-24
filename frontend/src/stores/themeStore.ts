import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { ThemeMode, LanguageCode } from '@/types'
import { applyDirection } from '@/utils/rtl'

interface ThemeState {
  theme: ThemeMode
  language: LanguageCode
  isRTL: boolean
  resolvedTheme: 'light' | 'dark'
}

interface ThemeActions {
  setTheme: (theme: ThemeMode) => void
  setLanguage: (lang: LanguageCode) => void
  toggleTheme: () => void
  initializeTheme: () => void
  getEffectiveTheme: () => 'light' | 'dark'
}

type ThemeStore = ThemeState & ThemeActions

const RTL_LANGS: LanguageCode[] = ['fa', 'ar']

function detectSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyThemeToDOM(resolvedTheme: 'light' | 'dark'): void {
  const root = document.documentElement
  if (resolvedTheme === 'dark') {
    root.classList.add('dark')
    root.classList.remove('light')
  } else {
    root.classList.remove('dark')
    root.classList.add('light')
  }
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      // State
      theme: 'system',
      language: 'en',
      isRTL: false,
      resolvedTheme: 'light',

      // Actions
      getEffectiveTheme: (): 'light' | 'dark' => {
        const { theme } = get()
        if (theme === 'system') return detectSystemTheme()
        return theme
      },

      setTheme: (theme) => {
        const resolvedTheme = theme === 'system' ? detectSystemTheme() : theme
        applyThemeToDOM(resolvedTheme)
        localStorage.setItem('theme', theme)
        set({ theme, resolvedTheme })
      },

      setLanguage: (language) => {
        const isRTL = RTL_LANGS.includes(language)
        applyDirection(language)
        localStorage.setItem('language', language)
        set({ language, isRTL })
      },

      toggleTheme: () => {
        const { resolvedTheme } = get()
        const newTheme: ThemeMode = resolvedTheme === 'dark' ? 'light' : 'dark'
        get().setTheme(newTheme)
      },

      initializeTheme: () => {
        const { theme, language } = get()
        const resolvedTheme = theme === 'system' ? detectSystemTheme() : theme
        const isRTL = RTL_LANGS.includes(language)

        applyThemeToDOM(resolvedTheme)
        applyDirection(language)
        set({ resolvedTheme, isRTL })

        // Listen for system theme changes
        if (typeof window !== 'undefined') {
          const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
          mediaQuery.addEventListener('change', (e) => {
            const { theme } = get()
            if (theme === 'system') {
              const resolved = e.matches ? 'dark' : 'light'
              applyThemeToDOM(resolved)
              set({ resolvedTheme: resolved })
            }
          })
        }
      },
    }),
    {
      name: 'theme-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        theme: state.theme,
        language: state.language,
      }),
    }
  )
)
