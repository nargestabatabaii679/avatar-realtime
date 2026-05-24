import { RTL_LANGUAGES, type LanguageCode } from '@/types'

export function isRTL(lang: LanguageCode): boolean {
  return RTL_LANGUAGES.includes(lang)
}

export function getDirection(lang: LanguageCode): 'rtl' | 'ltr' {
  return isRTL(lang) ? 'rtl' : 'ltr'
}

export function applyDirection(lang: LanguageCode): void {
  const dir = getDirection(lang)
  document.documentElement.dir = dir
  document.documentElement.lang = lang
  if (lang === 'fa' || lang === 'ar') {
    document.documentElement.style.fontFamily = "'Vazirmatn', system-ui, sans-serif"
  } else {
    document.documentElement.style.fontFamily = "'Inter', system-ui, sans-serif"
  }
}

// Tailwind RTL-aware class helpers
export function rtlClass(ltrClass: string, rtlClass: string, isRtl: boolean): string {
  return isRtl ? rtlClass : ltrClass
}

// Flip margin/padding for RTL
export function marginStart(isRtl: boolean): string {
  return isRtl ? 'mr' : 'ml'
}

export function marginEnd(isRtl: boolean): string {
  return isRtl ? 'ml' : 'mr'
}

// Icon direction flip for arrows
export function getArrowDirection(isRtl: boolean, direction: 'left' | 'right'): 'left' | 'right' {
  if (!isRtl) return direction
  return direction === 'left' ? 'right' : 'left'
}

// Sidebar position
export function getSidebarPosition(isRtl: boolean): 'left' | 'right' {
  return isRtl ? 'right' : 'left'
}

// Text alignment
export function getTextAlign(isRtl: boolean): 'text-right' | 'text-left' {
  return isRtl ? 'text-right' : 'text-left'
}

// Number display in Persian digits
const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹']

export function toPersianDigits(num: number | string): string {
  return String(num).replace(/\d/g, (d) => persianDigits[parseInt(d)])
}

// Convert Persian/Arabic digits to English
export function toEnglishDigits(str: string): string {
  return str
    .replace(/[۰-۹]/g, (d) => String(persianDigits.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 1632))
}
