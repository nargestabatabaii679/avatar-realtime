import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Users, Mic, Video, Bot, TrendingUp, HardDrive, Cpu, Plus } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../utils/cn";
import { formatBytes, formatDuration } from "../../utils/format";

function StatsCard({ icon: Icon, label, value, trend, color }: {
  icon: React.ElementType; label: string; value: string | number; trend?: number; color: string;
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 flex items-start gap-4">
      <div className={cn("p-3 rounded-xl", color)}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold text-foreground mt-0.5">{value}</p>
        {trend !== undefined && (
          <p className={cn("text-xs mt-1", trend >= 0 ? "text-green-500" : "text-red-500")}>
            {trend >= 0 ? "+" : ""}{trend}% this month
          </p>
        )}
      </div>
    </div>
  );
}

function QuickActionCard({ icon: Icon, label, description, onClick, color }: {
  icon: React.ElementType; label: string; description: string; onClick: () => void; color: string;
}) {
  return (
    <button
      onClick={onClick}
      className="bg-card border border-border rounded-xl p-5 text-start hover:border-primary/50 hover:shadow-md transition-all group"
    >
      <div className={cn("inline-flex p-3 rounded-xl mb-3 group-hover:scale-110 transition-transform", color)}>
        <Icon size={22} className="text-white" />
      </div>
      <h3 className="font-semibold text-foreground">{label}</h3>
      <p className="text-sm text-muted-foreground mt-1">{description}</p>
    </button>
  );
}

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
    <div className="space-y-6 animate-fade-in">
      {/* Welcome */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {t("dashboard.welcome")}, {firstName} 👋
          </h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Here's what's happening with your platform today.
          </p>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          icon={Video}
          label="Videos Generated"
          value={dashStats?.videos?.total ?? "—"}
          trend={12}
          color="bg-gradient-to-br from-indigo-500 to-indigo-600"
        />
        <StatsCard
          icon={Users}
          label="Avatars"
          value={dashStats?.avatars?.total ?? "—"}
          color="bg-gradient-to-br from-purple-500 to-purple-600"
        />
        <StatsCard
          icon={Mic}
          label="Voice Models"
          value={dashStats?.voices?.total ?? "—"}
          color="bg-gradient-to-br from-teal-500 to-teal-600"
        />
        <StatsCard
          icon={Bot}
          label="AI Agents"
          value={dashStats?.agents?.total ?? "—"}
          trend={5}
          color="bg-gradient-to-br from-orange-500 to-orange-600"
        />
      </div>

      {/* Quick Actions */}
      <section>
        <h2 className="text-lg font-semibold text-foreground mb-4">{t("dashboard.quickActions")}</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <QuickActionCard
            icon={Users}
            label={t("dashboard.createAvatar")}
            description="Upload photo or video"
            onClick={() => navigate("/avatar-studio")}
            color="bg-gradient-to-br from-indigo-500 to-indigo-600"
          />
          <QuickActionCard
            icon={Mic}
            label={t("dashboard.cloneVoice")}
            description="Clone your voice in seconds"
            onClick={() => navigate("/voice-studio")}
            color="bg-gradient-to-br from-purple-500 to-purple-600"
          />
          <QuickActionCard
            icon={Video}
            label={t("dashboard.generateVideo")}
            description="Create a talking avatar video"
            onClick={() => navigate("/video-studio")}
            color="bg-gradient-to-br from-teal-500 to-teal-600"
          />
          <QuickActionCard
            icon={Bot}
            label={t("dashboard.createAgent")}
            description="Build an AI assistant"
            onClick={() => navigate("/agent-builder")}
            color="bg-gradient-to-br from-orange-500 to-orange-600"
          />
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Videos */}
        <div className="lg:col-span-2 bg-card border border-border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-foreground">{t("dashboard.recentVideos")}</h2>
            <button
              onClick={() => navigate("/video-studio")}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              <Plus size={12} /> New Video
            </button>
          </div>
          {recentVideos?.items?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Video size={32} className="mx-auto mb-2 opacity-40" />
              <p className="text-sm">{t("video.noVideos")}</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {recentVideos?.items?.map((video: any) => (
                <div key={video.id} className="group relative rounded-lg overflow-hidden bg-muted aspect-video cursor-pointer hover:ring-2 hover:ring-primary transition-all">
                  {video.thumbnail_url ? (
                    <img src={video.thumbnail_url} alt={video.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Video size={24} className="text-muted-foreground opacity-50" />
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="absolute bottom-2 start-2 end-2">
                      <p className="text-white text-xs font-medium truncate">{video.title || "Untitled"}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="space-y-4">
          {/* GPU Status */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <Cpu size={16} className="text-muted-foreground" />
              <h3 className="font-semibold text-foreground text-sm">{t("dashboard.gpuStatus")}</h3>
            </div>
            {gpuStats?.available && gpuStats.gpus?.[0] ? (
              <div className="space-y-3">
                {gpuStats.gpus.map((gpu: any, i: number) => (
                  <div key={i}>
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span className="truncate">{gpu.name}</span>
                      <span>{gpu.utilization_percent}%</span>
                    </div>
                    <div className="progress-bar">
                      <div
                        className={cn(
                          "progress-fill",
                          gpu.utilization_percent > 90 ? "!from-red-500 !to-red-600" :
                          gpu.utilization_percent > 70 ? "!from-yellow-500 !to-orange-500" : ""
                        )}
                        style={{ width: `${gpu.utilization_percent}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>VRAM: {Math.round(gpu.memory_used_mb / 1024 * 10) / 10}GB / {Math.round(gpu.memory_total_mb / 1024 * 10) / 10}GB</span>
                      <span>{gpu.temperature_c}°C</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">GPU not available</p>
            )}
          </div>

          {/* Storage */}
          <div className="bg-card border border-border rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <HardDrive size={16} className="text-muted-foreground" />
              <h3 className="font-semibold text-foreground text-sm">{t("dashboard.storageUsage")}</h3>
            </div>
            {dashStats?.videos?.total_size_gb !== undefined ? (
              <div className="space-y-2">
                {[
                  { label: "Videos", gb: dashStats.videos.total_size_gb, color: "bg-indigo-500" },
                ].map(({ label, gb, color }) => (
                  <div key={label} className="flex items-center gap-2 text-xs">
                    <div className={cn("w-2 h-2 rounded-full", color)} />
                    <span className="text-muted-foreground flex-1">{label}</span>
                    <span className="text-foreground font-medium">{gb} GB</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Loading…</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
