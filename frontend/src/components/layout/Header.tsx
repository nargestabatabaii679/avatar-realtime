import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Menu, Sun, Moon, Monitor, Globe, Bell, Search, ChevronDown } from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { useThemeStore } from "../../stores/themeStore";
import { cn } from "../../utils/cn";

interface HeaderProps { onMenuClick: () => void; }

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
  "/agent-builder":    "Agent Builder",
  "/knowledge-center": "Knowledge Center",
  "/analytics":        "Analytics",
  "/realtime":         "Realtime",
  "/admin":            "Admin",
};

export function Header({ onMenuClick }: HeaderProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();
  const { theme, setTheme, language, setLanguage } = useThemeStore();
  const location = useLocation();
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showSearch, setShowSearch] = useState(false);

  const currentLang = LANGUAGES.find((l) => l.code === language);
  const pageTitle = PAGE_TITLES[location.pathname] || "";

  return (
    <header className="sticky top-0 z-30 flex items-center gap-3 px-4 h-16 bg-background/80 backdrop-blur-xl border-b border-border">

      {/* Mobile menu */}
      <button onClick={onMenuClick}
        className="md:hidden p-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors">
        <Menu size={18} />
      </button>

      {/* Page title */}
      {pageTitle && (
        <div className="hidden sm:flex items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">{pageTitle}</h2>
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
              placeholder="Search…"
              className="w-56 ps-9 pe-4 py-2 text-sm rounded-xl border border-border bg-background focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all"
            />
          </div>
        ) : (
          <button onClick={() => setShowSearch(true)}
            className="p-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors">
            <Search size={16} />
          </button>
        )}
      </div>

      {/* Theme toggle */}
      <div className="flex items-center bg-muted rounded-xl p-1 gap-0.5">
        {[
          { value: "light",  icon: Sun },
          { value: "dark",   icon: Moon },
          { value: "system", icon: Monitor },
        ].map(({ value, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setTheme(value as "light" | "dark" | "system")}
            className={cn(
              "p-1.5 rounded-lg transition-all duration-200",
              theme === value
                ? "bg-background shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon size={13} />
          </button>
        ))}
      </div>

      {/* Language */}
      <div className="relative">
        <button
          onClick={() => { setShowLangMenu(!showLangMenu); setShowUserMenu(false); }}
          className="flex items-center gap-1.5 px-2.5 py-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors text-sm"
        >
          <Globe size={14} />
          <span className="text-base leading-none">{currentLang?.flag}</span>
          <ChevronDown size={11} className={cn("transition-transform", showLangMenu && "rotate-180")} />
        </button>
        {showLangMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowLangMenu(false)} />
            <div className="absolute end-0 top-full mt-2 z-20 w-44 bg-popover border border-border rounded-xl shadow-lg py-1.5 overflow-hidden animate-fade-in-down">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => { setLanguage(lang.code); setShowLangMenu(false); }}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-accent transition-colors text-start",
                    language === lang.code ? "text-primary font-semibold" : "text-foreground"
                  )}
                >
                  <span className="text-base">{lang.flag}</span>
                  <span>{lang.label}</span>
                  {language === lang.code && (
                    <span className="ms-auto w-1.5 h-1.5 rounded-full bg-primary" />
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Notifications */}
      <button className="relative p-2 rounded-xl hover:bg-accent text-muted-foreground transition-colors">
        <Bell size={16} />
        <span className="absolute top-1.5 end-1.5 w-2 h-2 bg-red-500 rounded-full ring-2 ring-background" />
      </button>

      {/* User menu */}
      <div className="relative">
        <button
          onClick={() => { setShowUserMenu(!showUserMenu); setShowLangMenu(false); }}
          className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-accent transition-colors"
        >
          <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold"
            style={{ background: "var(--gradient-primary)" }}>
            {user?.full_name?.charAt(0).toUpperCase() || user?.email.charAt(0).toUpperCase()}
          </div>
          <div className="hidden sm:block text-start">
            <p className="text-xs font-semibold text-foreground leading-none">{user?.full_name || "User"}</p>
            <p className="text-[10px] text-muted-foreground leading-none mt-0.5 capitalize">{user?.role}</p>
          </div>
          <ChevronDown size={12} className={cn("text-muted-foreground transition-transform hidden sm:block", showUserMenu && "rotate-180")} />
        </button>

        {showUserMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowUserMenu(false)} />
            <div className="absolute end-0 top-full mt-2 z-20 w-56 bg-popover border border-border rounded-xl shadow-lg py-1.5 overflow-hidden animate-fade-in-down">
              <div className="px-3 py-2.5 border-b border-border">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold"
                    style={{ background: "var(--gradient-primary)" }}>
                    {user?.full_name?.charAt(0).toUpperCase() || user?.email.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-foreground truncate">{user?.full_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                  </div>
                </div>
              </div>
              <button
                onClick={() => { logout(); setShowUserMenu(false); }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-sm hover:bg-red-500/8 text-red-500 transition-colors text-start mt-0.5"
              >
                <div className="w-4 h-4 flex items-center justify-center">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                Sign out
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
