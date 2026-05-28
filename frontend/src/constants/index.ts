/** Centralized app-wide constants — import from here, not inline */
import type { LanguageCode } from "../types";

// ── Languages ─────────────────────────────────────────────────
export interface Language {
  code: LanguageCode;
  label: string;
  nativeLabel: string;
  flag: string;
  dir: "ltr" | "rtl";
}

export const LANGUAGES: Language[] = [
  { code: "fa", label: "Persian",  nativeLabel: "فارسی",    flag: "🇮🇷", dir: "rtl" },
  { code: "en", label: "English",  nativeLabel: "English",  flag: "🇺🇸", dir: "ltr" },
  { code: "ar", label: "Arabic",   nativeLabel: "العربية",  flag: "🇸🇦", dir: "rtl" },
  { code: "tr", label: "Turkish",  nativeLabel: "Türkçe",   flag: "🇹🇷", dir: "ltr" },
  { code: "fr", label: "French",   nativeLabel: "Français", flag: "🇫🇷", dir: "ltr" },
  { code: "de", label: "German",   nativeLabel: "Deutsch",  flag: "🇩🇪", dir: "ltr" },
];

export const RTL_LANGS = LANGUAGES.filter((l) => l.dir === "rtl").map((l) => l.code);

// ── Route → accent color (matches Sidebar) ────────────────────
export const ROUTE_COLORS: Record<string, string> = {
  "/dashboard":        "#6366f1",
  "/avatar-studio":    "#8b5cf6",
  "/voice-studio":     "#a855f7",
  "/video-studio":     "#06b6d4",
  "/storyboard":       "#f59e0b",
  "/agent-builder":    "#10b981",
  "/knowledge-center": "#0891b2",
  "/analytics":        "#ec4899",
  "/integrations":     "#06b6d4",
  "/realtime":         "#ef4444",
  "/admin":            "#64748b",
};

// ── Semantic gradient presets ──────────────────────────────────
export const GRADIENTS = {
  primary:   "var(--gradient-primary)",
  secondary: "var(--gradient-secondary)",
  danger:    "var(--gradient-danger)",
  warning:   "var(--gradient-warning)",
  // Named brand palettes (used for avatar/voice/video/agent)
  indigo:    "linear-gradient(135deg,#6366f1,#8b5cf6)",
  violet:    "linear-gradient(135deg,#8b5cf6,#a855f7)",
  purple:    "linear-gradient(135deg,#a855f7,#7c3aed)",
  cyan:      "linear-gradient(135deg,#06b6d4,#0284c7)",
  teal:      "linear-gradient(135deg,#10b981,#0d9488)",
  amber:     "linear-gradient(135deg,#f59e0b,#d97706)",
  red:       "linear-gradient(135deg,#ef4444,#dc2626)",
  voiceCard: "linear-gradient(135deg,#8b5cf6,#06b6d4)",
} as const;

// ── Semantic status colors ─────────────────────────────────────
export const STATUS_COLORS = {
  success:    { text: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500",                hex: "#10b981" },
  error:      { text: "text-red-500",     bg: "bg-red-500/10",     dot: "bg-red-500",                   hex: "#ef4444" },
  warning:    { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#f59e0b" },
  info:       { text: "text-primary",     bg: "bg-primary/10",     dot: "bg-primary animate-pulse",     hex: "#6366f1" },
  processing: { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#f59e0b" },
  ready:      { text: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500",               hex: "#10b981" },
  failed:     { text: "text-red-500",     bg: "bg-red-500/10",     dot: "bg-red-500",                   hex: "#ef4444" },
  pending:    { text: "text-blue-400",    bg: "bg-blue-400/10",    dot: "bg-blue-400 animate-pulse",    hex: "#60a5fa" },
  cloning:    { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#f59e0b" },
  training:   { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#f59e0b" },
  completed:  { text: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500",               hex: "#10b981" },
} as const;

export type StatusKey = keyof typeof STATUS_COLORS;

// ── Timing constants ───────────────────────────────────────────
export const TIMING = {
  toastDefault:   5_000,
  toastError:     8_000,
  gpuPollMs:      8_000,
  jobPollMs:      5_000,
  voicePollMs:    10_000,
  queryStaleMs:   5 * 60 * 1000,
  countUpMs:      1_400,
} as const;

// ── App meta ───────────────────────────────────────────────────
export const APP = {
  name:    "Avatar Platform",
  shortName: "A",
  version: "2.0.0",
} as const;
