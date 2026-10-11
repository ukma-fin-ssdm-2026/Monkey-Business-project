/**
 * Інструмент: Claude
 * Застосування: Route-guard — пускає до /board* лише автентифікованих
 * користувачів (дзеркалить вимогу Bearer-токена на бекенді, auth.py).
 * Верифікація: Перевірено типи й білд.
 */

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute() {
  const { user, isReady } = useAuth();
  if (!isReady) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}
