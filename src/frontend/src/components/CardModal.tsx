/**
 * Інструмент: Claude
 * Застосування: Модальне вікно картки — редагування полів (PATCH
 * .../cards/{id}), видалення, список/додавання/видалення посилань
 * (.../links) та нотаток/фідбеку (.../notes) по картці.
 * Codex: очищення nullable-полів, редагування URL і нотаток, стабільний
 * автор коментаря. Перевірка: first-phase.test.tsx та production build.
 */

import { FormEvent, useEffect, useState } from "react";
import { api, ApiError, formatApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type {
  BoardMentorOut,
  CardLinkOut,
  CardNoteOut,
  CardOut,
  CardStatus,
  CardUpdate,
  CommentOut,
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
  const { user } = useAuth();
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
  const [linksError, setLinksError] = useState<string | null>(null);
  const [newLink, setNewLink] = useState("");
  const [notes, setNotes] = useState<CardNoteOut[] | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [newNote, setNewNote] = useState("");
  const [newNoteSource, setNewNoteSource] = useState<NoteSource>("candidate");

  const [comments, setComments] = useState<CommentOut[] | null>(null);
  const [commentsLoading, setCommentsLoading] = useState(true);
  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [newComment, setNewComment] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);
  const [deletingCommentId, setDeletingCommentId] = useState<string | null>(null);
  const [mentors, setMentors] = useState<BoardMentorOut[]>([]);
  const [mentorsError, setMentorsError] = useState<string | null>(null);
  const [relatedDataReloadKey, setRelatedDataReloadKey] = useState(0);
  const [editingLink, setEditingLink] = useState<string | null>(null);
  const [linkDraft, setLinkDraft] = useState("");
  const [editingNote, setEditingNote] = useState<string | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [savingRelated, setSavingRelated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLinks(null);
    setNotes(null);
    setMentors([]);
    setLinksError(null);
    setNotesError(null);
    setMentorsError(null);

    api.listLinks(boardId, card.id).then((data) => {
      if (!cancelled) setLinks(data);
    }).catch((err) => {
      if (!cancelled) {
        console.error("Failed to load card links", err);
        setLinks([]);
        setLinksError(formatApiError(err, "Не вдалося завантажити посилання"));
      }
    });
    api.listNotes(boardId, card.id).then((data) => {
      if (!cancelled) setNotes(data);
    }).catch((err) => {
      if (!cancelled) {
        console.error("Failed to load card notes", err);
        setNotes([]);
        setNotesError(formatApiError(err, "Не вдалося завантажити нотатки"));
      }
    });

    setCommentsLoading(true);
    setCommentsError(null);
    api.listComments(boardId, card.id)
      .then((data) => setComments(data))
      .catch((err) => {
        setCommentsError(formatApiError(err, "Не вдалося завантажити коментарі"));
        setComments([]);
      })
      .finally(() => setCommentsLoading(false));

    api.listMentors(boardId).then((data) => {
      if (!cancelled) setMentors(data);
    }).catch((err) => {
      if (!cancelled) {
        console.error("Failed to load board mentors", err);
        setMentorsError(formatApiError(err, "Не вдалося завантажити менторів"));
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boardId, card.id, relatedDataReloadKey]);

  function reloadRelatedData() {
    setRelatedDataReloadKey((key) => key + 1);
  }

  function buildDiff(): CardUpdate {
    const diff: CardUpdate = {};
    if (company.trim() !== card.company) diff.company = company.trim();
    if (position.trim() !== card.position) diff.position = position.trim();
    const urlTrimmed = vacancyUrl.trim();
    if (urlTrimmed !== (card.vacancy_url ?? "")) {
      diff.vacancy_url = urlTrimmed || null;
    }
    const reqTrimmed = requirements.trim();
    if (reqTrimmed !== (card.requirements_text ?? "")) {
      diff.requirements_text = reqTrimmed || null;
    }
    const deadlineIso = deadline ? new Date(deadline).toISOString() : "";
    if (deadline !== toLocalInputValue(card.deadline)) {
      diff.deadline = deadlineIso || null;
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

  async function handleUpdateLink(e: FormEvent) {
    e.preventDefault();
    if (!editingLink || !linkDraft.trim()) return;
    setSavingRelated(true);
    setError(null);
    try {
      const updated = await api.updateLink(boardId, card.id, editingLink, { url: linkDraft.trim() });
      setLinks((prev) => (prev ?? []).map((link) => link.id === updated.id ? updated : link));
      setEditingLink(null);
    } catch (err) {
      setError(formatApiError(err, "Не вдалося змінити посилання"));
    } finally {
      setSavingRelated(false);
    }
  }

  async function handleUpdateNote(e: FormEvent) {
    e.preventDefault();
    if (!editingNote || !noteDraft.trim()) return;
    setSavingRelated(true);
    setError(null);
    try {
      const updated = await api.updateNote(boardId, card.id, editingNote, { content: noteDraft.trim() });
      setNotes((prev) => (prev ?? []).map((note) => note.id === updated.id ? updated : note));
      setEditingNote(null);
    } catch (err) {
      setError(formatApiError(err, "Не вдалося змінити нотатку"));
    } finally {
      setSavingRelated(false);
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

  async function handleAddComment(e: FormEvent) {
    e.preventDefault();
    const trimmed = newComment.trim();
    if (!trimmed) {
      setCommentsError("Вміст коментаря не може бути порожнім");
      return;
    }
    if (trimmed.length > 3000) {
      setCommentsError("Коментар не може перевищувати 3000 символів");
      return;
    }
    setSubmittingComment(true);
    setCommentsError(null);
    try {
      const created = await api.createComment(boardId, card.id, { content: trimmed });
      setComments((prev) => [...(prev ?? []), created]);
      setNewComment("");
    } catch (err) {
      setCommentsError(formatApiError(err, "Не вдалося додати коментар"));
    } finally {
      setSubmittingComment(false);
    }
  }

  async function handleDeleteComment(commentId: string) {
    if (!window.confirm("Ви дійсно бажаєте видалити цей коментар?")) return;
    setDeletingCommentId(commentId);
    setCommentsError(null);
    try {
      await api.deleteComment(boardId, card.id, commentId);
      setComments((prev) => (prev ?? []).filter((c) => c.id !== commentId));
    } catch (err) {
      setCommentsError(formatApiError(err, "Не вдалося видалити коментар"));
    } finally {
      setDeletingCommentId(null);
    }
  }

  return (
    <div className="modal-overlay">
      <button
        type="button"
        className="modal-backdrop"
        tabIndex={-1}
        aria-label="Закрити"
        onClick={onClose}
      />
      <div className="modal-card">
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
          {linksError && (
            <div className="section-error" role="alert">
              <span>{linksError}</span>
              <button
                type="button"
                onClick={reloadRelatedData}
              >
                Повторити
              </button>
            </div>
          )}
          <ul className="simple-list">
            {(links ?? []).map((link) => (
              <li key={link.id}>
                {editingLink === link.id ? (
                  <form className="inline-form stacked" onSubmit={handleUpdateLink}>
                    <label>Новий URL<input type="url" value={linkDraft} onChange={(e) => setLinkDraft(e.target.value)} required disabled={savingRelated} /></label>
                    <button type="submit" disabled={savingRelated}>Зберегти посилання</button>
                    <button type="button" disabled={savingRelated} onClick={() => setEditingLink(null)}>Скасувати</button>
                  </form>
                ) : <>
                <a href={link.url} target="_blank" rel="noreferrer">
                  {link.url}
                </a>
                {canWrite && <button type="button" className="secondary" onClick={() => { setEditingLink(link.id); setLinkDraft(link.url); }}>Редагувати посилання</button>}
                {canWrite && (
                  <button className="icon-button" onClick={() => handleDeleteLink(link.id)}>
                    ✕
                  </button>
                )}
                </>}
              </li>
            ))}
            {links !== null && !linksError && links.length === 0 && (
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
          {notesError && (
            <div className="section-error" role="alert">
              <span>{notesError}</span>
              <button
                type="button"
                onClick={reloadRelatedData}
              >
                Повторити
              </button>
            </div>
          )}
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
                {editingNote === note.id ? (
                  <form className="inline-form stacked" onSubmit={handleUpdateNote}>
                    <label>Текст нотатки<textarea value={noteDraft} onChange={(e) => setNoteDraft(e.target.value)} maxLength={3000} required disabled={savingRelated} /></label>
                    <button type="submit" disabled={savingRelated || !noteDraft.trim()}>Зберегти нотатку</button>
                    <button type="button" disabled={savingRelated} onClick={() => setEditingNote(null)}>Скасувати</button>
                  </form>
                ) : <>
                  <p>{note.content}</p>
                  {canWrite && <button type="button" className="secondary" onClick={() => { setEditingNote(note.id); setNoteDraft(note.content); }}>Редагувати нотатку</button>}
                </>}
              </li>
            ))}
            {notes !== null && !notesError && notes.length === 0 && (
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

        <section className="modal-section">
          <h3>Коментарі</h3>

          {mentorsError && (
            <div className="section-error" role="alert">
              <span>{mentorsError}</span>
              <button
                type="button"
                onClick={reloadRelatedData}
              >
                Повторити
              </button>
            </div>
          )}
          {commentsError && (
            <div className="section-error" role="alert">
              <span>{commentsError}</span>
              <button
                type="button"
                className="icon-button"
                onClick={() => setCommentsError(null)}
                aria-label="Закрити повідомлення про помилку"
              >
                ✕
              </button>
            </div>
          )}

          {commentsLoading ? (
            <p className="empty-hint">Завантаження коментарів...</p>
          ) : (
            <ul className="comments-list">
              {(comments ?? []).map((c) => {
                const isAuthor = user?.id === c.author_id;
                const canDelete = isAuthor || user?.role === "admin";
                const mentor = mentors.find((m) => m.mentor_id === c.author_id);
                const authorLabel = c.author_name
                  ? `${c.author_name}${c.author_role === "mentor" ? " (ментор)" : ""}${isAuthor ? " — Ви" : ""}`
                  : isAuthor
                  ? `Ви${user?.role === "mentor" ? " (ментор)" : ""}`
                  : mentor
                  ? `Ментор (${mentor.email})`
                  : user?.role === "mentor"
                  ? "Кандидат"
                  : "Користувач";

                const badgeClass = isAuthor
                  ? "badge-you"
                  : mentor
                  ? "badge-mentor"
                  : "badge-candidate";

                return (
                  <li key={c.id}>
                    <div className="comment-meta">
                      <span className={`comment-badge ${badgeClass}`}>
                        {authorLabel}
                      </span>
                      <span className="comment-date">
                        {new Date(c.created_at).toLocaleString("uk-UA")}
                      </span>
                      {canDelete && (
                        <button
                          type="button"
                          className="icon-button"
                          onClick={() => handleDeleteComment(c.id)}
                          title="Видалити коментар"
                          aria-label="Видалити коментар"
                          disabled={deletingCommentId === c.id}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                    <p>{c.content}</p>
                  </li>
                );
              })}
              {comments !== null && comments.length === 0 && (
                <li className="empty-hint">Ще немає коментарів</li>
              )}
            </ul>
          )}

          <form className="inline-form stacked" onSubmit={handleAddComment}>
            <textarea
              placeholder="Залишити коментар..."
              value={newComment}
              onChange={(e) => {
                setNewComment(e.target.value);
                if (commentsError) setCommentsError(null);
              }}
              onKeyDown={(e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                  e.preventDefault();
                  void handleAddComment(e);
                }
              }}
              maxLength={3000}
              rows={2}
              disabled={submittingComment}
            />
            <div className="inline-form-row" style={{ justifyContent: "flex-end" }}>
              <button
                type="submit"
                disabled={submittingComment || !newComment.trim()}
              >
                {submittingComment ? "Надсилання..." : "Додати коментар"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
