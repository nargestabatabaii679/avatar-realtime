import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload, Camera, Trash2, RefreshCw, Star, CheckCircle, XCircle, Clock } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";
import type { Avatar } from "../../types";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; icon: React.ElementType; class: string }> = {
    ready: { label: "Ready", icon: CheckCircle, class: "text-green-500 bg-green-500/10" },
    processing: { label: "Processing", icon: Clock, class: "text-yellow-500 bg-yellow-500/10" },
    failed: { label: "Failed", icon: XCircle, class: "text-red-500 bg-red-500/10" },
  };
  const cfg = map[status] ?? map.processing;
  const Icon = cfg.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium", cfg.class)}>
      <Icon size={11} />
      {cfg.label}
    </span>
  );
}

function AvatarCard({ avatar, onDelete }: { avatar: Avatar; onDelete: (id: string) => void }) {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden group hover:border-primary/50 transition-all">
      {/* Thumbnail */}
      <div className="aspect-square bg-muted relative overflow-hidden">
        {avatar.thumbnail_url ? (
          <img src={avatar.thumbnail_url} alt={avatar.name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-2xl font-bold">
              {avatar.name.charAt(0)}
            </div>
          </div>
        )}
        {/* Overlay on hover */}
        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
          <button
            onClick={() => onDelete(avatar.id)}
            className="p-2 rounded-lg bg-red-500/80 text-white hover:bg-red-600 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
        {/* Status badge */}
        <div className="absolute top-2 start-2">
          <StatusBadge status={avatar.status} />
        </div>
        {/* Quality score */}
        {avatar.metadata?.quality_score && (
          <div className="absolute top-2 end-2 flex items-center gap-0.5 bg-black/60 text-yellow-400 px-1.5 py-0.5 rounded text-xs">
            <Star size={10} fill="currentColor" />
            {(avatar.metadata.quality_score * 100).toFixed(0)}
          </div>
        )}
      </div>
      {/* Info */}
      <div className="p-3">
        <h3 className="font-medium text-foreground text-sm truncate">{avatar.name}</h3>
        <p className="text-xs text-muted-foreground mt-0.5 capitalize">{avatar.source_type}</p>
        {avatar.status === "processing" && (
          <div className="mt-2 progress-bar">
            <div className="progress-fill animate-pulse-slow" style={{ width: "60%" }} />
          </div>
        )}
      </div>
    </div>
  );
}

export default function AvatarStudioPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showUpload, setShowUpload] = useState(false);
  const [name, setName] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["avatars"],
    queryFn: () => api.get("/avatars").then((r) => r.data),
    refetchInterval: 10000,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile || !name) throw new Error("Name and file required");
      const form = new FormData();
      form.append("file", uploadFile);
      form.append("name", name);
      form.append("source_type", uploadFile.type.startsWith("video") ? "video" : "photo");
      return api.post("/avatars", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["avatars"] });
      setShowUpload(false);
      setName("");
      setUploadFile(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/avatars/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["avatars"] }),
  });

  const onDrop = useCallback((files: File[]) => {
    if (files[0]) setUploadFile(files[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"], "video/*": [".mp4", ".mov"] },
    maxFiles: 1,
  });

  const avatars: Avatar[] = data?.items || [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("avatar.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">Upload photos or videos to create AI avatars</p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm font-medium"
        >
          <Plus size={16} />
          {t("avatar.create")}
        </button>
      </div>

      {/* Upload Modal */}
      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-lg animate-fade-in">
            <h2 className="text-lg font-semibold text-foreground mb-4">Create New Avatar</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Avatar Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Professional Avatar"
                  className="w-full px-3 py-2 rounded-lg bg-muted border border-border text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>

              <div
                {...getRootProps()}
                className={cn(
                  "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
                  isDragActive ? "drop-zone-active" : "border-border hover:border-primary/50"
                )}
              >
                <input {...getInputProps()} />
                {uploadFile ? (
                  <div className="flex items-center justify-center gap-2 text-sm text-foreground">
                    <CheckCircle size={16} className="text-green-500" />
                    {uploadFile.name}
                  </div>
                ) : (
                  <>
                    <Upload size={32} className="mx-auto mb-3 text-muted-foreground opacity-50" />
                    <p className="text-sm font-medium text-foreground">{t("avatar.upload")}</p>
                    <p className="text-xs text-muted-foreground mt-1">JPG, PNG, MP4, MOV — max 500MB</p>
                  </>
                )}
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setShowUpload(false)}
                  className="flex-1 py-2 px-4 border border-border rounded-lg text-sm hover:bg-accent transition-colors"
                >
                  {t("common.cancel")}
                </button>
                <button
                  onClick={() => createMutation.mutate()}
                  disabled={!uploadFile || !name || createMutation.isPending}
                  className="flex-1 py-2 px-4 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {createMutation.isPending ? t("avatar.processing") : t("common.upload")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Avatars Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-xl overflow-hidden">
              <div className="aspect-square skeleton" />
              <div className="p-3 space-y-2">
                <div className="h-4 skeleton rounded w-3/4" />
                <div className="h-3 skeleton rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : avatars.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-20 h-20 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
            <Camera size={32} className="text-muted-foreground opacity-50" />
          </div>
          <h3 className="font-medium text-foreground mb-2">No Avatars Yet</h3>
          <p className="text-sm text-muted-foreground mb-6">{t("avatar.noAvatars")}</p>
          <button
            onClick={() => setShowUpload(true)}
            className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            {t("avatar.create")}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {avatars.map((avatar) => (
            <AvatarCard
              key={avatar.id}
              avatar={avatar}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
