import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import AppLayout from "./components/layout/AppLayout";
import LoginPage from "./pages/auth/LoginPage";
import DashboardPage from "./pages/dashboard/DashboardPage";
import AvatarStudioPage from "./pages/avatar-studio/AvatarStudioPage";
import VoiceStudioPage from "./pages/voice-studio/VoiceStudioPage";
import VideoStudioPage from "./pages/video-studio/VideoStudioPage";
import AgentBuilderPage from "./pages/agent-builder/AgentBuilderPage";
import KnowledgeCenterPage from "./pages/knowledge-center/KnowledgeCenterPage";
import AnalyticsPage from "./pages/analytics/AnalyticsPage";
import AdminPage from "./pages/admin/AdminPage";
import RealtimePage from "./pages/realtime/RealtimePage";
import { useAuthStore } from "./stores/authStore";
import { useThemeStore } from "./stores/themeStore";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { language } = useThemeStore();
  const { i18n } = useTranslation();
  const { theme } = useThemeStore();

  useEffect(() => {
    // Apply theme
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    if (theme === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.add(prefersDark ? "dark" : "light");
    } else {
      root.classList.add(theme);
    }
  }, [theme]);

  useEffect(() => {
    // Apply language and direction
    const rtlLangs = ["fa", "ar", "he", "ur"];
    const isRTL = rtlLangs.includes(language);
    document.documentElement.setAttribute("dir", isRTL ? "rtl" : "ltr");
    document.documentElement.setAttribute("lang", language);
    i18n.changeLanguage(language);

    // Apply Persian font for RTL
    if (isRTL) {
      document.body.style.fontFamily = "'Vazirmatn', sans-serif";
    } else {
      document.body.style.fontFamily = "'Inter', sans-serif";
    }
  }, [language, i18n]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="avatar-studio" element={<AvatarStudioPage />} />
        <Route path="voice-studio" element={<VoiceStudioPage />} />
        <Route path="video-studio" element={<VideoStudioPage />} />
        <Route path="agent-builder" element={<AgentBuilderPage />} />
        <Route path="knowledge-center" element={<KnowledgeCenterPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="realtime" element={<RealtimePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
