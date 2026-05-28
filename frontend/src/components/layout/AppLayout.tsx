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

/* ─── Toast Item ─────────────────────────────────────────── */
const TOAST_ICONS = {
  success: CheckCircle2,
  error:   XCircle,
  warning: AlertTriangle,
  info:    Info,
};
const TOAST_STYLES = {
  success: { border: "border-emerald-500/30", bg: "bg-emerald-500/10", icon: "text-emerald-500" },
  error:   { border: "border-red-500/30",     bg: "bg-red-500/10",     icon: "text-red-500" },
  warning: { border: "border-amber-500/30",   bg: "bg-amber-500/10",   icon: "text-amber-500" },
  info:    { border: "border-primary/30",     bg: "bg-primary/10",     icon: "text-primary" },
};

function ToastItem({ toast, onDismiss }: { toast: any; onDismiss: () => void }) {
  const Icon  = TOAST_ICONS[toast.type as keyof typeof TOAST_ICONS];
  const style = TOAST_STYLES[toast.type as keyof typeof TOAST_STYLES];
  return (
    <div className={cn(
      "flex items-start gap-3 p-3.5 rounded-xl border shadow-lg backdrop-blur-xl max-w-xs w-full animate-notify-in",
      "bg-card/95", style.border
    )}>
      <Icon size={16} className={cn("shrink-0 mt-0.5", style.icon)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-foreground leading-tight">{toast.title}</p>
        {toast.message && <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{toast.message}</p>}
      </div>
      <button onClick={onDismiss} className="p-0.5 rounded hover:bg-accent text-muted-foreground shrink-0">
        <X size={13} />
      </button>
    </div>
  );
}

/* ─── Toast Container ────────────────────────────────────── */
function ToastContainer() {
  const { toasts, removeToast } = useNotificationStore();
  if (!toasts.length) return null;
  return (
    <div className="fixed top-20 end-4 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map(t => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem toast={t} onDismiss={() => removeToast(t.id)} />
        </div>
      ))}
    </div>
  );
}

/* ─── Main Layout ────────────────────────────────────────── */
export default function AppLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const { language } = useThemeStore();
  const { tokens } = useAuthStore();
  const { addNotification, success } = useNotificationStore();
  const isRTL = ["fa", "ar", "he"].includes(language);

  /* Connect WebSocket when authenticated */
  useEffect(() => {
    if (!tokens?.access_token) return;
    wsService.connect(tokens.access_token);

    const unsubJobs = wsService.subscribeToAllJobs((event) => {
      if (event.status === "completed") {
        const titles: Record<string, string> = {
          avatar:  "آواتار آماده شد",
          voice:   "صدا کلون شد",
          video:   "ویدیو آماده است",
        };
        const title = titles[event.job_type] ?? "کار تمام شد";
        success(title, event.message);
        addNotification({ type: "success", title, message: event.message });
      }
    });

    return () => {
      unsubJobs();
      wsService.disconnect();
    };
  }, [tokens?.access_token]);

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
      <div
        className={cn(
          "fixed inset-y-0 z-50 transition-transform duration-300 md:relative md:translate-x-0",
          isRTL ? "right-0" : "left-0",
          mobileSidebarOpen ? "translate-x-0" : isRTL ? "translate-x-full md:translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
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

      {/* Global toasts */}
      <ToastContainer />
    </div>
  );
}
