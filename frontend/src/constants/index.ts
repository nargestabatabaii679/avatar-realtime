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

// ── Route → accent color (single design-system accent) ────────
export const ROUTE_COLORS: Record<string, string> = {
  "/dashboard":        "#00C8F0",
  "/avatar-studio":    "#00C8F0",
  "/voice-studio":     "#00C8F0",
  "/video-studio":     "#00C8F0",
  "/storyboard":       "#00C8F0",
  "/agent-builder":    "#00C8F0",
  "/knowledge-center": "#00C8F0",
  "/analytics":        "#00C8F0",
  "/integrations":     "#00C8F0",
  "/realtime":         "#00C8F0",
  "/admin":            "#00C8F0",
};

// ── Semantic status colors ─────────────────────────────────────
export const STATUS_COLORS = {
  success:    { text: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500",               hex: "#00E87A" },
  error:      { text: "text-red-500",     bg: "bg-red-500/10",     dot: "bg-red-500",                   hex: "#E05050" },
  warning:    { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#F0A500" },
  info:       { text: "text-primary",     bg: "bg-primary/10",     dot: "bg-primary animate-pulse",     hex: "#00C8F0" },
  processing: { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#F0A500" },
  ready:      { text: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500",               hex: "#00E87A" },
  failed:     { text: "text-red-500",     bg: "bg-red-500/10",     dot: "bg-red-500",                   hex: "#E05050" },
  pending:    { text: "text-primary",     bg: "bg-primary/10",     dot: "bg-primary animate-pulse",     hex: "#00C8F0" },
  cloning:    { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#F0A500" },
  training:   { text: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse",   hex: "#F0A500" },
  completed:  { text: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500",               hex: "#00E87A" },
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
