"""
Інструмент: Claude
Застосування: Розробка in-memory сховища з хардкодними даними (заглушками) для
демонстрації Code-First підходу без підключення БД.
Верифікація: Перевірено вручну коректність роботи CRUD-операцій з тестовими даними,
узгоджено командою.

In-memory сховище-заглушка.

Це НЕ реальна база даних — лише демонстраційні дані для Code-First лабораторної
(вимога "відповіді-заглушки для демонстрації"). Реальна інтеграція з PostgreSQL
(ADR-002, data-model.md) буде додана окремо бекенд-командою.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

DEMO_BOARD_ID = UUID("11111111-1111-1111-1111-111111111111")
DEMO_STAGE_ID = UUID("22222222-2222-2222-2222-222222222222")

_now = datetime.now(timezone.utc)

users_db: dict[UUID, dict] = {}
boards_db: dict[UUID, dict] = {}
stages_db: dict[UUID, dict] = {}
board_mentors_db: dict[tuple[UUID, UUID], dict] = {}

cards_db: dict[UUID, dict] = {
    UUID("33333333-3333-3333-3333-333333333333"): {
        "id": UUID("33333333-3333-3333-3333-333333333333"),
        "board_id": DEMO_BOARD_ID,
        "stage_id": DEMO_STAGE_ID,
        "company": "Acme Corp",
        "position": "Backend Engineer",
        "vacancy_url": "https://acme.example.com/jobs/42",
        "requirements_text": "3+ роки Python, знання FastAPI",
        "deadline": None,
        "notifications_enabled": True,
        "status": "active",
        "position_index": 0,
        "created_at": _now,
        "updated_at": _now,
    }
}

card_links_db: dict[UUID, dict] = {}


def create_user(email: str, password_hash: str, role: str) -> dict:
    user = {
        "id": uuid4(),
        "email": email.lower(),
        "password_hash": password_hash,
        "role": role,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    users_db[user["id"]] = user
    return user


def get_user(user_id: UUID) -> Optional[dict]:
    return users_db.get(user_id)


def get_user_by_email(email: str) -> Optional[dict]:
    email = email.lower()
    return next((user for user in users_db.values() if user["email"] == email), None)


def create_board(owner_id: UUID) -> dict:
    board = {
        "id": uuid4(),
        "owner_id": owner_id,
        "created_at": datetime.now(timezone.utc),
    }
    boards_db[board["id"]] = board
    return board


def get_board(board_id: UUID) -> Optional[dict]:
    if board_id == DEMO_BOARD_ID:
        return boards_db.setdefault(
            board_id,
            {
                "id": board_id,
                "owner_id": None,
                "created_at": datetime.now(timezone.utc),
            },
        )
    return boards_db.get(board_id)


def has_board_access(board_id: UUID, mentor_id: UUID) -> bool:
    relation = board_mentors_db.get((board_id, mentor_id))
    return relation is not None and relation["status"] == "accepted"


def claim_demo_board(owner_id: UUID) -> dict:
    board = get_board(DEMO_BOARD_ID)
    if board is not None and board["owner_id"] is None:
        board["owner_id"] = owner_id
    return board


def board_exists(board_id: UUID) -> bool:
    return get_board(board_id) is not None


def get_card(card_id: UUID) -> Optional[dict]:
    return cards_db.get(card_id)


def list_cards(
    board_id: UUID, stage_id: Optional[UUID], status_: Optional[str]
) -> list[dict]:
    items = [c for c in cards_db.values() if c["board_id"] == board_id]
    if stage_id is not None:
        items = [c for c in items if c["stage_id"] == stage_id]
    if status_ is not None:
        items = [c for c in items if c["status"] == status_]
    return sorted(items, key=lambda c: c["position_index"])


def create_card(board_id: UUID, data: dict) -> dict:
    card_id = uuid4()
    now = datetime.now(timezone.utc)
    record = {
        "id": card_id,
        "board_id": board_id,
        "position_index": len(list_cards(board_id, data["stage_id"], None)),
        "status": "active",
        "created_at": now,
        "updated_at": now,
        **data,
    }
    cards_db[card_id] = record
    return record


def update_card(card_id: UUID, changes: dict) -> Optional[dict]:
    record = cards_db.get(card_id)
    if record is None:
        return None
    record.update({k: v for k, v in changes.items() if v is not None})
    record["updated_at"] = datetime.now(timezone.utc)
    return record


def delete_card(card_id: UUID) -> bool:
    return cards_db.pop(card_id, None) is not None


def move_card(card_id: UUID, stage_id: UUID, position_index: int) -> Optional[dict]:
    record = cards_db.get(card_id)
    if record is None:
        return None
    record["stage_id"] = stage_id
    record["position_index"] = position_index
    record["updated_at"] = datetime.now(timezone.utc)
    return record


def list_links(card_id: UUID) -> list[dict]:
    return [link for link in card_links_db.values() if link["card_id"] == card_id]


def create_link(card_id: UUID, url: str) -> dict:
    link_id = uuid4()
    record = {
        "id": link_id,
        "card_id": card_id,
        "url": url,
        "created_at": datetime.now(timezone.utc),
    }
    card_links_db[link_id] = record
    return record


def delete_link(card_id: UUID, link_id: UUID) -> bool:
    link = card_links_db.get(link_id)
    if link is None or link["card_id"] != card_id:
        return False
    del card_links_db[link_id]
    return True
