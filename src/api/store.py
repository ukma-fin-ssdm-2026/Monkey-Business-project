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
DEMO_USER_ID = UUID("1a08b8c8-e8dd-452c-aa61-2448d36a4dd8")

DEFAULT_STAGE_NAMES = ["Відгук", "Скринінг", "Технічне інтерв'ю", "Офер"]

_now = datetime.now(timezone.utc)

_demo_salt = "64656d6f5f73616c745f313233343536"
_demo_digest = "a4dd4274787c86f531bbcc05aa2b09081ff14a2601d4d7c9e1e8d862bfb9e1d9"
_demo_pw_hash = f"{_demo_salt}${_demo_digest}"

users_db: dict[UUID, dict] = {
    DEMO_USER_ID: {
        "id": DEMO_USER_ID,
        "email": "candidate@example.com",
        "password_hash": _demo_pw_hash,
        "role": "candidate",
        "is_active": True,
        "created_at": _now,
    }
}
boards_db: dict[UUID, dict] = {
    DEMO_BOARD_ID: {
        "id": DEMO_BOARD_ID,
        "owner_id": DEMO_USER_ID,
        "created_at": _now,
    }
}
stages_db: dict[UUID, dict] = {
    DEMO_STAGE_ID: {
        "id": DEMO_STAGE_ID,
        "board_id": DEMO_BOARD_ID,
        "name": "Відгук",
        "order_index": 0,
        "created_at": _now,
    },
    UUID("22222222-2222-2222-2222-222222222223"): {
        "id": UUID("22222222-2222-2222-2222-222222222223"),
        "board_id": DEMO_BOARD_ID,
        "name": "Скринінг",
        "order_index": 1,
        "created_at": _now,
    },
    UUID("22222222-2222-2222-2222-222222222224"): {
        "id": UUID("22222222-2222-2222-2222-222222222224"),
        "board_id": DEMO_BOARD_ID,
        "name": "Технічне інтерв'ю",
        "order_index": 2,
        "created_at": _now,
    },
    UUID("22222222-2222-2222-2222-222222222225"): {
        "id": UUID("22222222-2222-2222-2222-222222222225"),
        "board_id": DEMO_BOARD_ID,
        "name": "Офер",
        "order_index": 3,
        "created_at": _now,
    },
}
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
card_notes_db: dict[UUID, dict] = {
    UUID("44444444-4444-4444-4444-444444444444"): {
        "id": UUID("44444444-4444-4444-4444-444444444444"),
        "card_id": UUID("33333333-3333-3333-3333-333333333333"),
        "content": "Скринінг пройдено успішно. Очікується технічне інтерв'ю.",
        "source": "recruiter",
        "created_at": _now,
        "updated_at": _now,
    }
}


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


def init_default_stages(board_id: UUID) -> list[dict]:
    created = []
    for idx, name in enumerate(DEFAULT_STAGE_NAMES):
        stage_id = uuid4()
        stage = {
            "id": stage_id,
            "board_id": board_id,
            "name": name,
            "order_index": idx,
            "created_at": datetime.now(timezone.utc),
        }
        stages_db[stage_id] = stage
        created.append(stage)
    return created


def create_board(owner_id: UUID) -> dict:
    board_id = uuid4()
    board = {
        "id": board_id,
        "owner_id": owner_id,
        "created_at": datetime.now(timezone.utc),
    }
    boards_db[board_id] = board
    init_default_stages(board_id)
    return board


def get_board(board_id: UUID) -> Optional[dict]:
    if board_id == DEMO_BOARD_ID:
        return boards_db.setdefault(
            board_id,
            {
                "id": board_id,
                "owner_id": DEMO_USER_ID,
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


def list_stages(board_id: UUID) -> list[dict]:
    items = [s for s in stages_db.values() if s["board_id"] == board_id]
    return sorted(items, key=lambda s: s["order_index"])


def get_stage(stage_id: UUID) -> Optional[dict]:
    return stages_db.get(stage_id)


def create_stage(board_id: UUID, name: str, order_index: Optional[int] = None) -> dict:
    stage_id = uuid4()
    if order_index is None:
        existing = list_stages(board_id)
        order_index = len(existing)
    record = {
        "id": stage_id,
        "board_id": board_id,
        "name": name,
        "order_index": order_index,
        "created_at": datetime.now(timezone.utc),
    }
    stages_db[stage_id] = record
    return record


def update_stage(stage_id: UUID, changes: dict) -> Optional[dict]:
    record = stages_db.get(stage_id)
    if record is None:
        return None
    record.update({k: v for k, v in changes.items() if v is not None})
    return record


def stage_has_cards(stage_id: UUID) -> bool:
    return any(c["stage_id"] == stage_id for c in cards_db.values())


def delete_stage(board_id: UUID, stage_id: UUID) -> tuple[bool, Optional[str]]:
    record = stages_db.get(stage_id)
    if record is None or record["board_id"] != board_id:
        return False, "Етап не знайдено"
    if stage_has_cards(stage_id):
        return False, "Неможливо видалити етап, у якому є картки"
    del stages_db[stage_id]
    return True, None


def list_card_notes(card_id: UUID) -> list[dict]:
    items = [n for n in card_notes_db.values() if n["card_id"] == card_id]
    return sorted(items, key=lambda n: n["created_at"])


def get_card_note(note_id: UUID) -> Optional[dict]:
    return card_notes_db.get(note_id)


def create_card_note(card_id: UUID, content: str, source: str) -> dict:
    note_id = uuid4()
    now = datetime.now(timezone.utc)
    record = {
        "id": note_id,
        "card_id": card_id,
        "content": content,
        "source": source,
        "created_at": now,
        "updated_at": now,
    }
    card_notes_db[note_id] = record
    return record


def update_card_note(note_id: UUID, content: str) -> Optional[dict]:
    record = card_notes_db.get(note_id)
    if record is None:
        return None
    record["content"] = content
    record["updated_at"] = datetime.now(timezone.utc)
    return record


def delete_card_note(card_id: UUID, note_id: UUID) -> bool:
    record = card_notes_db.get(note_id)
    if record is None or record["card_id"] != card_id:
        return False
    del card_notes_db[note_id]
    return True
