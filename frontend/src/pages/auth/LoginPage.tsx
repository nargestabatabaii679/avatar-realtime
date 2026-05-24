import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { useAuthStore } from "../../stores/authStore";
import { cn } from "../../utils/cn";

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type FormData = z.infer<typeof schema>;

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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-950 via-purple-950 to-slate-950 p-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -start-1/4 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -end-1/4 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md animate-fade-in">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg mb-4">
            <span className="text-white font-bold text-2xl">A</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Avatar Platform</h1>
          <p className="text-purple-300 mt-1 text-sm">AI Digital Human Platform</p>
        </div>

        {/* Card */}
        <div className="bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-xl font-semibold text-white mb-6">{t("auth.login")}</h2>

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email */}
            <div>
              <label className="block text-sm font-medium text-purple-200 mb-1.5">
                {t("auth.email")}
              </label>
              <input
                type="email"
                autoComplete="email"
                {...register("email")}
                className={cn(
                  "w-full px-4 py-2.5 rounded-lg bg-white/10 border text-white placeholder:text-white/40",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors text-sm",
                  errors.email ? "border-red-500" : "border-white/20"
                )}
                placeholder="you@company.com"
              />
              {errors.email && <p className="mt-1 text-xs text-red-400">{errors.email.message}</p>}
            </div>

            {/* Password */}
            <div>
              <label className="block text-sm font-medium text-purple-200 mb-1.5">
                {t("auth.password")}
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  {...register("password")}
                  className={cn(
                    "w-full px-4 py-2.5 pe-10 rounded-lg bg-white/10 border text-white placeholder:text-white/40",
                    "focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-colors text-sm",
                    errors.password ? "border-red-500" : "border-white/20"
                  )}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3 text-white/40 hover:text-white/70"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <p className="mt-1 text-xs text-red-400">{errors.password.message}</p>}
            </div>

            <div className="flex items-center justify-end">
              <a href="#" className="text-xs text-indigo-400 hover:text-indigo-300">
                {t("auth.forgotPassword")}
              </a>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className={cn(
                "w-full py-2.5 px-4 rounded-lg font-medium text-white text-sm transition-all",
                "bg-gradient-to-r from-indigo-500 to-purple-600",
                "hover:from-indigo-600 hover:to-purple-700",
                "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-transparent",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "flex items-center justify-center gap-2"
              )}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Signing in…
                </>
              ) : t("auth.login")}
            </button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-sm text-white/50">{t("auth.noAccount")} </span>
            <a href="#" className="text-sm text-indigo-400 hover:text-indigo-300 font-medium">
              {t("auth.register")}
            </a>
          </div>
        </div>

        <p className="text-center text-xs text-white/30 mt-6">
          © 2024 Avatar Platform. All rights reserved.
        </p>
      </div>
    </div>
  );
}
