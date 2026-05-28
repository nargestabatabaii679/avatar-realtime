import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Mic, Play, StopCircle, Trash2, Upload, CheckCircle2,
  Loader2, Plus, X, Volume2, Radio, Sparkles,
} from "lucide-react";
import { api }               from "../../services/api";
import { cn }                from "../../utils/cn";
import { formatDuration }    from "../../utils/format";
import { LANGUAGES, GRADIENTS, TIMING } from "../../constants";
import { useAudioRecorder }  from "../../hooks/useAudioRecorder";
import { Modal }             from "../../components/ui/Modal";
import { StatusBadge }       from "../../components/ui/StatusBadge";
import { PageHeader }        from "../../components/ui/PageHeader";
import type { VoiceModel }   from "../../types";
import { VoiceStatus }      from "../../types";

// ── Animated waveform bars ────────────────────────────────────
function WaveformBars({ active, values }: { active: boolean; values: number[] }) {
  return (
    <div className="flex items-center justify-center gap-0.5 h-10">
      {values.map((v, i) => (
        <div
          key={i}
          className="rounded-full transition-all"
          style={{
            width:      3,
            height:     active ? `${Math.max(4, v * 40)}px` : "4px",
            background: active
              ? `hsl(${262 + i * 3}, 80%, 65%)`
              : "hsl(var(--muted-foreground) / 0.3)",
            transitionDuration: "80ms",
          }}
        />
      ))}
    </div>
  );
}

// ── Voice card ────────────────────────────────────────────────
interface VoiceCardProps {
  voice: VoiceModel;
  onDelete: () => void;
  onTest: (text: string) => void;
}

