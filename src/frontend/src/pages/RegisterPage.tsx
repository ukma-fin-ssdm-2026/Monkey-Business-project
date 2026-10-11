/**
 * Інструмент: Claude
 * Застосування: Форма реєстрації кандидата — POST /v1/auth/register
 * (auth.py; бекенд дозволяє лише роль candidate, тому вибір ролі відсутній).
 * Верифікація: Перевірено типи й білд; ручний запуск проти живого API не
 * виконувався в цій сесії.
 */

import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export function RegisterPage() {
  const { register } = useAuth();
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
      // Бекенд реєструє лише кандидатів (auth.py: інша роль -> 403),
      // тож роль тут не вибирається.
      await register({ email, password, role: "candidate" });
      navigate("/board");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося зареєструватися");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Tech Interview Board</h1>
        <p className="auth-subtitle">
          Реєстрація кандидата — разом з акаунтом створюється ваша дошка з
          чотирма стандартними етапами.
        </p>
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
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? "Реєстрація..." : "Зареєструватися"}
        </button>
        <p className="auth-switch">
          Вже є акаунт? <Link to="/login">Увійти</Link>
        </p>
      </form>
    </div>
  );
}
