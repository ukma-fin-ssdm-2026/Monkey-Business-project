/**
 * Інструмент: Claude
 * Застосування: Канбан-дошка — колонки-етапи (GET .../stages) та картки
 * (GET .../cards з догортанням сторінок), drag-and-drop між етапами
 * (POST .../cards/{id}/move), керування етапами й картками; доступ на
 * запис обмежено на UI так само, як require_board_access/CandidateOrAdmin
 * обмежують його на бекенді (auth.py).
 * Верифікація: Перевірено типи (tsc -b) і продакшн-білд (vite build) без
 * помилок; ручний прогін проти живого API (з docker compose) не
 * виконувався в цій сесії — перевірте вхід/дошку/drag-and-drop локально.
 */

import { DragDropContext, type DropResult } from "@hello-pangea/dnd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { CardOut, StageOut } from "../api/types";
import { StageColumn } from "../components/StageColumn";
import { CardModal } from "../components/CardModal";

async function fetchAllCards(boardId: string): Promise<CardOut[]> {
  const limit = 100;
  let offset = 0;
  const all: CardOut[] = [];
  // Дошка розрахована на ~100 карток (api-design.md), але на випадок
  // більшого обсягу довантажуємо сторінками.
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const page = await api.listCards(boardId, limit, offset);
    all.push(...page.items);
    if (all.length >= page.pagination.total || page.items.length === 0) break;
    offset += limit;
  }
  return all;
}

export function BoardPage() {
  const { user, boardId, setBoardId, logout } = useAuth();
  const navigate = useNavigate();

  const [stages, setStages] = useState<StageOut[]>([]);
  const [cards, setCards] = useState<CardOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);

  const canWrite = user?.role === "candidate" || user?.role === "admin";

  const load = useCallback(async () => {
    if (!boardId) return;
    setLoading(true);
    setError(null);
    try {
      const [stagesData, cardsData] = await Promise.all([
        api.listStages(boardId),
        fetchAllCards(boardId),
      ]);
      setStages([...stagesData].sort((a, b) => a.order_index - b.order_index));
      setCards(cardsData);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Не вдалося завантажити дошку");
      }
    } finally {
      setLoading(false);
    }
  }, [boardId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!boardId) navigate("/board/setup", { replace: true });
  }, [boardId, navigate]);

  if (!boardId) {
    return null;
  }

  async function handleDragEnd(result: DropResult) {
    if (!boardId || !canWrite) return;
    const { destination, source, draggableId } = result;
    if (!destination) return;
    if (
      destination.droppableId === source.droppableId &&
      destination.index === source.index
    ) {
      return;
    }

    const card = cards.find((c) => c.id === draggableId);
    if (!card) return;

    // Оптимістичне оновлення: переносимо картку локально одразу.
    const previousCards = cards;
    const withoutCard = cards.filter((c) => c.id !== draggableId);
    const destCards = withoutCard
      .filter((c) => c.stage_id === destination.droppableId)
      .sort((a, b) => a.position_index - b.position_index);
    destCards.splice(destination.index, 0, {
      ...card,
      stage_id: destination.droppableId,
      position_index: destination.index,
    });
    const rest = withoutCard.filter((c) => c.stage_id !== destination.droppableId);
    setCards([...rest, ...destCards]);

    try {
      await api.moveCard(boardId, draggableId, {
        stage_id: destination.droppableId,
        position_index: destination.index,
      });
      await load();
    } catch (err) {
      setCards(previousCards);
      setError(err instanceof ApiError ? err.message : "Не вдалося перемістити картку");
    }
  }

  async function handleAddCard(stageId: string, company: string, position: string) {
    if (!boardId) return;
    try {
      await api.createCard(boardId, { company, position, stage_id: stageId });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося створити картку");
    }
  }

  async function handleAddStage() {
    if (!boardId) return;
    const name = window.prompt("Назва нового етапу");
    if (!name || !name.trim()) return;
    try {
      await api.createStage(boardId, { name: name.trim() });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося створити етап");
    }
  }

  async function handleRenameStage(stageId: string, name: string) {
    if (!boardId) return;
    try {
      await api.updateStage(boardId, stageId, { name });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося перейменувати етап");
    }
  }

  async function handleDeleteStage(stageId: string) {
    if (!boardId) return;
    if (!window.confirm("Видалити цей етап?")) return;
    try {
      await api.deleteStage(boardId, stageId);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не вдалося видалити етап");
    }
  }

  const selectedCard = cards.find((c) => c.id === selectedCardId) ?? null;

  return (
    <div className="board-page">
      <header className="board-topbar">
        <div>
          <h1>Tech Interview Board</h1>
          <span className="board-id-hint">board_id: {boardId}</span>
        </div>
        <div className="board-topbar-actions">
          <span className="current-user">
            {user?.email} ({user?.role})
          </span>
          <button
            className="secondary"
            onClick={() => navigate("/board/setup")}
          >
            Змінити дошку
          </button>
          <button className="secondary" onClick={logout}>
            Вийти
          </button>
        </div>
      </header>

      {error && (
        <div className="banner-error">
          {error}
          <button className="icon-button" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}

      {loading ? (
        <p className="board-status">Завантаження дошки...</p>
      ) : (
        <DragDropContext onDragEnd={handleDragEnd}>
          <div className="board-columns">
            {stages.map((stage) => (
              <StageColumn
                key={stage.id}
                stage={stage}
                cards={cards
                  .filter((c) => c.stage_id === stage.id)
                  .sort((a, b) => a.position_index - b.position_index)}
                canWrite={!!canWrite}
                onOpenCard={setSelectedCardId}
                onAddCard={handleAddCard}
                onRenameStage={handleRenameStage}
                onDeleteStage={handleDeleteStage}
              />
            ))}
            {canWrite && (
              <button className="add-stage-button" onClick={handleAddStage}>
                + Етап
              </button>
            )}
          </div>
        </DragDropContext>
      )}

      {selectedCard && boardId && (
        <CardModal
          boardId={boardId}
          card={selectedCard}
          canWrite={!!canWrite}
          onClose={() => setSelectedCardId(null)}
          onUpdated={(updated) => {
            setCards((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
          }}
          onDeleted={(cardId) => {
            setCards((prev) => prev.filter((c) => c.id !== cardId));
            setSelectedCardId(null);
          }}
        />
      )}
    </div>
  );
}
