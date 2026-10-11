/**
 * Інструмент: Claude
 * Застосування: Форма входу — викликає POST /v1/auth/login (auth.py).
 * Верифікація: Перевірено типи й білд; ручний запуск проти живого API не
 * виконувався в цій сесії.
 */

import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login({ email, password });
      navigate("/board");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося увійти");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Tech Interview Board</h1>
        <p className="auth-subtitle">Увійдіть у свій обліковий запис</p>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Вхід..." : "Увійти"}
        </button>
        <p className="auth-switch">
          Немає акаунту? <Link to="/register">Зареєструватися</Link>
        </p>
      </form>
    </div>
  );
}
