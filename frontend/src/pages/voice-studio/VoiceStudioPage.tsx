import { useState, useCallback, useRef, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Mic, MicOff, Play, Pause, StopCircle, Trash2, Upload, CheckCircle2,
  Loader2, Plus, X, Volume2, Radio, Sparkles, Clock,
} from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";

const LANGUAGES = [
  { code: "fa", label: "فارسی",   flag: "🇮🇷" },
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "ar", label: "عربی",    flag: "🇸🇦" },
  { code: "tr", label: "Türkçe",  flag: "🇹🇷" },
  { code: "fr", label: "Français",flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
];

/* ─── Waveform Bars ──────────────────────────────────────── */
function WaveformBars({ active, values }: { active: boolean; values: number[] }) {
  return (
    <div className="flex items-center justify-center gap-0.5 h-10">
      {values.map((v, i) => (
        <div key={i}
          className="rounded-full transition-all duration-75"
          style={{
            width: 3,
            height: active ? `${Math.max(4, v * 40)}px` : "4px",
            background: active
              ? `hsl(${262 + i * 3}, 80%, 65%)`
              : "hsl(var(--muted-foreground) / 0.3)",
            transition: "height 0.08s ease",
          }}
        />
      ))}
    </div>
  );
}

/* ─── Recording Hook ─────────────────────────────────────── */
function useAudioRecorder() {
  const [recording, setRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);
  const [waveValues, setWaveValues] = useState<number[]>(Array(32).fill(0));
  const mediaRef  = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef  = useRef<ReturnType<typeof setInterval>>();
  const analyserRef = useRef<AnalyserNode>();
  const animRef   = useRef<number>();

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 64;
    src.connect(analyser);
    analyserRef.current = analyser;

    const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRef.current = mr;
    chunksRef.current = [];
    mr.ondataavailable = (e) => chunksRef.current.push(e.data);
    mr.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      setAudioBlob(blob);
      stream.getTracks().forEach((t) => t.stop());
      ctx.close();
    };
    mr.start(100);
    setRecording(true);
    setDuration(0);

    timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);

    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(data);
      setWaveValues(Array.from(data).slice(0, 32).map((v) => v / 255));
      animRef.current = requestAnimationFrame(tick);
    };
    tick();
  }, []);

  const stop = useCallback(() => {
    mediaRef.current?.stop();
    clearInterval(timerRef.current);
    cancelAnimationFrame(animRef.current!);
    setRecording(false);
    setWaveValues(Array(32).fill(0));
  }, []);

  const clear = useCallback(() => {
    setAudioBlob(null);
    setDuration(0);
  }, []);

  return { recording, audioBlob, duration, waveValues, start, stop, clear };
}

