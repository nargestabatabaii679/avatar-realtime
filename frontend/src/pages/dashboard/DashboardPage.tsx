import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Users, Mic, Video, Bot, TrendingUp, TrendingDown,
  HardDrive, Cpu, Plus, ArrowRight, Activity, Zap,
  Clock, CheckCircle2, AlertCircle, Loader2, BarChart3, Globe2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api }                    from "../../services/api";
import { useAuthStore }           from "../../stores/authStore";
import { useNotificationStore }   from "../../stores/notificationStore";
import { wsService }              from "../../services/websocket";
import { useCountUp }             from "../../hooks/useCountUp";
import { cn }                     from "../../utils/cn";
import { TIMING }                 from "../../constants";
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
    <span className="tabular-nums font-mono text-xs" style={{ color: "var(--t2)" }}>
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
  delay?: number;
  trendLabel?: string;
}

function StatCard({ icon: Icon, label, value, trend, delay = 0, trendLabel }: StatCardProps) {
  const animated = useCountUp(value, TIMING.countUpMs, delay * 1000);
  return (
    <div className="stat-card animate-fade-in-up" style={{ animationDelay: `${delay}s` }}>
      <div className="stat-icon">
        <Icon size={19} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-2xl font-bold mt-0.5" style={{ color: "var(--t1)" }}>
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
  delay?: number;
  ctaLabel: string;
}

function ActionCard({ icon: Icon, label, description, onClick, delay = 0, ctaLabel }: ActionCardProps) {
  return (
    <button
      onClick={onClick}
      className="group card-premium p-5 text-start animate-fade-in-up w-full transition-all duration-150"
      style={{ animationDelay: `${delay}s` }}
    >
      <div
        className="inline-flex p-2.5 mb-4 transition-colors duration-150"
        style={{ background: "var(--s3)", borderRadius: "var(--r-tag)", color: "var(--accent)" }}
      >
        <Icon size={18} />
      </div>
      <h3 className="font-semibold text-sm" style={{ color: "var(--t1)" }}>{label}</h3>
      <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--t2)" }}>{description}</p>
      <div className="flex items-center gap-1 mt-3 text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ color: "var(--accent)", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.06em" }}>
        {ctaLabel} <ArrowRight size={11} className="rtl:rotate-180" />
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
  const barColor = util > 90 ? "var(--red)" : util > 70 ? "var(--amber)" : "var(--accent)";
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium truncate max-w-[130px]" style={{ color: "var(--t2)" }}>
          {name}
        </span>
        <div className="flex items-center gap-2">
          <span className="font-bold tabular-nums" style={{ color: barColor, fontFamily: "'IBM Plex Mono', monospace" }}>{util}%</span>
          <span style={{ color: "var(--t3)" }}>{tempC}°C</span>
        </div>
      </div>
      <div className="progress-bar">
        <div
          className="progress-fill transition-all duration-700"
          style={{ width: `${util}%`, background: barColor }}
        />
      </div>
      <div className="flex justify-between text-[10px]" style={{ color: "var(--t2)" }}>
        <span>VRAM {(vramUsedMb / 1024).toFixed(1)}GB / {(vramTotalMb / 1024).toFixed(1)}GB</span>
        <Activity size={10} style={{ color: "var(--green)" }} />
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
    entry.status === "completed"  ? "var(--green)" :
    entry.status === "failed"     ? "var(--red)"   :
    entry.status === "processing" ? "var(--amber)"  : "var(--accent)";

  const StatusIcon =
    entry.status === "completed"  ? CheckCircle2 :
    entry.status === "failed"     ? AlertCircle  : Loader2;

  return (
    <div
      className="flex items-start gap-3 py-2.5 border-b last:border-0"
      style={{ borderColor: "var(--border-rest)" }}
    >
      <div
        className="w-7 h-7 shrink-0 flex items-center justify-center"
        style={{ background: "var(--s3)", borderRadius: "var(--r-tag)" }}
      >
        <Icon size={13} style={{ color: "var(--t3)" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate" style={{ color: "var(--t1)" }}>
          {entry.message}
        </p>
        <p className="text-[10px] mt-0.5" style={{ color: "var(--t3)" }}>
          {entry.time}
        </p>
      </div>
      <StatusIcon
        size={13}
        className={cn("shrink-0 mt-0.5", entry.status === "processing" && "animate-spin")}
        style={{ color: statusColor }}
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
        className="card-premium animate-fade-in-down p-6"
        style={{ borderColor: "var(--accent-md)" }}
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium flex items-center gap-2" style={{ color: "var(--t2)" }}>
              <LiveClock />
              <span>·</span>
              <span>{greeting}،</span>
            </p>
            <h1 className="text-2xl font-bold mt-1" style={{ color: "var(--t1)" }}>
              {firstName}
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--t2)" }}>{t("dashboard.platformReady")}</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => navigate("/video-studio")} className="btn-primary">
              <Plus size={14} />
              {t("dashboard.newVideo")}
            </button>
            <button onClick={() => navigate("/realtime")} className="btn-secondary">
              <Globe2 size={14} />
              {t("dashboard.liveConversation")}
            </button>
          </div>
        </div>
      </div>

      {/* Stat grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Video}  label={t("dashboard.videoStats")}  value={videos}  trend={12} delay={0}    trendLabel={t("common.thisMonth")} />
        <StatCard icon={Users}  label={t("dashboard.avatarStats")} value={avatars}            delay={0.05} />
        <StatCard icon={Mic}    label={t("dashboard.voiceStats")}  value={voices}             delay={0.10} />
        <StatCard icon={Bot}    label={t("dashboard.agentStats")}  value={agents}  trend={5}  delay={0.15} trendLabel={t("common.thisMonth")} />
      </div>

      {/* Active jobs banner */}
      {(activeJobs?.items?.length ?? 0) > 0 && (
        <div className="card-premium p-4 animate-fade-in" style={{ borderColor: "rgba(240,165,0,0.2)" }}>
          <div className="flex items-center gap-2 mb-3">
            <Loader2 size={14} style={{ color: "var(--amber)" }} className="animate-spin" />
            <span className="text-sm font-semibold" style={{ color: "var(--t1)" }}>
              {t("dashboard.activeJobs")} ({activeJobs.items.length})
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {activeJobs.items.map((job: { id: string; job_type: string; progress?: number }) => (
              <div
                key={job.id}
                className="badge"
                style={{ background: "rgba(240,165,0,0.08)", color: "var(--amber)", border: "0.5px solid rgba(240,165,0,0.2)" }}
              >
                <span className="status-dot pending" />
                {t(`dashboard.jobType${job.job_type.charAt(0).toUpperCase()}${job.job_type.slice(1)}`, { defaultValue: job.job_type })} · {job.progress ?? 0}%
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick actions */}
      <section>
        <h2 className="section-label mb-4">{t("dashboard.quickActions")}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <ActionCard icon={Users} label={t("dashboard.createAvatar")}  description={t("avatar.noAvatars")}   onClick={() => navigate("/avatar-studio")} delay={0}    ctaLabel={t("common.getStarted")} />
          <ActionCard icon={Mic}   label={t("dashboard.cloneVoice")}    description={t("voice.noVoicesHint")} onClick={() => navigate("/voice-studio")}  delay={0.05} ctaLabel={t("common.getStarted")} />
          <ActionCard icon={Video} label={t("dashboard.generateVideo")} description={t("video.noVideos")}     onClick={() => navigate("/video-studio")}  delay={0.10} ctaLabel={t("common.getStarted")} />
          <ActionCard icon={Bot}   label={t("dashboard.createAgent")}   description={t("agent.noAgents")}     onClick={() => navigate("/agent-builder")} delay={0.15} ctaLabel={t("common.getStarted")} />
        </div>
      </section>

      {/* Bottom grid: recent videos + right column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Recent videos */}
        <div
          className="lg:col-span-2 card-premium p-5 animate-fade-in-up"
          style={{ animationDelay: ".2s" }}
        >
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-sm" style={{ color: "var(--t1)" }}>
                {t("dashboard.recentVideos")}
              </h2>
              <p className="text-xs mt-0.5" style={{ color: "var(--t2)" }}>
                {t("dashboard.recentVideosSubtitle")}
              </p>
            </div>
            <button
              onClick={() => navigate("/video-studio")}
              className="flex items-center gap-1 text-xs font-medium transition-colors"
              style={{ color: "var(--accent)", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.05em" }}
            >
              {t("common.viewAll")} <ArrowRight size={11} className="rtl:rotate-180" />
            </button>
          </div>

          {!recentVideos?.items?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div
                className="w-12 h-12 flex items-center justify-center mb-3"
                style={{ background: "var(--s3)", borderRadius: "var(--r-card)" }}
              >
                <Video size={20} style={{ color: "var(--t3)", opacity: 0.6 }} />
              </div>
              <p className="text-sm font-medium mb-1" style={{ color: "var(--t1)" }}>
                {t("dashboard.noVideos")}
              </p>
              <p className="text-xs mb-4" style={{ color: "var(--t2)" }}>
                {t("dashboard.noVideosHint")}
              </p>
              <button onClick={() => navigate("/video-studio")} className="btn-primary">
                <Plus size={13} /> {t("dashboard.createVideo")}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {recentVideos.items.map((video: { id: string; title?: string; thumbnail_url?: string }) => (
                <div
                  key={video.id}
                  className="group relative overflow-hidden aspect-video cursor-pointer transition-all"
                  style={{ background: "var(--s3)", borderRadius: "var(--r-card)", border: "0.5px solid var(--border-rest)" }}
                >
                  {video.thumbnail_url ? (
                    <img src={video.thumbnail_url} alt={video.title ?? ""} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video size={18} style={{ color: "var(--t3)", opacity: 0.5 }} />
                    </div>
                  )}
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2"
                    style={{ background: "linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 60%)" }}>
                    <p className="text-white text-[11px] font-medium truncate w-full">{video.title || t("common.noData")}</p>
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
            className="card-premium p-5 animate-fade-in-up"
            style={{ animationDelay: ".25s" }}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 flex items-center justify-center" style={{ background: "var(--s3)", borderRadius: "var(--r-tag)", color: "var(--accent)" }}>
                  <Cpu size={13} />
                </div>
                <h3 className="font-semibold text-sm" style={{ color: "var(--t1)" }}>
                  {t("dashboard.gpuStatus")}
                </h3>
              </div>
              <span
                className="badge"
                style={gpuStats?.available
                  ? { background: "rgba(0,232,122,0.08)", color: "var(--green)", border: "0.5px solid rgba(0,232,122,0.2)" }
                  : { background: "rgba(224,80,80,0.08)",  color: "var(--red)",   border: "0.5px solid rgba(224,80,80,0.2)" }}
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
                  <p className="text-[10px] text-right" style={{ color: "var(--t3)", fontFamily: "'IBM Plex Mono', monospace" }}>
                    {t("dashboard.gpuUpdated")}: {gpuUpdated}
                  </p>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 py-2">
                <Zap size={14} style={{ color: "var(--t3)" }} />
                <p className="text-sm" style={{ color: "var(--t3)" }}>
                  {t("dashboard.gpuNoDetected")}
                </p>
              </div>
            )}
          </div>

          {/* Storage */}
          <div
            className="card-premium p-5 animate-fade-in-up"
            style={{ animationDelay: ".3s" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 flex items-center justify-center" style={{ background: "var(--s3)", borderRadius: "var(--r-tag)", color: "var(--amber)" }}>
                <HardDrive size={13} />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: "var(--t1)" }}>
                {t("dashboard.storageUsage")}
              </h3>
            </div>
            <div className="space-y-3">
              {([
                { labelKey: "dashboard.storageVideos",  gb: dashStats?.videos?.total_size_gb,  color: "var(--accent)" },
                { labelKey: "dashboard.storageVoices",  gb: dashStats?.voices?.total_size_gb,  color: "var(--green)"  },
                { labelKey: "dashboard.storageAvatars", gb: dashStats?.avatars?.total_size_gb, color: "var(--amber)"  },
              ] as const).map(({ labelKey, gb, color }) => {
                const gbVal = (gb as number | undefined) ?? 0;
                const pct   = Math.min((gbVal / 100) * 100, 100);
                return (
                  <div key={labelKey}>
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                        <span style={{ color: "var(--t2)" }}>{t(labelKey)}</span>
                      </div>
                      <span className="font-semibold" style={{ color: "var(--t1)", fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px" }}>{gbVal} GB</span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
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
        <div className="card-premium p-5 animate-fade-in-up" style={{ animationDelay: ".35s" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 flex items-center justify-center" style={{ background: "var(--s3)", borderRadius: "var(--r-tag)", color: "var(--green)" }}>
                <Activity size={13} />
              </div>
              <h3 className="font-semibold text-sm" style={{ color: "var(--t1)" }}>
                {t("dashboard.liveActivity")}
              </h3>
            </div>
            <span className="badge" style={{ background: "rgba(0,232,122,0.08)", color: "var(--green)", border: "0.5px solid rgba(0,232,122,0.2)" }}>
              <span className="status-dot live" />
              LIVE
            </span>
          </div>

          {displayActivities.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 gap-2">
              <Activity size={24} style={{ color: "var(--t3)", opacity: 0.5 }} />
              <p className="text-xs" style={{ color: "var(--t3)" }}>
                {t("dashboard.waitingForEvents")}
              </p>
            </div>
          ) : (
            displayActivities.map((a) => <ActivityItem key={a.id} entry={a} />)
          )}
        </div>

        {/* Performance summary */}
        <div className="card-premium p-5 animate-fade-in-up" style={{ animationDelay: ".4s" }}>
          <div className="flex items-center gap-2 mb-5">
            <div className="w-7 h-7 flex items-center justify-center" style={{ background: "var(--s3)", borderRadius: "var(--r-tag)", color: "var(--accent)" }}>
              <BarChart3 size={13} />
            </div>
            <h3 className="font-semibold text-sm" style={{ color: "var(--t1)" }}>
              {t("dashboard.performanceSummary")}
            </h3>
          </div>
          <div className="space-y-3">
            {([
              { labelKey: "dashboard.successfulVideos", value: dashStats?.videos?.completed,  total: dashStats?.videos?.total,  color: "var(--accent)" },
              { labelKey: "dashboard.readyAvatars",     value: dashStats?.avatars?.ready,     total: dashStats?.avatars?.total, color: "var(--accent)" },
              { labelKey: "dashboard.readyVoiceModels", value: dashStats?.voices?.ready,      total: dashStats?.voices?.total,  color: "var(--green)"  },
              { labelKey: "dashboard.activeAgents",     value: dashStats?.agents?.active,     total: dashStats?.agents?.total,  color: "var(--green)"  },
            ] as const).map(({ labelKey, value, total, color }) => {
              const v   = (value as number | undefined) ?? 0;
              const tot = (total as number | undefined) ?? 1;
              const pct = tot > 0 ? Math.round((v / tot) * 100) : 0;
              return (
                <div key={labelKey}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <span style={{ color: "var(--t2)" }}>{t(labelKey)}</span>
                    <span className="font-semibold tabular-nums" style={{ color: "var(--t1)", fontFamily: "'IBM Plex Mono', monospace", fontSize: "11px" }}>
                      {v} / {tot}
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div
            className="mt-4 pt-4 border-t flex items-center justify-between"
            style={{ borderColor: "var(--border-rest)" }}
          >
            <button
              onClick={() => navigate("/analytics")}
              className="flex items-center gap-1 text-xs font-medium transition-colors"
              style={{ color: "var(--accent)", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.05em" }}
            >
              {t("dashboard.viewFullAnalytics")} <ArrowRight size={11} className="rtl:rotate-180" />
            </button>
            <div className="flex items-center gap-1 text-[10px]" style={{ color: "var(--t3)" }}>
              <Clock size={10} />
              {t("dashboard.last30Days")}
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
