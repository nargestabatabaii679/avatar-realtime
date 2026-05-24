import { useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Mic, Play, Trash2, Upload, CheckCircle, Loader2, Plus } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";

const LANGUAGES = [
  { code: "fa", label: "Persian (فارسی)" }, { code: "en", label: "English" },
  { code: "ar", label: "Arabic" }, { code: "tr", label: "Turkish" },
  { code: "fr", label: "French" }, { code: "de", label: "German" },
];

export default function VoiceStudioPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState("fa");
  const [files, setFiles] = useState<File[]>([]);
  const [testText, setTestText] = useState("");
  const [testingVoiceId, setTestingVoiceId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["voices"],
    queryFn: () => api.get("/voices").then((r) => r.data),
    refetchInterval: 15000,
  });

  const cloneMutation = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.append("name", name);
      form.append("language", language);
      files.forEach((f) => form.append("samples[]", f));
      return api.post("/voices/clone", form, { headers: { "Content-Type": "multipart/form-data" } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voices"] });
      setShowCreate(false); setName(""); setFiles([]);
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
      setTestingVoiceId(null);
    },
  });

  const onDrop = useCallback((dropped: File[]) => {
    setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { "audio/*": [".wav", ".mp3", ".flac", ".m4a"] }, multiple: true,
  });

  const voices = data?.items || [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("voice.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">Clone your voice in 6 languages</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus size={16} /> {t("voice.create")}
        </button>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-card border border-border rounded-2xl p-6 w-full max-w-lg animate-fade-in">
            <h2 className="text-lg font-semibold text-foreground mb-4">Clone Voice</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Voice Name</label>
                <input value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="My Voice Clone"
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">{t("voice.language")}</label>
                <select value={language} onChange={(e) => setLanguage(e.target.value)}
                  className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                >
                  {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                </select>
              </div>
              <div {...getRootProps()} className={cn(
                "border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors",
                isDragActive ? "drop-zone-active" : "border-border hover:border-primary/50"
              )}>
                <input {...getInputProps()} />
                <Upload size={28} className="mx-auto mb-2 text-muted-foreground opacity-50" />
                <p className="text-sm font-medium text-foreground">{t("voice.uploadSamples")}</p>
                <p className="text-xs text-muted-foreground mt-1">WAV, MP3, FLAC — min 30 seconds total</p>
              </div>
              {files.length > 0 && (
                <div className="space-y-1">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
                      <CheckCircle size={12} className="text-green-500" />
                      <span className="truncate">{f.name}</span>
                      <span>({(f.size / 1024 / 1024).toFixed(1)}MB)</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button onClick={() => setShowCreate(false)}
                  className="flex-1 py-2 px-4 border border-border rounded-lg text-sm hover:bg-accent transition-colors"
                >{t("common.cancel")}</button>
                <button onClick={() => cloneMutation.mutate()}
                  disabled={!name || files.length === 0 || cloneMutation.isPending}
                  className="flex-1 py-2 px-4 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {cloneMutation.isPending ? <><Loader2 size={14} className="animate-spin" /> {t("voice.cloning")}</> : t("voice.create")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Voice Models Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-32 skeleton rounded-xl" />
          ))}
        </div>
      ) : voices.length === 0 ? (
        <div className="text-center py-20">
          <Mic size={40} className="mx-auto mb-3 text-muted-foreground opacity-40" />
          <p className="text-sm text-muted-foreground">{t("voice.noVoices")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {voices.map((voice: any) => (
            <div key={voice.id} className="bg-card border border-border rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-teal-500 flex items-center justify-center text-white font-bold">
                    {voice.name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-medium text-foreground">{voice.name}</h3>
                    <p className="text-xs text-muted-foreground uppercase">{voice.language} · {voice.tts_engine}</p>
                  </div>
                </div>
                <button onClick={() => deleteMutation.mutate(voice.id)}
                  className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-red-500 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>

              {/* Status */}
              <div className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium mb-3",
                voice.status === "ready" ? "text-green-500 bg-green-500/10" :
                voice.status === "cloning" ? "text-yellow-500 bg-yellow-500/10" : "text-red-500 bg-red-500/10"
              )}>
                <div className={cn("w-1.5 h-1.5 rounded-full", voice.status === "ready" ? "bg-green-500" : voice.status === "cloning" ? "bg-yellow-500 animate-pulse" : "bg-red-500")} />
                {voice.status === "ready" ? "Ready" : voice.status === "cloning" ? "Cloning…" : "Failed"}
              </div>

              {/* Test voice */}
              {voice.status === "ready" && (
                <div className="flex gap-2">
                  <input
                    value={testingVoiceId === voice.id ? testText : ""}
                    onChange={(e) => { setTestText(e.target.value); setTestingVoiceId(voice.id); }}
                    placeholder={t("voice.enterTestText")}
                    className="flex-1 px-2 py-1.5 bg-muted border border-border rounded-lg text-xs text-foreground focus:outline-none"
                  />
                  <button
                    onClick={() => testMutation.mutate({ voiceId: voice.id, text: testText || "Hello!" })}
                    disabled={testMutation.isPending}
                    className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs hover:bg-primary/90 transition-colors"
                  >
                    <Play size={12} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
