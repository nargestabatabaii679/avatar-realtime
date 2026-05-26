import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, Users, Mic, Video, Bot, BookOpen, BarChart3,
  Settings, Radio, ChevronLeft, ChevronRight, X, LogOut,
  LayoutTemplate, Plug2,
} from "lucide-react";
import { cn } from "../../utils/cn";
import { useAuthStore } from "../../stores/authStore";
import { useThemeStore } from "../../stores/themeStore";

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  onClose: () => void;
}

const navItems = [
  { path: "/dashboard",       icon: LayoutDashboard, labelKey: "nav.dashboard",      color: "#6366f1" },
  { path: "/avatar-studio",   icon: Users,           labelKey: "nav.avatarStudio",    color: "#8b5cf6" },
  { path: "/voice-studio",    icon: Mic,             labelKey: "nav.voiceStudio",     color: "#a855f7" },
  { path: "/video-studio",    icon: Video,           labelKey: "nav.videoStudio",     color: "#06b6d4" },
  { path: "/storyboard",      icon: LayoutTemplate,  labelKey: "nav.storyboard",      color: "#f59e0b" },
  { path: "/agent-builder",   icon: Bot,             labelKey: "nav.agentBuilder",    color: "#10b981" },
  { path: "/knowledge-center",icon: BookOpen,        labelKey: "nav.knowledgeCenter", color: "#0891b2" },
  { path: "/analytics",       icon: BarChart3,       labelKey: "nav.analytics",       color: "#ec4899" },
  { path: "/integrations",    icon: Plug2,           labelKey: "nav.integrations",    color: "#06b6d4" },
  { path: "/realtime",        icon: Radio,           labelKey: "nav.realtime",        color: "#ef4444" },
  { path: "/admin",           icon: Settings,        labelKey: "nav.admin",           color: "#64748b", adminOnly: true },
] as const;

export function Sidebar({ collapsed, onToggleCollapse, onClose }: SidebarProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();
  const { language } = useThemeStore();
  const location = useLocation();
  const isRTL = ["fa", "ar", "he"].includes(language);
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  return (
    <aside
      className={cn(
        "flex flex-col h-full transition-all duration-300 overflow-hidden",
        "bg-card border-e border-border",
        collapsed ? "w-[68px]" : "w-[240px]"
      )}
    >
      {/* Logo */}
      <div className={cn(
        "flex items-center border-b border-border min-h-[64px] px-3",
        collapsed ? "justify-center" : "justify-between"
      )}>
        {!collapsed && (
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center"
              style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" }}>
              <span className="text-white font-black text-sm">A</span>
            </div>
            <div className="overflow-hidden">
              <p className="font-bold text-foreground text-sm truncate leading-none">Avatar</p>
              <p className="text-[10px] text-muted-foreground leading-none mt-0.5 truncate">Platform</p>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" }}>
            <span className="text-white font-black text-sm">A</span>
          </div>
        )}
        <div className="flex items-center gap-1">
          <button onClick={onClose} className="md:hidden p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors">
            <X size={15} />
          </button>
          {!collapsed && (
            <button onClick={onToggleCollapse} className="hidden md:flex p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors">
              {isRTL ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
            </button>
          )}
        </div>
      </div>

      {collapsed && (
        <button onClick={onToggleCollapse}
          className="hidden md:flex mx-auto mt-2 p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors">
          {isRTL ? <ChevronLeft size={15} /> : <ChevronRight size={15} />}
        </button>
      )}

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto scrollbar-hide py-3 px-2 space-y-0.5">
        {!collapsed && (
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground/60 font-semibold px-3 pb-2 pt-1">
            Menu
          </p>
        )}

        {navItems.map((item) => {
          if (item.adminOnly && !isAdmin) return null;
          const Icon = item.icon;
          const isActive = location.pathname === item.path ||
            (item.path !== "/dashboard" && location.pathname.startsWith(item.path));

          return (
            <NavLink
              key={item.path}
              to={item.path}
              title={collapsed ? t(item.labelKey) : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group relative",
                isActive
                  ? "text-white shadow-md"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent",
                collapsed && "justify-center px-0"
              )}
              style={isActive ? { background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" } : {}}
            >
              {/* Active indicator for collapsed */}
              {isActive && collapsed && (
                <span className="absolute -end-0 top-1/2 -translate-y-1/2 w-0.5 h-6 rounded-full bg-primary" />
              )}

              <Icon
                size={17}
                className={cn("shrink-0 transition-transform", !isActive && "group-hover:scale-110")}
                style={!isActive ? { color: item.color } : {}}
              />
              {!collapsed && (
                <span className="truncate">{t(item.labelKey)}</span>
              )}

              {/* Tooltip for collapsed */}
              {collapsed && (
                <div className={cn(
                  "absolute z-50 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-popover border border-border shadow-lg whitespace-nowrap opacity-0 pointer-events-none",
                  "group-hover:opacity-100 transition-opacity",
                  isRTL ? "end-full me-2" : "start-full ms-2"
                )}>
                  {t(item.labelKey)}
                </div>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* User section */}
      <div className={cn("border-t border-border p-3", collapsed && "flex justify-center")}>
        {!collapsed && user ? (
          <div className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-white text-xs font-bold"
              style={{ background: "var(--gradient-primary)" }}>
              {user.full_name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-foreground truncate">{user.full_name || user.email}</p>
              <p className="text-[10px] text-muted-foreground capitalize">{user.role}</p>
            </div>
            <button
              onClick={logout}
              className="p-1.5 rounded-lg hover:bg-red-500/10 text-muted-foreground hover:text-red-500 transition-colors flex-shrink-0"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : collapsed && user ? (
          <button
            onClick={logout}
            className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold hover:ring-2 hover:ring-red-500/50 transition-all"
            style={{ background: "var(--gradient-primary)" }}
            title={user.full_name || user.email}
          >
            {user.full_name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
          </button>
        ) : null}
      </div>
    </aside>
  );
}
