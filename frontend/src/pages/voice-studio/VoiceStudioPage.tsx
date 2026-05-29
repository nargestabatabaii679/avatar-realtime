import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Mic, Play, StopCircle, Trash2, Upload, CheckCircle2,
  Loader2, Plus, X, Volume2, Radio,
} from "lucide-react";
import { api }               from "../../services/api";
import { cn }                from "../../utils/cn";
import { formatDuration }    from "../../utils/format";
import { LANGUAGES, TIMING } from "../../constants";
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
          className="transition-all"
          style={{
            width:      2,
            height:     active ? `${Math.max(3, v * 36)}px` : "3px",
            background: active ? "var(--accent)" : "var(--b2)",
            transitionDuration: "80ms",
            borderRadius: 1,
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
    <div className="card-premium p-5 group transition-all duration-150">
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 flex items-center justify-center text-sm font-bold shrink-0"
            style={{ background: "var(--accent-bg)", border: "0.5px solid var(--accent-md)", borderRadius: "var(--r-tag)", color: "var(--accent)" }}
          >
            {initials}
          </div>
          <div>
            <h3 className="font-semibold text-sm leading-tight" style={{ color: "var(--t1)" }}>
              {voice.name}
            </h3>
            <p className="text-xs mt-0.5" style={{ color: "var(--t3)" }}>
              {langFlag} {voice.language?.toUpperCase()} · {voice.tts_engine}
            </p>
          </div>
        </div>
        <button
          onClick={onDelete}
          className="p-1.5 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all"
          style={{ color: "var(--t3)", borderRadius: "var(--r-btn)" }}
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
          <p className="text-xs font-medium" style={{ color: "var(--t3)" }}>
            {t("voice.testVoice")}
          </p>
          <div className="flex gap-2">
            <input
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              placeholder={t("voice.enterTestText")}
              onKeyDown={(e) => e.key === "Enter" && testText.trim() && onTest(testText)}
              className="input-field flex-1"
            />
            <button
              onClick={() => testText.trim() && onTest(testText)}
              disabled={!testText.trim()}
              className="btn-primary px-3"
              aria-label={t("voice.synthesize")}
            >
              <Play size={13} />
            </button>
          </div>
        </div>
      )}

      {/* Cloning progress */}
      {voice.status === VoiceStatus.TRAINING && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span style={{ color: "var(--t3)" }}>
              {t("voice.status.training_model")}
            </span>
            <span className="font-medium" style={{ color: "var(--t1)", fontFamily: "'IBM Plex Mono', monospace" }}>
              {voice.progress ?? 0}%
            </span>
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill transition-all duration-500"
              style={{ width: `${voice.progress ?? 30}%` }}
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
          <label className="block text-xs font-semibold mb-1.5" style={{ color: "var(--t1)" }}>
            {t("voice.cloneModal.modelName")}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("voice.cloneModal.modelNamePlaceholder")}
            className="input-field"
          />
        </div>

        {/* Language grid */}
        <div>
          <label className="block text-xs font-semibold mb-2" style={{ color: "var(--t1)" }}>
            {t("voice.language")}
          </label>
          <div className="grid grid-cols-3 gap-2">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => setLanguage(l.code)}
                className={cn("flex items-center gap-2 px-3 py-2 text-xs font-medium transition-all")}
                style={{
                  background:   language === l.code ? "var(--accent-bg)" : "var(--s2)",
                  border:       language === l.code ? "0.5px solid var(--accent-md)" : "0.5px solid var(--border-rest)",
                  borderRadius: "var(--r-btn)",
                  color:        language === l.code ? "var(--accent)" : "var(--t2)",
                }}
              >
                <span className="text-base">{l.flag}</span>
                <span>{l.nativeLabel}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Upload / Record toggle */}
        <div className="flex gap-1" style={{ borderBottom: "0.5px solid var(--border-rest)" }}>
          {([
            { mode: "upload", label: t("voice.cloneModal.uploadTab"), Icon: Upload },
            { mode: "record", label: t("voice.cloneModal.recordTab"), Icon: Mic    },
          ] as const).map(({ mode, label, Icon }) => (
            <button
              key={mode}
              onClick={() => setInputMode(mode)}
              className="flex items-center gap-1.5 py-2 px-3 text-xs font-medium transition-all"
              style={{
                color:        inputMode === mode ? "var(--accent)"  : "var(--t3)",
                borderBottom: inputMode === mode ? "1px solid var(--accent)" : "1px solid transparent",
                fontFamily:   "'IBM Plex Mono', monospace",
                letterSpacing: "0.05em",
              }}
            >
              <Icon size={12} />
              {label}
            </button>
          ))}
        </div>

        {/* Upload dropzone */}
        {inputMode === "upload" && (
          <div>
            <div
              {...getRootProps()}
              className={cn("drop-zone p-6 text-center cursor-pointer", isDragActive && "drop-zone-active")}
            >
              <input {...getInputProps()} />
              <Upload size={24} className="mx-auto mb-2" style={{ color: "var(--t3)", opacity: 0.6 }} />
              <p className="text-sm font-medium" style={{ color: "var(--t1)" }}>
                {isDragActive ? t("voice.cloneModal.dropHint") : t("voice.uploadSamples")}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--t3)" }}>
                {t("voice.cloneModal.uploadHint")}
              </p>
            </div>
            {uploadFiles.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {uploadFiles.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 px-3 py-2 text-xs"
                    style={{ background: "var(--s2)", borderRadius: "var(--r-btn)" }}
                  >
                    <CheckCircle2 size={12} style={{ color: "var(--green)" }} className="shrink-0" />
                    <span className="flex-1 truncate" style={{ color: "var(--t1)" }}>{f.name}</span>
                    <span style={{ color: "var(--t3)", fontFamily: "'IBM Plex Mono', monospace" }}>{(f.size / 1024 / 1024).toFixed(1)}MB</span>
                    <button
                      onClick={() => setUploadFiles((p) => p.filter((_, j) => j !== i))}
                      className="hover:text-red-500 transition-colors"
                      style={{ color: "var(--t3)" }}
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
            className="p-5 text-center space-y-4"
            style={{ background: "var(--s2)", borderRadius: "var(--r-card)", border: "0.5px solid var(--border-rest)" }}
          >
            <WaveformBars active={recorder.recording} values={recorder.waveValues} />

            <div
              className="flex items-center justify-center gap-1 text-sm tabular-nums"
              style={{ color: recorder.recording ? "var(--red)" : "var(--t3)", fontFamily: "'IBM Plex Mono', monospace" }}
            >
              {recorder.recording && <Radio size={13} className="animate-pulse" style={{ color: "var(--red)" }} />}
              {formatDuration(recorder.durationSec)}
            </div>

            {!recorder.recording && !recorder.audioBlob ? (
              <button
                onClick={recorder.start}
                className="btn-primary mx-auto"
              >
                <Mic size={14} />
                {t("voice.cloneModal.startRecording")}
              </button>
            ) : recorder.recording ? (
              <button
                onClick={recorder.stop}
                className="mx-auto inline-flex items-center gap-2"
                style={{
                  padding: "9px 16px",
                  borderRadius: "var(--r-btn)",
                  border: "0.5px solid var(--red)",
                  background: "rgba(224,80,80,0.08)",
                  color: "var(--red)",
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: "12px",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                <StopCircle size={14} />
                {t("voice.cloneModal.stopRecording")}
              </button>
            ) : (
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={() => { const url = URL.createObjectURL(recorder.audioBlob!); new Audio(url).play(); }}
                  className="btn-secondary"
                >
                  <Play size={13} />
                  {t("voice.cloneModal.playRecording")}
                </button>
                <button
                  onClick={recorder.clear}
                  className="btn-ghost hover:text-red-500"
                >
                  <Trash2 size={13} />
                  {t("voice.cloneModal.deleteRecording")}
                </button>
              </div>
            )}

            {recorder.audioBlob && (
              <p className="text-xs flex items-center justify-center gap-1" style={{ color: "var(--green)" }}>
                <CheckCircle2 size={12} />
                {t("voice.cloneModal.recordingReady")} ({formatDuration(recorder.durationSec)})
              </p>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-3 pt-1">
          <button onClick={handleClose} className="btn-secondary flex-1">
            {t("common.cancel")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="btn-primary flex-1"
          >
            {isPending
              ? <><Loader2 size={14} className="animate-spin" /> {t("voice.cloneModal.submitting")}</>
              : <><Mic size={14} /> {t("voice.cloneModal.startClone")}</>
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
            { labelKey: "voice.totalModels",  value: voices.length,   Icon: Volume2,     iconColor: "var(--accent)" },
            { labelKey: "voice.status.ready", value: readyCount,      Icon: CheckCircle2, iconColor: "var(--green)"  },
            { labelKey: "voice.processing",   value: processingCount, Icon: Loader2,      iconColor: "var(--amber)"  },
          ] as const).map(({ labelKey, value, Icon, iconColor }) => (
            <div key={labelKey} className="stat-card">
              <div className="stat-icon" style={{ color: iconColor }}>
                <Icon size={14} className={labelKey === "voice.processing" && processingCount > 0 ? "animate-spin" : ""} />
              </div>
              <div>
                <p className="text-lg font-bold" style={{ color: "var(--t1)", fontFamily: "'IBM Plex Mono', monospace" }}>{value}</p>
                <p className="text-xs" style={{ color: "var(--t2)" }}>{t(labelKey)}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Voice grid / empty state */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="skeleton h-36" />
          ))}
        </div>
      ) : voices.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div
            className="w-16 h-16 flex items-center justify-center mb-5"
            style={{ background: "var(--accent-bg)", border: "0.5px solid var(--accent-md)", borderRadius: "var(--r-card)" }}
          >
            <Mic size={28} style={{ color: "var(--accent)" }} />
          </div>
          <h2 className="text-lg font-bold mb-2" style={{ color: "var(--t1)" }}>
            {t("voice.noVoices")}
          </h2>
          <p className="text-sm mb-6 max-w-xs" style={{ color: "var(--t2)" }}>
            {t("voice.noVoicesHint")}
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary">
            <Plus size={14} />
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
