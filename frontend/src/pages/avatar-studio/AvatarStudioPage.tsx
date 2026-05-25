import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, Upload, Trash2, Star, CheckCircle, XCircle, Clock,
  X, Sparkles, Image as ImgIcon, Film, Eye, Zap, Users,
} from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";
import type { Avatar } from "../../types";

/* ─── Status Badge ──────────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; icon: React.ElementType; cls: string }> = {
    ready:      { label: "آماده",   icon: CheckCircle, cls: "badge-success" },
    processing: { label: "پردازش", icon: Clock,       cls: "badge-warning" },
    failed:     { label: "خطا",     icon: XCircle,     cls: "badge-danger"  },
  };
  const cfg = map[status] ?? map.processing;
  const Icon = cfg.icon;
  return <span className={cn("badge", cfg.cls)}><Icon size={9} />{cfg.label}</span>;
}

/* ─── Upload Modal ──────────────────────────────────────────── */
function UploadModal({ onClose, onSubmit, isPending }: {
  onClose: () => void;
  onSubmit: (name: string, file: File) => void;
  isPending: boolean;
}) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [imgPreview, setImgPreview] = useState<string | null>(null);

  const onDrop = useCallback((files: File[]) => {
    if (!files[0]) return;
    setFile(files[0]);
    if (files[0].type.startsWith("image/")) setImgPreview(URL.createObjectURL(files[0]));
    else setImgPreview(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"], "video/*": [".mp4", ".mov"] },
    maxFiles: 1,
    maxSize: 500 * 1024 * 1024,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/75 backdrop-blur-xl" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-card border border-border rounded-2xl p-6 shadow-2xl animate-scale-in">
        <button onClick={onClose} className="absolute top-4 end-4 p-1.5 rounded-lg hover:bg-accent text-muted-foreground transition-colors">
          <X size={16} />
        </button>
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" }}>
            <Sparkles size={17} className="text-white" />
          </div>
          <div>
            <h2 className="font-black text-foreground text-base">آواتار جدید</h2>
            <p className="text-xs text-muted-foreground">عکس یا ویدیو آپلود کنید</p>
          </div>
        </div>

        <div className="space-y-4">
          <div {...getRootProps()} className={cn("drop-zone cursor-pointer overflow-hidden", isDragActive && "drop-zone-active")}>
            <input {...getInputProps()} />
            {imgPreview ? (
              <div className="relative">
                <img src={imgPreview} alt="preview" className="w-full h-52 object-cover" />
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                  <p className="text-white text-sm font-medium flex items-center gap-2"><Upload size={16} /> تغییر فایل</p>
                </div>
                <div className="absolute bottom-2 start-2 glass-dark px-2.5 py-1 rounded-lg text-white text-[11px]">{file?.name}</div>
              </div>
            ) : file ? (
              <div className="p-10 flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
                  <Film size={26} className="text-emerald-500" />
                </div>
                <p className="text-sm font-bold text-foreground">{file.name}</p>
                <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              </div>
            ) : (
              <div className="p-12 flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <Upload size={24} className="text-primary" />
                </div>
                <p className="text-sm font-bold text-foreground">عکس یا ویدیو را اینجا بکشید</p>
                <p className="text-xs text-muted-foreground">JPG · PNG · MP4 · MOV — حداکثر ۵۰۰ مگابایت</p>
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-semibold text-foreground mb-1.5">نام آواتار</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="مثال: پرزنتر اصلی"
              className="input-field"
              dir="rtl"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button onClick={onClose} className="btn-secondary flex-1">انصراف</button>
            <button
              onClick={() => file && name && onSubmit(name, file)}
              disabled={!file || !name.trim() || isPending}
              className="btn-primary flex-1"
            >
              {isPending
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />پردازش…</>
                : <><Sparkles size={14} />ساخت آواتار</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Avatar Card ───────────────────────────────────────────── */
function AvatarCard({ avatar, onDelete }: { avatar: Avatar; onDelete: (id: string) => void }) {
  const [showInfo, setShowInfo] = useState(false);
  const quality = avatar.metadata?.quality_score;
  const qualityPct = quality != null ? Math.round((quality as number) * 100) : null;
  const qColor = qualityPct == null ? "" : qualityPct >= 80 ? "text-emerald-500" : qualityPct >= 60 ? "text-amber-500" : "text-red-500";
  const qBg = qualityPct == null ? "" : qualityPct >= 80 ? "var(--gradient-success)" : qualityPct >= 60 ? "var(--gradient-warning)" : "var(--gradient-danger)";

  return (
    <div
      className="group relative bg-card border border-border rounded-2xl overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:border-primary/25"
      style={{ boxShadow: "var(--shadow-sm)" }}
      onMouseEnter={e => (e.currentTarget.style.boxShadow = "var(--shadow-lg)")}
      onMouseLeave={e => (e.currentTarget.style.boxShadow = "var(--shadow-sm)")}
    >
      <div className="aspect-square relative overflow-hidden bg-[#080a10]">
        {avatar.thumbnail_url ? (
          <img src={avatar.thumbnail_url} alt={avatar.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-2xl font-black" style={{ background: "var(--gradient-primary)" }}>
              {avatar.name.charAt(0)}
            </div>
          </div>
        )}

        {/* Hover actions */}
        <div className="absolute inset-0 bg-black/55 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center gap-2">
          <button onClick={() => setShowInfo(true)} className="p-2.5 rounded-xl bg-white/15 text-white hover:bg-white/25 transition-colors">
            <Eye size={14} />
          </button>
          <button onClick={() => onDelete(avatar.id)} className="p-2.5 rounded-xl bg-red-500/80 text-white hover:bg-red-600 transition-colors">
            <Trash2 size={14} />
          </button>
        </div>

        <div className="absolute top-2.5 start-2.5"><StatusBadge status={avatar.status} /></div>
        {qualityPct != null && (
          <div className="absolute top-2.5 end-2.5 flex items-center gap-0.5 bg-black/65 backdrop-blur-sm px-2 py-1 rounded-lg">
            <Star size={9} className={qColor} fill="currentColor" />
            <span className={cn("text-[10px] font-bold", qColor)}>{qualityPct}</span>
          </div>
        )}
        {avatar.status === "processing" && (
          <div className="absolute bottom-0 inset-x-0 h-0.5 animate-pulse-slow" style={{ background: "var(--gradient-primary)" }} />
        )}
      </div>

      <div className="p-3.5">
        <h3 className="font-bold text-foreground text-sm truncate">{avatar.name}</h3>
        <div className="flex items-center gap-1.5 mt-1">
          {(avatar as any).source_type === "video" ? <Film size={10} className="text-muted-foreground" /> : <ImgIcon size={10} className="text-muted-foreground" />}
          <p className="text-xs text-muted-foreground capitalize">{(avatar as any).source_type || "photo"}</p>
        </div>
        {qualityPct != null && avatar.status === "ready" && (
          <div className="mt-2.5">
            <div className="h-1 bg-muted rounded-full overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${qualityPct}%`, background: qBg, transition: "width .8s ease" }} />
            </div>
          </div>
        )}
      </div>

      {/* Info overlay */}
      {showInfo && (
        <div className="absolute inset-0 bg-card/97 backdrop-blur-sm p-4 flex flex-col gap-2 z-10 animate-scale-in rounded-2xl">
          <div className="flex items-center justify-between mb-1">
            <p className="font-bold text-foreground text-xs">اطلاعات آواتار</p>
            <button onClick={() => setShowInfo(false)} className="p-1 rounded-lg hover:bg-accent text-muted-foreground"><X size={12} /></button>
          </div>
          {[
            { label: "کیفیت چهره", value: qualityPct != null ? `${qualityPct}%` : "—" },
            { label: "سن تخمینی",  value: (avatar.metadata as any)?.age ? `~${(avatar.metadata as any).age} سال` : "—" },
            { label: "جنسیت",      value: (avatar.metadata as any)?.gender || "—" },
            { label: "لندمارک",    value: (avatar.metadata as any)?.landmarks_count ?? "—" },
            { label: "استفاده",    value: `${avatar.usage_count ?? 0} بار` },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between text-[11px]">
              <span className="text-muted-foreground">{label}</span>
              <span className="font-semibold text-foreground">{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────────────────── */
export default function AvatarStudioPage() {
  const qc = useQueryClient();
  const [showUpload, setShowUpload] = useState(false);
  const [filter, setFilter] = useState<"all" | "ready" | "processing" | "failed">("all");

  const { data, isLoading } = useQuery({
    queryKey: ["avatars"],
    queryFn: () => api.get("/avatars").then(r => r.data),
    refetchInterval: 8000,
  });

  const createMutation = useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("name", name);
      form.append("source_type", file.type.startsWith("video") ? "video" : "photo");
      return api.post("/avatars", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["avatars"] }); setShowUpload(false); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/avatars/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["avatars"] }),
  });

  const all: Avatar[] = data?.items || [];
  const avatars = filter === "all" ? all : all.filter(a => a.status === filter);
  const stats = {
    total: all.length,
    ready: all.filter(a => a.status === "ready").length,
    processing: all.filter(a => a.status === "processing").length,
    failed: all.filter(a => a.status === "failed").length,
  };

  /* hero drop zone */
  const { getRootProps: heroProps } = useDropzone({ onDrop: () => setShowUpload(true), noClick: false });

  return (
    <div className="space-y-5 pb-4 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-start justify-between animate-fade-in-down">
        <div>
          <h1 className="text-2xl font-black text-foreground">استودیو آواتار</h1>
          <p className="text-muted-foreground text-sm mt-1">عکس یا ویدیو آپلود کنید و آواتار هوش مصنوعی بسازید</p>
        </div>
        <button onClick={() => setShowUpload(true)} className="btn-primary">
          <Plus size={15} /> آواتار جدید
        </button>
      </div>

      {/* Filter bar */}
      {!isLoading && all.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap animate-fade-in">
          {([
            { key: "all",        label: "همه",     val: stats.total,       cls: "text-foreground" },
            { key: "ready",      label: "آماده",   val: stats.ready,       cls: "text-emerald-500" },
            { key: "processing", label: "پردازش",  val: stats.processing,  cls: "text-amber-500" },
            { key: "failed",     label: "خطا",      val: stats.failed,      cls: "text-red-500" },
          ] as const).map(({ key, label, val, cls }) => (
            <button key={key} onClick={() => setFilter(key)}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-semibold transition-all",
                filter === key ? "border-primary bg-primary/8 text-primary" : "border-border bg-card text-muted-foreground hover:border-primary/40"
              )}
              style={{ boxShadow: "var(--shadow-xs)" }}>
              <span className={cn("font-black", filter === key ? "text-primary" : cls)}>{val}</span>
              {label}
            </button>
          ))}
        </div>
      )}

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSubmit={(name, file) => createMutation.mutate({ name, file })}
          isPending={createMutation.isPending}
        />
      )}

      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="rounded-2xl overflow-hidden">
              <div className="aspect-square skeleton" />
              <div className="p-3.5 space-y-2">
                <div className="h-3.5 skeleton rounded-lg w-3/4" />
                <div className="h-3 skeleton rounded-lg w-1/2" />
              </div>
            </div>
          ))}
        </div>
      ) : all.length === 0 ? (
        <div {...heroProps()}
          className="drop-zone p-16 flex flex-col items-center justify-center text-center animate-fade-in-up cursor-pointer">
          <div className="relative mb-6">
            <div className="w-28 h-28 rounded-3xl flex items-center justify-center"
              style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary-lg)" }}>
              <Users size={44} className="text-white" />
            </div>
            <div className="absolute -bottom-2 -end-2 w-10 h-10 rounded-xl flex items-center justify-center text-white"
              style={{ background: "var(--gradient-secondary)" }}>
              <Zap size={18} />
            </div>
          </div>
          <h3 className="text-xl font-black text-foreground mb-2">هنوز آواتاری ندارید</h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-xs leading-relaxed">
            عکس یا ویدیوی انسان آپلود کنید تا هوش مصنوعی چهره را تحلیل کند و آواتار بسازد
          </p>
          <button onClick={() => setShowUpload(true)} className="btn-primary text-base px-6 py-3">
            <Upload size={18} /> آپلود عکس
          </button>
          <p className="text-xs text-muted-foreground/50 mt-4">JPG · PNG · MP4 · MOV — حداکثر ۵۰۰ مگابایت</p>
        </div>
      ) : avatars.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">موردی با این فیلتر یافت نشد</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 stagger-children">
          {avatars.map((avatar, i) => (
            <div key={avatar.id} className="animate-fade-in-up" style={{ animationDelay: `${i * .04}s` }}>
              <AvatarCard avatar={avatar} onDelete={id => deleteMutation.mutate(id)} />
            </div>
          ))}
          <div className="animate-fade-in-up" style={{ animationDelay: `${avatars.length * .04}s` }}>
            <button onClick={() => setShowUpload(true)}
              className="w-full aspect-square rounded-2xl border-2 border-dashed border-border hover:border-primary/50 flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-primary transition-all hover:-translate-y-1"
              style={{ boxShadow: "var(--shadow-xs)" }}>
              <Plus size={22} />
              <span className="text-xs font-semibold">افزودن</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
