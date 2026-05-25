import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Play, Pause, Download, Trash2, Plus, Upload, Sparkles, ChevronDown,
  X, CheckCircle, AlertCircle, Clock, Volume2, Maximize2, RotateCcw,
  Film, Image as ImgIcon, Zap, Mic, Languages, Gauge, Star,
} from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";
import { useThemeStore } from "../../stores/themeStore";
import type { Avatar, VoiceModel, Video } from "../../types";

/* ─── Constants ────────────────────────────────────────────── */
const LANG_LIST = [
  { code: "fa", label: "فارسی",    flag: "🇮🇷", dir: "rtl" },
  { code: "en", label: "English",  flag: "🇺🇸", dir: "ltr" },
  { code: "ar", label: "العربية", flag: "🇸🇦", dir: "rtl" },
  { code: "tr", label: "Türkçe",  flag: "🇹🇷", dir: "ltr" },
  { code: "fr", label: "Français", flag: "🇫🇷", dir: "ltr" },
  { code: "de", label: "Deutsch",  flag: "🇩🇪", dir: "ltr" },
];
const RESOLUTIONS = ["720p", "1080p", "4k"] as const;
const PIPELINE = [
  { id: "downloading_assets", fa: "بارگذاری",    en: "Loading",    range:[0,15]  },
  { id: "tts_synthesis",      fa: "ساخت صدا",    en: "Voice TTS",  range:[15,42] },
  { id: "lip_sync_started",   fa: "لیپ‌سینک",    en: "Lip sync",   range:[42,72] },
  { id: "rendering",          fa: "رندر",         en: "Rendering",  range:[72,92] },
  { id: "uploading",          fa: "آپلود",        en: "Upload",     range:[92,100]},
];

const scriptPlaceholders: Record<string, string> = {
  fa: "متن گفتار آواتار را اینجا بنویسید…\n\nمثال: سلام، من یک دستیار هوش مصنوعی هستم و می‌توانم به شما در هر سوالی کمک کنم.",
  en: "Write what your avatar will say…\n\nExample: Hello, I'm an AI avatar. I can help answer your questions.",
  ar: "اكتب نص المتحدث هنا…",
  tr: "Avatar ne söyleyecek, buraya yazın…",
  fr: "Écrivez ce que dira votre avatar…",
  de: "Schreiben Sie, was Ihr Avatar sagen soll…",
};

/* ─── Helpers ───────────────────────────────────────────────── */
const fmtSec = (s?: number) => {
  if (!s) return "0:00";
  return `${Math.floor(s / 60)}:${(s % 60 | 0).toString().padStart(2, "0")}`;
};
const wordsPerSec: Record<string, number> = { fa: 2.6, ar: 2.8, en: 2.3, tr: 2.5, fr: 2.2, de: 2.1 };
const estimateDuration = (text: string, lang: string) => {
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  return Math.round(words / (wordsPerSec[lang] ?? 2.3));
};

/* ─── Audio Waveform ────────────────────────────────────────── */
function Waveform() {
  return (
    <div className="wave-container">
      {Array.from({ length: 10 }).map((_, i) => <div key={i} className="wave-bar" />)}
    </div>
  );
}

