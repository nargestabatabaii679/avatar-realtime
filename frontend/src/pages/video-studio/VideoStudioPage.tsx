import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Play, Pause, Download, Trash2, Plus, Upload, Mic, Sparkles,
  ChevronDown, X, CheckCircle, AlertCircle, Clock, Volume2,
  Maximize2, RotateCcw, Film, Image as ImageIcon, Zap, Settings2,
} from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";
import { useThemeStore } from "../../stores/themeStore";
import type { Avatar, VoiceModel, Video } from "../../types";

/* ── Constants ─────────────────────────────────────────────── */
const LANGUAGES = [
  { code: "fa", label: "فارسی", flag: "🇮🇷" },
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "ar", label: "العربية", flag: "🇸🇦" },
  { code: "tr", label: "Türkçe", flag: "🇹🇷" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
];

const RESOLUTIONS = ["720p", "1080p", "4k"] as const;

const PIPELINE_STEPS = [
  { id: "downloading_assets", label: "بارگذاری دارایی‌ها", labelEn: "Loading assets", pct: [0, 15] },
  { id: "tts_synthesis",      label: "ساخت صدا",          labelEn: "Synthesizing voice", pct: [15, 42] },
  { id: "lip_sync_started",   label: "همگام‌سازی لب",      labelEn: "Lip syncing", pct: [42, 72] },
  { id: "rendering",          label: "رندر ویدیو",          labelEn: "Rendering video", pct: [72, 92] },
  { id: "uploading",          label: "آپلود",               labelEn: "Uploading", pct: [92, 100] },
];

