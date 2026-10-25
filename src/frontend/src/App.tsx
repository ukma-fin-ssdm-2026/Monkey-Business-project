/**
 * Інструмент: Claude
 * Застосування: Маршрутизація фронтенду (react-router-dom) — публічні
 * /login, /register, /invitations/:token та захищені /board, /board/setup.
 * Верифікація: Перевірено типи й білд.
 */

import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { BoardSetupPage } from "./pages/BoardSetupPage";
import { BoardPage } from "./pages/BoardPage";
import { InvitationPage } from "./pages/InvitationPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/invitations/:token" element={<InvitationPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/board/setup" element={<BoardSetupPage />} />
          <Route path="/board" element={<BoardPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/board" replace />} />
      </Routes>
    </AuthProvider>
  );
}
