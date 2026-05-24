import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard, Users, Mic, Video, Bot, BookOpen, BarChart3,
  Settings, Radio, ChevronLeft, ChevronRight, X,
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
  { path: "/dashboard", icon: LayoutDashboard, labelKey: "nav.dashboard" },
  { path: "/avatar-studio", icon: Users, labelKey: "nav.avatarStudio" },
  { path: "/voice-studio", icon: Mic, labelKey: "nav.voiceStudio" },
  { path: "/video-studio", icon: Video, labelKey: "nav.videoStudio" },
  { path: "/agent-builder", icon: Bot, labelKey: "nav.agentBuilder" },
  { path: "/knowledge-center", icon: BookOpen, labelKey: "nav.knowledgeCenter" },
  { path: "/analytics", icon: BarChart3, labelKey: "nav.analytics" },
  { path: "/realtime", icon: Radio, labelKey: "nav.realtime" },
  { path: "/admin", icon: Settings, labelKey: "nav.admin", adminOnly: true },
] as const;

export function Sidebar({ collapsed, onToggleCollapse, onClose }: SidebarProps) {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const { language } = useThemeStore();
  const isRTL = ["fa", "ar", "he"].includes(language);
  const isAdmin = user?.role === "admin" || user?.role === "super_admin";

  return (
    <aside
      className={cn(
        "flex flex-col h-full bg-card border-e border-border transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex items-center justify-between p-4 border-b border-border min-h-[65px]">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">A</span>
            </div>
            <span className="font-bold text-foreground text-sm">Avatar Platform</span>
          </div>
        )}
        <div className="flex items-center gap-1 ms-auto">
          <button
            onClick={onClose}
            className="md:hidden p-1 rounded hover:bg-accent"
          >
            <X size={16} />
          </button>
          <button
            onClick={onToggleCollapse}
            className="hidden md:flex p-1 rounded hover:bg-accent text-muted-foreground"
          >
            {collapsed
              ? (isRTL ? <ChevronLeft size={16} /> : <ChevronRight size={16} />)
              : (isRTL ? <ChevronRight size={16} /> : <ChevronLeft size={16} />)
            }
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-2">
        {navItems.map((item) => {
          if (item.adminOnly && !isAdmin) return null;
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 mx-2 rounded-lg text-sm font-medium transition-colors",
                  "hover:bg-accent hover:text-accent-foreground",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-muted-foreground"
                )
              }
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span>{t(item.labelKey)}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* User info at bottom */}
      {!collapsed && user && (
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-xs font-bold">
              {user.full_name?.charAt(0).toUpperCase() || user.email.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium text-foreground truncate">{user.full_name || user.email}</p>
              <p className="text-xs text-muted-foreground capitalize">{user.role}</p>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
