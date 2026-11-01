"""
Інструмент: Gemini
Застосування: Створення REST-роутера для керування Канбан-етапами дошки (FR-003, FR-024).
Верифікація: Перевірено валідацію вхідних даних через Pydantic, коректність кодів відповідей
(200, 201, 204, 404, 409) та захист від видалення етапів із прив'язаними картками.

Ресурс: Stages (`/boards/{board_id}/stages`).
Покриває FR-003 (етапи Канбан-дошки: «Відгук», «Скринінг», «Технічне інтерв'ю», «Офер»)
та FR-024 (керування набором етапів).
"""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from fastapi import APIRouter, Path, status

from ..auth import CandidateOrAdmin, CurrentUser
from ..db import Repos
from ..domain import Stage
from ..errors import ConflictError, NotFoundError, error_responses
from ..repositories.base import Repositories
from ..schemas import StageCreate, StageOut, StageUpdate
from .card_access import require_board

router = APIRouter(prefix="/boards/{board_id}/stages", tags=["Stages"])


def _require_stage(repos: Repositories, board_id: UUID, stage_id: UUID) -> Stage:
    stage = repos.stages.get(stage_id)
    if stage is None or stage.board_id != board_id:
        raise NotFoundError(f"Етап {stage_id} на дошці {board_id} не знайдено")
    return stage


@router.get(
    "",
    response_model=list[StageOut],
    status_code=status.HTTP_200_OK,
    summary="Список етапів Канбан-дошки",
    description=(
        "Повертає всі етапи вказаної дошки, відсортовані за порядком "
        "відображення order_index (FR-003)."
    ),
    responses=error_responses("Дошку не знайдено", "Некоректний ідентифікатор дошки"),
)
def list_stages(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    user: CurrentUser = None,
    repos: Repos = None,
) -> list[StageOut]:
    require_board(repos, board_id, user)
    return [StageOut.model_validate(s) for s in repos.stages.list_for_board(board_id)]


@router.post(
    "",
    response_model=StageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Створити новий етап дошки",
    description=(
        "Створює новий кастомний етап для вказаної дошки. "
        "Дозволено лише кандидату-власнику дошки або адміністратору."
    ),
    responses=error_responses(
        "Дошку не знайдено",
        "Невалідна назва етапу або параметри",
    ),
)
def create_stage(
    payload: StageCreate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    user: CandidateOrAdmin = None,
    repos: Repos = None,
) -> StageOut:
    require_board(repos, board_id, user, write=True)
    order_index = payload.order_index
    if order_index is None:
        order_index = len(repos.stages.list_for_board(board_id))
    stage = repos.stages.add(
        Stage(board_id=board_id, name=payload.name, order_index=order_index)
    )
    return StageOut.model_validate(stage)


@router.patch(
    "/{stage_id}",
    response_model=StageOut,
    status_code=status.HTTP_200_OK,
    summary="Оновити етап дошки",
    description=(
        "Часткове оновлення назви етапу або його порядку сортування. "
        "Потрібно передати хоча б одне поле для зміни."
    ),
    responses=error_responses(
        "Дошку або етап не знайдено",
        "Невалідні дані оновлення",
    ),
)
def update_stage(
    payload: StageUpdate,
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    stage_id: UUID = Path(..., description="Ідентифікатор етапу"),
    user: CandidateOrAdmin = None,
    repos: Repos = None,
) -> StageOut:
    require_board(repos, board_id, user, write=True)
    stage = _require_stage(repos, board_id, stage_id)
    changes = {
        k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None
    }
    stage = repos.stages.save(replace(stage, **changes))
    return StageOut.model_validate(stage)


@router.delete(
    "/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Видалити етап дошки",
    description=(
        "Видаляє етап із дошки. Якщо в етапі присутні картки вакансій, "
        "операція повертає 409 Conflict задля збереження цілісності даних."
    ),
    responses=error_responses(
        "Дошку або етап не знайдено",
        "Некоректний ідентифікатор",
        conflict="Неможливо видалити етап, у якому є картки",
    ),
)
def delete_stage(
    board_id: UUID = Path(..., description="Ідентифікатор дошки"),
    stage_id: UUID = Path(..., description="Ідентифікатор етапу"),
    user: CandidateOrAdmin = None,
    repos: Repos = None,
) -> None:
    require_board(repos, board_id, user, write=True)
    _require_stage(repos, board_id, stage_id)
    if repos.stages.has_cards(stage_id):
        raise ConflictError("Неможливо видалити етап, у якому є картки")
    repos.stages.delete(stage_id)
