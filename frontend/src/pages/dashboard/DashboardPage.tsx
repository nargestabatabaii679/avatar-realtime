import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users, Mic, Video, Bot, TrendingUp, TrendingDown,
  HardDrive, Cpu, Plus, ArrowRight, Activity, Zap,
  Clock, CheckCircle2, AlertCircle, Loader2, Sparkles,
  BarChart3, Globe2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { useNotificationStore } from "../../stores/notificationStore";
import { wsService } from "../../services/websocket";
import { cn } from "../../utils/cn";

/* ─── Count-up Hook ──────────────────────────────────────── */
function useCountUp(target: number, duration = 1200, delay = 0) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!target) return;
    const start = Date.now() + delay;
    const raf = requestAnimationFrame(function tick() {
      const elapsed = Date.now() - start;
      if (elapsed < 0) { requestAnimationFrame(tick); return; }
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * ease));
      if (progress < 1) requestAnimationFrame(tick);
    });
    return () => cancelAnimationFrame(raf);
  }, [target, duration, delay]);
  return value;
}

/* ─── Time-based greeting ────────────────────────────────── */
function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "صبح بخیر";
  if (h < 17) return "عصر بخیر";
  return "شب بخیر";
}

/* ─── Stat Card ─────────────────────────────────────────── */
function StatCard({ icon: Icon, label, value, trend, gradient, delay = 0, unit = "" }: {
  icon: React.ElementType;
  label: string;
  value: number;
  trend?: number;
  gradient: string;
  delay?: number;
  unit?: string;
}) {
  const animated = useCountUp(value || 0, 1400, delay * 1000);
  return (
    <div className="stat-card animate-fade-in-up" style={{ animationDelay: `${delay}s` }}>
      <div className="stat-icon" style={{ background: gradient }}>
        <Icon size={19} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-2xl font-bold mt-0.5" style={{ color: "hsl(var(--foreground))" }}>
          {animated}{unit}
        </p>
        {trend !== undefined && (
          <div className={cn("flex items-center gap-1 mt-1 text-xs font-medium",
            trend >= 0 ? "text-emerald-500" : "text-red-500")}>
            {trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {trend >= 0 ? "+" : ""}{trend}% این ماه
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Action Card ────────────────────────────────────────── */
function ActionCard({ icon: Icon, label, description, onClick, gradient, delay = 0 }: {
  icon: React.ElementType;
  label: string;
  description: string;
  onClick: () => void;
  gradient: string;
  delay?: number;
}) {
  return (
    <button onClick={onClick}
      className="group relative rounded-2xl p-5 text-start overflow-hidden transition-all duration-300 hover:-translate-y-1 animate-fade-in-up border"
      style={{
        animationDelay: `${delay}s`,
        backgroundColor: "hsl(var(--card))",
        borderColor: "hsl(var(--border))",
        boxShadow: "var(--shadow-sm)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-lg)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-sm)")}>
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 rounded-2xl"
        style={{ background: `radial-gradient(circle at 0% 0%, ${gradient.includes("6366f1") ? "rgba(99,102,241,0.08)" : gradient.includes("a855f7") ? "rgba(168,85,247,0.08)" : gradient.includes("06b6d4") ? "rgba(6,182,212,0.08)" : "rgba(16,185,129,0.08)"} 0%, transparent 70%)` }} />
      <div className="relative z-10">
        <div className="inline-flex p-3 rounded-xl mb-4 text-white group-hover:scale-110 transition-transform duration-200"
          style={{ background: gradient }}>
          <Icon size={20} />
        </div>
        <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>{label}</h3>
        <p className="text-xs mt-1 leading-relaxed" style={{ color: "hsl(var(--muted-foreground))" }}>{description}</p>
        <div className="flex items-center gap-1 mt-3 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
          شروع کنید <ArrowRight size={11} className="rtl:rotate-180" />
        </div>
      </div>
    </button>
  );
}

/* ─── GPU Bar ────────────────────────────────────────────── */
function GpuBar({ name, util, vramUsed, vramTotal, temp }: {
  name: string; util: number; vramUsed: number; vramTotal: number; temp: number;
}) {
  const color = util > 90 ? "#ef4444" : util > 70 ? "#f59e0b" : "#6366f1";
  const vramPct = Math.round((vramUsed / vramTotal) * 100);
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium truncate max-w-[130px]" style={{ color: "hsl(var(--muted-foreground))" }}>{name}</span>
        <div className="flex items-center gap-2">
          <span className="font-bold tabular-nums" style={{ color: util > 90 ? "#ef4444" : util > 70 ? "#f59e0b" : "hsl(var(--foreground))" }}>{util}%</span>
          <span style={{ color: "hsl(var(--muted-foreground))" }}>{temp}°C</span>
        </div>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${util}%`, background: color }} />
      </div>
      <div className="flex justify-between text-[10px]" style={{ color: "hsl(var(--muted-foreground))" }}>
        <span>VRAM {(vramUsed/1024).toFixed(1)}GB / {(vramTotal/1024).toFixed(1)}GB ({vramPct}%)</span>
        <Activity size={10} className="text-emerald-500" />
      </div>
    </div>
  );
}

/* ─── Activity Item ──────────────────────────────────────── */
function ActivityItem({ type, message, time, status }: {
  type: string; message: string; time: string; status: string;
}) {
  const icons: Record<string, React.ElementType> = { avatar: Users, voice: Mic, video: Video, default: Activity };
  const Icon = icons[type] || icons.default;
  const colors: Record<string, string> = {
    completed: "text-emerald-500", failed: "text-red-500",
    processing: "text-amber-500", queued: "text-blue-400",
  };
  const StatusIcon = status === "completed" ? CheckCircle2 : status === "failed" ? AlertCircle : Loader2;
  return (
    <div className="flex items-start gap-3 py-2.5 border-b last:border-0" style={{ borderColor: "hsl(var(--border))" }}>
      <div className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center"
        style={{ background: "hsl(var(--muted))" }}>
        <Icon size={13} style={{ color: "hsl(var(--muted-foreground))" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate" style={{ color: "hsl(var(--foreground))" }}>{message}</p>
        <p className="text-[10px] mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>{time}</p>
      </div>
      <StatusIcon size={13} className={cn("shrink-0 mt-0.5", colors[status] || "text-muted-foreground",
        status === "processing" && "animate-spin")} />
    </div>
  );
}

/* ─── Live Clock ─────────────────────────────────────────── */
function LiveClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="tabular-nums font-mono text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
      {time.toLocaleTimeString("fa-IR")}
    </span>
  );
}

/* ─── Main Page ──────────────────────────────────────────── */
export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { notifications } = useNotificationStore();

  const [liveActivities, setLiveActivities] = useState<Array<{
    id: string; type: string; message: string; time: string; status: string;
  }>>([]);

  const { data: dashStats } = useQuery({
    queryKey: ["analytics", "dashboard"],
    queryFn: () => api.get("/analytics/dashboard?period=30d").then((r) => r.data),
  });
  const { data: gpuStats, dataUpdatedAt } = useQuery({
    queryKey: ["analytics", "gpu"],
    queryFn: () => api.get("/analytics/gpu").then((r) => r.data),
    refetchInterval: 8000,
  });
  const { data: recentVideos } = useQuery({
    queryKey: ["videos", "recent"],
    queryFn: () => api.get("/videos?limit=6&status=completed").then((r) => r.data),
  });
  const { data: activeJobs } = useQuery({
    queryKey: ["jobs", "active"],
    queryFn: () => api.get("/jobs?status=processing&limit=5").then((r) => r.data),
    refetchInterval: 5000,
  });

  /* Subscribe to WS events for live activity feed */
  const activitiesRef = useRef(liveActivities);
  activitiesRef.current = liveActivities;
  useEffect(() => {
    const unsub = wsService.subscribeToAllJobs((event) => {
      const typeLabels: Record<string, string> = {
        avatar: "ساخت آواتار", voice: "کلون صدا", video: "تولید ویدیو",
      };
      const statusLabels: Record<string, string> = {
        completed: "تکمیل شد", failed: "ناموفق", processing: "در حال پردازش",
      };
      const entry = {
        id: `${event.job_id}-${Date.now()}`,
        type: event.job_type,
        message: `${typeLabels[event.job_type] ?? "کار"} ${statusLabels[event.status] ?? event.status}`,
        time: new Date().toLocaleTimeString("fa-IR"),
        status: event.status,
      };
      setLiveActivities((prev) => [entry, ...prev].slice(0, 8));
    });
    return () => unsub();
  }, []);

  const firstName = user?.full_name?.split(" ")[0] || user?.email?.split("@")[0] || "کاربر";
  const gpuUpdated = dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString("fa-IR") : null;

  const videos  = dashStats?.videos?.total  ?? 0;
  const avatars = dashStats?.avatars?.total ?? 0;
  const voices  = dashStats?.voices?.total  ?? 0;
  const agents  = dashStats?.agents?.total  ?? 0;

  /* Merge notification + live feed */
  const recentNotifs = notifications.slice(0, 3);

  return (
    <div className="space-y-7 pb-6">

      {/* Welcome Banner */}
      <div className="relative rounded-2xl overflow-hidden animate-fade-in-down p-6"
        style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-lg)" }}>
        <div className="absolute inset-0 opacity-20"
          style={{ backgroundImage: "radial-gradient(circle at 70% 50%, white 0%, transparent 60%)" }} />
        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="text-white/70 text-sm font-medium flex items-center gap-2">
              <LiveClock />
              <span>·</span>
              <span>{getGreeting()}،</span>
            </p>
            <h1 className="text-2xl font-bold text-white mt-1">
              {firstName} <span className="opacity-80">✨</span>
            </h1>
            <p className="text-white/70 text-sm mt-1">
              پلتفرم هوش مصنوعی شما آماده‌ی خلق است
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/video-studio")}
              className="flex items-center gap-2 px-5 py-2.5 bg-white text-primary rounded-xl text-sm font-semibold shadow-lg hover:bg-white/90 transition-colors">
              <Sparkles size={15} />
              ویدیو جدید
            </button>
            <button onClick={() => navigate("/realtime")}
              className="flex items-center gap-2 px-4 py-2.5 bg-white/20 text-white rounded-xl text-sm font-semibold hover:bg-white/30 transition-colors border border-white/20">
              <Globe2 size={15} />
              مکالمه آنی
            </button>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Video}  label="ویدیو تولید شده" value={videos}  trend={12} gradient="linear-gradient(135deg,#6366f1,#8b5cf6)" delay={0} />
        <StatCard icon={Users}  label="آواتارها"         value={avatars}             gradient="linear-gradient(135deg,#8b5cf6,#a855f7)" delay={0.05} />
        <StatCard icon={Mic}    label="مدل‌های صدا"      value={voices}              gradient="linear-gradient(135deg,#06b6d4,#0891b2)" delay={0.10} />
        <StatCard icon={Bot}    label="ایجنت‌های AI"     value={agents}  trend={5}  gradient="linear-gradient(135deg,#10b981,#059669)" delay={0.15} />
      </div>

      {/* Active Jobs Banner */}
      {activeJobs?.items?.length > 0 && (
        <div className="rounded-2xl p-4 border animate-fade-in"
          style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
          <div className="flex items-center gap-2 mb-3">
            <Loader2 size={14} className="text-amber-500 animate-spin" />
            <span className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>
              کارهای در حال اجرا ({activeJobs.items.length})
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {activeJobs.items.map((job: any) => (
              <div key={job.id} className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium border"
                style={{ backgroundColor: "hsl(var(--muted))", borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                {job.job_type === "avatar" ? "آواتار" : job.job_type === "voice" ? "صدا" : "ویدیو"} · {job.progress ?? 0}%
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>اقدامات سریع</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <ActionCard icon={Users} label="ساخت آواتار"
            description="عکس یا ویدیو بارگذاری کنید و آواتار AI بسازید"
            onClick={() => navigate("/avatar-studio")}
            gradient="linear-gradient(135deg,#6366f1,#8b5cf6)" delay={0} />
          <ActionCard icon={Mic} label="کلون صدا"
            description="صدای خود را با XTTS-v2 در ۶ زبان کلون کنید"
            onClick={() => navigate("/voice-studio")}
            gradient="linear-gradient(135deg,#a855f7,#7c3aed)" delay={0.05} />
          <ActionCard icon={Video} label="تولید ویدیو"
            description="ویدیوهای ۴K با آواتار سخن‌گو و لب‌سینک بسازید"
            onClick={() => navigate("/video-studio")}
            gradient="linear-gradient(135deg,#06b6d4,#0284c7)" delay={0.10} />
          <ActionCard icon={Bot} label="ساخت ایجنت"
            description="دستیار هوشمند با حافظه و دانش اختصاصی بسازید"
            onClick={() => navigate("/agent-builder")}
            gradient="linear-gradient(135deg,#10b981,#0d9488)" delay={0.15} />
        </div>
      </section>

      {/* Bottom Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Recent Videos */}
        <div className="lg:col-span-2 rounded-2xl p-5 border animate-fade-in-up"
          style={{ animationDelay: ".2s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>ویدیوهای اخیر</h2>
              <p className="text-xs mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>آخرین ویدیوهای تولید شده</p>
            </div>
            <button onClick={() => navigate("/video-studio")}
              className="flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors">
              همه <ArrowRight size={11} className="rtl:rotate-180" />
            </button>
          </div>
          {!recentVideos?.items?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-3"
                style={{ backgroundColor: "hsl(var(--muted))" }}>
                <Video size={24} style={{ color: "hsl(var(--muted-foreground))", opacity: 0.4 }} />
              </div>
              <p className="text-sm font-medium mb-1" style={{ color: "hsl(var(--foreground))" }}>هنوز ویدیویی ندارید</p>
              <p className="text-xs mb-4" style={{ color: "hsl(var(--muted-foreground))" }}>اولین ویدیوی آواتار سخن‌گو را بسازید</p>
              <button onClick={() => navigate("/video-studio")}
                className="btn-primary text-xs px-4 py-2">
                <Plus size={13} /> ساخت ویدیو
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {recentVideos.items.map((video: any) => (
                <div key={video.id}
                  className="group relative rounded-xl overflow-hidden aspect-video cursor-pointer ring-1 transition-all hover:shadow-md"
                  style={{ backgroundColor: "hsl(var(--muted))", ringColor: "hsl(var(--border))" }}>
                  {video.thumbnail_url ? (
                    <img src={video.thumbnail_url} alt={video.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video size={20} style={{ color: "hsl(var(--muted-foreground))", opacity: 0.4 }} />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="absolute bottom-2 start-2 end-2">
                      <p className="text-white text-xs font-medium truncate">{video.title || "بدون عنوان"}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-4">

          {/* GPU Status */}
          <div className="rounded-2xl p-5 border animate-fade-in-up"
            style={{ animationDelay: ".25s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }}>
                  <Cpu size={13} className="text-white" />
                </div>
                <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>وضعیت GPU</h3>
              </div>
              <div className="flex items-center gap-1.5">
                {gpuStats?.available ? (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                    style={{ background: "rgb(16 185 129 / 0.12)", color: "#10b981" }}>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    آنلاین
                  </span>
                ) : (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                    style={{ background: "rgb(239 68 68 / 0.12)", color: "#ef4444" }}>
                    آفلاین
                  </span>
                )}
              </div>
            </div>
            {gpuStats?.available && gpuStats.gpus?.[0] ? (
              <div className="space-y-4">
                {gpuStats.gpus.map((gpu: any, i: number) => (
                  <GpuBar key={i} name={gpu.name} util={gpu.utilization_percent}
                    vramUsed={gpu.memory_used_mb} vramTotal={gpu.memory_total_mb}
                    temp={gpu.temperature_c} />
                ))}
                {gpuUpdated && (
                  <p className="text-[10px] text-right" style={{ color: "hsl(var(--muted-foreground))" }}>
                    بروزرسانی: {gpuUpdated}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 py-2">
                <Zap size={14} style={{ color: "hsl(var(--muted-foreground))" }} />
                <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>GPU یافت نشد — حالت CPU</p>
              </div>
            )}
          </div>

          {/* Storage */}
          <div className="rounded-2xl p-5 border animate-fade-in-up"
            style={{ animationDelay: ".3s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: "linear-gradient(135deg,#f59e0b,#d97706)" }}>
                <HardDrive size={13} className="text-white" />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>مصرف فضا</h3>
            </div>
            <div className="space-y-3">
              {[
                { label: "ویدیوها",   gb: dashStats?.videos?.total_size_gb  ?? 0, color: "#6366f1" },
                { label: "صداها",     gb: dashStats?.voices?.total_size_gb  ?? 0, color: "#a855f7" },
                { label: "آواتارها",  gb: dashStats?.avatars?.total_size_gb ?? 0, color: "#06b6d4" },
              ].map(({ label, gb, color }) => {
                const pct = Math.min(((gb as number) / 100) * 100, 100);
                return (
                  <div key={label}>
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                        <span style={{ color: "hsl(var(--muted-foreground))" }}>{label}</span>
                      </div>
                      <span className="font-semibold" style={{ color: "hsl(var(--foreground))" }}>{gb} GB</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, background: color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Live Activity + Analytics Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Live Activity Feed */}
        <div className="rounded-2xl p-5 border animate-fade-in-up"
          style={{ animationDelay: ".35s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: "linear-gradient(135deg,#10b981,#059669)" }}>
                <Activity size={13} className="text-white" />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>فعالیت زنده</h3>
            </div>
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
              style={{ background: "rgb(16 185 129 / 0.12)", color: "#10b981" }}>
              <span className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </span>
          </div>
          <div className="space-y-0">
            {liveActivities.length === 0 && recentNotifs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 gap-2">
                <Activity size={24} style={{ color: "hsl(var(--muted-foreground))", opacity: 0.3 }} />
                <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>منتظر رویدادهای زنده…</p>
              </div>
            ) : (
              <>
                {liveActivities.map((a) => (
                  <ActivityItem key={a.id} type={a.type} message={a.message} time={a.time} status={a.status} />
                ))}
                {liveActivities.length === 0 && recentNotifs.map((n) => (
                  <ActivityItem key={n.id} type="default" message={n.title} time={n.timestamp} status={n.type} />
                ))}
              </>
            )}
          </div>
        </div>

        {/* Quick Stats Chart Area */}
        <div className="rounded-2xl p-5 border animate-fade-in-up"
          style={{ animationDelay: ".4s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "linear-gradient(135deg,#06b6d4,#0284c7)" }}>
              <BarChart3 size={13} className="text-white" />
            </div>
            <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>خلاصه عملکرد</h3>
          </div>
          <div className="space-y-3">
            {[
              { label: "ویدیوهای موفق",     value: dashStats?.videos?.completed    ?? 0, total: dashStats?.videos?.total    ?? 1, color: "#6366f1" },
              { label: "آواتارهای آماده",   value: dashStats?.avatars?.ready       ?? 0, total: dashStats?.avatars?.total   ?? 1, color: "#8b5cf6" },
              { label: "مدل‌های صدای آماده", value: dashStats?.voices?.ready       ?? 0, total: dashStats?.voices?.total    ?? 1, color: "#06b6d4" },
              { label: "ایجنت‌های فعال",    value: dashStats?.agents?.active       ?? 0, total: dashStats?.agents?.total    ?? 1, color: "#10b981" },
            ].map(({ label, value, total, color }) => {
              const pct = total > 0 ? Math.round((value / total) * 100) : 0;
              return (
                <div key={label}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span style={{ color: "hsl(var(--muted-foreground))" }}>{label}</span>
                    <span className="font-semibold tabular-nums" style={{ color: "hsl(var(--foreground))" }}>
                      {value} / {total}
                    </span>
                  </div>
                  <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
                    <div className="h-full rounded-full transition-all duration-1000"
                      style={{ width: `${pct}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-4 pt-4 border-t flex items-center justify-between"
            style={{ borderColor: "hsl(var(--border))" }}>
            <button onClick={() => navigate("/analytics")}
              className="flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors">
              مشاهده آمار کامل <ArrowRight size={11} className="rtl:rotate-180" />
            </button>
            <div className="flex items-center gap-1 text-[10px]" style={{ color: "hsl(var(--muted-foreground))" }}>
              <Clock size={10} />
              ۳۰ روز گذشته
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