/* ── Helpers ────────────────────────────────────────────────── */
function fmtDuration(s?: number) {
  if (!s) return "--:--";
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function stepLabel(stepId: string, isFa: boolean) {
  const s = PIPELINE_STEPS.find((p) => p.id === stepId);
  if (!s) return stepId;
  return isFa ? s.label : s.labelEn;
}

/* ── Avatar Quick-Upload Modal ──────────────────────────────── */
function AvatarUploadModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const onDrop = useCallback((f: File[]) => f[0] && setFile(f[0]), []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"], "video/*": [".mp4", ".mov"] },
    maxFiles: 1,
  });

  const mutation = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("file", file!);
      form.append("name", name || file!.name.replace(/\.[^.]+$/, ""));
      form.append("source_type", file!.type.startsWith("video") ? "video" : "photo");
      return api.post("/avatars", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: (res) => onCreated(res.data.id),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-md" onClick={onClose} />
      <div className="relative w-full max-w-md bg-card border border-border rounded-2xl p-6 shadow-2xl animate-scale-in">
        <button onClick={onClose} className="absolute top-4 end-4 p-1.5 rounded-lg hover:bg-accent text-muted-foreground">
          <X size={16} />
        </button>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
            <Upload size={18} className="text-white" />
          </div>
          <div>
            <h2 className="font-bold text-foreground">آواتار جدید</h2>
            <p className="text-xs text-muted-foreground">عکس یا ویدیو آپلود کنید</p>
          </div>
        </div>

        <div {...getRootProps()} className={cn("drop-zone p-8 text-center cursor-pointer mb-4", isDragActive && "drop-zone-active")}>
          <input {...getInputProps()} />
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <div className="w-16 h-16 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                {file.type.startsWith("video") ? <Film size={28} className="text-emerald-500" /> : <ImageIcon size={28} className="text-emerald-500" />}
              </div>
              <p className="text-sm font-medium text-foreground">{file.name}</p>
              <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <div className="w-14 h-14 rounded-xl bg-primary/10 flex items-center justify-center mb-1">
                <Upload size={24} className="text-primary" />
              </div>
              <p className="text-sm font-semibold text-foreground">عکس یا ویدیو را اینجا بکشید</p>
              <p className="text-xs text-muted-foreground">JPG، PNG، MP4، MOV — حداکثر ۵۰۰ مگابایت</p>
            </div>
          )}
        </div>

        {file && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="نام آواتار (اختیاری)"
            className="input-field mb-4 text-sm"
            dir="rtl"
          />
        )}

        <div className="flex gap-3">
          <button onClick={onClose} className="btn-secondary flex-1 text-sm">انصراف</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!file || mutation.isPending}
            className="btn-primary flex-1 text-sm"
          >
            {mutation.isPending ? <><span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> در حال پردازش…</> : <><Sparkles size={14} /> ساخت آواتار</>}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Video Player ───────────────────────────────────────────── */
function VideoPlayer({ url, thumbnail }: { url: string; thumbnail?: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);

  const toggle = () => {
    if (!ref.current) return;
    if (playing) { ref.current.pause(); setPlaying(false); }
    else { ref.current.play(); setPlaying(true); }
  };

  return (
    <div className="relative w-full h-full bg-black rounded-2xl overflow-hidden group">
      <video
        ref={ref}
        src={url}
        poster={thumbnail}
        className="w-full h-full object-contain"
        onTimeUpdate={() => ref.current && setProgress(ref.current.currentTime / (ref.current.duration || 1) * 100)}
        onLoadedMetadata={() => ref.current && setDuration(ref.current.duration)}
        onEnded={() => setPlaying(false)}
      />
      {/* Controls overlay */}
      <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        {/* Progress bar */}
        <div className="px-4 pb-2">
          <div className="h-1 bg-white/20 rounded-full cursor-pointer"
            onClick={(e) => {
              if (!ref.current) return;
              const rect = e.currentTarget.getBoundingClientRect();
              ref.current.currentTime = ((e.clientX - rect.left) / rect.width) * duration;
            }}>
            <div className="h-full rounded-full bg-white transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <div className="flex items-center gap-3 px-4 pb-4">
          <button onClick={toggle} className="p-2 rounded-full bg-white/20 hover:bg-white/30 text-white transition-colors">
            {playing ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <span className="text-white text-xs">{fmtDuration(ref.current?.currentTime)} / {fmtDuration(duration)}</span>
          <div className="ms-auto flex items-center gap-2">
            <Volume2 size={14} className="text-white/80" />
            <button onClick={() => ref.current?.requestFullscreen()} className="p-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white">
              <Maximize2 size={14} />
            </button>
          </div>
        </div>
      </div>
      {/* Big play button when paused */}
      {!playing && (
        <button onClick={toggle} className="absolute inset-0 flex items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center hover:bg-white/30 transition-colors">
            <Play size={28} className="text-white ms-1" />
          </div>
        </button>
      )}
    </div>
  );
}

/* ── Progress Overlay ───────────────────────────────────────── */
function GeneratingOverlay({ progress, step, isFa }: { progress: number; step: string; isFa: boolean }) {
  const activeStepIdx = PIPELINE_STEPS.findIndex((s) => s.id === step);

  return (
    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm rounded-2xl">
      {/* Animated avatar silhouette */}
      <div className="relative mb-6">
        <div className="w-24 h-24 rounded-full border-4 border-primary/30 border-t-primary animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <Sparkles size={28} className="text-primary" />
        </div>
      </div>

      <p className="text-white font-semibold text-lg mb-1">
        {isFa ? "در حال ساخت ویدیو…" : "Generating video…"}
      </p>
      <p className="text-white/70 text-sm mb-6">{stepLabel(step, isFa)}</p>

      {/* Progress bar */}
      <div className="w-64 h-2 bg-white/20 rounded-full overflow-hidden mb-4">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${progress}%`, background: "var(--gradient-primary)" }}
        />
      </div>
      <p className="text-white/60 text-xs">{progress}%</p>

      {/* Steps */}
      <div className="flex gap-2 mt-5">
        {PIPELINE_STEPS.map((s, i) => (
          <div
            key={s.id}
            className={cn(
              "w-2 h-2 rounded-full transition-all",
              i < activeStepIdx ? "bg-emerald-400" :
              i === activeStepIdx ? "bg-primary scale-125" :
              "bg-white/20"
            )}
          />
        ))}
      </div>
    </div>
  );
}

/* ── Avatar Selector Panel ──────────────────────────────────── */
function AvatarPanel({
  avatars, selected, onSelect, onAddNew, isLoading,
}: {
  avatars: Avatar[];
  selected: string | null;
  onSelect: (id: string) => void;
  onAddNew: () => void;
  isLoading: boolean;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">آواتار</p>
        <button onClick={onAddNew} className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary transition-colors">
          <Plus size={14} />
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-2">
          {[...Array(4)].map((_, i) => <div key={i} className="aspect-square skeleton rounded-xl" />)}
        </div>
      ) : avatars.length === 0 ? (
        <button
          onClick={onAddNew}
          className="flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed border-border hover:border-primary/50 text-muted-foreground hover:text-primary transition-all"
        >
          <Upload size={20} />
          <span className="text-xs text-center">آپلود عکس<br />یا ویدیو</span>
        </button>
      ) : (
        <div className="grid grid-cols-2 gap-2 overflow-y-auto flex-1 scrollbar-thin">
          {avatars.map((a) => (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={cn(
                "relative aspect-square rounded-xl overflow-hidden border-2 transition-all",
                selected === a.id
                  ? "border-primary ring-2 ring-primary/30 scale-95"
                  : "border-border hover:border-primary/40"
              )}
            >
              {a.thumbnail_url ? (
                <img src={a.thumbnail_url} alt={a.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-muted text-lg font-bold text-muted-foreground">
                  {a.name.charAt(0)}
                </div>
              )}
              {selected === a.id && (
                <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                  <CheckCircle size={18} className="text-white drop-shadow" />
                </div>
              )}
              <div className="absolute bottom-0 inset-x-0 bg-black/60 px-1.5 py-1">
                <p className="text-white text-[10px] truncate">{a.name}</p>
              </div>
            </button>
          ))}
          {/* Add new button */}
          <button
            onClick={onAddNew}
            className="aspect-square rounded-xl border-2 border-dashed border-border hover:border-primary/50 flex items-center justify-center text-muted-foreground hover:text-primary transition-all"
          >
            <Plus size={18} />
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Voice Selector ─────────────────────────────────────────── */
function VoiceSelector({
  voices, selected, onSelect, language, onLangChange, isFa,
}: {
  voices: VoiceModel[];
  selected: string | null;
  onSelect: (id: string) => void;
  language: string;
  onLangChange: (l: string) => void;
  isFa: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selectedVoice = voices.find((v) => v.id === selected);
  const lang = LANGUAGES.find((l) => l.code === language);

  return (
    <div className="space-y-3">
      {/* Language */}
      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5">زبان</label>
        <div className="flex flex-wrap gap-1.5">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              onClick={() => onLangChange(l.code)}
              className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-lg text-xs border transition-all",
                language === l.code
                  ? "border-primary bg-primary/10 text-primary font-medium"
                  : "border-border text-muted-foreground hover:border-primary/40"
              )}
            >
              <span>{l.flag}</span>
              <span>{l.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Voice picker */}
      <div>
        <label className="block text-xs font-medium text-muted-foreground mb-1.5">صدا</label>
        <div className="relative">
          <button
            onClick={() => setOpen(!open)}
            className="w-full flex items-center gap-2 p-2.5 rounded-xl border border-border bg-muted hover:border-primary/50 transition-colors text-sm"
          >
            {selectedVoice ? (
              <>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0"
                  style={{ background: "var(--gradient-primary)" }}>
                  {selectedVoice.name.charAt(0)}
                </div>
                <div className="flex-1 text-start min-w-0">
                  <p className="text-foreground text-xs font-medium truncate">{selectedVoice.name}</p>
                  <p className="text-muted-foreground text-[10px]">{selectedVoice.language?.toUpperCase()}</p>
                </div>
              </>
            ) : (
              <><Mic size={14} className="text-muted-foreground" /><span className="text-muted-foreground">انتخاب صدا</span></>
            )}
            <ChevronDown size={14} className={cn("text-muted-foreground ms-auto transition-transform", open && "rotate-180")} />
          </button>

          {open && (
            <div className="absolute top-full mt-1 inset-x-0 z-20 bg-card border border-border rounded-xl shadow-xl max-h-48 overflow-y-auto scrollbar-thin">
              {voices.length === 0 ? (
                <p className="text-xs text-muted-foreground p-3 text-center">هنوز صدایی ندارید</p>
              ) : voices.map((v) => (
                <button
                  key={v.id}
                  onClick={() => { onSelect(v.id); setOpen(false); }}
                  className={cn(
                    "w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-accent text-start transition-colors",
                    v.id === selected && "bg-primary/5"
                  )}
                >
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0"
                    style={{ background: "var(--gradient-primary)" }}>
                    {v.name.charAt(0)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-foreground truncate">{v.name}</p>
                    <p className="text-[10px] text-muted-foreground">{v.language?.toUpperCase()}</p>
                  </div>
                  {v.id === selected && <CheckCircle size={12} className="text-primary shrink-0" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Recent Videos Strip ────────────────────────────────────── */
function VideoLibrary({
  videos, generatingId, onDelete, onPreview,
}: {
  videos: Video[];
  generatingId: string | null;
  onDelete: (id: string) => void;
  onPreview: (v: Video) => void;
}) {
  if (videos.length === 0) return null;

  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">ویدیوهای اخیر</p>
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
        {videos.map((v: any) => {
          const isGenerating = v.id === generatingId && v.status !== "completed" && v.status !== "failed";
          return (
            <div
              key={v.id}
              className="shrink-0 w-44 bg-card border border-border rounded-xl overflow-hidden hover:border-primary/30 transition-all group"
            >
              {/* Thumbnail */}
              <div className="relative w-full h-24 bg-muted cursor-pointer" onClick={() => v.status === "completed" && onPreview(v)}>
                {v.thumbnail_url ? (
                  <img src={v.thumbnail_url} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Film size={20} className="text-muted-foreground" />
                  </div>
                )}
                {isGenerating && (
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                    <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  </div>
                )}
                {v.status === "completed" && (
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <Play size={20} className="text-white" />
                  </div>
                )}
                {/* Status pill */}
                <div className="absolute top-1.5 start-1.5">
                  {v.status === "completed" && <span className="badge badge-success text-[9px]"><CheckCircle size={8} />آماده</span>}
                  {v.status === "failed" && <span className="badge badge-danger text-[9px]"><AlertCircle size={8} />خطا</span>}
                  {isGenerating && <span className="badge badge-warning text-[9px]"><Clock size={8} />در حال ساخت</span>}
                </div>
              </div>
              {/* Info */}
              <div className="p-2.5 flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-foreground truncate">{v.title || "بدون عنوان"}</p>
                  {isGenerating && v.progress != null && (
                    <div className="mt-1 h-1 bg-muted-foreground/20 rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${v.progress}%` }} />
                    </div>
                  )}
                  {!isGenerating && <p className="text-[10px] text-muted-foreground">{v.resolution} • {fmtDuration(v.duration_seconds)}</p>}
                </div>
                <div className="flex items-center gap-0.5">
                  {v.status === "completed" && (
                    <a href={`/api/v1/videos/${v.id}/download`} target="_blank"
                      className="p-1 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary transition-colors" rel="noreferrer">
                      <Download size={12} />
                    </a>
                  )}
                  <button onClick={() => onDelete(v.id)}
                    className="p-1 rounded-lg hover:bg-accent text-muted-foreground hover:text-red-500 transition-colors">
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Main Studio Page ───────────────────────────────────────── */
export default function VideoStudioPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { language: uiLang } = useThemeStore();
  const isFa = uiLang === "fa";
  const isRTL = ["fa", "ar"].includes(uiLang);

  // State
  const [selectedAvatarId, setSelectedAvatarId] = useState<string | null>(null);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
  const [script, setScript] = useState("");
  const [resolution, setResolution] = useState<string>("1080p");
  const [language, setLanguage] = useState(isFa ? "fa" : "en");
  const [title, setTitle] = useState("");
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [genProgress, setGenProgress] = useState(0);
  const [genStep, setGenStep] = useState("downloading_assets");
  const [showAvatarUpload, setShowAvatarUpload] = useState(false);
  const [previewVideo, setPreviewVideo] = useState<Video | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  // Queries
  const { data: avatarsData, isLoading: avatarsLoading } = useQuery({
    queryKey: ["avatars"],
    queryFn: () => api.get("/avatars?status=ready&limit=20").then((r) => r.data),
    refetchInterval: 8000,
  });

  const { data: voicesData } = useQuery({
    queryKey: ["voices"],
    queryFn: () => api.get("/voices?status=ready&limit=30").then((r) => r.data),
  });

  const { data: videosData } = useQuery({
    queryKey: ["videos"],
    queryFn: () => api.get("/videos?limit=20").then((r) => r.data),
    refetchInterval: generatingId ? 3000 : 15000,
  });

  // Poll video progress
  const { data: progressData } = useQuery({
    queryKey: ["video-progress", generatingId],
    queryFn: () => api.get(`/videos/${generatingId}/status`).then((r) => r.data),
    enabled: !!generatingId,
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (!progressData) return;
    const { progress, current_step, status } = progressData;
    if (progress != null) setGenProgress(progress);
    if (current_step) setGenStep(current_step);
    if (status === "completed" || status === "failed") {
      setGeneratingId(null);
      qc.invalidateQueries({ queryKey: ["videos"] });
      if (status === "completed") {
        // Auto-preview
        const found = videosData?.items?.find((v: any) => v.id === generatingId);
        if (found) setPreviewVideo(found);
      }
    }
  }, [progressData]);

  // Mutations
  const generateMutation = useMutation({
    mutationFn: () =>
      api.post("/videos/generate", {
        avatar_id: selectedAvatarId,
        voice_model_id: selectedVoiceId,
        script,
        language,
        resolution,
        title: title.trim() || "ویدیو جدید",
      }),
    onSuccess: (res) => {
      setGeneratingId(res.data.video_id);
      setGenProgress(0);
      setGenStep("downloading_assets");
      qc.invalidateQueries({ queryKey: ["videos"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/videos/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["videos"] }),
  });

  const avatars: Avatar[] = avatarsData?.items || [];
  const voices: VoiceModel[] = voicesData?.items || [];
  const videos: Video[] = videosData?.items || [];
  const selectedAvatar = avatars.find((a) => a.id === selectedAvatarId);
  const isGenerating = !!generatingId;
  const canGenerate = !!selectedAvatarId && !!selectedVoiceId && script.trim().length > 5 && !isGenerating;

  const scriptWordCount = script.trim() ? script.trim().split(/\s+/).length : 0;
  const estimatedDuration = Math.round(scriptWordCount / (language === "fa" ? 2.8 : 2.5));

  return (
    <div className="flex flex-col gap-4 animate-fade-in pb-4">
      {/* ── Header ── */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <h1 className="text-xl font-bold text-foreground">استودیو ویدیو</h1>
          <p className="text-xs text-muted-foreground mt-0.5">عکس انسان → آواتار سخن‌گو</p>
        </div>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="عنوان ویدیو…"
          className="input-field text-sm w-48"
          dir="rtl"
        />
        <div className="flex items-center gap-1 p-1 bg-muted rounded-xl border border-border">
          {RESOLUTIONS.map((r) => (
            <button
              key={r}
              onClick={() => setResolution(r)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                resolution === r ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {r}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={cn("p-2 rounded-xl border transition-all", showSettings ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:border-primary/40")}
        >
          <Settings2 size={16} />
        </button>
      </div>

      {/* ── Main Area ── */}
      <div className="grid grid-cols-[200px_1fr_260px] gap-4" style={{ minHeight: "540px" }}>

        {/* LEFT: Avatar Panel */}
        <div className="bg-card border border-border rounded-2xl p-4 flex flex-col" style={{ boxShadow: "var(--shadow-sm)", minHeight: "540px" }}>
          <AvatarPanel
            avatars={avatars}
            selected={selectedAvatarId}
            onSelect={setSelectedAvatarId}
            onAddNew={() => setShowAvatarUpload(true)}
            isLoading={avatarsLoading}
          />
        </div>

        {/* CENTER: Preview + Script */}
        <div className="flex flex-col gap-4">
          {/* Preview Frame */}
          <div
            className="relative rounded-2xl overflow-hidden bg-[#0a0a0a] border border-border"
            style={{ boxShadow: "var(--shadow-lg)", height: "360px" }}
          >
            {/* Completed video player */}
            {previewVideo?.output_url ? (
              <VideoPlayer
                url={`/api/v1/videos/${previewVideo.id}/stream`}
                thumbnail={previewVideo.thumbnail_url}
              />
            ) : selectedAvatar?.thumbnail_url ? (
              /* Avatar preview */
              <div className="w-full h-full flex items-center justify-center">
                <div className="relative">
                  <img
                    src={selectedAvatar.thumbnail_url}
                    alt={selectedAvatar.name}
                    className="h-full max-h-72 w-auto object-contain rounded-xl"
                    style={{ filter: isGenerating ? "brightness(0.4)" : undefined }}
                  />
                  {/* Quality score */}
                  {selectedAvatar.metadata?.quality_score != null && (
                    <div className="absolute top-2 end-2 flex items-center gap-1 bg-black/60 backdrop-blur-sm px-2 py-1 rounded-lg">
                      <Zap size={10} className="text-yellow-400" />
                      <span className="text-yellow-400 text-[10px] font-bold">
                        {Math.round((selectedAvatar.metadata.quality_score as number) * 100)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              /* Empty state */
              <div className="w-full h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
                <div className="w-20 h-20 rounded-2xl bg-muted flex items-center justify-center">
                  <ImageIcon size={32} className="opacity-30" />
                </div>
                <p className="text-sm font-medium">یک آواتار انتخاب کنید</p>
                <p className="text-xs opacity-60">یا عکس جدید آپلود کنید</p>
                <button onClick={() => setShowAvatarUpload(true)} className="btn-primary text-xs mt-1">
                  <Upload size={12} /> آپلود عکس
                </button>
              </div>
            )}

            {/* Generating overlay */}
            {isGenerating && (
              <GeneratingOverlay progress={genProgress} step={genStep} isFa={isFa} />
            )}

            {/* Top-right controls when video is shown */}
            {previewVideo && (
              <div className="absolute top-3 end-3 flex gap-2">
                <button
                  onClick={() => setPreviewVideo(null)}
                  className="p-1.5 rounded-lg bg-black/50 backdrop-blur-sm text-white hover:bg-black/70 transition-colors"
                >
                  <RotateCcw size={13} />
                </button>
              </div>
            )}
          </div>

          {/* Script Editor */}
          <div className="bg-card border border-border rounded-2xl p-4 flex-shrink-0" style={{ boxShadow: "var(--shadow-sm)" }}>
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">متن گفتار</label>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>{scriptWordCount} کلمه</span>
                <span>~{estimatedDuration} ثانیه</span>
                <span>{script.length} کاراکتر</span>
              </div>
            </div>
            <textarea
              value={script}
              onChange={(e) => setScript(e.target.value)}
              dir={isRTL ? "rtl" : "ltr"}
              placeholder={isRTL ? "متن گفتار آواتار را اینجا بنویسید…\n\nمثال: سلام، من یک آواتار هوش مصنوعی هستم. می‌توانم به فارسی با شما صحبت کنم." : "Write the script for your avatar to speak…"}
              className="w-full h-28 px-3 py-2.5 bg-muted border border-border rounded-xl text-foreground text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary placeholder:text-muted-foreground/50 leading-relaxed"
              maxLength={5000}
            />
          </div>
        </div>

        {/* RIGHT: Voice + Settings + Generate */}
        <div className="bg-card border border-border rounded-2xl p-4 flex flex-col gap-4" style={{ boxShadow: "var(--shadow-sm)" }}>
          <VoiceSelector
            voices={voices}
            selected={selectedVoiceId}
            onSelect={setSelectedVoiceId}
            language={language}
            onLangChange={setLanguage}
            isFa={isFa}
          />

          {/* Advanced settings */}
          {showSettings && (
            <div className="space-y-3 p-3 bg-muted rounded-xl border border-border text-xs">
              <p className="font-semibold text-foreground">تنظیمات پیشرفته</p>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">لیپ‌سینک فوق‌طبیعی</span>
                <span className="badge badge-success">فعال</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">پلک زدن</span>
                <span className="badge badge-success">فعال</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">میکروحالت‌ها</span>
                <span className="badge badge-success">فعال</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">خروجی ۵۰fps</span>
                <span className="badge badge-success">فعال</span>
              </div>
            </div>
          )}

          <div className="mt-auto space-y-3">
            {/* Validation hints */}
            {!selectedAvatarId && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <AlertCircle size={13} className="text-amber-500 shrink-0" />
                <p className="text-[11px] text-amber-600 dark:text-amber-400">یک آواتار انتخاب کنید</p>
              </div>
            )}
            {selectedAvatarId && !selectedVoiceId && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <AlertCircle size={13} className="text-amber-500 shrink-0" />
                <p className="text-[11px] text-amber-600 dark:text-amber-400">یک صدا انتخاب کنید</p>
              </div>
            )}
            {selectedAvatarId && selectedVoiceId && script.trim().length < 5 && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <AlertCircle size={13} className="text-amber-500 shrink-0" />
                <p className="text-[11px] text-amber-600 dark:text-amber-400">متن گفتار را بنویسید</p>
              </div>
            )}

            {/* Generate button */}
            <button
              onClick={() => generateMutation.mutate()}
              disabled={!canGenerate || generateMutation.isPending}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-semibold text-sm transition-all duration-300",
                canGenerate
                  ? "text-white hover:opacity-90 hover:-translate-y-0.5 active:translate-y-0 shadow-lg"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
              style={canGenerate ? { background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" } : {}}
            >
              {generateMutation.isPending || isGenerating ? (
                <><div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />در حال ساخت…</>
              ) : (
                <><Sparkles size={16} />ساخت ویدیو</>
              )}
            </button>

            {isGenerating && (
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground">{genProgress}% • {stepLabel(genStep, isFa)}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Recent Videos ── */}
      <div>
        <VideoLibrary
          videos={videos}
          generatingId={generatingId}
          onDelete={(id) => deleteMutation.mutate(id)}
          onPreview={(v) => setPreviewVideo(v as any)}
        />
      </div>

      {/* ── Modals ── */}
      {showAvatarUpload && (
        <AvatarUploadModal
          onClose={() => setShowAvatarUpload(false)}
          onCreated={(id) => {
            setShowAvatarUpload(false);
            qc.invalidateQueries({ queryKey: ["avatars"] });
            setSelectedAvatarId(id);
          }}
        />
      )}
    </div>
  );
}
