import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import {
  Menu, Sun, Moon, Monitor, Globe, Bell, Search, ChevronDown,
  CheckCircle2, AlertCircle, Info, X, Check, Trash2,
} from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { useThemeStore } from "../../stores/themeStore";
import { useNotificationStore } from "../../stores/notificationStore";
import { wsService } from "../../services/websocket";
import { cn } from "../../utils/cn";

const LANGUAGES = [
  { code: "en", label: "English",   flag: "🇺🇸" },
  { code: "fa", label: "فارسی",     flag: "🇮🇷" },
  { code: "ar", label: "العربية",  flag: "🇸🇦" },
  { code: "tr", label: "Türkçe",   flag: "🇹🇷" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch",  flag: "🇩🇪" },
];

const PAGE_TITLES: Record<string, string> = {
  "/dashboard":        "Dashboard",
  "/avatar-studio":    "Avatar Studio",
  "/voice-studio":     "Voice Studio",
  "/video-studio":     "Video Studio",
  "/storyboard":       "Storyboard",
  "/agent-builder":    "Agent Builder",
  "/knowledge-center": "Knowledge Center",
  "/analytics":        "Analytics",
  "/integrations":     "Integrations",
  "/realtime":         "Real-Time",
  "/admin":            "Admin",
};

const NOTIF_ICONS = {
  success: CheckCircle2,
  error:   AlertCircle,
  warning: AlertCircle,
  info:    Info,
};
const NOTIF_COLORS = {
  success: "text-emerald-500",
  error:   "text-red-500",
  warning: "text-amber-500",
  info:    "text-primary",
};

function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)   return `${Math.round(diff)}s`;
  if (diff < 3600) return `${Math.round(diff/60)}m`;
  return `${Math.round(diff/3600)}h`;
}

interface HeaderProps { onMenuClick: () => void; }

