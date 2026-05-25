import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Users, Mic, Video, Bot, TrendingUp, TrendingDown,
  HardDrive, Cpu, Plus, ArrowRight, Activity, Zap,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../utils/cn";

/* ─── Stat Card ─────────────────────────────────────────── */
function StatCard({ icon: Icon, label, value, trend, gradient, delay = 0 }: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  trend?: number;
  gradient: string;
  delay?: number;
}) {
  return (
    <div className="stat-card animate-fade-in-up" style={{ animationDelay: `${delay}s` }}>
      <div className="stat-icon" style={{ background: gradient }}>
        <Icon size={19} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground font-medium">{label}</p>
        <p className="text-2xl font-bold text-foreground mt-0.5 animate-number-up" style={{ animationDelay: `${delay + .1}s` }}>
          {value}
        </p>
        {trend !== undefined && (
          <div className={cn("flex items-center gap-1 mt-1 text-xs font-medium",
            trend >= 0 ? "text-emerald-500" : "text-red-500")}>
            {trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
            {trend >= 0 ? "+" : ""}{trend}% this month
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Quick Action Card ──────────────────────────────────── */
function ActionCard({ icon: Icon, label, description, onClick, gradient, delay = 0 }: {
  icon: React.ElementType;
  label: string;
  description: string;
  onClick: () => void;
  gradient: string;
  delay?: number;
}) {
  return (
    <button
      onClick={onClick}
      className="group relative bg-card border border-border rounded-2xl p-5 text-start overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:border-primary/30 animate-fade-in-up"
      style={{ animationDelay: `${delay}s`, boxShadow: "var(--shadow-sm)" }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-lg)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-sm)")}
    >
      {/* Background glow */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-2xl"
        style={{ background: `${gradient.replace("135deg,", "135deg, rgba(").replace(" 0%", " 0%, ").split(",").slice(0,2).join(",").trim()})`.replace("linear-gradient(135deg, rgba(", "radial-gradient(circle at 0% 0%, ").replace(")", ", transparent 60%)") }}
      />
      <div className="relative z-10">
        <div className="inline-flex p-3 rounded-xl mb-4 text-white group-hover:scale-110 transition-transform duration-200"
          style={{ background: gradient }}>
          <Icon size={20} />
        </div>
        <h3 className="font-semibold text-foreground text-sm">{label}</h3>
        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{description}</p>
        <div className="flex items-center gap-1 mt-3 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
          Get started <ArrowRight size={11} />
        </div>
      </div>
    </button>
  );
}

/* ─── GPU Gauge ──────────────────────────────────────────── */
function GpuBar({ name, util, vramUsed, vramTotal, temp }: {
  name: string; util: number; vramUsed: number; vramTotal: number; temp: number;
}) {
  const color = util > 90 ? "var(--gradient-danger)" : util > 70 ? "var(--gradient-warning)" : "var(--gradient-primary)";
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground font-medium truncate max-w-[140px]">{name}</span>
        <div className="flex items-center gap-2">
          <span className={cn("font-bold", util > 90 ? "text-red-500" : util > 70 ? "text-amber-500" : "text-foreground")}>{util}%</span>
          <span className="text-muted-foreground">{temp}°C</span>
        </div>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${util}%`, background: color }} />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>VRAM {(vramUsed/1024).toFixed(1)}GB / {(vramTotal/1024).toFixed(1)}GB</span>
        <Activity size={10} className="text-emerald-500" />
      </div>
    </div>
  );
}

/* ─── Main Page ──────────────────────────────────────────── */
export default function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const { data: dashStats } = useQuery({
    queryKey: ["analytics", "dashboard"],
    queryFn: () => api.get("/analytics/dashboard?period=30d").then((r) => r.data),
  });
  const { data: gpuStats } = useQuery({
    queryKey: ["analytics", "gpu"],
    queryFn: () => api.get("/analytics/gpu").then((r) => r.data),
    refetchInterval: 10000,
  });
  const { data: recentVideos } = useQuery({
    queryKey: ["videos", "recent"],
    queryFn: () => api.get("/videos?limit=6&status=completed").then((r) => r.data),
  });

  const firstName = user?.full_name?.split(" ")[0] || user?.email.split("@")[0];

  return (
    <div className="space-y-7 pb-4">

      {/* Welcome header */}
      <div className="flex items-start justify-between animate-fade-in-down">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {t("dashboard.welcome")}, <span className="gradient-text">{firstName}</span> 👋
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Here's an overview of your AI platform today.
          </p>
        </div>
        <button
          onClick={() => navigate("/video-studio")}
          className="btn-primary hidden sm:flex"
        >
          <Plus size={15} />
          New Video
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger-children">
        <StatCard
          icon={Video} label="Videos Generated"
          value={dashStats?.videos?.total ?? "—"} trend={12}
          gradient="linear-gradient(135deg, #6366f1, #8b5cf6)" delay={0}
        />
        <StatCard
          icon={Users} label="Avatars"
          value={dashStats?.avatars?.total ?? "—"}
          gradient="linear-gradient(135deg, #8b5cf6, #a855f7)" delay={.05}
        />
        <StatCard
          icon={Mic} label="Voice Models"
          value={dashStats?.voices?.total ?? "—"}
          gradient="linear-gradient(135deg, #06b6d4, #0891b2)" delay={.10}
        />
        <StatCard
          icon={Bot} label="AI Agents"
          value={dashStats?.agents?.total ?? "—"} trend={5}
          gradient="linear-gradient(135deg, #10b981, #059669)" delay={.15}
        />
      </div>

      {/* Quick actions */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-foreground">{t("dashboard.quickActions")}</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger-children">
          <ActionCard icon={Users} label={t("dashboard.createAvatar")}
            description="Upload photo or video to create your AI avatar"
            onClick={() => navigate("/avatar-studio")}
            gradient="linear-gradient(135deg, #6366f1, #8b5cf6)" delay={0} />
          <ActionCard icon={Mic} label={t("dashboard.cloneVoice")}
            description="Clone your voice in 7 languages with XTTS-v2"
            onClick={() => navigate("/voice-studio")}
            gradient="linear-gradient(135deg, #a855f7, #7c3aed)" delay={.05} />
          <ActionCard icon={Video} label={t("dashboard.generateVideo")}
            description="Generate 4K talking avatar videos with lip sync"
            onClick={() => navigate("/video-studio")}
            gradient="linear-gradient(135deg, #06b6d4, #0284c7)" delay={.10} />
          <ActionCard icon={Bot} label={t("dashboard.createAgent")}
            description="Build an intelligent AI assistant with RAG"
            onClick={() => navigate("/agent-builder")}
            gradient="linear-gradient(135deg, #10b981, #0d9488)" delay={.15} />
        </div>
      </section>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Recent Videos */}
        <div className="lg:col-span-2 card-premium p-5 animate-fade-in-up" style={{ animationDelay: ".2s" }}>
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-semibold text-foreground text-sm">{t("dashboard.recentVideos")}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">Recently generated videos</p>
            </div>
            <button onClick={() => navigate("/video-studio")}
              className="btn-ghost text-xs text-primary hover:text-primary/80 gap-1">
              View all <ArrowRight size={11} />
            </button>
          </div>
          {!recentVideos?.items?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-3">
                <Video size={24} className="text-muted-foreground opacity-40" />
              </div>
              <p className="text-sm font-medium text-foreground mb-1">{t("video.noVideos")}</p>
              <p className="text-xs text-muted-foreground mb-4">Generate your first talking avatar video</p>
              <button onClick={() => navigate("/video-studio")} className="btn-primary text-xs px-4 py-2">
                <Plus size={13} /> Create Video
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {recentVideos.items.map((video: any) => (
                <div key={video.id}
                  className="group relative rounded-xl overflow-hidden bg-muted aspect-video cursor-pointer ring-1 ring-border hover:ring-primary/50 transition-all hover:shadow-md">
                  {video.thumbnail_url ? (
                    <img src={video.thumbnail_url} alt={video.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video size={20} className="text-muted-foreground opacity-40" />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="absolute bottom-2 start-2 end-2">
                      <p className="text-white text-xs font-medium truncate">{video.title || "Untitled"}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-4">
          {/* GPU Status */}
          <div className="card-premium p-5 animate-fade-in-up" style={{ animationDelay: ".25s" }}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }}>
                  <Cpu size={13} className="text-white" />
                </div>
                <h3 className="font-semibold text-foreground text-sm">{t("dashboard.gpuStatus")}</h3>
              </div>
              {gpuStats?.available && (
                <span className="badge badge-success">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Online
                </span>
              )}
            </div>
            {gpuStats?.available && gpuStats.gpus?.[0] ? (
              <div className="space-y-4">
                {gpuStats.gpus.map((gpu: any, i: number) => (
                  <GpuBar key={i}
                    name={gpu.name} util={gpu.utilization_percent}
                    vramUsed={gpu.memory_used_mb} vramTotal={gpu.memory_total_mb}
                    temp={gpu.temperature_c} />
                ))}
              </div>
            ) : (
              <div className="flex items-center gap-2 py-2">
                <Zap size={14} className="text-muted-foreground" />
                <p className="text-sm text-muted-foreground">No GPU detected — CPU mode</p>
              </div>
            )}
          </div>

          {/* Storage */}
          <div className="card-premium p-5 animate-fade-in-up" style={{ animationDelay: ".3s" }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>
                <HardDrive size={13} className="text-white" />
              </div>
              <h3 className="font-semibold text-foreground text-sm">{t("dashboard.storageUsage")}</h3>
            </div>
            <div className="space-y-3">
              {[
                { label: "Videos",  gb: dashStats?.videos?.total_size_gb ?? 0,   color: "#6366f1" },
                { label: "Voices",  gb: dashStats?.voices?.total_size_gb ?? 0,   color: "#a855f7" },
                { label: "Avatars", gb: dashStats?.avatars?.total_size_gb ?? 0,  color: "#06b6d4" },
              ].map(({ label, gb, color }) => (
                <div key={label}>
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                      <span className="text-muted-foreground">{label}</span>
                    </div>
                    <span className="font-semibold text-foreground">{gb} GB</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${Math.min((gb / 100) * 100, 100)}%`, background: color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
