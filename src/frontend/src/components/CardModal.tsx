/**
 * Інструмент: Claude
 * Застосування: Модальне вікно картки — редагування полів (PATCH
 * .../cards/{id}), видалення, список/додавання/видалення посилань
 * (.../links) та нотаток/фідбеку (.../notes) по картці.
 * Верифікація: PATCH надсилає лише змінені поля (diff), бо CardUpdate у
 * schemas.py вимагає хоча б одне поле в model_fields_set; явне очищення
 * необов'язкового поля (null) не надсилається, бо бекенд такий null
 * ігнорує (коментар у routers/cards.py: "optional fields cannot be
 * cleared yet") — це обмеження бекенду, не фронтенду. Перевірено типи й
 * білд.
 */

import { FormEvent, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type {
  CardLinkOut,
  CardNoteOut,
  CardOut,
  CardStatus,
  CardUpdate,
  NoteSource,
} from "../api/types";

const STATUS_OPTIONS: { value: CardStatus; label: string }[] = [
  { value: "active", label: "Активна" },
  { value: "rejected", label: "Відмова" },
  { value: "offer_accepted", label: "Офер" },
];

const SOURCE_OPTIONS: { value: NoteSource; label: string }[] = [
  { value: "candidate", label: "Кандидат" },
  { value: "recruiter", label: "Рекрутер" },
  { value: "ai", label: "AI-асистент" },
];

function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

interface Props {
  boardId: string;
  card: CardOut;
  canWrite: boolean;
  onClose: () => void;
  onUpdated: (card: CardOut) => void;
  onDeleted: (cardId: string) => void;
}

export function CardModal({ boardId, card, canWrite, onClose, onUpdated, onDeleted }: Props) {
  const [company, setCompany] = useState(card.company);
  const [position, setPosition] = useState(card.position);
  const [vacancyUrl, setVacancyUrl] = useState(card.vacancy_url ?? "");
  const [requirements, setRequirements] = useState(card.requirements_text ?? "");
  const [deadline, setDeadline] = useState(toLocalInputValue(card.deadline));
  const [notificationsEnabled, setNotificationsEnabled] = useState(
    card.notifications_enabled,
  );
  const [status, setStatus] = useState<CardStatus>(card.status);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [links, setLinks] = useState<CardLinkOut[] | null>(null);
  const [newLink, setNewLink] = useState("");
  const [notes, setNotes] = useState<CardNoteOut[] | null>(null);
  const [newNote, setNewNote] = useState("");
  const [newNoteSource, setNewNoteSource] = useState<NoteSource>("candidate");

  useEffect(() => {
    api.listLinks(boardId, card.id).then(setLinks).catch(() => setLinks([]));
    api.listNotes(boardId, card.id).then(setNotes).catch(() => setNotes([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [card.id]);

  function buildDiff(): CardUpdate {
    const diff: CardUpdate = {};
    if (company.trim() !== card.company) diff.company = company.trim();
    if (position.trim() !== card.position) diff.position = position.trim();
    const urlTrimmed = vacancyUrl.trim();
    if (urlTrimmed !== (card.vacancy_url ?? "")) {
      if (urlTrimmed) diff.vacancy_url = urlTrimmed;
    }
    const reqTrimmed = requirements.trim();
    if (reqTrimmed !== (card.requirements_text ?? "")) {
      if (reqTrimmed) diff.requirements_text = reqTrimmed;
    }
    const deadlineIso = deadline ? new Date(deadline).toISOString() : "";
    if (deadlineIso !== (card.deadline ?? "")) {
      if (deadlineIso) diff.deadline = deadlineIso;
    }
    if (notificationsEnabled !== card.notifications_enabled) {
      diff.notifications_enabled = notificationsEnabled;
    }
    if (status !== card.status) diff.status = status;
    return diff;
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    const diff = buildDiff();
    if (Object.keys(diff).length === 0) {
      onClose();
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateCard(boardId, card.id, diff);
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося зберегти картку");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Видалити картку "${card.company} — ${card.position}"?`)) return;
    try {
      await api.deleteCard(boardId, card.id);
      onDeleted(card.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося видалити картку");
    }
  }

  async function handleAddLink(e: FormEvent) {
    e.preventDefault();
    if (!newLink.trim()) return;
    try {
      const link = await api.createLink(boardId, card.id, { url: newLink.trim() });
      setLinks((prev) => [...(prev ?? []), link]);
      setNewLink("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося додати посилання");
    }
  }

  async function handleDeleteLink(linkId: string) {
    try {
      await api.deleteLink(boardId, card.id, linkId);
      setLinks((prev) => (prev ?? []).filter((l) => l.id !== linkId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося видалити посилання");
    }
  }

  async function handleAddNote(e: FormEvent) {
    e.preventDefault();
    if (!newNote.trim()) return;
    try {
      const note = await api.createNote(boardId, card.id, {
        content: newNote.trim(),
        source: newNoteSource,
      });
      setNotes((prev) => [...(prev ?? []), note]);
      setNewNote("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося додати нотатку");
    }
  }

  async function handleDeleteNote(noteId: string) {
    try {
      await api.deleteNote(boardId, card.id, noteId);
      setNotes((prev) => (prev ?? []).filter((n) => n.id !== noteId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося видалити нотатку");
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Картка вакансії</h2>
          <button className="icon-button" onClick={onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSave} className="modal-body">
          {error && <p className="form-error">{error}</p>}

          <div className="field-row">
            <label>
              Компанія
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                maxLength={200}
                disabled={!canWrite}
                required
              />
            </label>
            <label>
              Посада
              <input
                value={position}
                onChange={(e) => setPosition(e.target.value)}
                maxLength={200}
                disabled={!canWrite}
                required
              />
            </label>
          </div>

          <div className="field-row">
            <label>
              Статус
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as CardStatus)}
                disabled={!canWrite}
              >
                {STATUS_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Дедлайн
              <input
                type="datetime-local"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                disabled={!canWrite}
              />
            </label>
          </div>

          <label>
            Посилання на вакансію
            <input
              type="url"
              value={vacancyUrl}
              onChange={(e) => setVacancyUrl(e.target.value)}
              placeholder="https://..."
              disabled={!canWrite}
            />
          </label>

          <label>
            Вимоги вакансії
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              maxLength={5000}
              rows={4}
              disabled={!canWrite}
            />
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={notificationsEnabled}
              onChange={(e) => setNotificationsEnabled(e.target.checked)}
              disabled={!canWrite}
            />
            Нагадування про дедлайн увімкнені
          </label>

          {canWrite && (
            <div className="modal-actions">
              <button type="submit" disabled={saving}>
                {saving ? "Збереження..." : "Зберегти"}
              </button>
              <button type="button" className="danger" onClick={handleDelete}>
                Видалити картку
              </button>
            </div>
          )}
        </form>

        <section className="modal-section">
          <h3>Посилання на тестові завдання</h3>
          <ul className="simple-list">
            {(links ?? []).map((link) => (
              <li key={link.id}>
                <a href={link.url} target="_blank" rel="noreferrer">
                  {link.url}
                </a>
                {canWrite && (
                  <button className="icon-button" onClick={() => handleDeleteLink(link.id)}>
                    ✕
                  </button>
                )}
              </li>
            ))}
            {links !== null && links.length === 0 && (
              <li className="empty-hint">Ще немає посилань</li>
            )}
          </ul>
          {canWrite && (
            <form className="inline-form" onSubmit={handleAddLink}>
              <input
                type="url"
                placeholder="https://github.com/.../test-task"
                value={newLink}
                onChange={(e) => setNewLink(e.target.value)}
              />
              <button type="submit">Додати</button>
            </form>
          )}
        </section>

        <section className="modal-section">
          <h3>Нотатки та фідбек</h3>
          <ul className="notes-list">
            {(notes ?? []).map((note) => (
              <li key={note.id}>
                <div className="note-meta">
                  <span className={`source-badge source-${note.source}`}>
                    {SOURCE_OPTIONS.find((s) => s.value === note.source)?.label}
                  </span>
                  <span className="note-date">
                    {new Date(note.created_at).toLocaleString("uk-UA")}
                  </span>
                  {canWrite && (
                    <button
                      className="icon-button"
                      onClick={() => handleDeleteNote(note.id)}
                    >
                      ✕
                    </button>
                  )}
                </div>
                <p>{note.content}</p>
              </li>
            ))}
            {notes !== null && notes.length === 0 && (
              <li className="empty-hint">Ще немає нотаток</li>
            )}
          </ul>
          {canWrite && (
            <form className="inline-form stacked" onSubmit={handleAddNote}>
              <textarea
                placeholder="Текст нотатки або фідбеку"
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                maxLength={3000}
                rows={2}
              />
              <div className="inline-form-row">
                <select
                  value={newNoteSource}
                  onChange={(e) => setNewNoteSource(e.target.value as NoteSource)}
                >
                  {SOURCE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <button type="submit">Додати нотатку</button>
              </div>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
