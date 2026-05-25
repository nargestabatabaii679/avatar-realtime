import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Upload, Camera, Trash2, Star, CheckCircle,
  XCircle, Clock, X, Sparkles, Image, Film,
} from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";
import type { Avatar } from "../../types";

/* ─── Status Badge ───────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; icon: React.ElementType; cls: string }> = {
    ready:      { label: "Ready",      icon: CheckCircle, cls: "badge-success" },
    processing: { label: "Processing", icon: Clock,        cls: "badge-warning" },
    failed:     { label: "Failed",     icon: XCircle,      cls: "badge-danger"  },
  };
  const cfg = map[status] ?? map.processing;
  const Icon = cfg.icon;
  return (
    <span className={cn("badge", cfg.cls)}>
      <Icon size={10} />
      {cfg.label}
    </span>
  );
}

/* ─── Avatar Card ────────────────────────────────────────── */
function AvatarCard({ avatar, onDelete }: { avatar: Avatar; onDelete: (id: string) => void }) {
  return (
    <div className="group relative bg-card border border-border rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:border-primary/30"
      style={{ boxShadow: "var(--shadow-sm)" }}
      onMouseEnter={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-lg)")}
      onMouseLeave={(e) => (e.currentTarget.style.boxShadow = "var(--shadow-sm)")}
    >
      {/* Thumbnail */}
      <div className="aspect-square bg-muted relative overflow-hidden">
        {avatar.thumbnail_url ? (
          <img src={avatar.thumbnail_url} alt={avatar.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-2xl font-black"
              style={{ background: "var(--gradient-primary)" }}>
              {avatar.name.charAt(0)}
            </div>
          </div>
        )}

        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center">
          <button
            onClick={() => onDelete(avatar.id)}
            className="p-2.5 rounded-xl bg-red-500/90 text-white hover:bg-red-600 transition-colors shadow-lg"
          >
            <Trash2 size={15} />
          </button>
        </div>

        {/* Status */}
        <div className="absolute top-2.5 start-2.5">
          <StatusBadge status={avatar.status} />
        </div>

        {/* Quality score */}
        {avatar.metadata?.quality_score && (
          <div className="absolute top-2.5 end-2.5 flex items-center gap-0.5 bg-black/70 text-yellow-400 px-1.5 py-0.5 rounded-lg text-[10px] font-semibold backdrop-blur-sm">
            <Star size={9} fill="currentColor" />
            {(avatar.metadata.quality_score * 100).toFixed(0)}
          </div>
        )}
      </div>

      {/* Info */}
      <div className="p-3.5">
        <h3 className="font-semibold text-foreground text-sm truncate">{avatar.name}</h3>
        <div className="flex items-center gap-1.5 mt-1">
          {avatar.source_type === "video" ? (
            <Film size={10} className="text-muted-foreground" />
          ) : (
            <Image size={10} className="text-muted-foreground" />
          )}
          <p className="text-xs text-muted-foreground capitalize">{avatar.source_type}</p>
        </div>
        {avatar.status === "processing" && (
          <div className="mt-2.5 progress-bar">
            <div className="progress-fill animate-pulse-slow" style={{ width: "65%" }} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Upload Modal ───────────────────────────────────────── */
function UploadModal({ onClose, onSubmit, isPending }: {
  onClose: () => void;
  onSubmit: (name: string, file: File) => void;
  isPending: boolean;
}) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) setFile(files[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"], "video/*": [".mp4", ".mov"] },
    maxFiles: 1,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-card border border-border rounded-2xl p-6 shadow-2xl animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "var(--gradient-primary)" }}>
              <Sparkles size={16} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground">Create New Avatar</h2>
              <p className="text-xs text-muted-foreground">Upload photo or video</p>
            </div>
          </div>
          <button onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="space-y-4">
          {/* Name input */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Avatar Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Professional Avatar"
              className="input-field"
            />
          </div>

          {/* Drop zone */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-1.5">Source File</label>
            <div
              {...getRootProps()}
              className={cn("drop-zone p-8 text-center cursor-pointer", isDragActive && "drop-zone-active")}
            >
              <input {...getInputProps()} />
              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-emerald-500/10">
                    <CheckCircle size={22} className="text-emerald-500" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{file.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {(file.size / 1024 / 1024).toFixed(1)} MB · Click to change
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-primary/10 mb-1">
                    <Upload size={22} className="text-primary" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">{t("avatar.upload")}</p>
                  <p className="text-xs text-muted-foreground">JPG, PNG, MP4, MOV — max 500MB</p>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-1">
            <button onClick={onClose} className="btn-secondary flex-1">
              {t("common.cancel")}
            </button>
            <button
              onClick={() => file && name && onSubmit(name, file)}
              disabled={!file || !name || isPending}
              className="btn-primary flex-1"
            >
              {isPending ? (
                <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Processing…</>
              ) : (
                <><Sparkles size={14} /> {t("common.upload")}</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Main Page ──────────────────────────────────────────── */
export default function AvatarStudioPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showUpload, setShowUpload] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["avatars"],
    queryFn: () => api.get("/avatars").then((r) => r.data),
    refetchInterval: 10000,
  });

  const createMutation = useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("name", name);
      form.append("source_type", file.type.startsWith("video") ? "video" : "photo");
      return api.post("/avatars", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["avatars"] });
      setShowUpload(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/avatars/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["avatars"] }),
  });

  const avatars: Avatar[] = data?.items || [];

  return (
    <div className="space-y-6 pb-4">
      {/* Header */}
      <div className="flex items-start justify-between animate-fade-in-down">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("avatar.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload photos or videos to create photorealistic AI avatars
          </p>
        </div>
        <button onClick={() => setShowUpload(true)} className="btn-primary">
          <Plus size={15} />
          {t("avatar.create")}
        </button>
      </div>

      {/* Stats bar */}
      {!isLoading && avatars.length > 0 && (
        <div className="flex items-center gap-6 p-4 bg-card border border-border rounded-2xl animate-fade-in" style={{ boxShadow: "var(--shadow-sm)" }}>
          {[
            { label: "Total",      value: avatars.length, color: "text-foreground" },
            { label: "Ready",      value: avatars.filter(a => a.status === "ready").length,      color: "text-emerald-500" },
            { label: "Processing", value: avatars.filter(a => a.status === "processing").length, color: "text-amber-500"  },
            { label: "Failed",     value: avatars.filter(a => a.status === "failed").length,     color: "text-red-500"    },
          ].map(({ label, value, color }) => (
            <div key={label} className="flex items-center gap-2">
              <span className={cn("text-lg font-bold", color)}>{value}</span>
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSubmit={(name, file) => createMutation.mutate({ name, file })}
          isPending={createMutation.isPending}
        />
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="rounded-2xl overflow-hidden" style={{ animationDelay: `${i * .04}s` }}>
              <div className="aspect-square skeleton" />
              <div className="p-3.5 space-y-2">
                <div className="h-3.5 skeleton rounded-lg w-3/4" />
                <div className="h-3 skeleton rounded-lg w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : avatars.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center animate-fade-in-up">
          <div className="relative mb-6">
            <div className="w-24 h-24 rounded-3xl bg-muted flex items-center justify-center">
              <Camera size={36} className="text-muted-foreground opacity-40" />
            </div>
            <div className="absolute -bottom-2 -end-2 w-10 h-10 rounded-xl flex items-center justify-center text-white"
              style={{ background: "var(--gradient-primary)" }}>
              <Plus size={18} />
            </div>
          </div>
          <h3 className="text-lg font-bold text-foreground mb-2">No avatars yet</h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-xs">{t("avatar.noAvatars")}</p>
          <button onClick={() => setShowUpload(true)} className="btn-primary">
            <Sparkles size={15} />
            {t("avatar.create")}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 stagger-children">
          {avatars.map((avatar, i) => (
            <div key={avatar.id} className="animate-fade-in-up" style={{ animationDelay: `${i * .04}s` }}>
              <AvatarCard avatar={avatar} onDelete={(id) => deleteMutation.mutate(id)} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
