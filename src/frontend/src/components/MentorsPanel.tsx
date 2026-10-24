/**
 * Інструмент: Claude
 * Застосування: Панель керування менторами дошки — запрошення (POST
 * /boards/{id}/mentors), перегляд списку (GET /boards/{id}/mentors) та
 * відкликання доступу (DELETE /boards/{id}/mentors/{mentor_id}).
 * Покриває FR-012, FR-015, US-002.
 * Верифікація: Перевірено типи (tsc -b) і продакшн-білд (vite build).
 */

import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { BoardMentorOut } from "../api/types";

interface Props {
  boardId: string;
  /** Лише кандидат/адмін може запрошувати та відкликати */
  canWrite: boolean;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  pending: "Очікує",
  accepted: "Прийнято",
  revoked: "Відкликано",
};

export function MentorsPanel({ boardId, canWrite, onClose }: Props) {
  const [mentors, setMentors] = useState<BoardMentorOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null); // id ментора що відкликується
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setListError(null);
    try {
      const data = await api.listMentors(boardId);
      setMentors(data);
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : "Не вдалося завантажити менторів");
    } finally {
      setLoading(false);
    }
  }, [boardId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    setInviteError(null);
    setInviteSuccess(null);
    setInviting(true);
    try {
      await api.inviteMentor(boardId, { email: inviteEmail.trim() });
      setInviteSuccess(`Запрошення надіслано на ${inviteEmail.trim()}`);
      setInviteEmail("");
      await load();
    } catch (err) {
      setInviteError(err instanceof ApiError ? err.message : "Не вдалося надіслати запрошення");
    } finally {
      setInviting(false);
    }
  }

  async function handleRevoke(mentor: BoardMentorOut) {
    setRevokeError(null);
    setRevoking(mentor.id);
    try {
      await api.revokeMentor(boardId, mentor.mentor_id!);
      await load();
    } catch (err) {
      setRevokeError(err instanceof ApiError ? err.message : "Не вдалося відкликати доступ");
    } finally {
      setRevoking(null);
    }
  }

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card" style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <h2>Ментори дошки</h2>
          <button className="icon-button" onClick={onClose} aria-label="Закрити">
            ✕
          </button>
        </div>

        <div className="modal-body">
          {canWrite && (
            <form onSubmit={handleInvite} className="inline-form">
              <label style={{ flex: 1 }}>
                Email ментора
                <input
                  type="email"
                  placeholder="mentor@example.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  required
                  autoComplete="off"
                />
              </label>
              <button
                type="submit"
                disabled={inviting}
                style={{ alignSelf: "flex-end" }}
              >
                {inviting ? "Надсилання..." : "Запросити"}
              </button>
            </form>
          )}
          {inviteError && <p className="form-error">{inviteError}</p>}
          {inviteSuccess && (
            <p style={{ color: "#006644", fontSize: 13 }}>{inviteSuccess}</p>
          )}
        </div>

        <div className="modal-section">
          <h3>Список менторів</h3>
          {listError && <p className="form-error">{listError}</p>}
          {revokeError && <p className="form-error">{revokeError}</p>}
          {loading ? (
            <p className="empty-hint">Завантаження...</p>
          ) : mentors.length === 0 ? (
            <p className="empty-hint">Менторів ще не запрошено.</p>
          ) : (
            <ul className="simple-list mentors-list">
              {mentors.map((m) => (
                <li key={m.id}>
                  <span className="mentor-email">{m.email}</span>
                  <span className={`mentor-status-badge status-${m.status}`}>
                    {STATUS_LABELS[m.status] ?? m.status}
                  </span>
                  {canWrite && m.status !== "revoked" && (
                    <button
                      className="icon-button danger-text"
                      onClick={() => handleRevoke(m)}
                      disabled={revoking === m.id}
                      title="Відкликати доступ"
                    >
                      {revoking === m.id ? "..." : "Відкликати"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
