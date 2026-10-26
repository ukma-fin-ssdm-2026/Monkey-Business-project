/**
 * Інструмент: Claude
 * Застосування: Draggable-картка вакансії в колонці — компанія, посада,
 * статус (CardStatus зі schemas.py), прострочений дедлайн.
 * Верифікація: Перевірено типи й білд; локалізація дати/часу — uk-UA.
 */

import { Draggable } from "@hello-pangea/dnd";
import type { CardOut } from "../api/types";

const STATUS_LABEL: Record<CardOut["status"], string> = {
  active: "Активна",
  rejected: "Відмова",
  offer_accepted: "Офер",
};

function formatDeadline(iso: string | null): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  return date.toLocaleString("uk-UA", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isOverdue(iso: string | null): boolean {
  if (!iso) return false;
  return new Date(iso).getTime() < Date.now();
}

interface Props {
  card: CardOut;
  index: number;
  draggable: boolean;
  onOpen: (cardId: string) => void;
}

export function CardItem({ card, index, draggable, onOpen }: Props) {
  const deadline = formatDeadline(card.deadline);

  // The library ignores drags that start on a <button> unless interactive
  // element blocking is disabled.
  return (
    <Draggable
      draggableId={card.id}
      index={index}
      isDragDisabled={!draggable}
      disableInteractiveElementBlocking
    >
      {(provided, snapshot) => (
        <button
          type="button"
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={`card-item status-${card.status}${
            snapshot.isDragging ? " dragging" : ""
          }`}
          onClick={() => onOpen(card.id)}
        >
          <span className="card-item-header">
            <span className="card-company">{card.company}</span>
            <span className={`status-badge status-${card.status}`}>
              {STATUS_LABEL[card.status]}
            </span>
          </span>
          <span className="card-position">{card.position}</span>
          {deadline && (
            <span className={`card-deadline${isOverdue(card.deadline) ? " overdue" : ""}`}>
              ⏰ {deadline}
            </span>
          )}
        </button>
      )}
    </Draggable>
  );
}
