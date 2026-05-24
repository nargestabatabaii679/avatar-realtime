import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Download, TrendingUp, Video, Users, Mic, Bot } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";

const PERIODS = [
  { value: "7d", label: "7 Days" },
  { value: "30d", label: "30 Days" },
  { value: "90d", label: "3 Months" },
  { value: "365d", label: "1 Year" },
];

const COLORS = ["#6366f1", "#8b5cf6", "#14b8a6", "#f97316", "#ec4899", "#84cc16"];

function KPICard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color: string;
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="flex items-start justify-between mb-3">
        <div className={cn("p-2.5 rounded-xl", color)}>
          <Icon size={18} className="text-white" />
        </div>
        <TrendingUp size={14} className="text-green-500" />
      </div>
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <p className="text-sm text-muted-foreground mt-0.5">{label}</p>
      {sub && <p className="text-xs text-primary mt-1">{sub}</p>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState("30d");

  const { data: stats } = useQuery({
    queryKey: ["analytics", "dashboard", period],
    queryFn: () => api.get(`/analytics/dashboard?period=${period}`).then((r) => r.data),
  });

  const { data: videoMetrics } = useQuery({
    queryKey: ["analytics", "videos", period],
    queryFn: () => api.get(`/analytics/videos?period=${period}`).then((r) => r.data),
  });

  const { data: gpuData } = useQuery({
    queryKey: ["analytics", "gpu"],
    queryFn: () => api.get("/analytics/gpu").then((r) => r.data),
    refetchInterval: 15000,
  });

  const resolutionData = Object.entries(videoMetrics?.by_resolution || {}).map(([name, value]) => ({ name, value }));
  const gpu = gpuData?.gpus?.[0];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("analytics.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">Platform performance and usage insights</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="flex bg-muted rounded-lg p-1 gap-0.5">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
                  period === p.value ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          <button className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm hover:bg-accent transition-colors">
            <Download size={14} />
            {t("analytics.export")}
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          icon={Video}
          label="Videos Generated"
          value={stats?.videos?.total ?? "—"}
          sub={`${stats?.videos?.total_duration_hours ?? 0}h total`}
          color="bg-gradient-to-br from-indigo-500 to-indigo-600"
        />
        <KPICard
          icon={Users}
          label="Active Avatars"
          value={stats?.avatars?.total ?? "—"}
          color="bg-gradient-to-br from-purple-500 to-purple-600"
        />
        <KPICard
          icon={Mic}
          label="Voice Models"
          value={stats?.voices?.total ?? "—"}
          color="bg-gradient-to-br from-teal-500 to-teal-600"
        />
        <KPICard
          icon={Bot}
          label="Conversations"
          value={stats?.agents?.conversations ?? "—"}
          color="bg-gradient-to-br from-orange-500 to-orange-600"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Video generation trend */}
        <div className="lg:col-span-2 bg-card border border-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">Videos Generated Over Time</h3>
          {videoMetrics?.daily?.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={videoMetrics.daily} margin={{ top: 0, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }}
                  labelStyle={{ color: "hsl(var(--foreground))" }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-60 flex items-center justify-center text-muted-foreground text-sm">
              No data for this period
            </div>
          )}
        </div>

        {/* Resolution breakdown */}
        <div className="bg-card border border-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">Resolution Breakdown</h3>
          {resolutionData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={resolutionData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} dataKey="value">
                    {resolutionData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {resolutionData.map((item, i) => (
                  <div key={item.name} className="flex items-center gap-2 text-sm">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="flex-1 text-muted-foreground">{item.name}</span>
                    <span className="font-medium text-foreground">{item.value as number}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-60 flex items-center justify-center text-muted-foreground text-sm">No data</div>
          )}
        </div>
      </div>

      {/* GPU Metrics */}
      {gpu && (
        <div className="bg-card border border-border rounded-xl p-5">
          <h3 className="font-semibold text-foreground mb-4">GPU Status — {gpu.name}</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Utilization", value: `${gpu.utilization_percent}%`, progress: gpu.utilization_percent },
              { label: "VRAM Used", value: `${Math.round(gpu.memory_used_mb / 1024 * 10) / 10} GB`, progress: (gpu.memory_used_mb / gpu.memory_total_mb) * 100 },
              { label: "Temperature", value: `${gpu.temperature_c}°C`, progress: (gpu.temperature_c / 100) * 100 },
              { label: "Power Draw", value: `${gpu.power_draw_w ?? "—"}W`, progress: 0 },
            ].map(({ label, value, progress }) => (
              <div key={label}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">{label}</span>
                  <span className="font-medium text-foreground">{value}</span>
                </div>
                {progress > 0 && (
                  <div className="progress-bar">
                    <div
                      className={cn("progress-fill", progress > 90 ? "!from-red-500 !to-red-600" : "")}
                      style={{ width: `${Math.min(100, progress)}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