/* ─── Voice Card ─────────────────────────────────────────── */
function VoiceCard({ voice, onDelete, onTest }: {
  voice: any;
  onDelete: () => void;
  onTest: (text: string) => void;
}) {
  const [testText, setTestText] = useState("");
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handlePlay = () => {
    if (!testText.trim()) return;
    onTest(testText);
  };

  const statusConfig = {
    ready:    { label: "آماده",          color: "text-emerald-500", bg: "bg-emerald-500/10", dot: "bg-emerald-500" },
    cloning:  { label: "در حال کلون",   color: "text-amber-500",   bg: "bg-amber-500/10",   dot: "bg-amber-500 animate-pulse" },
    failed:   { label: "ناموفق",         color: "text-red-500",     bg: "bg-red-500/10",     dot: "bg-red-500" },
    pending:  { label: "در صف",          color: "text-blue-400",    bg: "bg-blue-400/10",    dot: "bg-blue-400 animate-pulse" },
  };
  const s = statusConfig[voice.status as keyof typeof statusConfig] || statusConfig.pending;

  const initials = voice.name?.charAt(0)?.toUpperCase() || "V";
  const langFlag = LANGUAGES.find((l) => l.code === voice.language)?.flag || "🌐";

  return (
    <div className="rounded-2xl p-5 border transition-all hover:shadow-md group"
      style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-full flex items-center justify-center text-white text-base font-bold shrink-0"
            style={{ background: "linear-gradient(135deg,#8b5cf6,#06b6d4)" }}>
            {initials}
          </div>
          <div>
            <h3 className="font-semibold text-sm leading-tight" style={{ color: "hsl(var(--foreground))" }}>
              {voice.name}
            </h3>
            <p className="text-xs mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
              {langFlag} {voice.language?.toUpperCase()} · {voice.tts_engine}
            </p>
          </div>
        </div>
        <button onClick={onDelete}
          className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all"
          style={{ color: "hsl(var(--muted-foreground))" }}>
          <Trash2 size={14} />
        </button>
      </div>

      {/* Status */}
      <div className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium mb-4", s.bg, s.color)}>
        <span className={cn("w-1.5 h-1.5 rounded-full", s.dot)} />
        {s.label}
      </div>

      {/* Test Voice */}
      {voice.status === "ready" && (
        <div className="space-y-2">
          <p className="text-xs font-medium" style={{ color: "hsl(var(--muted-foreground))" }}>آزمایش صدا</p>
          <div className="flex gap-2">
            <input
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder="متن برای آزمایش…"
              className="flex-1 px-3 py-2 rounded-xl text-xs border focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all"
              style={{
                backgroundColor: "hsl(var(--muted))",
                borderColor: "hsl(var(--border))",
                color: "hsl(var(--foreground))",
              }}
              onKeyDown={(e) => e.key === "Enter" && handlePlay()}
            />
            <button
              onClick={handlePlay}
              disabled={!testText.trim()}
              className="p-2 rounded-xl transition-colors disabled:opacity-40"
              style={{ background: "var(--gradient-primary)" }}>
              <Play size={13} className="text-white" />
            </button>
          </div>
        </div>
      )}

      {/* Cloning Progress */}
      {voice.status === "cloning" && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: "hsl(var(--muted-foreground))" }}>در حال آموزش مدل…</span>
            <span className="font-medium" style={{ color: "hsl(var(--foreground))" }}>{voice.progress ?? 0}%</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
            <div className="h-full rounded-full transition-all duration-500"
              style={{ width: `${voice.progress ?? 30}%`, background: "var(--gradient-primary)" }} />
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Main Page ──────────────────────────────────────────── */
export default function VoiceStudioPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate]   = useState(false);
  const [name, setName]               = useState("");
  const [language, setLanguage]       = useState("fa");
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [inputMode, setInputMode]     = useState<"upload" | "record">("upload");

  const recorder = useAudioRecorder();

  const { data, isLoading } = useQuery({
    queryKey: ["voices"],
    queryFn: () => api.get("/voices").then((r) => r.data),
    refetchInterval: 10000,
  });

  const cloneMutation = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.append("name", name);
      form.append("language", language);
      if (inputMode === "upload") {
        uploadedFiles.forEach((f) => form.append("samples[]", f));
      } else if (recorder.audioBlob) {
        form.append("samples[]", recorder.audioBlob, "recording.webm");
      }
      return api.post("/voices/clone", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voices"] });
      setShowCreate(false);
      setName("");
      setUploadedFiles([]);
      recorder.clear();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/voices/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["voices"] }),
  });

  const testMutation = useMutation({
    mutationFn: ({ voiceId, text }: { voiceId: string; text: string }) =>
      api.post("/voices/tts", { voice_model_id: voiceId, text, language }),
    onSuccess: (res) => {
      const audio = new Audio(res.data.audio_url);
      audio.play();
    },
  });

  const onDrop = useCallback((dropped: File[]) => {
    setUploadedFiles((prev) => [...prev, ...dropped]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "audio/*": [".wav", ".mp3", ".flac", ".m4a", ".ogg"] },
    multiple: true,
  });

  const voices = data?.items || [];
  const cloningCount = voices.filter((v: any) => v.status === "cloning").length;
  const readyCount   = voices.filter((v: any) => v.status === "ready").length;

  const canClone = name.trim() && (
    (inputMode === "upload" && uploadedFiles.length > 0) ||
    (inputMode === "record" && recorder.audioBlob)
  );

  const formatDuration = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="space-y-6 animate-fade-in pb-6">

      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "hsl(var(--foreground))" }}>
            استودیو صدا
          </h1>
          <p className="text-sm mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
            صدای خود را با XTTS-v2 در ۶ زبان کلون کنید
          </p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="btn-primary flex items-center gap-2">
          <Plus size={15} />
          کلون صدا
        </button>
      </div>

      {/* Stats Bar */}
      {voices.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "کل مدل‌ها",         value: voices.length,  icon: Volume2,    color: "#8b5cf6" },
            { label: "آماده",              value: readyCount,     icon: CheckCircle2, color: "#10b981" },
            { label: "در حال پردازش",     value: cloningCount,   icon: Loader2,    color: "#f59e0b" },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="rounded-2xl p-4 border flex items-center gap-3"
              style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>
              <div className="w-8 h-8 rounded-xl flex items-center justify-center"
                style={{ background: `${color}22` }}>
                <Icon size={14} style={{ color }} className={label === "در حال پردازش" && cloningCount > 0 ? "animate-spin" : ""} />
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: "hsl(var(--foreground))" }}>{value}</p>
                <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>{label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Voice Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 rounded-2xl animate-pulse"
              style={{ backgroundColor: "hsl(var(--muted))" }} />
          ))}
        </div>
      ) : voices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-20 h-20 rounded-3xl flex items-center justify-center mb-5"
            style={{ background: "linear-gradient(135deg,#8b5cf6,#06b6d4)" }}>
            <Mic size={32} className="text-white" />
          </div>
          <h2 className="text-lg font-bold mb-2" style={{ color: "hsl(var(--foreground))" }}>
            هنوز مدل صدایی ندارید
          </h2>
          <p className="text-sm mb-6 max-w-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
            با بارگذاری نمونه صدا یا ضبط مستقیم، صدای خود را کلون کنید
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <Sparkles size={15} />
            شروع کلون صدا
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {voices.map((voice: any) => (
            <VoiceCard
              key={voice.id}
              voice={voice}
              onDelete={() => deleteMutation.mutate(voice.id)}
              onTest={(text) => testMutation.mutate({ voiceId: voice.id, text })}
            />
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-lg rounded-3xl p-6 animate-fade-in border shadow-2xl"
            style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}>

            {/* Modal Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                  style={{ background: "linear-gradient(135deg,#8b5cf6,#06b6d4)" }}>
                  <Mic size={16} className="text-white" />
                </div>
                <div>
                  <h2 className="text-base font-bold" style={{ color: "hsl(var(--foreground))" }}>کلون صدا</h2>
                  <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>حداقل ۳۰ ثانیه صدا نیاز دارید</p>
                </div>
              </div>
              <button onClick={() => setShowCreate(false)}
                className="p-2 rounded-xl hover:bg-accent transition-colors"
                style={{ color: "hsl(var(--muted-foreground))" }}>
                <X size={16} />
              </button>
            </div>

            <div className="space-y-4">

              {/* Name */}
              <div>
                <label className="block text-xs font-semibold mb-1.5" style={{ color: "hsl(var(--foreground))" }}>
                  نام مدل صدا
                </label>
                <input value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="مثال: صدای من"
                  className="w-full px-3 py-2.5 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
                  style={{
                    backgroundColor: "hsl(var(--muted))",
                    borderColor: "hsl(var(--border))",
                    color: "hsl(var(--foreground))",
                  }} />
              </div>

              {/* Language */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "hsl(var(--foreground))" }}>زبان</label>
                <div className="grid grid-cols-3 gap-2">
                  {LANGUAGES.map((l) => (
                    <button key={l.code}
                      onClick={() => setLanguage(l.code)}
                      className={cn("flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all",
                        language === l.code
                          ? "border-primary/50 text-primary"
                          : "hover:border-primary/30"
                      )}
                      style={{
                        backgroundColor: language === l.code ? "hsl(var(--primary) / 0.08)" : "hsl(var(--muted))",
                        borderColor: language === l.code ? "hsl(var(--primary) / 0.5)" : "hsl(var(--border))",
                        color: language === l.code ? "hsl(var(--primary))" : "hsl(var(--foreground))",
                      }}>
                      <span className="text-base">{l.flag}</span>
                      <span>{l.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Input Mode Toggle */}
              <div className="flex rounded-xl p-1 gap-1" style={{ backgroundColor: "hsl(var(--muted))" }}>
                {[
                  { mode: "upload", label: "بارگذاری فایل", icon: Upload },
                  { mode: "record", label: "ضبط مستقیم",    icon: Mic },
                ].map(({ mode, label, icon: Icon }) => (
                  <button key={mode}
                    onClick={() => setInputMode(mode as "upload" | "record")}
                    className={cn("flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all")}
                    style={{
                      backgroundColor: inputMode === mode ? "hsl(var(--background))" : "transparent",
                      color: inputMode === mode ? "hsl(var(--foreground))" : "hsl(var(--muted-foreground))",
                      boxShadow: inputMode === mode ? "var(--shadow-sm)" : "none",
                    }}>
                    <Icon size={13} />
                    {label}
                  </button>
                ))}
              </div>

              {/* Upload Mode */}
              {inputMode === "upload" && (
                <div>
                  <div {...getRootProps()}
                    className={cn(
                      "border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all",
                      isDragActive ? "border-primary bg-primary/5" : "hover:border-primary/40"
                    )}
                    style={{ borderColor: isDragActive ? "hsl(var(--primary))" : "hsl(var(--border))" }}>
                    <input {...getInputProps()} />
                    <Upload size={28} className="mx-auto mb-2" style={{ color: "hsl(var(--muted-foreground))", opacity: 0.5 }} />
                    <p className="text-sm font-medium" style={{ color: "hsl(var(--foreground))" }}>
                      {isDragActive ? "رها کنید…" : "بارگذاری نمونه صدا"}
                    </p>
                    <p className="text-xs mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
                      WAV, MP3, FLAC, M4A — حداقل ۳۰ ثانیه
                    </p>
                  </div>
                  {uploadedFiles.length > 0 && (
                    <div className="mt-2 space-y-1.5">
                      {uploadedFiles.map((f, i) => (
                        <div key={i}
                          className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
                          style={{ backgroundColor: "hsl(var(--muted))" }}>
                          <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />
                          <span className="flex-1 truncate" style={{ color: "hsl(var(--foreground))" }}>{f.name}</span>
                          <span style={{ color: "hsl(var(--muted-foreground))" }}>{(f.size / 1024 / 1024).toFixed(1)}MB</span>
                          <button onClick={() => setUploadedFiles((p) => p.filter((_, j) => j !== i))}
                            style={{ color: "hsl(var(--muted-foreground))" }}
                            className="hover:text-red-500 transition-colors">
                            <X size={11} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Record Mode */}
              {inputMode === "record" && (
                <div className="rounded-2xl p-5 border text-center space-y-4"
                  style={{ backgroundColor: "hsl(var(--muted))", borderColor: "hsl(var(--border))" }}>
                  <WaveformBars active={recorder.recording} values={recorder.waveValues} />

                  <div className="flex items-center justify-center gap-1 text-sm font-mono tabular-nums"
                    style={{ color: recorder.recording ? "#ef4444" : "hsl(var(--muted-foreground))" }}>
                    {recorder.recording && <Radio size={13} className="animate-pulse text-red-500" />}
                    {formatDuration(recorder.duration)}
                  </div>

                  {!recorder.recording && !recorder.audioBlob ? (
                    <button onClick={recorder.start}
                      className="mx-auto flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-all hover:scale-105"
                      style={{ background: "var(--gradient-primary)" }}>
                      <Mic size={16} />
                      شروع ضبط
                    </button>
                  ) : recorder.recording ? (
                    <button onClick={recorder.stop}
                      className="mx-auto flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-all hover:scale-105"
                      style={{ background: "linear-gradient(135deg,#ef4444,#dc2626)" }}>
                      <StopCircle size={16} />
                      توقف ضبط
                    </button>
                  ) : (
                    <div className="flex items-center justify-center gap-3">
                      <button
                        onClick={() => {
                          const url = URL.createObjectURL(recorder.audioBlob!);
                          new Audio(url).play();
                        }}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-colors"
                        style={{
                          backgroundColor: "hsl(var(--background))",
                          borderColor: "hsl(var(--border))",
                          color: "hsl(var(--foreground))",
                        }}>
                        <Play size={13} />
                        پخش
                      </button>
                      <button onClick={recorder.clear}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-colors hover:text-red-500"
                        style={{
                          backgroundColor: "hsl(var(--background))",
                          borderColor: "hsl(var(--border))",
                          color: "hsl(var(--muted-foreground))",
                        }}>
                        <Trash2 size={13} />
                        حذف
                      </button>
                    </div>
                  )}

                  {recorder.audioBlob && (
                    <p className="text-xs text-emerald-500 flex items-center justify-center gap-1">
                      <CheckCircle2 size={12} />
                      ضبط آماده است ({formatDuration(recorder.duration)})
                    </p>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 pt-1">
                <button onClick={() => setShowCreate(false)}
                  className="flex-1 py-2.5 rounded-xl text-sm border transition-colors hover:bg-accent"
                  style={{
                    borderColor: "hsl(var(--border))",
                    color: "hsl(var(--foreground))",
                  }}>
                  انصراف
                </button>
                <button
                  onClick={() => cloneMutation.mutate()}
                  disabled={!canClone || cloneMutation.isPending}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-40 flex items-center justify-center gap-2"
                  style={{ background: "var(--gradient-primary)" }}>
                  {cloneMutation.isPending
                    ? <><Loader2 size={14} className="animate-spin" /> در حال ارسال…</>
                    : <><Sparkles size={14} /> شروع کلون</>
                  }
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
