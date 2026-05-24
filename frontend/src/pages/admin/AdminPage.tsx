import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Users, Building2, Activity, Server, Shield, RefreshCw, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";

const TABS = [
  { id: "users", label: "Users", icon: Users },
  { id: "system", label: "System", icon: Server },
  { id: "jobs", label: "Jobs", icon: Activity },
  { id: "audit", label: "Audit Logs", icon: Shield },
];

export default function AdminPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("system");

  const { data: systemHealth, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ["admin", "system"],
    queryFn: () => api.get("/admin/system").then((r) => r.data),
    refetchInterval: 30000,
    enabled: activeTab === "system",
  });

  const { data: users } = useQuery({
    queryKey: ["admin", "users"],
    queryFn: () => api.get("/admin/users?limit=50").then((r) => r.data),
    enabled: activeTab === "users",
  });

  const { data: jobs } = useQuery({
    queryKey: ["admin", "jobs"],
    queryFn: () => api.get("/admin/jobs?limit=50").then((r) => r.data),
    refetchInterval: activeTab === "jobs" ? 10000 : false,
    enabled: activeTab === "jobs",
  });

  const { data: auditLogs } = useQuery({
    queryKey: ["admin", "audit"],
    queryFn: () => api.get("/admin/audit-logs?limit=50").then((r) => r.data),
    enabled: activeTab === "audit",
  });

  const suspendMutation = useMutation({
    mutationFn: (userId: string) => api.post(`/admin/users/${userId}/suspend`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] }),
  });

  const retryJobMutation = useMutation({
    mutationFn: (jobId: string) => api.post(`/admin/jobs/${jobId}/retry`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "jobs"] }),
  });

  const ServiceStatus = ({ name, status, details }: { name: string; status: string; details?: any }) => (
    <div className="flex items-center justify-between p-4 bg-muted rounded-xl">
      <div className="flex items-center gap-3">
        <div className={cn("w-2.5 h-2.5 rounded-full", status === "connected" || status === "available" ? "bg-green-500" : "bg-red-500 animate-pulse")} />
        <span className="font-medium text-foreground text-sm">{name}</span>
      </div>
      <div className="flex items-center gap-3">
        {status === "connected" || status === "available" ? (
          <CheckCircle size={14} className="text-green-500" />
        ) : (
          <XCircle size={14} className="text-red-500" />
        )}
        {details?.latency_ms !== undefined && <span className="text-xs text-muted-foreground">{details.latency_ms}ms</span>}
        {details?.memory_used_mb !== undefined && <span className="text-xs text-muted-foreground">{details.memory_used_mb}MB</span>}
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("admin.title")}</h1>
        <p className="text-muted-foreground text-sm mt-1">System administration and monitoring</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted p-1 rounded-xl w-fit">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
              activeTab === id ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon size={14} />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* System Health */}
      {activeTab === "system" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-foreground">System Health</h2>
            <button onClick={() => refetchHealth()} className="flex items-center gap-1.5 px-3 py-1.5 border border-border rounded-lg text-xs hover:bg-accent transition-colors">
              <RefreshCw size={12} /> Refresh
            </button>
          </div>
          {healthLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 skeleton rounded-xl" />)}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(systemHealth?.services || {}).map(([name, svc]: [string, any]) => (
                <ServiceStatus key={name} name={name.charAt(0).toUpperCase() + name.slice(1)} status={svc.status} details={svc} />
              ))}
            </div>
          )}
          {systemHealth?.services?.gpu?.name && (
            <div className="bg-card border border-border rounded-xl p-5">
              <h3 className="font-semibold text-foreground mb-3">GPU: {systemHealth.services.gpu.name}</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                  { label: "VRAM", value: `${Math.round(systemHealth.services.gpu.memory_used_mb / 1024 * 10) / 10}/${Math.round(systemHealth.services.gpu.memory_total_mb / 1024 * 10) / 10} GB` },
                  { label: "Utilization", value: `${systemHealth.services.gpu.utilization_percent}%` },
                  { label: "Temperature", value: `${systemHealth.services.gpu.temperature_c}°C` },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="font-semibold text-foreground text-lg">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Users */}
      {activeTab === "users" && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  {["Name", "Email", "Role", "Status", "Created", "Actions"].map((h) => (
                    <th key={h} className="px-4 py-3 text-start text-xs font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(users?.items || []).map((user: any) => (
                  <tr key={user.id} className="hover:bg-muted/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-foreground">{user.full_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs capitalize">{user.role}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("px-2 py-0.5 rounded-full text-xs", user.is_active ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500")}>
                        {user.is_active ? "Active" : "Suspended"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{new Date(user.created_at).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => suspendMutation.mutate(user.id)}
                        disabled={suspendMutation.isPending}
                        className={cn("px-3 py-1 rounded-lg text-xs font-medium transition-colors",
                          user.is_active ? "bg-red-500/10 text-red-500 hover:bg-red-500/20" : "bg-green-500/10 text-green-500 hover:bg-green-500/20"
                        )}
                      >
                        {user.is_active ? "Suspend" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Jobs */}
      {activeTab === "jobs" && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  {["Job ID", "Video ID", "Status", "Progress", "Started", "Actions"].map((h) => (
                    <th key={h} className="px-4 py-3 text-start text-xs font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(jobs?.items || []).map((job: any) => (
                  <tr key={job.id} className="hover:bg-muted/50 transition-colors">
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{job.id.slice(0, 8)}…</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono">{job.video_id?.slice(0, 8)}…</td>
                    <td className="px-4 py-3">
                      <span className={cn("px-2 py-0.5 rounded-full text-xs",
                        job.status === "completed" ? "bg-green-500/10 text-green-500" :
                        job.status === "running" ? "bg-blue-500/10 text-blue-500" :
                        job.status === "failed" ? "bg-red-500/10 text-red-500" : "bg-yellow-500/10 text-yellow-500"
                      )}>{job.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 progress-bar">
                          <div className="progress-fill" style={{ width: `${job.progress}%` }} />
                        </div>
                        <span className="text-xs text-muted-foreground">{job.progress}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{job.started_at ? new Date(job.started_at).toLocaleString() : "—"}</td>
                    <td className="px-4 py-3">
                      {job.status === "failed" && (
                        <button onClick={() => retryJobMutation.mutate(job.id)} disabled={retryJobMutation.isPending}
                          className="flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary rounded-lg text-xs hover:bg-primary/20 transition-colors"
                        >
                          {retryJobMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />} Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Audit Logs */}
      {activeTab === "audit" && (
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  {["Action", "Resource", "IP Address", "User", "Timestamp"].map((h) => (
                    <th key={h} className="px-4 py-3 text-start text-xs font-medium text-muted-foreground">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(auditLogs?.items || []).map((log: any) => (
                  <tr key={log.id} className="hover:bg-muted/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-foreground text-xs">{log.action}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{log.resource_type} {log.resource_id?.slice(0,8)}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs font-mono">{log.ip_address}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{log.user_id?.slice(0,8)}</td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
