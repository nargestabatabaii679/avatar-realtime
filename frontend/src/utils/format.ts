import { format, formatDistanceToNow, parseISO, isValid } from 'date-fns'
import { ar, faIR, enUS, tr, fr, de } from 'date-fns/locale'

const localeMap: Record<string, Locale> = {
  en: enUS,
  fa: faIR,
  ar: ar,
  tr: tr,
  fr: fr,
  de: de,
}

export function getLocale(lang = 'en'): Locale {
  return localeMap[lang] ?? enUS
}

// Date formatting
export function formatDate(date: string | Date, lang = 'en', pattern = 'MMM d, yyyy'): string {
  try {
    const d = typeof date === 'string' ? parseISO(date) : date
    if (!isValid(d)) return '—'
    return format(d, pattern, { locale: getLocale(lang) })
  } catch {
    return '—'
  }
}

export function formatDateTime(date: string | Date, lang = 'en'): string {
  return formatDate(date, lang, 'MMM d, yyyy HH:mm')
}

export function formatRelativeTime(date: string | Date, lang = 'en'): string {
  try {
    const d = typeof date === 'string' ? parseISO(date) : date
    if (!isValid(d)) return '—'
    return formatDistanceToNow(d, { addSuffix: true, locale: getLocale(lang) })
  } catch {
    return '—'
  }
}

// File size formatting
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatStoragePercent(used: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((used / total) * 100)}%`
}

// Duration formatting
export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

export function formatDurationVerbose(seconds: number): string {
  if (!seconds || seconds < 0) return '0s'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const parts: string[] = []
  if (h > 0) parts.push(`${h}h`)
  if (m > 0) parts.push(`${m}m`)
  if (s > 0 || parts.length === 0) parts.push(`${s}s`)
  return parts.join(' ')
}

// Number formatting
export function formatNumber(value: number, lang = 'en'): string {
  return new Intl.NumberFormat(lang === 'fa' ? 'fa-IR' : lang).format(value)
}

export function formatCompactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}

export function formatChangePercent(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

// Status labels
export function formatStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' ')
}

// Truncation
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 3)}...`
}

// Bytes to appropriate unit
export function bytesToUnit(bytes: number, unit: 'B' | 'KB' | 'MB' | 'GB'): number {
  const k = 1024
  const units = { B: 0, KB: 1, MB: 2, GB: 3 }
  return bytes / Math.pow(k, units[unit])
}

// ETA formatting
export function formatETA(seconds: number): string {
  if (seconds <= 0) return 'Almost done...'
  if (seconds < 60) return `${Math.round(seconds)}s remaining`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m remaining`
  return `${Math.round(seconds / 3600)}h remaining`
}

// Script word count
export function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

// Estimated video duration from script
export function estimateVideoDuration(script: string, wpm = 140): number {
  const words = wordCount(script)
  return Math.round((words / wpm) * 60)
}
