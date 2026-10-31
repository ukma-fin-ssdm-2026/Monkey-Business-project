/**
 * Інструмент: Claude
 * Застосування: Вибір дошки після входу — список з GET /v1/boards
 * (routers/boards.py); єдина дошка відкривається автоматично, ручний
 * ввід board_id показується лише адміністратору.
 * Верифікація: Перевірено типи й білд; регулярний вираз UUID перевірено
 * вручну на прикладі з документації (3fa85f64-5717-4562-b3fc-2c963f66afa6).
 */

import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, formatApiError } from "../api/client";
import type { BoardOut } from "../api/types";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function BoardSetupPage() {
  const { user, boardId, setBoardId, logout } = useAuth();
  const navigate = useNavigate();
  const [boards, setBoards] = useState<BoardOut[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function openBoard(id: string) {
    setBoardId(id);
    navigate("/board", { replace: true });
  }

  useEffect(() => {
    let cancelled = false;
    api
      .listMyBoards()
      .then((data) => {
        if (cancelled) return;
        // Одразу після входу чи реєстрації (дошку ще не обрано) єдину
        // доступну дошку відкриваємо без зайвого кроку.
        if (data.length === 1 && !boardId) {
          openBoard(data[0].id);
          return;
        }
        setBoards(data);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(formatApiError(err, "Не вдалося отримати список дошок"));
      });
    return () => {
      cancelled = true;
    };
    // Лише при відкритті сторінки: після openBoard boardId змінюється,
    // і повторний запит не потрібен.
  }, []);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!UUID_RE.test(trimmed)) {
      setError("Це не схоже на UUID дошки (напр. 3fa85f64-5717-4562-b3fc-2c963f66afa6)");
      return;
    }
    openBoard(trimmed);
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1>Оберіть дошку</h1>
        <p className="auth-subtitle">Привіт, {user?.email}!</p>

        {boards === null && !loadError && <p className="hint">Завантаження дошок...</p>}
        {loadError && <p className="form-error">{loadError}</p>}

        {boards && boards.length > 0 && (
          <ul className="board-list">
            {boards.map((board) => (
              <li key={board.id}>
                <button type="button" onClick={() => openBoard(board.id)}>
                  {board.access === "owner" ? "Моя дошка" : "Дошка кандидата (ментор)"}
                  {board.id === boardId && " — поточна"}
                </button>
                <code>{board.id}</code>
              </li>
            ))}
          </ul>
        )}

        {boards && boards.length === 0 && user?.role !== "admin" && (
          <p className="hint">
            {user?.role === "mentor"
              ? "Немає дошок, до яких у вас є доступ. Прийміть запрошення від кандидата за посиланням з листа."
              : "Немає дошок, пов'язаних з вашим акаунтом."}
          </p>
        )}

        {/* Ручний ввід — лише для адміністратора: список не повертає йому
            чужі дошки, а кандидат і ментор не мають доступу поза списком
            (auth.py: require_board_access). */}
        {user?.role === "admin" && (
          <form onSubmit={onSubmit}>
            <label>
              Введіть board_id дошки
              <input
                type="text"
                placeholder="3fa85f64-5717-4562-b3fc-2c963f66afa6"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                required
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button type="submit" className="secondary">
              Відкрити дошку
            </button>
          </form>
        )}
        <button type="button" className="link-button" onClick={logout}>
          Вийти з акаунту
        </button>
      </div>
    </div>
  );
}
