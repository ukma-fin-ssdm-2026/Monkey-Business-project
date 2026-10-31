/**
 * Інструмент: Claude
 * Застосування: Публічна сторінка прийняття запрошення ментора за токеном
 * (GET /v1/invitations/{token}, POST /v1/invitations/{token}/accept).
 * Покриває FR-012, US-002.
 *
 * Логіка:
 *  1. Завантажуємо деталі запрошення (email, статус).
 *  2. Якщо ментор уже залогінений (токен у AuthContext) — приймаємо без пароля.
 *  3. Якщо ні — пропонуємо форму встановлення пароля.
 *  4. Після успішного прийняття зберігаємо сесію та board_id, переходимо на /board.
 *
 * Верифікація: Перевірено типи і білд.
 */

/**
 * ## Використання ШІ (рефакторинг)
 * - **Інструмент:** Codex.
 * - **Застосування:** винесення повторюваної розмітки в InvitationStatusScreen.
 * - **Верифікація:** автор перевірив зміни, результати 12 тестів до/після та збірки.
 */
import { FormEvent, type ReactNode, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, setAuthToken } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { BoardMentorOut } from "../api/types";

const TOKEN_KEY = "tib.token";
const USER_KEY = "tib.user";
const BOARD_KEY_PREFIX = "tib.board.";

function InvitationStatusScreen({ children }: { children: ReactNode }) {
  return (
    <div className="auth-screen">
      <div className="auth-card">{children}</div>
    </div>
  );
}

export function InvitationPage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { token: authToken, setBoardId } = useAuth();

  const [invitation, setInvitation] = useState<BoardMentorOut | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingInv, setLoadingInv] = useState(true);

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Крок 1: Завантажити дані запрошення
  useEffect(() => {
    if (!token) {
      setLoadError("Токен запрошення відсутній у посиланні");
      setLoadingInv(false);
      return;
    }
    void (async () => {
      try {
        const inv = await api.getInvitation(token);
        setInvitation(inv);
      } catch (err) {
        setLoadError(
          err instanceof ApiError
            ? err.message
            : "Запрошення не знайдено або термін його дії минув",
        );
      } finally {
        setLoadingInv(false);
      }
    })();
  }, [token]);

  async function handleAccept(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setAcceptError(null);

    // Перевірка паролів лише якщо ментор не залогінений
    if (!authToken) {
      if (!password) {
        setAcceptError("Введіть пароль для активації облікового запису");
        return;
      }
      if (password !== confirmPassword) {
        setAcceptError("Паролі не співпадають");
        return;
      }
    }

    setAccepting(true);
    try {
      const payload = authToken ? undefined : { password };
      const result = await api.acceptInvitation(token, payload);

      // Якщо бекенд повернув новий токен (новий ментор встановив пароль)
      if (result.access_token) {
        // Зберігаємо JWT у клієнта та localStorage.
        // AuthContext.applySession — приватний, тому оновлюємо вручну.
        setAuthToken(result.access_token);
        localStorage.setItem(TOKEN_KEY, result.access_token);
        // USER_KEY видаляємо — AuthProvider прочитає його на наступному mount
        // і покаже "Завантаження" до входу. Натомість зберігаємо board_id
        // прямо в localStorage під ключем інвайтованого ментора (mentor_id
        // з запрошення), щоб він не загубився після перезавантаження.
        localStorage.removeItem(USER_KEY);
        if (invitation) {
          localStorage.setItem(
            BOARD_KEY_PREFIX + invitation.mentor_id,
            result.board_id,
          );
        }
      } else {
        // Вже залогінений ментор — setBoardId спрацює, бо user в контексті є
        setBoardId(result.board_id);
      }

      setDone(true);
      setTimeout(() => navigate("/board"), 2000);
    } catch (err) {
      setAcceptError(
        err instanceof ApiError ? err.message : "Не вдалося прийняти запрошення",
      );
    } finally {
      setAccepting(false);
    }
  }

  // --- Рендер: завантаження ---
  if (loadingInv) {
    return (
      <InvitationStatusScreen>
        <p className="auth-subtitle">Перевірка запрошення...</p>
      </InvitationStatusScreen>
    );
  }

  // --- Рендер: помилка завантаження ---
  if (loadError || !invitation) {
    return (
      <InvitationStatusScreen>
        <h1>Запрошення не знайдено</h1>
        <p className="form-error">{loadError ?? "Невідома помилка"}</p>
        <p className="auth-subtitle">
          Посилання могло протерміновуватись або вже було використано.
        </p>
        <button onClick={() => navigate("/login")}>Перейти до входу</button>
      </InvitationStatusScreen>
    );
  }

  // --- Рендер: успіх ---
  if (done) {
    return (
      <InvitationStatusScreen>
        <h1>🎉 Запрошення прийнято!</h1>
        <p className="auth-subtitle">
          Ви приєдналися до дошки. Перенаправляємо...
        </p>
      </InvitationStatusScreen>
    );
  }

  // --- Рендер: форма прийняття ---
  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={handleAccept}>
        <h1>Tech Interview Board</h1>
        <p className="auth-subtitle">Запрошення ментора</p>

        <div className="invitation-info">
          <p>
            <strong>Ваш email:</strong> {invitation.email}
          </p>
          <p>
            <strong>Дошка:</strong> <code>{invitation.board_id}</code>
          </p>
          <p>
            <strong>Статус:</strong>{" "}
            <span className="mentor-status-badge status-pending">Очікує підтвердження</span>
          </p>
        </div>

        {authToken ? (
          <p className="hint">
            Ви вже залогінені. Натисніть «Прийняти», щоб приєднатися до дошки.
          </p>
        ) : (
          <>
            <p className="hint">
              Встановіть пароль для вашого облікового запису ментора.
            </p>
            <label>
              Пароль
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                minLength={8}
              />
            </label>
            <label>
              Підтвердіть пароль
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </label>
          </>
        )}

        {acceptError && <p className="form-error">{acceptError}</p>}

        <button type="submit" disabled={accepting}>
          {accepting ? "Прийняття..." : "Прийняти запрошення"}
        </button>

        <p className="auth-switch">
          Вже маєте акаунт?{" "}
          <a href="/login" onClick={(e) => { e.preventDefault(); navigate("/login"); }}>
            Увійти
          </a>
        </p>
      </form>
    </div>
  );
}
