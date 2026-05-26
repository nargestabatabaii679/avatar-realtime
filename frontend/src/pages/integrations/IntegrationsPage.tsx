import { useState, useEffect } from "react";
import {
  Key, CheckCircle, XCircle, Save, Eye, EyeOff, Info,
  Plug, Zap, Sparkles, Globe,
} from "lucide-react";
import { cn } from "../../utils/cn";

/* ─── Types ──────────────────────────────────────────────────── */
interface ServiceConfig {
  id: string;
  name: string;
  description: string;
  icon: string;
  iconColor: string;
  placeholder: string;
  docsUrl: string;
}

interface IntegrationState {
  [serviceId: string]: {
    apiKey: string;
    connected: boolean;
  };
}

const STORAGE_KEY = "avatar_integrations";

/* ─── Service definitions ────────────────────────────────────── */
const SERVICES: ServiceConfig[] = [
  {
    id: "heygen",
    name: "HeyGen",
    description: "ساخت ویدیوهای آواتار با هوش مصنوعی - لیپ‌سینک و تولید آواتار واقعی‌نما",
    icon: "🎬",
    iconColor: "#6366f1",
    placeholder: "hg_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    docsUrl: "https://docs.heygen.com",
  },
  {
    id: "syncso",
    name: "Sync.so",
    description: "همگام‌سازی صدا با ویدیو - سینک دقیق لب‌ها با فایل صوتی",
    icon: "⚡",
    iconColor: "#06b6d4",
    placeholder: "sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    docsUrl: "https://sync.so/docs",
  },
  {
    id: "minimax",
    name: "MiniMax",
    description: "تولید تصویر و ویدیو با MiniMax AI - مدل‌های پیشرفته چینی",
    icon: "🔮",
    iconColor: "#8b5cf6",
    placeholder: "mm_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    docsUrl: "https://minimax.chat",
  },
  {
    id: "googleflow",
    name: "Google Flow",
    description: "سرویس‌های هوش مصنوعی Google - Vertex AI و Gemini برای تولید محتوا",
    icon: "🌐",
    iconColor: "#10b981",
    placeholder: "AIza_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    docsUrl: "https://cloud.google.com/vertex-ai",
  },
];

/* ─── Single service card ─────────────────────────────────────── */
function ServiceCard({
  service,
  apiKey,
  connected,
  onSave,
}: {
  service: ServiceConfig;
  apiKey: string;
  connected: boolean;
  onSave: (id: string, key: string) => void;
}) {
  const [inputValue, setInputValue] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    onSave(service.id, inputValue.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const hasKey = inputValue.trim().length > 0;
  const isDirty = inputValue !== apiKey;

  return (
    <div className="card-premium p-5 flex flex-col gap-4 animate-fade-in-up">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center text-2xl shrink-0 border border-border"
            style={{ backgroundColor: `${service.iconColor}15` }}
          >
            {service.icon}
          </div>
          <div>
            <h3 className="font-bold text-foreground text-base">{service.name}</h3>
            <p className="text-xs text-muted-foreground leading-relaxed mt-0.5 max-w-xs">
              {service.description}
            </p>
          </div>
        </div>

        {/* Status badge */}
        <div className="shrink-0">
          {connected ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-semibold border border-emerald-500/20">
              <CheckCircle size={12} />
              متصل
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted text-muted-foreground text-xs font-semibold border border-border">
              <XCircle size={12} />
              قطع
            </div>
          )}
        </div>
      </div>

      {/* API Key input */}
      <div className="space-y-2">
        <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <Key size={10} />
          کلید API
        </label>
        <div className="relative flex gap-2">
          <div className="relative flex-1">
            <input
              type={showKey ? "text" : "password"}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={service.placeholder}
              className="input-field text-sm pe-10 font-mono"
              dir="ltr"
            />
            <button
              onClick={() => setShowKey(!showKey)}
              className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              tabIndex={-1}
            >
              {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <button
            onClick={handleSave}
            disabled={!isDirty && connected}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold transition-all shrink-0",
              saved
                ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                : hasKey
                ? "btn-primary"
                : "btn-secondary opacity-50 cursor-not-allowed"
            )}
          >
            {saved ? (
              <><CheckCircle size={13} />ذخیره شد</>
            ) : (
              <><Save size={13} />ذخیره</>
            )}
          </button>
        </div>
      </div>

      {/* Docs link */}
      <a
        href={service.docsUrl}
        target="_blank"
        rel="noreferrer"
        className="text-[11px] text-primary hover:underline flex items-center gap-1 w-fit"
      >
        <Info size={10} />
        مستندات {service.name}
      </a>
    </div>
  );
}

