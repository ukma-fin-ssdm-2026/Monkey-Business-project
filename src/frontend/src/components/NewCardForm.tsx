/**
 * Інструмент: Claude
 * Застосування: Міні-форма створення картки в колонці (company, position —
 * обов'язкові поля CardCreate зі schemas.py).
 * Верифікація: Перевірено типи й білд.
 */

import { FormEvent, useState } from "react";
import { focusOnMount } from "./focusOnMount";

interface Props {
  onSubmit: (company: string, position: string) => Promise<void>;
  onCancel: () => void;
}

export function NewCardForm({ onSubmit, onCancel }: Props) {
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!company.trim() || !position.trim()) return;
    setSaving(true);
    try {
      await onSubmit(company.trim(), position.trim());
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="new-card-form" onSubmit={handleSubmit}>
      <input
        ref={focusOnMount}
        placeholder="Компанія"
        value={company}
        onChange={(e) => setCompany(e.target.value)}
        maxLength={200}
        required
      />
      <input
        placeholder="Посада"
        value={position}
        onChange={(e) => setPosition(e.target.value)}
        maxLength={200}
        required
      />
      <div className="new-card-form-actions">
        <button type="submit" disabled={saving}>
          Додати
        </button>
        <button type="button" className="secondary" onClick={onCancel}>
          Скасувати
        </button>
      </div>
    </form>
  );
}
