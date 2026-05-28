import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, Zap, Shield, Globe, User, Mail, Lock } from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../utils/cn";

const loginSchema = z.object({
  email: z.string().email("ایمیل نامعتبر"),
  password: z.string().min(6, "رمز باید حداقل ۶ کاراکتر باشد"),
});

const registerSchema = z.object({
  full_name: z.string().min(2, "نام باید حداقل ۲ کاراکتر باشد"),
  email: z.string().email("ایمیل نامعتبر"),
  password: z.string()
    .min(8, "رمز باید حداقل ۸ کاراکتر باشد")
    .regex(/[A-Z]/, "باید حداقل یک حرف بزرگ داشته باشد")
    .regex(/[0-9]/, "باید حداقل یک عدد داشته باشد")
    .regex(/[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?]/, "باید حداقل یک کاراکتر خاص داشته باشد"),
});

type LoginData = z.infer<typeof loginSchema>;
type RegisterData = z.infer<typeof registerSchema>;

const features = [
  { icon: "🎭", title: "آواتار واقعی",   desc: "تبدیل عکس به آواتار سخنگو با هوش مصنوعی" },
  { icon: "🗣️", title: "صدای طبیعی",    desc: "کلونینگ صدا با XTTS-v2 بهینه برای فارسی" },
  { icon: "⚡", title: "لیپ‌سینک ۵۰fps", desc: "حرکات طبیعی لب، پلک و میکروحالت‌ها" },
  { icon: "🌐", title: "چندزبانه",       desc: "فارسی، انگلیسی، عربی، ترکی و بیشتر" },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register: registerUser } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [showPw, setShowPw] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loginForm = useForm<LoginData>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterData>({ resolver: zodResolver(registerSchema) });

  const onLogin = async (data: LoginData) => {
    setErr(null);
    try {
      await login({ email: data.email, password: data.password });
      navigate("/dashboard");
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setErr(typeof detail === "string" ? detail : "ایمیل یا رمز عبور اشتباه است");
    }
  };

  const onRegister = async (data: RegisterData) => {
    setErr(null);
    try {
      await registerUser({ email: data.email, password: data.password, full_name: data.full_name });
      navigate("/dashboard");
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      setErr(typeof detail === "string" ? detail : "خطا در ثبت‌نام. لطفاً دوباره تلاش کنید");
    }
  };

  const switchMode = (m: "login" | "register") => {
    setMode(m);
    setErr(null);
    loginForm.reset();
    registerForm.reset();
  };

  return (
    <div className="min-h-screen flex overflow-hidden bg-background">

      {/* ─── Left: Cinematic Panel ─── */}
      <div className="hidden lg:flex lg:w-[54%] relative flex-col bg-mesh noise overflow-hidden">
        <div className="absolute inset-0 grid-pattern opacity-40 pointer-events-none" />

        {/* Floating orbs */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute top-[-8%] left-[-8%] w-[520px] h-[520px] rounded-full opacity-30"
            style={{ background: "radial-gradient(circle, #6366f1 0%, transparent 70%)", animation: "float 7s ease-in-out infinite" }} />
          <div className="absolute bottom-[-6%] right-[-6%] w-[420px] h-[420px] rounded-full opacity-25"
            style={{ background: "radial-gradient(circle, #a855f7 0%, transparent 70%)", animation: "float 9s ease-in-out infinite reverse" }} />
          <div className="absolute top-[45%] right-[8%] w-[280px] h-[280px] rounded-full opacity-20"
            style={{ background: "radial-gradient(circle, #3b82f6 0%, transparent 70%)", animation: "float 6s ease-in-out infinite 1.5s" }} />
        </div>

        <div className="relative z-10 flex flex-col h-full p-12">
          {/* Logo */}
          <div className="flex items-center gap-3 animate-fade-in-down">
            <div className="w-11 h-11 rounded-2xl flex items-center justify-center"
              style={{ background: "var(--gradient-primary)", boxShadow: "0 0 32px rgba(91,95,239,.6)" }}>
              <span className="text-white font-black text-xl">A</span>
            </div>
            <div>
              <p className="text-white font-bold text-base leading-none">Avatar</p>
              <p className="text-white/50 text-xs leading-none mt-0.5">AI Platform</p>
            </div>
          </div>

          <div className="flex-1 flex flex-col justify-center animate-fade-in-up" style={{ animationDelay: ".1s" }}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-7 w-fit"
              style={{ background: "rgba(91,95,239,.18)", border: "1px solid rgba(91,95,239,.35)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-indigo-200 text-xs font-medium">هوش مصنوعی نسل جدید</span>
            </div>

            <h1 className="text-5xl xl:text-6xl font-black text-white leading-[1.1] mb-6">
              ساخت<br />
              <span className="gradient-text" style={{ backgroundImage: "linear-gradient(135deg, #a5b4fc 0%, #c4b5fd 50%, #f0abfc 100%)" }}>
                آواتار
              </span>
              <br />سخن‌گو
            </h1>

            <p className="text-indigo-200/70 text-base leading-relaxed max-w-sm mb-10">
              عکس انسان را آپلود کنید، متن بنویسید،<br />
              ویدیوی آواتار سخنگو بسازید — مثل D-ID و HeyGen
            </p>

            <div className="grid grid-cols-2 gap-3">
              {features.map(({ icon, title, desc }, i) => (
                <div key={title}
                  className="p-3.5 rounded-2xl animate-fade-in-up"
                  style={{
                    animationDelay: `${.2 + i * .07}s`,
                    background: "rgba(255,255,255,.05)",
                    border: "1px solid rgba(255,255,255,.08)",
                    backdropFilter: "blur(12px)",
                  }}>
                  <div className="text-2xl mb-1.5">{icon}</div>
                  <p className="text-white text-sm font-bold mb-0.5">{title}</p>
                  <p className="text-white/50 text-xs leading-relaxed">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="text-white/20 text-xs">© 2024 Avatar Platform · پلتفرم آواتار هوش مصنوعی</p>
        </div>
      </div>

      {/* ─── Right: Form Panel ─── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden">
        <div className="absolute inset-0 grid-pattern opacity-30 pointer-events-none" />

        {/* Mobile logo */}
        <div className="lg:hidden mb-8 text-center animate-fade-in">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-3"
            style={{ background: "var(--gradient-primary)", boxShadow: "var(--shadow-primary-lg)" }}>
            <span className="text-white font-black text-xl">A</span>
          </div>
          <h1 className="text-2xl font-black text-foreground">Avatar Platform</h1>
        </div>

        <div className="relative z-10 w-full max-w-[400px]">

          {/* Mode toggle tabs */}
          <div className="flex bg-surface rounded-xl p-1 mb-7 border border-border">
            {(["login", "register"] as const).map((m) => (
              <button key={m}
                onClick={() => switchMode(m)}
                className={cn(
                  "flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-200",
                  mode === m
                    ? "bg-primary text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {m === "login" ? "ورود" : "ثبت‌نام"}
              </button>
            ))}
          </div>

          {/* Header */}
          <div className="mb-6">
            <h2 className="text-2xl font-black text-foreground">
              {mode === "login" ? "خوش آمدید" : "حساب جدید"}
            </h2>
            <p className="text-muted-foreground mt-1.5 text-sm">
              {mode === "login"
                ? "وارد حساب کاربری خود شوید"
                : "در چند ثانیه ثبت‌نام کنید و شروع کنید"}
            </p>
          </div>

          {/* Error */}
          {err && (
            <div className="mb-5 p-3.5 rounded-xl flex items-start gap-3 animate-scale-in"
              style={{ background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.2)" }}>
              <div className="w-5 h-5 rounded-full bg-red-500/15 flex items-center justify-center shrink-0 mt-0.5">
                <span className="text-red-500 text-xs font-black">!</span>
              </div>
              <p className="text-red-500 text-sm" dir="rtl">{err}</p>
            </div>
          )}

          {/* ── Login Form ── */}
          {mode === "login" && (
            <form onSubmit={loginForm.handleSubmit(onLogin)} className="space-y-4" dir="rtl">
              <div className="space-y-1.5">
                <label className="block text-sm font-semibold text-foreground">ایمیل</label>
                <div className="relative">
                  <Mail size={15} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <input type="email" autoComplete="email"
                    {...loginForm.register("email")}
                    className={cn("input-field text-left pr-10", loginForm.formState.errors.email && "border-red-500")}
                    placeholder="you@example.com" dir="ltr" />
                </div>
                {loginForm.formState.errors.email && (
                  <p className="text-xs text-red-500">{loginForm.formState.errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-sm font-semibold text-foreground">رمز عبور</label>
                  <button type="button" className="text-xs text-primary hover:text-primary/80 transition-colors">فراموشی رمز</button>
                </div>
                <div className="relative">
                  <Lock size={15} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <input
                    type={showPw ? "text" : "password"}
                    autoComplete="current-password"
                    {...loginForm.register("password")}
                    className={cn("input-field ps-11 pr-10", loginForm.formState.errors.password && "border-red-500")}
                    placeholder="••••••••" dir="ltr" />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute inset-y-0 start-0 flex items-center ps-3.5 text-muted-foreground hover:text-foreground transition-colors">
                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {loginForm.formState.errors.password && (
                  <p className="text-xs text-red-500">{loginForm.formState.errors.password.message}</p>
                )}
              </div>

              <button type="submit" disabled={loginForm.formState.isSubmitting} className="btn-primary w-full py-3 text-base mt-2">
                {loginForm.formState.isSubmitting
                  ? <><Loader2 size={16} className="animate-spin" /> در حال ورود…</>
                  : "ورود به حساب"}
              </button>

              <p className="text-center text-sm text-muted-foreground pt-1">
                حساب ندارید؟{" "}
                <button type="button" onClick={() => switchMode("register")}
                  className="text-primary font-bold hover:text-primary/80 transition-colors">
                  ثبت‌نام کنید
                </button>
              </p>
            </form>
          )}

          {/* ── Register Form ── */}
          {mode === "register" && (
            <form onSubmit={registerForm.handleSubmit(onRegister)} className="space-y-4" dir="rtl">
              <div className="space-y-1.5">
                <label className="block text-sm font-semibold text-foreground">نام کامل</label>
                <div className="relative">
                  <User size={15} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <input type="text" autoComplete="name"
                    {...registerForm.register("full_name")}
                    className={cn("input-field pr-10", registerForm.formState.errors.full_name && "border-red-500")}
                    placeholder="نام و نام خانوادگی" />
                </div>
                {registerForm.formState.errors.full_name && (
                  <p className="text-xs text-red-500">{registerForm.formState.errors.full_name.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="block text-sm font-semibold text-foreground">ایمیل</label>
                <div className="relative">
                  <Mail size={15} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <input type="email" autoComplete="email"
                    {...registerForm.register("email")}
                    className={cn("input-field text-left pr-10", registerForm.formState.errors.email && "border-red-500")}
                    placeholder="you@example.com" dir="ltr" />
                </div>
                {registerForm.formState.errors.email && (
                  <p className="text-xs text-red-500">{registerForm.formState.errors.email.message}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="block text-sm font-semibold text-foreground">رمز عبور</label>
                <div className="relative">
                  <Lock size={15} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <input
                    type={showPw ? "text" : "password"}
                    autoComplete="new-password"
                    {...registerForm.register("password")}
                    className={cn("input-field ps-11 pr-10", registerForm.formState.errors.password && "border-red-500")}
                    placeholder="حداقل ۸ کاراکتر" dir="ltr" />
                  <button type="button" onClick={() => setShowPw(!showPw)}
                    className="absolute inset-y-0 start-0 flex items-center ps-3.5 text-muted-foreground hover:text-foreground transition-colors">
                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {registerForm.formState.errors.password && (
                  <p className="text-xs text-red-500">{registerForm.formState.errors.password.message}</p>
                )}
                <p className="text-[11px] text-muted-foreground">
                  باید شامل حرف بزرگ، عدد و کاراکتر خاص باشد
                </p>
              </div>

              <button type="submit" disabled={registerForm.formState.isSubmitting} className="btn-primary w-full py-3 text-base mt-2">
                {registerForm.formState.isSubmitting
                  ? <><Loader2 size={16} className="animate-spin" /> در حال ثبت‌نام…</>
                  : "ایجاد حساب رایگان"}
              </button>

              <p className="text-center text-sm text-muted-foreground pt-1">
                قبلاً ثبت‌نام کرده‌اید؟{" "}
                <button type="button" onClick={() => switchMode("login")}
                  className="text-primary font-bold hover:text-primary/80 transition-colors">
                  وارد شوید
                </button>
              </p>
            </form>
          )}

          {/* Trust badges */}
          <div className="flex items-center justify-center gap-4 mt-8">
            {[
              { icon: Zap, text: "GPU-Accelerated" },
              { icon: Shield, text: "Self-Hosted" },
              { icon: Globe, text: "RTL-Ready" },
            ].map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-1 text-muted-foreground/50">
                <Icon size={11} />
                <span className="text-[10px]">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
