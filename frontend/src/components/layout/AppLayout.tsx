import { useState, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useThemeStore } from "../../stores/themeStore";
import { useAuthStore } from "../../stores/authStore";
import { useNotificationStore } from "../../stores/notificationStore";
import { wsService } from "../../services/websocket";
import { cn } from "../../utils/cn";
import { STATUS_COLORS, RTL_LANGS } from "../../constants";
import type { ToastNotification } from "../../types/ui";
import type { WSJobProgressEvent } from "../../types";
import { JobStatus } from "../../types";
import { useTranslation } from "react-i18next";

// ── Toast icons / border colours keyed by type ────────────────
const TOAST_ICONS = {
  success: CheckCircle2,
  error:   XCircle,
  warning: AlertTriangle,
  info:    Info,
} as const;

// ── Single toast item ─────────────────────────────────────────
function ToastItem({ toast, onDismiss }: { toast: ToastNotification; onDismiss: () => void }) {
  const Icon      = TOAST_ICONS[toast.type];
  const colorKey  = toast.type === "error" ? "error" : toast.type === "warning" ? "warning" : toast.type === "success" ? "success" : "info";
  const textColor = STATUS_COLORS[colorKey].text;
  const bgClass   = STATUS_COLORS[colorKey].bg;

  return (
    <div className={cn(
      "flex items-start gap-3 p-3.5 rounded-xl border shadow-lg backdrop-blur-xl max-w-xs w-full animate-notify-in",
      bgClass,
    )} style={{ borderColor: `hsl(var(--border))`, backgroundColor: "hsl(var(--card) / 0.95)" }}>
      <Icon size={16} className={cn("shrink-0 mt-0.5", textColor)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-tight" style={{ color: "hsl(var(--foreground))" }}>
          {toast.title}
        </p>
        {toast.message && (
          <p className="text-xs mt-0.5 leading-relaxed" style={{ color: "hsl(var(--muted-foreground))" }}>
            {toast.message}
          </p>
        )}
      </div>
      <button
        onClick={onDismiss}
        className="p-0.5 rounded hover:bg-accent transition-colors shrink-0"
        style={{ color: "hsl(var(--muted-foreground))" }}
      >
        <X size={13} />
      </button>
    </div>
  );
}

// ── Toast stack (top-right) ───────────────────────────────────
function ToastContainer() {
  const { toasts, removeToast } = useNotificationStore();
  if (!toasts.length) return null;

  return (
    <div className="fixed top-20 end-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem toast={t} onDismiss={() => removeToast(t.id)} />
        </div>
      ))}
    </div>
  );
}

// ── Root layout ───────────────────────────────────────────────
export default function AppLayout() {
  const [sidebarCollapsed,   setSidebarCollapsed]   = useState(false);
  const [mobileSidebarOpen,  setMobileSidebarOpen]  = useState(false);

  const { language }                    = useThemeStore();
  const { tokens }                      = useAuthStore();
  const { addNotification, success }    = useNotificationStore();
  const { t }                           = useTranslation();
  const isRTL = RTL_LANGS.includes(language);

  // Connect WebSocket when authenticated; clean up on logout / token change
  useEffect(() => {
    if (!tokens?.access_token) return;
    wsService.connect(tokens.access_token);

    const unsubJobs = wsService.subscribeToAllJobs((event: WSJobProgressEvent) => {
      if (event.status !== JobStatus.COMPLETED) return;
      const title   = t("notifications.jobDone");
      const message = event.current_step ?? undefined;
      success(title, message);
      addNotification({ type: "success", title, message });
    });

    return () => {
      unsubJobs();
      wsService.disconnect();
    };
  }, [tokens?.access_token, t]);

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{ backgroundColor: "hsl(var(--background))" }}
    >
      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        "fixed inset-y-0 z-50 transition-transform duration-300 md:relative md:translate-x-0",
        isRTL ? "right-0" : "left-0",
        mobileSidebarOpen
          ? "translate-x-0"
          : isRTL ? "translate-x-full md:translate-x-0" : "-translate-x-full md:translate-x-0",
      )}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
          onClose={() => setMobileSidebarOpen(false)}
        />
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header onMenuClick={() => setMobileSidebarOpen(true)} />
        <main className="flex-1 overflow-auto p-4 md:p-6 lg:p-8 scrollbar-thin">
          <Outlet />
        </main>
      </div>

      <ToastContainer />
    </div>
  );
}
