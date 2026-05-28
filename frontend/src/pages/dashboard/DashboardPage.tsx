import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Users, Mic, Video, Bot, TrendingUp, TrendingDown,
  HardDrive, Cpu, Plus, ArrowRight, Activity, Zap,
  Clock, CheckCircle2, AlertCircle, Loader2, Sparkles, BarChart3, Globe2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api }                    from "../../services/api";
import { useAuthStore }           from "../../stores/authStore";
import { useNotificationStore }   from "../../stores/notificationStore";
import { wsService }              from "../../services/websocket";
import { useCountUp }             from "../../hooks/useCountUp";
import { cn }                     from "../../utils/cn";
import { GRADIENTS, TIMING }      from "../../constants";
import type { NotificationItem, WSJobProgressEvent } from "../../types";

// ── Greeting helper ───────────────────────────────────────────
function getGreetingKey(): "morning" | "afternoon" | "evening" {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}

// ── Live clock ────────────────────────────────────────────────
function LiveClock() {
  const [time, setTime] = useState(new Date());
  const { i18n } = useTranslation();

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const locale = i18n.language === "fa" ? "fa-IR" : i18n.language;
  return (
    <span className="tabular-nums font-mono text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
      {time.toLocaleTimeString(locale)}
    </span>
  );
}

// ── Stat card ─────────────────────────────────────────────────
interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: number;
  trend?: number;
  gradient: string;
  delay?: number;
  trendLabel?: string;
}

