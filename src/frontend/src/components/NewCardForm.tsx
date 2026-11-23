/**
 * Інструмент: Claude
 * Застосування: Міні-форма створення картки в колонці (company, position —
 * обов'язкові поля CardCreate зі schemas.py).
 * Верифікація: Перевірено типи й білд.
 */

import { FormEvent, useState } from "react";
import type { CardCreate } from "../api/types";
import { formatApiError } from "../api/client";
import { focusOnMount } from "./focusOnMount";

interface Props {
  onSubmit: (payload: Omit<CardCreate, "stage_id">) => Promise<void>;
  onCancel: () => void;
}

export function NewCardForm({ onSubmit, onCancel }: Props) {
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [vacancyUrl, setVacancyUrl] = useState("");
  const [requirements, setRequirements] = useState("");
  const [deadline, setDeadline] = useState("");
  const [links, setLinks] = useState([""]);
  const [note, setNote] = useState("");
  const [notifications, setNotifications] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!company.trim() || !position.trim()) {
      setError("Вкажіть компанію і посаду");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        company: company.trim(), position: position.trim(),
        vacancy_url: vacancyUrl.trim() || null,
        requirements_text: requirements.trim() || null,
        deadline: deadline ? new Date(deadline).toISOString() : null,
        notifications_enabled: notifications,
        links: links.map((url) => url.trim()).filter(Boolean),
        notes: note.trim() ? [{ content: note.trim(), source: "candidate" }] : [],
      });
    } catch (err) {
      setError(formatApiError(err, "Не вдалося створити картку. Введені дані збережено у формі."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="new-card-form" onSubmit={handleSubmit}>
      <fieldset disabled={saving} className="card-create-fields">
      <input
        aria-label="Компанія"
        ref={focusOnMount}
        placeholder="Компанія"
        value={company}
        onChange={(e) => setCompany(e.target.value)}
        maxLength={200}
        required
      />
      <input
        aria-label="Посада"
        placeholder="Посада"
        value={position}
        onChange={(e) => setPosition(e.target.value)}
        maxLength={200}
        required
      />
      <label>Посилання на вакансію<input type="url" value={vacancyUrl} onChange={(e) => setVacancyUrl(e.target.value)} /></label>
      <label>Вимоги вакансії<textarea value={requirements} onChange={(e) => setRequirements(e.target.value)} maxLength={5000} rows={3} /></label>
      <label>Дедлайн<input type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
      {links.map((url, index) => (
        <label key={index}>Посилання на завдання {index + 1}
          <input type="url" value={url} onChange={(e) => setLinks((items) => items.map((item, i) => i === index ? e.target.value : item))} />
        </label>
      ))}
      <button type="button" className="secondary" disabled={links.length >= 50} onClick={() => setLinks((items) => [...items, ""])}>Ще посилання</button>
      <label>Нотатка<textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={3000} rows={3} /></label>
      <label className="checkbox-label"><input type="checkbox" checked={notifications} onChange={(e) => setNotifications(e.target.checked)} />Нагадування про дедлайн</label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="new-card-form-actions">
        <button type="submit" disabled={saving}>
          Додати
        </button>
        <button type="button" className="secondary" onClick={onCancel}>
          Скасувати
        </button>
      </div>
      </fieldset>
    </form>
  );
}