/* ─── Main page ──────────────────────────────────────────────── */
export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<IntegrationState>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch {}
    return {};
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(integrations));
  }, [integrations]);

  const handleSave = (serviceId: string, key: string) => {
    setIntegrations((prev) => ({
      ...prev,
      [serviceId]: {
        apiKey: key,
        connected: key.length > 0,
      },
    }));
  };

  const connectedCount = Object.values(integrations).filter((v) => v.connected).length;

  return (
    <div dir="rtl" className="flex flex-col gap-6 pb-8 animate-fade-in">

      {/* ═══ PAGE HEADER ═══════════════════════════════════════════ */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "var(--gradient-teal)", boxShadow: "0 6px 20px rgba(6,182,212,.38)" }}
            >
              <Plug size={18} className="text-white" />
            </div>
            <h1 className="text-xl font-bold text-foreground">ادغام‌های خارجی</h1>
          </div>
          <p className="text-sm text-muted-foreground mr-13">
            API کلیدهای سرویس‌های ابری را مدیریت کنید
          </p>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-xs font-semibold border border-primary/20">
            <Zap size={12} />
            {connectedCount} از {SERVICES.length} متصل
          </div>
        </div>
      </div>

      {/* ═══ SECURITY NOTE ════════════════════════════════════════ */}
      <div className="flex items-start gap-3 p-4 rounded-2xl bg-amber-500/8 border border-amber-500/20 animate-fade-in-up">
        <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0 mt-0.5">
          <Key size={15} className="text-amber-600 dark:text-amber-400" />
        </div>
        <div>
          <p className="text-sm font-semibold text-amber-700 dark:text-amber-300 mb-0.5">
            کلیدها فقط در مرورگر شما ذخیره می‌شوند
          </p>
          <p className="text-xs text-amber-600/80 dark:text-amber-400/70 leading-relaxed">
            کلیدهای API در localStorage مرورگر ذخیره می‌شوند و هیچ‌گاه به سرور ارسال نمی‌شوند.
            از اشتراک‌گذاری مرورگر با دیگران خودداری کنید.
          </p>
        </div>
      </div>

      {/* ═══ SERVICE CARDS ════════════════════════════════════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {SERVICES.map((service) => (
          <ServiceCard
            key={service.id}
            service={service}
            apiKey={integrations[service.id]?.apiKey ?? ""}
            connected={integrations[service.id]?.connected ?? false}
            onSave={handleSave}
          />
        ))}
      </div>

      {/* ═══ COMING SOON ══════════════════════════════════════════ */}
      <div className="card-premium p-5 opacity-60">
        <div className="flex items-center gap-3 mb-4">
          <Sparkles size={16} className="text-primary" />
          <p className="text-sm font-bold text-foreground">سرویس‌های در راه</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {["ElevenLabs", "D-ID", "RunwayML", "Pika Labs", "Stable Diffusion", "OpenAI Sora"].map((name) => (
            <span
              key={name}
              className="px-3 py-1.5 rounded-lg border border-dashed border-border text-xs text-muted-foreground"
            >
              {name}
            </span>
          ))}
        </div>
      </div>

    </div>
  );
}