function StatCard({ icon: Icon, label, value, trend, gradient, delay = 0, trendLabel }: StatCardProps) {
  const animated = useCountUp(value, TIMING.countUpMs, delay * 1000);
  return (
    <div className="stat-card animate-fade-in-up" style={{ animationDelay: `${delay}s` }}>
      <div className="stat-icon" style={{ background: gradient }}>
        <Icon size={19} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-2xl font-bold mt-0.5" style={{ color: "hsl(var(--foreground))" }}>
          {animated}
        </p>
        {trend !== undefined && (
          <div className={cn("flex items-center gap-1 mt-1 text-xs font-medium",
            trend >= 0 ? "text-emerald-500" : "text-red-500")}>
            {trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {trend >= 0 ? "+" : ""}{trend}% {trendLabel}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Quick action card ─────────────────────────────────────────
interface ActionCardProps {
  icon: React.ElementType;
  label: string;
  description: string;
  onClick: () => void;
  gradient: string;
  delay?: number;
  ctaLabel: string;
}

function ActionCard({ icon: Icon, label, description, onClick, gradient, delay = 0, ctaLabel }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      className="group relative rounded-2xl p-5 text-start overflow-hidden transition-all duration-300 hover:-translate-y-1 animate-fade-in-up border"
      style={{
        animationDelay:  `${delay}s`,
        backgroundColor: "hsl(var(--card))",
        borderColor:     "hsl(var(--border))",
        boxShadow:       "var(--shadow-sm)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-lg)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-sm)")}
    >
      <div className="relative z-10">
        <div
          className="inline-flex p-3 rounded-xl mb-4 text-white group-hover:scale-110 transition-transform duration-200"
          style={{ background: gradient }}
        >
          <Icon size={20} />
        </div>
        <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>{label}</h3>
        <p className="text-xs mt-1 leading-relaxed" style={{ color: "hsl(var(--muted-foreground))" }}>{description}</p>
        <div className="flex items-center gap-1 mt-3 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
          {ctaLabel} <ArrowRight size={11} className="rtl:rotate-180" />
        </div>
      </div>
    </button>
  );
}

// ── GPU bar ───────────────────────────────────────────────────
interface GpuBarProps {
  name: string;
  util: number;
  vramUsedMb: number;
  vramTotalMb: number;
  tempC: number;
}

function GpuBar({ name, util, vramUsedMb, vramTotalMb, tempC }: GpuBarProps) {
  const barColor = util > 90 ? "#ef4444" : util > 70 ? "#f59e0b" : "#6366f1";
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium truncate max-w-[130px]" style={{ color: "hsl(var(--muted-foreground))" }}>
          {name}
        </span>
        <div className="flex items-center gap-2">
          <span className="font-bold tabular-nums" style={{ color: barColor }}>{util}%</span>
          <span style={{ color: "hsl(var(--muted-foreground))" }}>{tempC}°C</span>
        </div>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${util}%`, background: barColor }}
        />
      </div>
      <div className="flex justify-between text-[10px]" style={{ color: "hsl(var(--muted-foreground))" }}>
        <span>VRAM {(vramUsedMb / 1024).toFixed(1)}GB / {(vramTotalMb / 1024).toFixed(1)}GB</span>
        <Activity size={10} className="text-emerald-500" />
      </div>
    </div>
  );
}

// ── Live activity item ────────────────────────────────────────
interface ActivityEntry {
  id: string;
  jobType: string;
  message: string;
  time: string;
  status: string;
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  const JOB_ICONS: Record<string, React.ElementType> = { avatar: Users, voice: Mic, video: Video };
  const Icon = JOB_ICONS[entry.jobType] ?? Activity;

  const statusColor =
    entry.status === "completed"  ? "text-emerald-500" :
    entry.status === "failed"     ? "text-red-500"     :
    entry.status === "processing" ? "text-amber-500"   : "text-blue-400";

  const StatusIcon =
    entry.status === "completed"  ? CheckCircle2 :
    entry.status === "failed"     ? AlertCircle  : Loader2;

  return (
    <div
      className="flex items-start gap-3 py-2.5 border-b last:border-0"
      style={{ borderColor: "hsl(var(--border))" }}
    >
      <div
        className="w-7 h-7 rounded-lg shrink-0 flex items-center justify-center"
        style={{ backgroundColor: "hsl(var(--muted))" }}
      >
        <Icon size={13} style={{ color: "hsl(var(--muted-foreground))" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate" style={{ color: "hsl(var(--foreground))" }}>
          {entry.message}
        </p>
        <p className="text-[10px] mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
          {entry.time}
        </p>
      </div>
      <StatusIcon
        size={13}
        className={cn("shrink-0 mt-0.5", statusColor, entry.status === "processing" && "animate-spin")}
      />
    </div>
  );
}

// ── Dashboard page ────────────────────────────────────────────
export default function DashboardPage() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { user } = useAuthStore();
  const { notifications } = useNotificationStore();

  const [liveActivities, setLiveActivities] = useState<ActivityEntry[]>([]);

  // Data queries
  const { data: dashStats } = useQuery({
    queryKey: ["analytics", "dashboard"],
    queryFn:  () => api.get("/analytics/dashboard?period=30d").then((r) => r.data),
  });

  const { data: gpuStats, dataUpdatedAt } = useQuery({
    queryKey:       ["analytics", "gpu"],
    queryFn:        () => api.get("/analytics/gpu").then((r) => r.data),
    refetchInterval: TIMING.gpuPollMs,
  });

  const { data: recentVideos } = useQuery({
    queryKey: ["videos", "recent"],
    queryFn:  () => api.get("/videos?limit=6&status=completed").then((r) => r.data),
  });

  const { data: activeJobs } = useQuery({
    queryKey:       ["jobs", "active"],
    queryFn:        () => api.get("/jobs?status=processing&limit=5").then((r) => r.data),
    refetchInterval: TIMING.jobPollMs,
  });

  // Live WebSocket activity feed (capped at 8 entries)
  const activitiesRef = useRef(liveActivities);
  activitiesRef.current = liveActivities;

  useEffect(() => {
    const locale = i18n.language === "fa" ? "fa-IR" : i18n.language;

    const unsub = wsService.subscribeToAllJobs((event: WSJobProgressEvent) => {
      const statusLabel = t(`notifications.activityStatus.${event.status}`, { defaultValue: event.status });
      const stepLabel   = event.current_step ?? t("notifications.jobDone");

      const entry: ActivityEntry = {
        id:      `${event.job_id}-${Date.now()}`,
        jobType: "default",
        message: `${stepLabel} · ${statusLabel}`,
        time:    new Date().toLocaleTimeString(locale),
        status:  event.status,
      };
      setLiveActivities((prev) => [entry, ...prev].slice(0, 8));
    });
    return () => unsub();
  }, [i18n.language, t]);

  // Derived values
  const firstName  = user?.full_name?.split(" ")[0] ?? user?.email?.split("@")[0] ?? "کاربر";
  const greeting   = t(`dashboard.greeting.${getGreetingKey()}`);

  const locale     = i18n.language === "fa" ? "fa-IR" : i18n.language;
  const gpuUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(locale)
    : null;

  const videos  = (dashStats?.videos?.total   as number) ?? 0;
  const avatars = (dashStats?.avatars?.total  as number) ?? 0;
  const voices  = (dashStats?.voices?.total   as number) ?? 0;
  const agents  = (dashStats?.agents?.total   as number) ?? 0;

  const fallbackActivities: ActivityEntry[] = (notifications as NotificationItem[])
    .slice(0, 3)
    .map((n) => ({
      id:      n.id,
      jobType: "default",
      message: n.title,
      time:    n.timestamp,
      status:  n.type,
    }));

  const displayActivities = liveActivities.length > 0 ? liveActivities : fallbackActivities;

  return (
    <div className="space-y-7 pb-6">

      {/* Welcome banner */}
      <div
        className="relative rounded-2xl overflow-hidden animate-fade-in-down p-6"
        style={{ background: GRADIENTS.primary, boxShadow: "var(--shadow-lg)" }}
      >
        <div
          className="absolute inset-0 opacity-20"
          style={{ backgroundImage: "radial-gradient(circle at 70% 50%, white 0%, transparent 60%)" }}
        />
        <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="text-white/70 text-sm font-medium flex items-center gap-2">
              <LiveClock />
              <span>·</span>
              <span>{greeting}،</span>
            </p>
            <h1 className="text-2xl font-bold text-white mt-1">
              {firstName} <span className="opacity-80">✨</span>
            </h1>
            <p className="text-white/70 text-sm mt-1">{t("dashboard.platformReady")}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/video-studio")}
              className="flex items-center gap-2 px-5 py-2.5 bg-white text-primary rounded-xl text-sm font-semibold shadow-lg hover:bg-white/90 transition-colors"
            >
              <Sparkles size={15} />
              {t("dashboard.newVideo")}
            </button>
            <button
              onClick={() => navigate("/realtime")}
              className="flex items-center gap-2 px-4 py-2.5 bg-white/20 text-white rounded-xl text-sm font-semibold hover:bg-white/30 transition-colors border border-white/20"
            >
              <Globe2 size={15} />
              {t("dashboard.liveConversation")}
            </button>
          </div>
        </div>
      </div>

      {/* Stat grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Video}  label={t("dashboard.videoStats")}  value={videos}  trend={12} gradient={GRADIENTS.indigo}  delay={0}    trendLabel={t("common.thisMonth")} />
        <StatCard icon={Users}  label={t("dashboard.avatarStats")} value={avatars}            gradient={GRADIENTS.violet}  delay={0.05} />
        <StatCard icon={Mic}    label={t("dashboard.voiceStats")}  value={voices}             gradient={GRADIENTS.cyan}    delay={0.10} />
        <StatCard icon={Bot}    label={t("dashboard.agentStats")}  value={agents}  trend={5}  gradient={GRADIENTS.teal}    delay={0.15} trendLabel={t("common.thisMonth")} />
      </div>

      {/* Active jobs banner */}
      {(activeJobs?.items?.length ?? 0) > 0 && (
        <div
          className="rounded-2xl p-4 border animate-fade-in"
          style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Loader2 size={14} className="text-amber-500 animate-spin" />
            <span className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>
              {t("dashboard.activeJobs")} ({activeJobs.items.length})
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {activeJobs.items.map((job: { id: string; job_type: string; progress?: number }) => (
              <div
                key={job.id}
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium border"
                style={{
                  backgroundColor: "hsl(var(--muted))",
                  borderColor:     "hsl(var(--border))",
                  color:           "hsl(var(--foreground))",
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                {t(`dashboard.jobType${job.job_type.charAt(0).toUpperCase()}${job.job_type.slice(1)}`, { defaultValue: job.job_type })} · {job.progress ?? 0}%
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick actions */}
      <section>
        <h2 className="text-sm font-semibold mb-4" style={{ color: "hsl(var(--foreground))" }}>
          {t("dashboard.quickActions")}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <ActionCard icon={Users} label={t("dashboard.createAvatar")}   description={t("avatar.noAvatars")}   onClick={() => navigate("/avatar-studio")}    gradient={GRADIENTS.indigo} delay={0}    ctaLabel={t("common.getStarted")} />
          <ActionCard icon={Mic}   label={t("dashboard.cloneVoice")}     description={t("voice.noVoicesHint")} onClick={() => navigate("/voice-studio")}     gradient={GRADIENTS.purple} delay={0.05} ctaLabel={t("common.getStarted")} />
          <ActionCard icon={Video} label={t("dashboard.generateVideo")}  description={t("video.noVideos")}     onClick={() => navigate("/video-studio")}     gradient={GRADIENTS.cyan}   delay={0.10} ctaLabel={t("common.getStarted")} />
          <ActionCard icon={Bot}   label={t("dashboard.createAgent")}    description={t("agent.noAgents")}     onClick={() => navigate("/agent-builder")}    gradient={GRADIENTS.teal}   delay={0.15} ctaLabel={t("common.getStarted")} />
        </div>
      </section>

      {/* Bottom grid: recent videos + right column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Recent videos */}
        <div
          className="lg:col-span-2 rounded-2xl p-5 border animate-fade-in-up"
          style={{ animationDelay: ".2s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
        >
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>
                {t("dashboard.recentVideos")}
              </h2>
              <p className="text-xs mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
                {t("dashboard.recentVideosSubtitle")}
              </p>
            </div>
            <button
              onClick={() => navigate("/video-studio")}
              className="flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
            >
              {t("common.viewAll")} <ArrowRight size={11} className="rtl:rotate-180" />
            </button>
          </div>

          {!recentVideos?.items?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center mb-3"
                style={{ backgroundColor: "hsl(var(--muted))" }}
              >
                <Video size={24} style={{ color: "hsl(var(--muted-foreground))", opacity: 0.4 }} />
              </div>
              <p className="text-sm font-medium mb-1" style={{ color: "hsl(var(--foreground))" }}>
                {t("dashboard.noVideos")}
              </p>
              <p className="text-xs mb-4" style={{ color: "hsl(var(--muted-foreground))" }}>
                {t("dashboard.noVideosHint")}
              </p>
              <button onClick={() => navigate("/video-studio")} className="btn-primary text-xs px-4 py-2">
                <Plus size={13} /> {t("dashboard.createVideo")}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {recentVideos.items.map((video: { id: string; title?: string; thumbnail_url?: string }) => (
                <div
                  key={video.id}
                  className="group relative rounded-xl overflow-hidden aspect-video cursor-pointer ring-1 transition-all hover:shadow-md"
                  style={{ backgroundColor: "hsl(var(--muted))" }}
                >
                  {video.thumbnail_url ? (
                    <img src={video.thumbnail_url} alt={video.title ?? ""} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video size={20} style={{ color: "hsl(var(--muted-foreground))", opacity: 0.4 }} />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="absolute bottom-2 start-2 end-2">
                      <p className="text-white text-xs font-medium truncate">{video.title || t("common.noData")}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* GPU */}
          <div
            className="rounded-2xl p-5 border animate-fade-in-up"
            style={{ animationDelay: ".25s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: GRADIENTS.indigo }}>
                  <Cpu size={13} className="text-white" />
                </div>
                <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>
                  {t("dashboard.gpuStatus")}
                </h3>
              </div>
              <span
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                style={gpuStats?.available
                  ? { background: "rgb(16 185 129 / 0.12)", color: "#10b981" }
                  : { background: "rgb(239 68 68 / 0.12)",  color: "#ef4444" }}
              >
                {gpuStats?.available ? t("dashboard.gpuOnline") : t("dashboard.gpuOffline")}
              </span>
            </div>

            {gpuStats?.available && gpuStats.gpus?.[0] ? (
              <div className="space-y-4">
                {(gpuStats.gpus as Array<{ name: string; utilization_percent: number; memory_used_mb: number; memory_total_mb: number; temperature_c: number }>)
                  .map((gpu, i) => (
                    <GpuBar
                      key={i}
                      name={gpu.name}
                      util={gpu.utilization_percent}
                      vramUsedMb={gpu.memory_used_mb}
                      vramTotalMb={gpu.memory_total_mb}
                      tempC={gpu.temperature_c}
                    />
                  ))}
                {gpuUpdated && (
                  <p className="text-[10px] text-right" style={{ color: "hsl(var(--muted-foreground))" }}>
                    {t("dashboard.gpuUpdated")}: {gpuUpdated}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 py-2">
                <Zap size={14} style={{ color: "hsl(var(--muted-foreground))" }} />
                <p className="text-sm" style={{ color: "hsl(var(--muted-foreground))" }}>
                  {t("dashboard.gpuNoDetected")}
                </p>
              </div>
            )}
          </div>

          {/* Storage */}
          <div
            className="rounded-2xl p-5 border animate-fade-in-up"
            style={{ animationDelay: ".3s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: GRADIENTS.amber }}>
                <HardDrive size={13} className="text-white" />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>
                {t("dashboard.storageUsage")}
              </h3>
            </div>
            <div className="space-y-3">
              {([
                { labelKey: "dashboard.storageVideos",  gb: dashStats?.videos?.total_size_gb,  color: "#6366f1" },
                { labelKey: "dashboard.storageVoices",  gb: dashStats?.voices?.total_size_gb,  color: "#a855f7" },
                { labelKey: "dashboard.storageAvatars", gb: dashStats?.avatars?.total_size_gb, color: "#06b6d4" },
              ] as const).map(({ labelKey, gb, color }) => {
                const gbVal = (gb as number | undefined) ?? 0;
                const pct   = Math.min((gbVal / 100) * 100, 100);
                return (
                  <div key={labelKey}>
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                        <span style={{ color: "hsl(var(--muted-foreground))" }}>{t(labelKey)}</span>
                      </div>
                      <span className="font-semibold" style={{ color: "hsl(var(--foreground))" }}>{gbVal} GB</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom row: live activity + performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

        {/* Live activity */}
        <div
          className="rounded-2xl p-5 border animate-fade-in-up"
          style={{ animationDelay: ".35s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: GRADIENTS.teal }}>
                <Activity size={13} className="text-white" />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>
                {t("dashboard.liveActivity")}
              </h3>
            </div>
            <span
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
              style={{ background: "rgb(16 185 129 / 0.12)", color: "#10b981" }}
            >
              <span className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </span>
          </div>

          {displayActivities.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <Activity size={24} style={{ color: "hsl(var(--muted-foreground))", opacity: 0.3 }} />
              <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
                {t("dashboard.waitingForEvents")}
              </p>
            </div>
          ) : (
            displayActivities.map((a) => <ActivityItem key={a.id} entry={a} />)
          )}
        </div>

        {/* Performance summary */}
        <div
          className="rounded-2xl p-5 border animate-fade-in-up"
          style={{ animationDelay: ".4s", backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
        >
          <div className="flex items-center gap-2 mb-5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: GRADIENTS.cyan }}>
              <BarChart3 size={13} className="text-white" />
            </div>
            <h3 className="font-semibold text-sm" style={{ color: "hsl(var(--foreground))" }}>
              {t("dashboard.performanceSummary")}
            </h3>
          </div>
          <div className="space-y-3">
            {([
              { labelKey: "dashboard.successfulVideos", value: dashStats?.videos?.completed,  total: dashStats?.videos?.total,  color: "#6366f1" },
              { labelKey: "dashboard.readyAvatars",     value: dashStats?.avatars?.ready,     total: dashStats?.avatars?.total, color: "#8b5cf6" },
              { labelKey: "dashboard.readyVoiceModels", value: dashStats?.voices?.ready,      total: dashStats?.voices?.total,  color: "#06b6d4" },
              { labelKey: "dashboard.activeAgents",     value: dashStats?.agents?.active,     total: dashStats?.agents?.total,  color: "#10b981" },
            ] as const).map(({ labelKey, value, total, color }) => {
              const v   = (value as number | undefined) ?? 0;
              const tot = (total as number | undefined) ?? 1;
              const pct = tot > 0 ? Math.round((v / tot) * 100) : 0;
              return (
                <div key={labelKey}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span style={{ color: "hsl(var(--muted-foreground))" }}>{t(labelKey)}</span>
                    <span className="font-semibold tabular-nums" style={{ color: "hsl(var(--foreground))" }}>
                      {v} / {tot}
                    </span>
                  </div>
                  <div className="h-2 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
                    <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${pct}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div
            className="mt-4 pt-4 border-t flex items-center justify-between"
            style={{ borderColor: "hsl(var(--border))" }}
          >
            <button
              onClick={() => navigate("/analytics")}
              className="flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
            >
              {t("dashboard.viewFullAnalytics")} <ArrowRight size={11} className="rtl:rotate-180" />
            </button>
            <div className="flex items-center gap-1 text-[10px]" style={{ color: "hsl(var(--muted-foreground))" }}>
              <Clock size={10} />
              {t("dashboard.last30Days")}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