/* ─── Avatar Upload Modal ───────────────────────────────────── */
function UploadAvatarModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const onDrop = useCallback((f: File[]) => f[0] && setFile(f[0]), []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"], "video/*": [".mp4", ".mov"] },
    maxFiles: 1,
  });

  const mut = useMutation({
    mutationFn: () => {
      const f = new FormData();
      f.append("file", file!);
      f.append("name", name.trim() || file!.name.replace(/\.[^.]+$/, ""));
      f.append("source_type", file!.type.startsWith("video") ? "video" : "photo");
      return api.post("/avatars", f, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: (r) => onCreated(r.data.id),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/75 backdrop-blur-lg" onClick={onClose} />
      <div className="relative w-full max-w-md bg-card border border-border rounded-2xl p-6 shadow-2xl animate-scale-in">
        <button onClick={onClose} className="absolute top-4 end-4 btn-icon p-1.5">
          <X size={16} />
        </button>
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: "var(--gradient-primary)" }}>
            <Upload size={17} className="text-white" />
          </div>
          <div>
            <h2 className="font-bold text-foreground text-base">آواتار جدید</h2>
            <p className="text-xs text-muted-foreground">عکس یا ویدیو آپلود کنید</p>
          </div>
        </div>

        <div {...getRootProps()} className={cn("drop-zone p-10 text-center cursor-pointer mb-4", isDragActive && "drop-zone-active")}>
          <input {...getInputProps()} />
          {file ? (
            <div className="flex flex-col items-center gap-2.5">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
                {file.type.startsWith("video") ? <Film size={28} className="text-emerald-500" /> : <ImgIcon size={28} className="text-emerald-500" />}
              </div>
              <p className="text-sm font-semibold text-foreground">{file.name}</p>
              <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(1)} MB — کلیک برای تغییر</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2.5">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-1">
                <Upload size={26} className="text-primary" />
              </div>
              <p className="text-sm font-bold text-foreground">عکس یا ویدیو را اینجا بکشید</p>
              <p className="text-xs text-muted-foreground">JPG · PNG · MP4 · MOV — حداکثر ۵۰۰ مگابایت</p>
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
          <button onClick={onClose} className="btn-secondary flex-1">انصراف</button>
          <button
            onClick={() => mut.mutate()}
            disabled={!file || mut.isPending}
            className="btn-primary flex-1"
          >
            {mut.isPending
              ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> پردازش…</>
              : <><Sparkles size={14} /> ساخت آواتار</>}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Custom Video Player ───────────────────────────────────── */
function StudioPlayer({ videoId, thumbnail }: { videoId: string; thumbnail?: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [vol, setVol] = useState(true);

  const toggle = () => {
    if (!ref.current) return;
    if (playing) { ref.current.pause(); setPlaying(false); }
    else { ref.current.play().then(() => setPlaying(true)); }
  };
  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const r = e.currentTarget.getBoundingClientRect();
    ref.current.currentTime = ((e.clientX - r.left) / r.width) * duration;
  };

  return (
    <div className="relative w-full h-full bg-black group">
      <video
        ref={ref}
        src={`/api/v1/videos/${videoId}/stream`}
        poster={thumbnail}
        className="w-full h-full object-contain"
        onTimeUpdate={() => ref.current && setProgress(ref.current.currentTime / (ref.current.duration || 1) * 100)}
        onLoadedMetadata={() => ref.current && setDuration(ref.current.duration)}
        onEnded={() => setPlaying(false)}
        onClick={toggle}
      />
      {/* Controls */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <div className="h-1 bg-white/20 rounded-full mb-3 cursor-pointer" onClick={seek}>
          <div className="h-full bg-white rounded-full" style={{ width: `${progress}%` }} />
        </div>
        <div className="flex items-center gap-3">
          <button onClick={toggle} className="w-8 h-8 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center text-white transition-colors">
            {playing ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <span className="text-white/80 text-xs tabular-nums">{fmtSec(ref.current?.currentTime)} / {fmtSec(duration)}</span>
          <button onClick={() => { if (ref.current) { ref.current.muted = vol; setVol(!vol); } }}
            className="ms-auto text-white/70 hover:text-white transition-colors">
            <Volume2 size={14} className={vol ? "" : "opacity-30"} />
          </button>
          <button onClick={() => ref.current?.requestFullscreen()} className="text-white/70 hover:text-white transition-colors">
            <Maximize2 size={14} />
          </button>
        </div>
      </div>
      {/* Big play */}
      {!playing && (
        <button onClick={toggle} className="absolute inset-0 flex items-center justify-center">
          <div className="w-16 h-16 rounded-full bg-white/15 backdrop-blur-sm flex items-center justify-center hover:bg-white/25 transition-colors">
            <Play size={26} className="text-white ms-1" />
          </div>
        </button>
      )}
    </div>
  );
}

/* ─── Generating Overlay ────────────────────────────────────── */
function GenOverlay({ progress, step, isFa }: { progress: number; step: string; isFa: boolean }) {
  const s = PIPELINE.find((p) => p.id === step);
  const stepIdx = PIPELINE.findIndex((p) => p.id === step);
  const label = s ? (isFa ? s.fa : s.en) : step;

  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm rounded-2xl">
      {/* Rings */}
      <div className="relative flex items-center justify-center mb-6">
        <div className="absolute w-32 h-32 ring-pulse-outer" />
        <div className="absolute w-24 h-24 ring-pulse-inner" />
        <div className="relative w-16 h-16 rounded-full flex items-center justify-center"
          style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary-lg)" }}>
          <Sparkles size={24} className="text-white" />
        </div>
      </div>

      <p className="text-white font-bold text-lg mb-1">{isFa ? "در حال ساخت ویدیو" : "Creating your video"}</p>

      {/* Waveform */}
      <div className="my-2">
        <Waveform />
      </div>

      <p className="text-white/60 text-sm mb-5">{label}…</p>

      {/* Progress */}
      <div className="w-56 h-1.5 bg-white/15 rounded-full overflow-hidden mb-2">
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${progress}%`, background: "var(--gradient-primary)" }} />
      </div>
      <p className="text-white/40 text-xs">{progress}%</p>

      {/* Step dots */}
      <div className="flex items-center gap-2 mt-4">
        {PIPELINE.map((p, i) => (
          <div key={p.id} className={cn(
            "transition-all duration-300",
            i < stepIdx ? "w-2 h-2 rounded-full bg-emerald-400" :
            i === stepIdx ? "w-5 h-2 rounded-full bg-primary" :
            "w-2 h-2 rounded-full bg-white/20"
          )} />
        ))}
      </div>
    </div>
  );
}

/* ─── Avatar Card (gallery) ─────────────────────────────────── */
function AvatarThumb({ avatar, selected, onClick }: { avatar: Avatar; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative aspect-square rounded-xl overflow-hidden border-2 transition-all duration-200 group",
        selected
          ? "border-primary ring-2 ring-primary/30 scale-[0.96]"
          : "border-transparent hover:border-primary/40 hover:scale-[1.02]"
      )}
    >
      {avatar.thumbnail_url ? (
        <img src={avatar.thumbnail_url} alt={avatar.name} className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full bg-muted flex items-center justify-center text-xl font-bold text-muted-foreground">
          {avatar.name.charAt(0)}
        </div>
      )}
      {/* Selected check */}
      {selected && (
        <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
          <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
            <CheckCircle size={14} className="text-white" />
          </div>
        </div>
      )}
      {/* Quality badge */}
      {avatar.metadata?.quality_score != null && !selected && (
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="flex items-center gap-0.5 justify-center">
            <Star size={8} className="text-yellow-400" fill="currentColor" />
            <span className="text-yellow-300 text-[9px] font-bold">{Math.round((avatar.metadata.quality_score as number) * 100)}</span>
          </div>
        </div>
      )}
      {/* Name on hover */}
      <div className="absolute top-0 inset-x-0 bg-gradient-to-b from-black/60 to-transparent p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
        <p className="text-white text-[9px] font-medium truncate text-center">{avatar.name}</p>
      </div>
    </button>
  );
}

/* ─── Voice Picker ──────────────────────────────────────────── */
function VoicePicker({ voices, selected, onSelect }: { voices: VoiceModel[]; selected: string | null; onSelect: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const chosen = voices.find((v) => v.id === selected);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-border bg-muted hover:border-primary/50 transition-all text-sm"
      >
        {chosen ? (
          <>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0"
              style={{ background: "var(--gradient-primary)" }}>
              {chosen.name.charAt(0)}
            </div>
            <div className="flex-1 text-start min-w-0">
              <p className="text-foreground text-xs font-semibold truncate">{chosen.name}</p>
              <p className="text-muted-foreground text-[10px]">{chosen.language?.toUpperCase()}</p>
            </div>
          </>
        ) : (
          <><Mic size={14} className="text-muted-foreground" /><span className="text-muted-foreground text-xs">انتخاب صدا</span></>
        )}
        <ChevronDown size={13} className={cn("text-muted-foreground ms-auto shrink-0 transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute z-30 top-full mt-1 inset-x-0 bg-popover border border-border rounded-xl shadow-xl max-h-52 overflow-y-auto scrollbar-thin animate-scale-in">
          {voices.length === 0
            ? <p className="text-xs text-muted-foreground p-4 text-center">صدایی موجود نیست — ابتدا صدا بسازید</p>
            : voices.map((v) => (
              <button key={v.id} onClick={() => { onSelect(v.id); setOpen(false); }}
                className={cn("w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-accent text-start transition-colors",
                  v.id === selected && "bg-primary/5")}>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0"
                  style={{ background: "var(--gradient-primary)" }}>
                  {v.name.charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-foreground truncate">{v.name}</p>
                  <p className="text-[10px] text-muted-foreground">{v.language?.toUpperCase()}{v.quality_score ? ` · ${Math.round(v.quality_score * 100)}%` : ""}</p>
                </div>
                {v.id === selected && <CheckCircle size={12} className="text-primary shrink-0" />}
              </button>
            ))
          }
        </div>
      )}
    </div>
  );
}

/* ─── Video Card (library) ──────────────────────────────────── */
function VideoCard({ video, onDelete, onPreview, isActive }: {
  video: any; onDelete: () => void; onPreview: () => void; isActive: boolean;
}) {
  const busy = isActive && video.status !== "completed" && video.status !== "failed";
  return (
    <div className={cn(
      "shrink-0 w-40 rounded-xl overflow-hidden border-2 transition-all group cursor-pointer",
      isActive && video.status === "completed"
        ? "border-primary ring-2 ring-primary/25"
        : "border-border hover:border-primary/30"
    )} onClick={() => video.status === "completed" && onPreview()}>
      <div className="relative w-full h-[88px] bg-[#0a0a0e]">
        {video.thumbnail_url
          ? <img src={video.thumbnail_url} alt="" className="w-full h-full object-cover" />
          : <div className="w-full h-full flex items-center justify-center"><Film size={18} className="text-white/20" /></div>}
        {busy && (
          <div className="absolute inset-0 bg-black/65 flex flex-col items-center justify-center gap-1.5">
            <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          </div>
        )}
        {video.status === "completed" && (
          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
            <Play size={18} className="text-white" />
          </div>
        )}
        <div className="absolute top-1.5 start-1.5">
          {video.status === "completed" && <span className="badge badge-success text-[9px] px-1.5"><CheckCircle size={7} /> آماده</span>}
          {video.status === "failed"    && <span className="badge badge-danger text-[9px] px-1.5"><AlertCircle size={7} /> خطا</span>}
          {busy                         && <span className="badge badge-warning text-[9px] px-1.5"><Clock size={7} /> ساخت</span>}
        </div>
      </div>
      <div className="p-2 bg-card">
        <p className="text-[11px] font-semibold text-foreground truncate">{video.title || "بدون عنوان"}</p>
        {busy && video.progress != null
          ? <div className="mt-1 h-0.5 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-primary" style={{ width: `${video.progress}%`, transition: "width 1s" }} />
            </div>
          : <p className="text-[10px] text-muted-foreground mt-0.5">{video.resolution} · {fmtSec(video.duration_seconds)}</p>}
      </div>
      <div className="flex border-t border-border">
        {video.status === "completed" && (
          <a href={`/api/v1/videos/${video.id}/download`} target="_blank" rel="noreferrer"
            className="flex-1 flex items-center justify-center py-1.5 hover:bg-primary/5 text-muted-foreground hover:text-primary transition-colors"
            onClick={(e) => e.stopPropagation()}>
            <Download size={11} />
          </a>
        )}
        <button className="flex-1 flex items-center justify-center py-1.5 hover:bg-red-500/5 text-muted-foreground hover:text-red-500 transition-colors"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}>
          <Trash2 size={11} />
        </button>
      </div>
    </div>
  );
}

/* ─── Main Page ─────────────────────────────────────────────── */
export default function VideoStudioPage() {
  const qc = useQueryClient();
  const { language: uiLang } = useThemeStore();
  const isFa = uiLang === "fa";

  const [avatarId, setAvatarId]   = useState<string | null>(null);
  const [voiceId, setVoiceId]     = useState<string | null>(null);
  const [script, setScript]       = useState("");
  const [lang, setLang]           = useState(isFa ? "fa" : "en");
  const [res, setRes]             = useState<string>("1080p");
  const [title, setTitle]         = useState("");
  const [uploadOpen, setUpload]   = useState(false);
  const [previewId, setPreview]   = useState<string | null>(null);
  const [genId, setGenId]         = useState<string | null>(null);
  const [genPct, setGenPct]       = useState(0);
  const [genStep, setGenStep]     = useState("downloading_assets");

  /* Queries */
  const { data: avData, isLoading: avLoad } = useQuery({
    queryKey: ["avatars", "ready"],
    queryFn: () => api.get("/avatars?status=ready&limit=30").then(r => r.data),
    refetchInterval: 8000,
  });
  const { data: voData } = useQuery({
    queryKey: ["voices", "ready"],
    queryFn: () => api.get("/voices?status=ready&limit=30").then(r => r.data),
  });
  const { data: vidData } = useQuery({
    queryKey: ["videos"],
    queryFn: () => api.get("/videos?limit=15").then(r => r.data),
    refetchInterval: genId ? 3000 : 20000,
  });
  const { data: prog } = useQuery({
    queryKey: ["vprog", genId],
    queryFn: () => api.get(`/videos/${genId}/status`).then(r => r.data),
    enabled: !!genId,
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (!prog) return;
    if (prog.progress != null) setGenPct(prog.progress);
    if (prog.current_step)     setGenStep(prog.current_step);
    if (prog.status === "completed" || prog.status === "failed") {
      qc.invalidateQueries({ queryKey: ["videos"] });
      if (prog.status === "completed") setPreview(genId);
      setGenId(null);
    }
  }, [prog, genId]);

  const genMut = useMutation({
    mutationFn: () => api.post("/videos/generate", {
      avatar_id: avatarId, voice_model_id: voiceId,
      script, language: lang, resolution: res,
      title: title.trim() || (isFa ? "ویدیو جدید" : "New Video"),
    }),
    onSuccess: (r) => {
      setGenId(r.data.video_id);
      setGenPct(0);
      setGenStep("downloading_assets");
      setPreview(null);
      qc.invalidateQueries({ queryKey: ["videos"] });
    },
  });

  const delMut = useMutation({
    mutationFn: (id: string) => api.delete(`/videos/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["videos"] }),
  });

  const avatars: Avatar[]    = avData?.items || [];
  const voices: VoiceModel[] = voData?.items || [];
  const videos: any[]        = vidData?.items || [];
  const selAvatar = avatars.find(a => a.id === avatarId);
  const selVid    = videos.find(v => v.id === previewId);
  const isGen     = !!genId;
  const canGen    = !!avatarId && !!voiceId && script.trim().length > 5 && !isGen && !genMut.isPending;
  const wordCount = script.trim() ? script.trim().split(/\s+/).length : 0;
  const estSec    = estimateDuration(script, lang);
  const langDir   = LANG_LIST.find(l => l.code === lang)?.dir ?? "ltr";

  return (
    <div dir="rtl" className="flex flex-col gap-5 pb-6 animate-fade-in">

      {/* ═══ TITLE BAR ═══════════════════════════════════════════ */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-foreground">استودیو ویدیو</h1>
          <p className="text-xs text-muted-foreground mt-0.5">عکس انسان → آواتار سخن‌گو</p>
        </div>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder={isFa ? "عنوان ویدیو…" : "Video title…"}
          className="input-field text-sm w-44"
          dir="rtl"
        />
        <div className="flex items-center gap-1 p-1 bg-muted rounded-xl border border-border">
          {RESOLUTIONS.map(r => (
            <button key={r} onClick={() => setRes(r)}
              className={cn("px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                res === r ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* ═══ MAIN 3-COLUMN ═══════════════════════════════════════ */}
      <div className="grid grid-cols-[180px_1fr_230px] gap-4">

        {/* ─ LEFT: Avatar Gallery ─ */}
        <div className="card-studio p-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">آواتار</span>
            <button onClick={() => setUpload(true)} className="p-1 rounded-lg hover:bg-accent text-muted-foreground hover:text-primary transition-colors">
              <Plus size={13} />
            </button>
          </div>

          {avLoad ? (
            <div className="grid grid-cols-2 gap-1.5">
              {[...Array(6)].map((_, i) => <div key={i} className="aspect-square skeleton rounded-xl" />)}
            </div>
          ) : avatars.length === 0 ? (
            <button onClick={() => setUpload(true)}
              className="flex flex-col items-center justify-center gap-2 py-10 rounded-xl border-2 border-dashed border-border hover:border-primary/50 text-muted-foreground hover:text-primary transition-all">
              <Upload size={22} />
              <span className="text-[11px] text-center leading-tight">آپلود عکس<br />یا ویدیو</span>
            </button>
          ) : (
            <div className="grid grid-cols-2 gap-1.5 overflow-y-auto scrollbar-thin max-h-[340px]">
              {avatars.map(a => (
                <AvatarThumb key={a.id} avatar={a} selected={avatarId === a.id} onClick={() => { setAvatarId(a.id); setPreview(null); }} />
              ))}
              <button onClick={() => setUpload(true)}
                className="aspect-square rounded-xl border-2 border-dashed border-border hover:border-primary/50 flex items-center justify-center text-muted-foreground hover:text-primary transition-all">
                <Plus size={16} />
              </button>
            </div>
          )}

          {/* Avatar info card */}
          {selAvatar && (
            <div className="mt-auto pt-2 border-t border-border animate-fade-in">
              <p className="text-[10px] font-bold text-foreground truncate">{selAvatar.name}</p>
              {selAvatar.metadata?.quality_score != null && (
                <div className="flex items-center gap-1 mt-1">
                  <Star size={9} className="text-yellow-500" fill="currentColor" />
                  <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${Math.round((selAvatar.metadata.quality_score as number) * 100)}%`, background: "var(--gradient-warning)" }} />
                  </div>
                  <span className="text-[9px] text-muted-foreground">{Math.round((selAvatar.metadata.quality_score as number) * 100)}%</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ─ CENTER: Presenter Stage + Script ─ */}
        <div className="flex flex-col gap-3">

          {/* STAGE */}
          <div className="presenter-stage scan-line" style={{ height: "320px" }}>
            <div className="stage-content w-full h-full flex items-center justify-center">
              {previewId && selVid?.status === "completed" ? (
                /* Completed video player */
                <StudioPlayer videoId={previewId} thumbnail={selVid?.thumbnail_url} />
              ) : selAvatar?.thumbnail_url ? (
                /* Avatar preview */
                <div className="relative flex items-center justify-center w-full h-full">
                  <img
                    src={selAvatar.thumbnail_url}
                    alt={selAvatar.name}
                    className={cn(
                      "max-h-full max-w-full object-contain",
                      isGen ? "animate-avatar-breathe opacity-50" : "animate-avatar-glow"
                    )}
                    style={{ filter: isGen ? "blur(2px) brightness(.4)" : undefined }}
                  />
                  {/* Name plate */}
                  {!isGen && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 glass-dark px-4 py-1.5 rounded-full">
                      <p className="text-white text-xs font-semibold">{selAvatar.name}</p>
                    </div>
                  )}
                </div>
              ) : (
                /* Empty state */
                <div className="flex flex-col items-center justify-center gap-4 text-center px-6">
                  <div className="w-20 h-20 rounded-2xl border-2 border-dashed border-white/15 flex items-center justify-center">
                    <ImgIcon size={30} className="text-white/20" />
                  </div>
                  <div>
                    <p className="text-white/60 text-sm font-medium mb-1">یک آواتار انتخاب کنید</p>
                    <p className="text-white/30 text-xs">یا عکس جدید آپلود کنید</p>
                  </div>
                  <button onClick={() => setUpload(true)} className="btn-primary text-xs py-2 px-4">
                    <Upload size={12} /> آپلود عکس
                  </button>
                </div>
              )}

              {/* Generating overlay */}
              {isGen && <GenOverlay progress={genPct} step={genStep} isFa={isFa} />}
            </div>

            {/* Reset button after preview */}
            {previewId && (
              <button onClick={() => setPreview(null)}
                className="absolute top-3 end-3 z-30 glass-dark px-2.5 py-1.5 rounded-lg text-white/70 hover:text-white text-xs flex items-center gap-1.5 transition-colors">
                <RotateCcw size={11} /> آواتار
              </button>
            )}
          </div>

          {/* SCRIPT EDITOR */}
          <div className="card-studio p-4 flex-1">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">متن گفتار</label>
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                {wordCount > 0 && <span className="badge badge-primary">{wordCount} کلمه</span>}
                {estSec > 0   && <span className="text-muted-foreground">~{fmtSec(estSec)}</span>}
                <span>{script.length}/5000</span>
              </div>
            </div>
            <textarea
              value={script}
              onChange={e => setScript(e.target.value)}
              dir={langDir}
              placeholder={scriptPlaceholders[lang] ?? scriptPlaceholders.en}
              maxLength={5000}
              className="w-full h-32 px-3.5 py-3 bg-muted border border-border rounded-xl text-foreground text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 placeholder:text-muted-foreground/40 leading-relaxed"
            />
          </div>
        </div>

        {/* ─ RIGHT: Controls Panel ─ */}
        <div className="card-studio p-4 flex flex-col gap-4">
          {/* Language */}
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Languages size={12} className="text-muted-foreground" />
              <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">زبان</label>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {LANG_LIST.map(l => (
                <button key={l.code} onClick={() => setLang(l.code)}
                  className={cn(
                    "flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-[11px] border transition-all",
                    lang === l.code
                      ? "border-primary bg-primary/10 text-primary font-bold"
                      : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground"
                  )}>
                  <span className="text-sm leading-none">{l.flag}</span>
                  <span className="truncate">{l.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Voice */}
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Mic size={12} className="text-muted-foreground" />
              <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">صدا</label>
            </div>
            <VoicePicker voices={voices} selected={voiceId} onSelect={setVoiceId} />
          </div>

          {/* Quality indicators */}
          <div className="p-3 rounded-xl bg-muted border border-border space-y-2">
            <p className="text-[10px] font-bold text-foreground mb-2 flex items-center gap-1.5">
              <Gauge size={11} className="text-primary" /> کیفیت ویدیو
            </p>
            {[
              { label: "لیپ‌سینک فوق‌طبیعی", ok: true },
              { label: "پلک زدن طبیعی",      ok: true },
              { label: "میکروحالت‌ها",        ok: true },
              { label: "خروجی ۵۰fps",         ok: true },
              { label: `رزولوشن ${res}`,       ok: true },
            ].map(({ label, ok }) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground">{label}</span>
                <span className={cn("badge text-[9px] px-1.5 py-0", ok ? "badge-success" : "badge-danger")}>
                  {ok ? "✓" : "✗"}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-auto space-y-2.5">
            {/* Hints */}
            {!avatarId && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/20 animate-fade-in">
                <AlertCircle size={13} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-[11px] text-amber-600 dark:text-amber-400 leading-tight">یک آواتار از پنل چپ انتخاب کنید</p>
              </div>
            )}
            {avatarId && !voiceId && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/20 animate-fade-in">
                <AlertCircle size={13} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-[11px] text-amber-600 dark:text-amber-400 leading-tight">یک صدا از لیست بالا انتخاب کنید</p>
              </div>
            )}
            {avatarId && voiceId && script.trim().length < 5 && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-500/8 border border-amber-500/20 animate-fade-in">
                <AlertCircle size={13} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-[11px] text-amber-600 dark:text-amber-400 leading-tight">متن گفتار را در کادر وسط بنویسید</p>
              </div>
            )}

            {/* CTA */}
            <button
              onClick={() => genMut.mutate()}
              disabled={!canGen}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-4 rounded-xl font-bold text-sm transition-all duration-300",
                canGen
                  ? "text-white"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              )}
              style={canGen ? {
                background: "var(--gradient-primary)",
                boxShadow: "var(--shadow-primary-lg)",
              } : {}}
            >
              {genMut.isPending || isGen
                ? <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />در حال ساخت…</>
                : <><Sparkles size={16} />ساخت ویدیو</>}
            </button>

            {isGen && (
              <p className="text-center text-[10px] text-muted-foreground animate-pulse-slow">
                {genPct}% — {PIPELINE.find(p => p.id === genStep)?.[isFa ? "fa" : "en"] ?? genStep}
              </p>
            )}

            {previewId && !isGen && (
              <a href={`/api/v1/videos/${previewId}/download`} target="_blank" rel="noreferrer"
                className="w-full btn-secondary text-xs justify-center py-2.5">
                <Download size={13} /> دانلود ویدیو
              </a>
            )}
          </div>
        </div>
      </div>

      {/* ═══ VIDEO LIBRARY ═══════════════════════════════════════ */}
      {videos.length > 0 && (
        <div className="animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">ویدیوهای اخیر</p>
            <span className="badge badge-primary">{videos.length}</span>
          </div>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
            {videos.map((v: any) => (
              <VideoCard
                key={v.id}
                video={v}
                isActive={v.id === genId || v.id === previewId}
                onDelete={() => delMut.mutate(v.id)}
                onPreview={() => setPreview(v.id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ═══ MODALS ══════════════════════════════════════════════ */}
      {uploadOpen && (
        <UploadAvatarModal
          onClose={() => setUpload(false)}
          onCreated={(id) => { setUpload(false); qc.invalidateQueries({ queryKey: ["avatars", "ready"] }); setAvatarId(id); setPreview(null); }}
        />
      )}
    </div>
  );
}
