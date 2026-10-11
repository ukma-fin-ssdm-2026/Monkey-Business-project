/**
 * Інструмент: Claude
 * Застосування: Колонка етапу дошки — список карток (droppable-зона),
 * перейменування/видалення етапу (PATCH/DELETE .../stages/{id}), форма
 * додавання картки.
 * Верифікація: Перевірено типи й білд; поведінка 409 при видаленні
 * непорожнього етапу покладається на обробку помилки в BoardPage.
 */

import { Droppable } from "@hello-pangea/dnd";
import { useState } from "react";
import type { CardOut, StageOut } from "../api/types";
import { CardItem } from "./CardItem";
import { NewCardForm } from "./NewCardForm";

interface Props {
  stage: StageOut;
  cards: CardOut[];
  canWrite: boolean;
  onOpenCard: (cardId: string) => void;
  onAddCard: (stageId: string, company: string, position: string) => Promise<void>;
  onRenameStage: (stageId: string, name: string) => Promise<void>;
  onDeleteStage: (stageId: string) => Promise<void>;
}

export function StageColumn({
  stage,
  cards,
  canWrite,
  onOpenCard,
  onAddCard,
  onRenameStage,
  onDeleteStage,
}: Props) {
  const [adding, setAdding] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(stage.name);

  async function saveName() {
    setEditingName(false);
    const trimmed = nameDraft.trim();
    if (trimmed && trimmed !== stage.name) {
      await onRenameStage(stage.id, trimmed);
    } else {
      setNameDraft(stage.name);
    }
  }

  return (
    <div className="stage-column">
      <div className="stage-header">
        {editingName ? (
          <input
            className="stage-name-input"
            value={nameDraft}
            autoFocus
            maxLength={100}
            onChange={(e) => setNameDraft(e.target.value)}
            onBlur={saveName}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") {
                setNameDraft(stage.name);
                setEditingName(false);
              }
            }}
          />
        ) : (
          <h3
            onClick={() => canWrite && setEditingName(true)}
            title={canWrite ? "Клацніть, щоб перейменувати" : undefined}
          >
            {stage.name}
          </h3>
        )}
        <span className="stage-count">{cards.length}</span>
        {canWrite && (
          <button
            className="icon-button"
            title="Видалити етап"
            onClick={() => onDeleteStage(stage.id)}
          >
            ✕
          </button>
        )}
      </div>

      <Droppable droppableId={stage.id} isDropDisabled={!canWrite}>
        {(provided, snapshot) => (
          <div
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={`stage-body${snapshot.isDraggingOver ? " drag-over" : ""}`}
          >
            {cards.map((card, index) => (
              <CardItem
                key={card.id}
                card={card}
                index={index}
                draggable={canWrite}
                onOpen={onOpenCard}
              />
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>

      {canWrite &&
        (adding ? (
          <NewCardForm
            onSubmit={async (company, position) => {
              await onAddCard(stage.id, company, position);
              setAdding(false);
            }}
            onCancel={() => setAdding(false)}
          />
        ) : (
          <button className="add-card-button" onClick={() => setAdding(true)}>
            + Картка
          </button>
        ))}
    </div>
  );
}
