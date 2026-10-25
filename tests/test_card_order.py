"""TP-03: FR-005 / US-005. Card ordering with an in-memory repository."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.api.domain import Board, Card, Stage, User
from src.api.errors import ForbiddenError, NotFoundError
from src.api.routers.cards import move_card
from src.api.schemas import CardMove


class MemoryCards:
    def __init__(self, cards):
        self.items = {card.id: card for card in cards}

    def get(self, card_id):
        return self.items.get(card_id)

    def save(self, card):
        self.items[card.id] = card
        return card

    def list_for_board(self, board_id, stage_id, status):
        return sorted(
            (
                card
                for card in self.items.values()
                if card.board_id == board_id
                and (stage_id is None or card.stage_id == stage_id)
                and (status is None or card.status == status)
            ),
            key=lambda card: card.position_index,
        )


@pytest.fixture
def board_cards():
    owner = User(email="owner@example.com", password_hash="unused", role="candidate")
    board = Board(owner_id=owner.id)
    stages = [
        Stage(board_id=board.id, name=name, order_index=index)
        for index, name in enumerate(("S1", "S2"))
    ]
    cards = [
        Card(
            board_id=board.id,
            stage_id=stages[0].id,
            company=name,
            position="Developer",
            position_index=index,
        )
        for index, name in enumerate(("A", "B", "C"))
    ]
    repos = SimpleNamespace(
        boards=Mock(get=Mock(return_value=board)),
        stages=Mock(
            get=Mock(
                side_effect=lambda key: next(
                    (stage for stage in stages if stage.id == key), None
                )
            )
        ),
        cards=MemoryCards(cards),
    )
    return owner, board, stages, cards, repos


@pytest.mark.parametrize(
    "source,target,expected",
    [(2, 0, "CAB"), (0, 2, "BCA"), (1, 1, "ABC"), (0, 99, "BCA")],
    ids=["TP-03", "move-to-end", "same-position", "clamp-to-end"],
)
def test_tp03_reorder_preserves_all_cards(board_cards, source, target, expected):
    """TP-03 / FR-005 / US-005: unique contiguous positions in both directions."""
    owner, board, stages, cards, repos = board_cards

    result = move_card(
        CardMove(stage_id=stages[0].id, position_index=target),
        board_id=board.id,
        card_id=cards[source].id,
        user=owner,
        repos=repos,
    )

    ordered = repos.cards.list_for_board(board.id, stages[0].id, None)
    assert [card.company for card in ordered] == list(expected)
    assert [card.position_index for card in ordered] == [0, 1, 2]
    assert {card.id for card in ordered} == {card.id for card in cards}
    assert result.position_index == min(target, 2)


def test_cross_stage_move_compacts_source_and_shifts_destination(board_cards):
    """FR-004, FR-005 / US-005: moving B leaves no source-stage gap."""
    owner, board, stages, cards, repos = board_cards
    destination = Card(
        board_id=board.id,
        stage_id=stages[1].id,
        company="D",
        position="Developer",
        position_index=0,
    )
    repos.cards.items[destination.id] = destination

    move_card(
        CardMove(stage_id=stages[1].id, position_index=0),
        board_id=board.id,
        card_id=cards[1].id,
        user=owner,
        repos=repos,
    )

    for stage, names in zip(stages, ("AC", "BD")):
        ordered = repos.cards.list_for_board(board.id, stage.id, None)
        assert [card.company for card in ordered] == list(names)
        assert [card.position_index for card in ordered] == [0, 1]
    assert len(repos.cards.items) == 4


def test_move_to_foreign_stage_does_not_modify_cards(board_cards):
    """FR-004 / US-005: rejected destination cannot change existing order."""
    owner, board, stages, cards, repos = board_cards
    foreign_stage = Stage(
        board_id=Board(owner_id=owner.id).id, name="Other", order_index=0
    )
    repos.stages.get.side_effect = None
    repos.stages.get.return_value = foreign_stage
    before = dict(repos.cards.items)

    with pytest.raises(NotFoundError):
        move_card(
            CardMove(stage_id=foreign_stage.id, position_index=0),
            board_id=board.id,
            card_id=cards[0].id,
            user=owner,
            repos=repos,
        )

    assert repos.cards.items == before


def test_mentor_cannot_reorder_cards(board_cards):
    """SEC-3 / FR-014 / US-002: read access does not allow reordering."""
    _, board, stages, cards, repos = board_cards
    mentor = User(email="mentor@example.com", password_hash="unused", role="mentor")
    before = dict(repos.cards.items)

    with pytest.raises(ForbiddenError):
        move_card(
            CardMove(stage_id=stages[0].id, position_index=0),
            board_id=board.id,
            card_id=cards[2].id,
            user=mentor,
            repos=repos,
        )

    assert repos.cards.items == before
