import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, Sparkles, Zap, Shield } from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../utils/cn";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type FormData = z.infer<typeof schema>;

const features = [
  { icon: Sparkles, text: "Realistic AI Avatars" },
  { icon: Zap, text: "Real-time < 1.2s Latency" },
  { icon: Shield, text: "Enterprise Security" },
];

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      await login(data.email, data.password);
      navigate("/dashboard");
    } catch (e: any) {
      setError(e.message || "Invalid credentials. Please try again.");
    }
  };

  return (
    <div className="min-h-screen flex overflow-hidden">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col justify-between p-12 bg-mesh overflow-hidden">
        {/* Animated orbs */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(99,102,241,0.3) 0%, transparent 70%)", animation: "float 6s ease-in-out infinite" }} />
          <div className="absolute bottom-[-5%] right-[-5%] w-[400px] h-[400px] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(168,85,247,0.25) 0%, transparent 70%)", animation: "float 8s ease-in-out infinite reverse" }} />
          <div className="absolute top-[40%] right-[10%] w-[300px] h-[300px] rounded-full"
            style={{ background: "radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)", animation: "float 5s ease-in-out infinite 1s" }} />
          {/* Grid pattern */}
          <div className="absolute inset-0 opacity-[0.04]"
            style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.3) 1px, transparent 1px)", backgroundSize: "60px 60px" }} />
        </div>

        {/* Logo */}
        <div className="relative z-10 animate-fade-in-down">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" }}>
              <span className="text-white font-black text-lg">A</span>
            </div>
            <span className="text-white font-bold text-lg tracking-tight">Avatar Platform</span>
          </div>
        </div>

        {/* Hero text */}
        <div className="relative z-10 animate-fade-in-up" style={{ animationDelay: ".1s" }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-6 text-xs font-medium text-indigo-300"
            style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            AI Digital Human Platform
          </div>

          <h1 className="text-5xl xl:text-6xl font-extrabold text-white leading-tight mb-6">
            Create{" "}
            <span className="relative">
              <span className="gradient-text bg-gradient-to-r from-indigo-300 via-purple-300 to-pink-300">
                Lifelike
              </span>
            </span>
            {" "}AI Avatars
          </h1>

          <p className="text-lg text-indigo-200/80 leading-relaxed max-w-md mb-10">
            Build, train, and deploy realistic talking avatars with real-time conversational AI.
            Self-hosted. GPU-accelerated. RTL-ready.
          </p>

          {/* Feature pills */}
          <div className="flex flex-col gap-3">
            {features.map(({ icon: Icon, text }, i) => (
              <div key={text} className="flex items-center gap-3 animate-fade-in" style={{ animationDelay: `${.2 + i * .08}s` }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(99,102,241,0.2)", border: "1px solid rgba(99,102,241,0.3)" }}>
                  <Icon size={15} className="text-indigo-300" />
                </div>
                <span className="text-indigo-100/90 text-sm font-medium">{text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom quote */}
        <div className="relative z-10 animate-fade-in" style={{ animationDelay: ".5s" }}>
          <p className="text-white/30 text-xs">© 2024 Avatar Platform — Enterprise AI Communications</p>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 bg-background relative">
        {/* Mobile logo */}
        <div className="lg:hidden mb-8 text-center animate-fade-in">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-3"
            style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary)" }}>
            <span className="text-white font-black text-xl">A</span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">Avatar Platform</h1>
        </div>

        <div className="w-full max-w-[400px] animate-fade-in-up" style={{ animationDelay: ".05s" }}>
          {/* Header */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-foreground">Welcome back</h2>
            <p className="text-muted-foreground mt-1.5 text-sm">Sign in to your account to continue</p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-5 p-3.5 rounded-xl flex items-start gap-3 animate-scale-in"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
              <div className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-red-500 text-xs font-bold">!</span>
              </div>
              <p className="text-red-500 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-foreground">
                {t("auth.email")}
              </label>
              <input
                type="email"
                autoComplete="email"
                {...register("email")}
                className={cn(
                  "input-field",
                  errors.email && "border-red-500 focus:border-red-500"
                )}
                placeholder="you@company.com"
              />
              {errors.email && (
                <p className="text-xs text-red-500 flex items-center gap-1">
                  <span>·</span> {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-foreground">
                  {t("auth.password")}
                </label>
                <a href="#" className="text-xs text-primary hover:text-primary/80 transition-colors">
                  {t("auth.forgotPassword")}
                </a>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  {...register("password")}
                  className={cn(
                    "input-field pe-11",
                    errors.password && "border-red-500 focus:border-red-500"
                  )}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3.5 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-red-500 flex items-center gap-1">
                  <span>·</span> {errors.password.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-primary w-full mt-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                t("auth.login")
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Register link */}
          <p className="text-center text-sm text-muted-foreground">
            {t("auth.noAccount")}{" "}
            <a href="#" className="text-primary font-medium hover:text-primary/80 transition-colors">
              {t("auth.register")}
            </a>
          </p>

          <p className="text-center text-xs text-muted-foreground/50 mt-8">
            © 2024 Avatar Platform
          </p>
        </div>
      </div>
    </div>
  );
}