export function Header({ onMenuClick }: HeaderProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();
  const { theme, setTheme, language, setLanguage } = useThemeStore();
  const { notifications, unreadCount, markAllAsRead, markAsRead, removeNotification, clearNotifications } = useNotificationStore();
  const location = useLocation();
  const [showLangMenu,  setShowLangMenu]  = useState(false);
  const [showUserMenu,  setShowUserMenu]  = useState(false);
  const [showSearch,    setShowSearch]    = useState(false);
  const [showNotifs,    setShowNotifs]    = useState(false);

  const currentLang = LANGUAGES.find((l) => l.code === language);
  const pageTitle   = PAGE_TITLES[location.pathname] || "";

  const wsConnected = wsService.isConnected;

  const closeAll = () => {
    setShowLangMenu(false);
    setShowUserMenu(false);
    setShowNotifs(false);
  };

  return (
    <header className="sticky top-0 z-30 flex items-center gap-2 px-4 h-16 backdrop-blur-xl border-b"
      style={{
        backgroundColor: "hsl(var(--background) / 0.85)",
        borderColor: "hsl(var(--border))",
      }}>

      {/* Mobile menu */}
      <button onClick={onMenuClick}
        className="md:hidden p-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors">
        <Menu size={18} />
      </button>

      {/* Page title + WS indicator */}
      {pageTitle && (
        <div className="hidden sm:flex items-center gap-2">
          <h2 className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>{pageTitle}</h2>
          {wsConnected && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium"
              style={{ background: "rgb(16 185 129 / 0.12)", color: "#10b981" }}>
              <span className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" /> LIVE
            </span>
          )}
        </div>
      )}

      <div className="flex-1" />

      {/* Search */}
      <div className="hidden md:flex">
        {showSearch ? (
          <div className="relative animate-scale-in">
            <Search size={14} className="absolute start-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              autoFocus
              onBlur={() => setShowSearch(false)}
              placeholder="جستجو…"
              dir="rtl"
              className="w-56 ps-9 pe-4 py-2 text-sm rounded-xl border focus:outline-none transition-all"
              style={{
                borderColor: "hsl(var(--border))",
                backgroundColor: "hsl(var(--background))",
                color: "hsl(var(--foreground))",
              }}
            />
          </div>
        ) : (
          <button onClick={() => { setShowSearch(true); closeAll(); }}
            className="p-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors">
            <Search size={16} />
          </button>
        )}
      </div>

      {/* Theme toggle */}
      <div className="flex items-center rounded-xl p-1 gap-0.5" style={{ backgroundColor: "hsl(var(--muted))" }}>
        {[
          { value: "light",  icon: Sun },
          { value: "dark",   icon: Moon },
          { value: "system", icon: Monitor },
        ].map(({ value, icon: Icon }) => (
          <button key={value} onClick={() => setTheme(value as "light" | "dark" | "system")}
            className={cn(
              "p-1.5 rounded-lg transition-all duration-200",
              theme === value ? "shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
            style={theme === value ? {
              backgroundColor: "hsl(var(--background))",
              color: "hsl(var(--foreground))",
            } : {}}>
            <Icon size={13} />
          </button>
        ))}
      </div>

      {/* Language */}
      <div className="relative">
        <button
          onClick={() => { setShowLangMenu(!showLangMenu); setShowUserMenu(false); setShowNotifs(false); }}
          className="flex items-center gap-1.5 px-2.5 py-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors text-sm">
          <Globe size={14} />
          <span className="text-base leading-none">{currentLang?.flag}</span>
          <ChevronDown size={11} className={cn("transition-transform", showLangMenu && "rotate-180")} />
        </button>
        {showLangMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowLangMenu(false)} />
            <div className="absolute end-0 top-full mt-2 z-20 w-44 rounded-xl shadow-lg py-1.5 overflow-hidden animate-fade-in-down border"
              style={{
                backgroundColor: "hsl(var(--popover))",
                borderColor: "hsl(var(--border))",
              }}>
              {LANGUAGES.map((lang) => (
                <button key={lang.code}
                  onClick={() => { setLanguage(lang.code); setShowLangMenu(false); }}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-accent transition-colors text-start",
                    language === lang.code ? "text-primary font-semibold" : "text-foreground"
                  )}>
                  <span className="text-base">{lang.flag}</span>
                  <span>{lang.label}</span>
                  {language === lang.code && <span className="ms-auto w-1.5 h-1.5 rounded-full bg-primary" />}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Notifications */}
      <div className="relative">
        <button
          onClick={() => { setShowNotifs(!showNotifs); setShowLangMenu(false); setShowUserMenu(false); }}
          className="relative p-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors">
          <Bell size={16} />
          {unreadCount > 0 && (
            <span className="absolute top-1 end-1 min-w-[16px] h-4 px-0.5 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center ring-2 ring-background">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>

        {showNotifs && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowNotifs(false)} />
            <div className="absolute end-0 top-full mt-2 z-20 w-80 rounded-xl shadow-xl overflow-hidden animate-fade-in-down border"
              style={{
                backgroundColor: "hsl(var(--popover))",
                borderColor: "hsl(var(--border))",
              }}>
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b"
                style={{ borderColor: "hsl(var(--border))" }}>
                <div className="flex items-center gap-2">
                  <Bell size={14} style={{ color: "hsl(var(--foreground))" }} />
                  <span className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>اعلان‌ها</span>
                  {unreadCount > 0 && (
                    <span className="badge badge-primary text-[10px]">{unreadCount} جدید</span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {notifications.length > 0 && (
                    <>
                      <button onClick={markAllAsRead}
                        className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors" title="همه خوانده شد">
                        <Check size={13} />
                      </button>
                      <button onClick={clearNotifications}
                        className="p-1.5 rounded-lg hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors" title="پاک کردن همه">
                        <Trash2 size={13} />
                      </button>
                    </>
                  )}
                  <button onClick={() => setShowNotifs(false)}
                    className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors">
                    <X size={13} />
                  </button>
                </div>
              </div>

              {/* List */}
              <div className="max-h-80 overflow-y-auto scrollbar-thin">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 gap-2">
                    <Bell size={28} className="text-muted-foreground opacity-30" />
                    <p className="text-sm text-muted-foreground">هیچ اعلانی ندارید</p>
                  </div>
                ) : (
                  notifications.map(n => {
                    const Icon  = NOTIF_ICONS[n.type as keyof typeof NOTIF_ICONS] || Info;
                    const color = NOTIF_COLORS[n.type as keyof typeof NOTIF_COLORS] || "text-primary";
                    return (
                      <div key={n.id}
                        className={cn(
                          "flex items-start gap-3 px-4 py-3 border-b transition-colors hover:bg-accent/50 cursor-pointer",
                          !n.read && "bg-primary/4"
                        )}
                        style={{ borderColor: "hsl(var(--border))" }}
                        onClick={() => markAsRead(n.id)}>
                        <Icon size={15} className={cn("shrink-0 mt-0.5", color)} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold truncate" style={{ color: "hsl(var(--foreground))" }}>{n.title}</p>
                          {n.message && <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">{n.message}</p>}
                          <p className="text-[10px] text-muted-foreground mt-1">{timeAgo(n.timestamp)} پیش</p>
                        </div>
                        <button onClick={(e) => { e.stopPropagation(); removeNotification(n.id); }}
                          className="p-0.5 rounded hover:text-red-500 text-muted-foreground transition-colors shrink-0">
                          <X size={11} />
                        </button>
                        {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-primary shrink-0 mt-1" />}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* User menu */}
      <div className="relative">
        <button
          onClick={() => { setShowUserMenu(!showUserMenu); setShowLangMenu(false); setShowNotifs(false); }}
          className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-accent transition-colors">
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold"
            style={{ background: "var(--gradient-primary)" }}>
            {user?.full_name?.charAt(0).toUpperCase() || user?.email.charAt(0).toUpperCase()}
          </div>
          <div className="hidden sm:block text-start">
            <p className="text-xs font-semibold leading-none" style={{ color: "hsl(var(--foreground))" }}>
              {user?.full_name || "User"}
            </p>
            <p className="text-[10px] text-muted-foreground leading-none mt-0.5 capitalize">{user?.role}</p>
          </div>
          <ChevronDown size={12} className={cn("text-muted-foreground transition-transform hidden sm:block", showUserMenu && "rotate-180")} />
        </button>

        {showUserMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowUserMenu(false)} />
            <div className="absolute end-0 top-full mt-2 z-20 w-56 rounded-xl shadow-lg py-1.5 overflow-hidden animate-fade-in-down border"
              style={{
                backgroundColor: "hsl(var(--popover))",
                borderColor: "hsl(var(--border))",
              }}>
              <div className="px-3 py-2.5 border-b" style={{ borderColor: "hsl(var(--border))" }}>
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold"
                    style={{ background: "var(--gradient-primary)" }}>
                    {user?.full_name?.charAt(0).toUpperCase() || user?.email.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold truncate" style={{ color: "hsl(var(--foreground))" }}>{user?.full_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                  </div>
                </div>
              </div>
              <button
                onClick={() => { logout(); setShowUserMenu(false); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-red-500/8 text-red-500 transition-colors text-start mt-0.5">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                خروج از حساب
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