function VoiceCard({ voice, onDelete, onTest }: VoiceCardProps) {
  const { t } = useTranslation();
  const [testText, setTestText] = useState("");

  const langFlag  = LANGUAGES.find((l) => l.code === voice.language)?.flag ?? "🌐";
  const initials  = (voice.name?.charAt(0) ?? "V").toUpperCase();

  // Map domain VoiceStatus to StatusBadge key
  const statusLabelKey = `voice.status.${voice.status}` as const;

  return (
    <div
      className="rounded-2xl p-5 border transition-all hover:shadow-md group"
      style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-11 h-11 rounded-full flex items-center justify-center text-white text-base font-bold shrink-0"
            style={{ background: GRADIENTS.voiceCard }}
          >
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
        <button
          onClick={onDelete}
          className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all"
          style={{ color: "hsl(var(--muted-foreground))" }}
          aria-label={t("common.delete")}
        >
          <Trash2 size={14} />
        </button>
      </div>

      <div className="mb-4">
        <StatusBadge status={voice.status} label={t(statusLabelKey, { defaultValue: voice.status })} />
      </div>

      {/* Test voice */}
      {voice.status === VoiceStatus.READY && (
        <div className="space-y-2">
          <p className="text-xs font-medium" style={{ color: "hsl(var(--muted-foreground))" }}>
            {t("voice.testVoice")}
          </p>
          <div className="flex gap-2">
            <input
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder={t("voice.enterTestText")}
              onKeyDown={(e) => e.key === "Enter" && testText.trim() && onTest(testText)}
              className="flex-1 px-3 py-2 rounded-xl text-xs border focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
              style={{
                backgroundColor: "hsl(var(--muted))",
                borderColor:     "hsl(var(--border))",
                color:           "hsl(var(--foreground))",
              }}
            />
            <button
              onClick={() => testText.trim() && onTest(testText)}
              disabled={!testText.trim()}
              className="p-2 rounded-xl transition-colors disabled:opacity-40"
              style={{ background: GRADIENTS.primary }}
              aria-label={t("voice.synthesize")}
            >
              <Play size={13} className="text-white" />
            </button>
          </div>
        </div>
      )}

      {/* Cloning progress */}
      {voice.status === VoiceStatus.TRAINING && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: "hsl(var(--muted-foreground))" }}>
              {t("voice.status.training_model")}
            </span>
            <span className="font-medium" style={{ color: "hsl(var(--foreground))" }}>
              {voice.progress ?? 0}%
            </span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ backgroundColor: "hsl(var(--muted))" }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${voice.progress ?? 30}%`, background: GRADIENTS.primary }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Clone modal ───────────────────────────────────────────────
interface CloneModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, language: string, files: File[], recordingBlob: Blob | null) => void;
  isPending: boolean;
}

function CloneModal({ open, onClose, onSubmit, isPending }: CloneModalProps) {
  const { t } = useTranslation();
  const [name,        setName]        = useState("");
  const [language,    setLanguage]    = useState("fa");
  const [inputMode,   setInputMode]   = useState<"upload" | "record">("upload");
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);

  const recorder = useAudioRecorder();

  const onDrop = useCallback((dropped: File[]) => {
    setUploadFiles((prev) => [...prev, ...dropped]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "audio/*": [".wav", ".mp3", ".flac", ".m4a", ".ogg"] },
    multiple: true,
  });

  const canSubmit =
    name.trim() &&
    (inputMode === "upload" ? uploadFiles.length > 0 : !!recorder.audioBlob) &&
    !isPending;

  const handleSubmit = () => {
    onSubmit(name, language, uploadFiles, recorder.audioBlob);
  };

  const handleClose = () => {
    setName("");
    setUploadFiles([]);
    recorder.clear();
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={t("voice.cloneModal.title")}
      subtitle={t("voice.cloneModal.subtitle")}
      icon={<Mic size={16} />}
    >
      <div className="space-y-4">
        {/* Name */}
        <div>
          <label className="block text-xs font-semibold mb-1.5" style={{ color: "hsl(var(--foreground))" }}>
            {t("voice.cloneModal.modelName")}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("voice.cloneModal.modelNamePlaceholder")}
            className="w-full px-3 py-2.5 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
            style={{
              backgroundColor: "hsl(var(--muted))",
              borderColor:     "hsl(var(--border))",
              color:           "hsl(var(--foreground))",
            }}
          />
        </div>

        {/* Language grid */}
        <div>
          <label className="block text-xs font-semibold mb-2" style={{ color: "hsl(var(--foreground))" }}>
            {t("voice.language")}
          </label>
          <div className="grid grid-cols-3 gap-2">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => setLanguage(l.code)}
                className={cn("flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-all")}
                style={{
                  backgroundColor: language === l.code ? "hsl(var(--primary) / 0.08)" : "hsl(var(--muted))",
                  borderColor:     language === l.code ? "hsl(var(--primary) / 0.5)"  : "hsl(var(--border))",
                  color:           language === l.code ? "hsl(var(--primary))"         : "hsl(var(--foreground))",
                }}
              >
                <span className="text-base">{l.flag}</span>
                <span>{l.nativeLabel}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Upload / Record toggle */}
        <div className="flex rounded-xl p-1 gap-1" style={{ backgroundColor: "hsl(var(--muted))" }}>
          {([
            { mode: "upload", label: t("voice.cloneModal.uploadTab"), Icon: Upload },
            { mode: "record", label: t("voice.cloneModal.recordTab"), Icon: Mic    },
          ] as const).map(({ mode, label, Icon }) => (
            <button
              key={mode}
              onClick={() => setInputMode(mode)}
              className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all"
              style={{
                backgroundColor: inputMode === mode ? "hsl(var(--background))" : "transparent",
                color:           inputMode === mode ? "hsl(var(--foreground))"  : "hsl(var(--muted-foreground))",
                boxShadow:       inputMode === mode ? "var(--shadow-sm)"        : "none",
              }}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </div>

        {/* Upload dropzone */}
        {inputMode === "upload" && (
          <div>
            <div
              {...getRootProps()}
              className={cn(
                "border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all",
                isDragActive ? "border-primary bg-primary/5" : "hover:border-primary/40",
              )}
              style={{ borderColor: isDragActive ? "hsl(var(--primary))" : "hsl(var(--border))" }}
            >
              <input {...getInputProps()} />
              <Upload size={28} className="mx-auto mb-2" style={{ color: "hsl(var(--muted-foreground))", opacity: 0.5 }} />
              <p className="text-sm font-medium" style={{ color: "hsl(var(--foreground))" }}>
                {isDragActive ? t("voice.cloneModal.dropHint") : t("voice.uploadSamples")}
              </p>
              <p className="text-xs mt-1" style={{ color: "hsl(var(--muted-foreground))" }}>
                {t("voice.cloneModal.uploadHint")}
              </p>
            </div>
            {uploadFiles.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {uploadFiles.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
                    style={{ backgroundColor: "hsl(var(--muted))" }}
                  >
                    <CheckCircle2 size={12} className="text-emerald-500 shrink-0" />
                    <span className="flex-1 truncate" style={{ color: "hsl(var(--foreground))" }}>{f.name}</span>
                    <span style={{ color: "hsl(var(--muted-foreground))" }}>{(f.size / 1024 / 1024).toFixed(1)}MB</span>
                    <button
                      onClick={() => setUploadFiles((p) => p.filter((_, j) => j !== i))}
                      className="hover:text-red-500 transition-colors"
                      style={{ color: "hsl(var(--muted-foreground))" }}
                      aria-label={t("common.delete")}
                    >
                      <X size={11} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Mic recorder */}
        {inputMode === "record" && (
          <div
            className="rounded-2xl p-5 border text-center space-y-4"
            style={{ backgroundColor: "hsl(var(--muted))", borderColor: "hsl(var(--border))" }}
          >
            <WaveformBars active={recorder.recording} values={recorder.waveValues} />

            <div
              className="flex items-center justify-center gap-1 text-sm font-mono tabular-nums"
              style={{ color: recorder.recording ? "#ef4444" : "hsl(var(--muted-foreground))" }}
            >
              {recorder.recording && <Radio size={13} className="animate-pulse text-red-500" />}
              {formatDuration(recorder.durationSec)}
            </div>

            {!recorder.recording && !recorder.audioBlob ? (
              <button
                onClick={recorder.start}
                className="mx-auto flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-all hover:scale-105"
                style={{ background: GRADIENTS.primary }}
              >
                <Mic size={16} />
                {t("voice.cloneModal.startRecording")}
              </button>
            ) : recorder.recording ? (
              <button
                onClick={recorder.stop}
                className="mx-auto flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium text-white transition-all hover:scale-105"
                style={{ background: GRADIENTS.red }}
              >
                <StopCircle size={16} />
                {t("voice.cloneModal.stopRecording")}
              </button>
            ) : (
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={() => { const url = URL.createObjectURL(recorder.audioBlob!); new Audio(url).play(); }}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-colors"
                  style={{
                    backgroundColor: "hsl(var(--background))",
                    borderColor:     "hsl(var(--border))",
                    color:           "hsl(var(--foreground))",
                  }}
                >
                  <Play size={13} />
                  {t("voice.cloneModal.playRecording")}
                </button>
                <button
                  onClick={recorder.clear}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-colors hover:text-red-500"
                  style={{
                    backgroundColor: "hsl(var(--background))",
                    borderColor:     "hsl(var(--border))",
                    color:           "hsl(var(--muted-foreground))",
                  }}
                >
                  <Trash2 size={13} />
                  {t("voice.cloneModal.deleteRecording")}
                </button>
              </div>
            )}

            {recorder.audioBlob && (
              <p className="text-xs text-emerald-500 flex items-center justify-center gap-1">
                <CheckCircle2 size={12} />
                {t("voice.cloneModal.recordingReady")} ({formatDuration(recorder.durationSec)})
              </p>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3 pt-1">
          <button
            onClick={handleClose}
            className="flex-1 py-2.5 rounded-xl text-sm border transition-colors hover:bg-accent"
            style={{ borderColor: "hsl(var(--border))", color: "hsl(var(--foreground))" }}
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-40 flex items-center justify-center gap-2"
            style={{ background: GRADIENTS.primary }}
          >
            {isPending
              ? <><Loader2 size={14} className="animate-spin" /> {t("voice.cloneModal.submitting")}</>
              : <><Sparkles size={14} /> {t("voice.cloneModal.startClone")}</>
            }
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Main page ─────────────────────────────────────────────────
export default function VoiceStudioPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey:        ["voices"],
    queryFn:         () => api.get("/voices").then((r) => r.data),
    refetchInterval: TIMING.voicePollMs,
  });

  const cloneMutation = useMutation({
    mutationFn: async ({
      name, language, files, recordingBlob,
    }: { name: string; language: string; files: File[]; recordingBlob: Blob | null }) => {
      const form = new FormData();
      form.append("name", name);
      form.append("language", language);
      if (files.length > 0) {
        files.forEach((f) => form.append("samples[]", f));
      } else if (recordingBlob) {
        form.append("samples[]", recordingBlob, "recording.webm");
      }
      return api.post("/voices/clone", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voices"] });
      setShowCreate(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/voices/${id}`),
    onSuccess:  () => queryClient.invalidateQueries({ queryKey: ["voices"] }),
  });

  const testMutation = useMutation({
    mutationFn: ({ voiceId, text }: { voiceId: string; text: string }) =>
      api.post<{ audio_url: string }>("/voices/tts", { voice_model_id: voiceId, text }),
    onSuccess: (res) => new Audio(res.data.audio_url).play(),
  });

  const voices: VoiceModel[] = data?.items ?? [];
  const readyCount      = voices.filter((v) => v.status === VoiceStatus.READY).length;
  const processingCount = voices.filter((v) => v.status === VoiceStatus.TRAINING || v.status === VoiceStatus.PENDING).length;

  return (
    <div className="space-y-6 animate-fade-in pb-6">

      <PageHeader
        title={t("voice.title")}
        subtitle={t("voice.subtitle")}
        action={
          <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
            <Plus size={15} />
            {t("voice.create")}
          </button>
        }
      />

      {/* Stats bar */}
      {voices.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {([
            { labelKey: "voice.totalModels",   value: voices.length,    Icon: Volume2,    color: "#8b5cf6" },
            { labelKey: "voice.status.ready",   value: readyCount,       Icon: CheckCircle2, color: "#10b981" },
            { labelKey: "voice.processing",     value: processingCount,  Icon: Loader2,    color: "#f59e0b" },
          ] as const).map(({ labelKey, value, Icon, color }) => (
            <div
              key={labelKey}
              className="rounded-2xl p-4 border flex items-center gap-3"
              style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
            >
              <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: `${color}22` }}>
                <Icon size={14} style={{ color }} className={labelKey === "voice.processing" && processingCount > 0 ? "animate-spin" : ""} />
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: "hsl(var(--foreground))" }}>{value}</p>
                <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>{t(labelKey)}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Voice grid / empty state */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 rounded-2xl animate-pulse" style={{ backgroundColor: "hsl(var(--muted))" }} />
          ))}
        </div>
      ) : voices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div
            className="w-20 h-20 rounded-3xl flex items-center justify-center mb-5"
            style={{ background: GRADIENTS.voiceCard }}
          >
            <Mic size={32} className="text-white" />
          </div>
          <h2 className="text-lg font-bold mb-2" style={{ color: "hsl(var(--foreground))" }}>
            {t("voice.noVoices")}
          </h2>
          <p className="text-sm mb-6 max-w-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
            {t("voice.noVoicesHint")}
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <Sparkles size={15} />
            {t("voice.startCloning")}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {voices.map((voice) => (
            <VoiceCard
              key={voice.id}
              voice={voice}
              onDelete={() => deleteMutation.mutate(voice.id)}
              onTest={(text) => testMutation.mutate({ voiceId: voice.id, text })}
            />
          ))}
        </div>
      )}

      <CloneModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={(name, language, files, recordingBlob) =>
          cloneMutation.mutate({ name, language, files, recordingBlob })
        }
        isPending={cloneMutation.isPending}
      />
    </div>
  );
}
