import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Menu, Sun, Moon, Monitor, Globe, Bell, LogOut, User, ChevronDown } from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { useThemeStore } from "../../stores/themeStore";
import { cn } from "../../utils/cn";

interface HeaderProps {
  onMenuClick: () => void;
}

const LANGUAGES = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "fa", label: "فارسی", flag: "🇮🇷" },
  { code: "ar", label: "العربية", flag: "🇸🇦" },
  { code: "tr", label: "Türkçe", flag: "🇹🇷" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
];

export function Header({ onMenuClick }: HeaderProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();
  const { theme, setTheme, language, setLanguage } = useThemeStore();
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const currentLang = LANGUAGES.find((l) => l.code === language);

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between px-4 py-3 bg-card border-b border-border">
      {/* Left: menu + breadcrumb */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 rounded-lg hover:bg-accent text-muted-foreground"
        >
          <Menu size={20} />
        </button>
      </div>

      {/* Right: controls */}
      <div className="flex items-center gap-2">
        {/* Theme toggle */}
        <div className="flex items-center bg-muted rounded-lg p-1 gap-0.5">
          {[
            { value: "light", icon: Sun },
            { value: "dark", icon: Moon },
            { value: "system", icon: Monitor },
          ].map(({ value, icon: Icon }) => (
            <button
              key={value}
              onClick={() => setTheme(value as "light" | "dark" | "system")}
              className={cn(
                "p-1.5 rounded-md transition-colors",
                theme === value ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon size={14} />
            </button>
          ))}
        </div>

        {/* Language selector */}
        <div className="relative">
          <button
            onClick={() => setShowLangMenu(!showLangMenu)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-accent text-sm font-medium text-muted-foreground"
          >
            <Globe size={14} />
            <span>{currentLang?.flag}</span>
            <ChevronDown size={12} />
          </button>
          {showLangMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowLangMenu(false)} />
              <div className="absolute end-0 top-full mt-1 z-20 w-44 bg-popover border border-border rounded-lg shadow-lg py-1 overflow-hidden">
                {LANGUAGES.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => { setLanguage(lang.code); setShowLangMenu(false); }}
                    className={cn(
                      "w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent text-start",
                      language === lang.code ? "text-primary font-medium" : "text-foreground"
                    )}
                  >
                    <span>{lang.flag}</span>
                    <span>{lang.label}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg hover:bg-accent text-muted-foreground">
          <Bell size={18} />
          <span className="absolute top-1.5 end-1.5 w-2 h-2 bg-red-500 rounded-full" />
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-accent"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
              {user?.full_name?.charAt(0).toUpperCase() || user?.email.charAt(0).toUpperCase()}
            </div>
            <ChevronDown size={12} className="text-muted-foreground" />
          </button>
          {showUserMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowUserMenu(false)} />
              <div className="absolute end-0 top-full mt-1 z-20 w-52 bg-popover border border-border rounded-lg shadow-lg py-1">
                <div className="px-3 py-2 border-b border-border">
                  <p className="text-sm font-medium text-foreground">{user?.full_name}</p>
                  <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                </div>
                <button className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent text-foreground text-start">
                  <User size={14} />
                  Profile
                </button>
                <button
                  onClick={() => { logout(); setShowUserMenu(false); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent text-red-500 text-start"
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
