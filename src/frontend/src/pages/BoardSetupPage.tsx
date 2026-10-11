/**
 * Інструмент: Claude
 * Застосування: Екран ручного вводу board_id — обхід відсутнього в API
 * ендпоінта "мої дошки" (фіксується в src/api/README.md), реалізований
 * лише на фронтенді, без змін бекенду.
 * Верифікація: Перевірено типи й білд; регулярний вираз UUID перевірено
 * вручну на прикладі з документації (3fa85f64-5717-4562-b3fc-2c963f66afa6).
 */

import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

// Бекенд поки не має ендпоінта "мої дошки" (src/api/README.md:
// "Окремого ендпоінта для отримання board_id поки немає"), тому board_id
// цього користувача просять ввести один раз і зберігають лише в браузері.
export function BoardSetupPage() {
  const { user, setBoardId, logout } = useAuth();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const UUID_RE =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!UUID_RE.test(trimmed)) {
      setError("Це не схоже на UUID дошки (напр. 3fa85f64-5717-4562-b3fc-2c963f66afa6)");
      return;
    }
    setBoardId(trimmed);
    navigate("/board");
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1>Ідентифікатор дошки</h1>
        <p className="auth-subtitle">
          Привіт, {user?.email}! API поки не має ендпоінта для отримання
          списку власних дошок, тому введіть <code>board_id</code> вручну.
        </p>
        {user?.role === "candidate" ? (
          <p className="hint">
            Якщо ви щойно зареєструвалися, ваша дошка вже створена. Знайти
            її ID можна в базі даних:
            <br />
            <code>
              docker compose exec db psql -U interview_board -d
              interview_board -c &quot;select b.id from boards b join users u
              on u.id = b.owner_id where u.email = &apos;{user.email}
              &apos;&quot;
            </code>
          </p>
        ) : (
          <p className="hint">
            Запитайте board_id у кандидата, що веде цю дошку (ви —{" "}
            {user?.role === "mentor" ? "ментор" : "адміністратор"}).
          </p>
        )}
        <label>
          board_id
          <input
            type="text"
            placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          />
        </label>
        {error && <p className="form-error">{error}</p>}
        <button type="submit">Відкрити дошку</button>
        <button type="button" className="link-button" onClick={logout}>
          Вийти з акаунту
        </button>
      </form>
    </div>
  );
}
