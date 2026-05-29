import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2, Zap, Shield, Globe, User, Mail, Lock, Mic } from "lucide-react";
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
  { Icon: User,  title: "آواتار واقعی",    desc: "تبدیل عکس به آواتار سخنگو با هوش مصنوعی" },
  { Icon: Mic,   title: "صدای طبیعی",     desc: "کلونینگ صدا با XTTS-v2 بهینه برای فارسی" },
  { Icon: Zap,   title: "لیپ‌سینک ۵۰fps", desc: "حرکات طبیعی لب، پلک و میکروحالت‌ها" },
  { Icon: Globe, title: "چندزبانه",        desc: "فارسی، انگلیسی، عربی، ترکی و بیشتر" },
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

      {/* ─── Left: Info Panel ─── */}
      <div className="hidden lg:flex lg:w-[54%] relative flex-col overflow-hidden"
        style={{ background: "var(--s1)", borderRight: "0.5px solid var(--border-rest)" }}>
        <div className="absolute inset-0 pointer-events-none"
          style={{ backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "24px 24px", opacity: 0.4 }} />

        <div className="relative z-10 flex flex-col h-full p-12">
          {/* Logo */}
          <div className="flex items-center gap-3 animate-fade-in-down">
            <div className="w-10 h-10 rounded flex items-center justify-center"
              style={{ background: "var(--accent-bg)", border: "0.5px solid var(--accent-md)" }}>
              <span className="font-black text-xl" style={{ color: "var(--accent)" }}>A</span>
            </div>
            <div>
              <p className="font-bold text-base leading-none" style={{ color: "var(--t1)" }}>Avatar</p>
              <p className="text-xs leading-none mt-0.5" style={{ color: "var(--t3)" }}>AI Platform</p>
            </div>
          </div>

          <div className="flex-1 flex flex-col justify-center animate-fade-in-up" style={{ animationDelay: ".1s" }}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-7 w-fit"
              style={{ background: "var(--accent-bg)", border: "0.5px solid var(--accent-md)", borderRadius: "var(--r-tag)" }}>
              <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "var(--green)" }} />
              <span className="text-xs font-medium" style={{ color: "var(--accent)", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.08em" }}>هوش مصنوعی نسل جدید</span>
            </div>

            <h1 className="text-5xl xl:text-6xl font-black leading-[1.1] mb-6" style={{ color: "var(--t1)" }}>
              ساخت <span style={{ color: "var(--accent)" }}>آواتار</span> سخن‌گو
            </h1>

            <p className="text-base leading-relaxed max-w-sm mb-10" style={{ color: "var(--t2)" }}>
              عکس انسان را آپلود کنید، متن بنویسید،
              ویدیوی آواتار سخنگو بسازید — مثل D-ID و HeyGen
            </p>

            <div className="grid grid-cols-2 gap-3">
              {features.map(({ Icon, title, desc }, i) => (
                <div key={title}
                  className="p-3.5 animate-fade-in-up"
                  style={{
                    animationDelay: `${.2 + i * .07}s`,
                    background: "var(--s2)",
                    border: "0.5px solid var(--border-rest)",
                    borderRadius: "var(--r-card)",
                  }}>
                  <Icon size={14} style={{ color: "var(--accent)", marginBottom: "6px" }} />
                  <p className="text-sm font-bold mb-0.5" style={{ color: "var(--t1)" }}>{title}</p>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--t3)" }}>{desc}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs" style={{ color: "var(--t4)" }}>© 2024 Avatar Platform · پلتفرم آواتار هوش مصنوعی</p>
        </div>
      </div>

      {/* ─── Right: Form Panel ─── */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden"
        style={{ background: "var(--bg)" }}>
        <div className="absolute inset-0 pointer-events-none"
          style={{ backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.025) 1px, transparent 1px)", backgroundSize: "24px 24px", opacity: 0.3 }} />

        {/* Mobile logo */}
        <div className="lg:hidden mb-8 text-center animate-fade-in">
          <div className="inline-flex items-center justify-center w-12 h-12 mb-3"
            style={{ background: "var(--accent-bg)", border: "0.5px solid var(--accent-md)", borderRadius: "var(--r-card)" }}>
            <span className="font-black text-xl" style={{ color: "var(--accent)" }}>A</span>
          </div>
          <h1 className="text-2xl font-black text-foreground">Avatar Platform</h1>
        </div>

        <div className="relative z-10 w-full max-w-[400px]">

          {/* Mode toggle tabs */}
          <div className="flex mb-7"
            style={{ borderBottom: "0.5px solid var(--border-rest)" }}>
            {(["login", "register"] as const).map((m) => (
              <button key={m}
                onClick={() => switchMode(m)}
                className="flex-1 py-2.5 text-sm font-medium transition-all duration-150"
                style={{
                  color: mode === m ? "var(--accent)" : "var(--t3)",
                  borderBottom: mode === m ? "1px solid var(--accent)" : "1px solid transparent",
                  fontFamily: "'IBM Plex Mono', monospace",
                  fontSize: "12px",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
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
