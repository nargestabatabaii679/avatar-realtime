import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, ChevronLeft, Play, Download, Trash2, CheckCircle, Loader2 } from "lucide-react";
import { api } from "../../services/api";
import { cn } from "../../utils/cn";
import { useThemeStore } from "../../stores/themeStore";

const STEPS = ["Select Avatar", "Select Voice", "Write Script", "Configure", "Generate"];
const RESOLUTIONS = ["720p", "1080p", "4k"];
const LANGUAGES = [
  { code: "fa", label: "Persian (فارسی)" },
  { code: "en", label: "English" },
  { code: "ar", label: "Arabic (العربية)" },
  { code: "tr", label: "Turkish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
];

export default function VideoStudioPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { language: uiLang } = useThemeStore();
  const isRTL = ["fa", "ar"].includes(uiLang);

  const [step, setStep] = useState(0);
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(null);
  const [selectedVoice, setSelectedVoice] = useState<string | null>(null);
  const [script, setScript] = useState("");
  const [resolution, setResolution] = useState("1080p");
  const [language, setLanguage] = useState(uiLang === "fa" ? "fa" : "en");
  const [title, setTitle] = useState("");
  const [generatingId, setGeneratingId] = useState<string | null>(null);

  const { data: avatars } = useQuery({
    queryKey: ["avatars", "ready"],
    queryFn: () => api.get("/avatars?status=ready").then((r) => r.data),
  });

  const { data: voices } = useQuery({
    queryKey: ["voices", "ready"],
    queryFn: () => api.get("/voices?status=ready").then((r) => r.data),
  });

  const { data: videos } = useQuery({
    queryKey: ["videos"],
    queryFn: () => api.get("/videos?limit=20").then((r) => r.data),
    refetchInterval: generatingId ? 5000 : false,
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      api.post("/videos/generate", {
        avatar_id: selectedAvatar,
        voice_model_id: selectedVoice,
        script,
        language,
        resolution,
        title: title || "My Video",
      }),
    onSuccess: (res) => {
      setGeneratingId(res.data.video_id);
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      setStep(4);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/videos/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["videos"] }),
  });

  const readyAvatars = avatars?.items || [];
  const readyVoices = voices?.items || [];
  const videoList = videos?.items || [];

  const canProceed = [
    !!selectedAvatar,
    !!selectedVoice,
    script.trim().length > 10,
    true,
    true,
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("video.title")}</h1>
        <p className="text-muted-foreground text-sm mt-1">Create professional talking avatar videos</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Wizard */}
        <div className="lg:col-span-2 bg-card border border-border rounded-xl overflow-hidden">
          {/* Step indicators */}
          <div className="flex border-b border-border">
            {STEPS.map((s, i) => (
              <button
                key={i}
                onClick={() => i < step && setStep(i)}
                className={cn(
                  "flex-1 px-2 py-3 text-xs font-medium transition-colors",
                  step === i ? "bg-primary text-primary-foreground" :
                  i < step ? "text-primary bg-primary/10 cursor-pointer" :
                  "text-muted-foreground cursor-default"
                )}
              >
                <span className="hidden sm:inline">{s}</span>
                <span className="sm:hidden">{i + 1}</span>
              </button>
            ))}
          </div>

          <div className="p-6">
            {/* Step 0: Select Avatar */}
            {step === 0 && (
              <div className="space-y-4">
                <h2 className="font-semibold text-foreground">{t("video.selectAvatar")}</h2>
                {readyAvatars.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No ready avatars. Create one in Avatar Studio first.</p>
                ) : (
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                    {readyAvatars.map((a: any) => (
                      <button
                        key={a.id}
                        onClick={() => setSelectedAvatar(a.id)}
                        className={cn(
                          "rounded-xl overflow-hidden border-2 transition-all",
                          selectedAvatar === a.id ? "border-primary ring-2 ring-primary/30" : "border-border hover:border-primary/50"
                        )}
                      >
                        <div className="aspect-square bg-muted">
                          {a.thumbnail_url ? (
                            <img src={a.thumbnail_url} alt={a.name} className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-muted-foreground">
                              {a.name.charAt(0)}
                            </div>
                          )}
                        </div>
                        <p className="text-xs p-1 text-center truncate text-foreground">{a.name}</p>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Step 1: Select Voice */}
            {step === 1 && (
              <div className="space-y-4">
                <h2 className="font-semibold text-foreground">{t("video.selectVoice")}</h2>
                {readyVoices.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No voice models. Create one in Voice Studio first.</p>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {readyVoices.map((v: any) => (
                      <button
                        key={v.id}
                        onClick={() => setSelectedVoice(v.id)}
                        className={cn(
                          "flex items-center gap-3 p-4 rounded-xl border-2 text-start transition-all",
                          selectedVoice === v.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                        )}
                      >
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-teal-500 flex items-center justify-center text-white font-bold">
                          {v.name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-medium text-foreground text-sm">{v.name}</p>
                          <p className="text-xs text-muted-foreground uppercase">{v.language}</p>
                        </div>
                        {selectedVoice === v.id && <CheckCircle size={16} className="text-primary ms-auto" />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Step 2: Script */}
            {step === 2 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-foreground">{t("video.writeScript")}</h2>
                  <span className="text-xs text-muted-foreground">{script.length} chars</span>
                </div>
                <textarea
                  value={script}
                  onChange={(e) => setScript(e.target.value)}
                  dir={isRTL ? "rtl" : "ltr"}
                  placeholder={isRTL ? "اسکریپت خود را اینجا بنویسید…" : "Write your script here…"}
                  className="w-full h-64 px-4 py-3 bg-muted border border-border rounded-xl text-foreground text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <p className="text-xs text-muted-foreground">
                  Tip: {isRTL ? "حداکثر ۵۰۰ کلمه برای بهترین نتیجه" : "Up to 500 words for best results"}
                </p>
              </div>
            )}

            {/* Step 3: Configure */}
            {step === 3 && (
              <div className="space-y-5">
                <h2 className="font-semibold text-foreground">{t("video.configure")}</h2>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Video Title</label>
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="My Video"
                    className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">{t("video.resolution")}</label>
                  <div className="flex gap-2">
                    {RESOLUTIONS.map((r) => (
                      <button
                        key={r}
                        onClick={() => setResolution(r)}
                        className={cn(
                          "px-4 py-2 rounded-lg text-sm font-medium border transition-colors",
                          resolution === r ? "bg-primary text-primary-foreground border-primary" : "border-border text-foreground hover:border-primary/50"
                        )}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">{t("video.language")}</label>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-foreground focus:outline-none"
                  >
                    {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
                  </select>
                </div>
              </div>
            )}

            {/* Step 4: Generating */}
            {step === 4 && (
              <div className="text-center py-12">
                {generateMutation.isPending || generatingId ? (
                  <>
                    <div className="w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                      <Loader2 size={36} className="text-primary animate-spin" />
                    </div>
                    <h3 className="font-semibold text-foreground text-lg">{t("video.generating")}</h3>
                    <p className="text-muted-foreground text-sm mt-2">Processing: TTS → Lip Sync → Rendering…</p>
                    <div className="mt-6 progress-bar max-w-xs mx-auto">
                      <div className="progress-fill animate-pulse-slow" style={{ width: "60%" }} />
                    </div>
                  </>
                ) : (
                  <>
                    <CheckCircle size={48} className="text-green-500 mx-auto mb-4" />
                    <h3 className="font-semibold text-foreground text-lg">Video Ready!</h3>
                    <p className="text-muted-foreground text-sm mt-2">Your video has been generated successfully.</p>
                  </>
                )}
              </div>
            )}

            {/* Navigation */}
            <div className="flex justify-between mt-6 pt-6 border-t border-border">
              <button
                onClick={() => setStep(Math.max(0, step - 1))}
                disabled={step === 0}
                className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg text-sm hover:bg-accent transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {isRTL ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                Back
              </button>
              {step < 3 ? (
                <button
                  onClick={() => setStep(step + 1)}
                  disabled={!canProceed[step]}
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                  {isRTL ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
                </button>
              ) : step === 3 ? (
                <button
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                  className="flex items-center gap-2 px-6 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-all"
                >
                  {generateMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                  {t("video.generate")}
                </button>
              ) : null}
            </div>
          </div>
        </div>

        {/* Video Library */}
        <div className="bg-card border border-border rounded-xl p-5">
          <h2 className="font-semibold text-foreground mb-4">Video Library</h2>
          <div className="space-y-3 max-h-[600px] overflow-y-auto scrollbar-thin">
            {videoList.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">{t("video.noVideos")}</p>
            ) : videoList.map((video: any) => (
              <div key={video.id} className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-accent/50 transition-colors">
                <div className="w-14 h-10 rounded bg-muted overflow-hidden shrink-0">
                  {video.thumbnail_url ? (
                    <img src={video.thumbnail_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Play size={14} className="text-muted-foreground" />
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{video.title || "Untitled"}</p>
                  <p className="text-xs text-muted-foreground">{video.status} • {video.resolution}</p>
                </div>
                <div className="flex items-center gap-1">
                  {video.status === "completed" && (
                    <a
                      href={`/api/v1/videos/${video.id}/download`}
                      className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground"
                    >
                      <Download size={14} />
                    </a>
                  )}
                  <button
                    onClick={() => deleteMutation.mutate(video.id)}
                    className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-red-500"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
