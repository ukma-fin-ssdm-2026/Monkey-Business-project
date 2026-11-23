"""Codex: PostgreSQL row locks prevent concurrent invitation activation.

Uses only the dedicated TEST_DATABASE_URL managed by integration fixtures.
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

from fastapi.testclient import TestClient
from src.api.main import app
from src.api.repositories.sql import UserRow
from src.api.routers import mentors
from src.api.auth import _verify_password


def _parallel_accept(tokens):
    barrier = Barrier(2)

    def request(index):
        with_client = TestClient(app)  # no lifespan / OpenAPI file writes
        try:
            barrier.wait(timeout=10)
            return with_client.post(
                f"/v1/invitations/{tokens[index]}/accept",
                json={"password": f"concurrent-test-pass-{index}"},
            )
        finally:
            with_client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(request, range(2)))


def test_same_invitation_is_accepted_exactly_once(
    client, owner, monkeypatch, new_session
):
    monkeypatch.setattr(mentors, "_send_invitation_email", lambda *args: None)
    invitation = client.post(
        f"/v1/boards/{owner.board_id}/mentors",
        headers=owner.headers,
        json={"email": "parallel@example.com"},
    )
    assert invitation.status_code == 201
    data = invitation.json()
    responses = _parallel_accept([data["invite_token"], data["invite_token"]])
    assert sorted(response.status_code for response in responses) == [200, 403]
    winner = next(
        index for index, response in enumerate(responses) if response.status_code == 200
    )
    with new_session() as session:
        saved = session.get(UserRow, UUID(data["mentor_id"]))
        assert _verify_password(f"concurrent-test-pass-{winner}", saved.password_hash)


def test_different_invitations_cannot_overwrite_same_mentor_password(
    client, owner, monkeypatch, new_session
):
    monkeypatch.setattr(mentors, "_send_invitation_email", lambda *args: None)
    other = client.post(
        "/v1/auth/register",
        json={
            "email": "other-owner@example.com",
            "password": "other-owner-test-pass",  # pragma: allowlist secret
        },
    )
    assert other.status_code == 201
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    other_board = client.get("/v1/boards", headers=other_headers).json()[0]["id"]
    invitations = []
    for board_id, headers in (
        (owner.board_id, owner.headers),
        (other_board, other_headers),
    ):
        response = client.post(
            f"/v1/boards/{board_id}/mentors",
            headers=headers,
            json={"email": "shared-mentor@example.com"},
        )
        assert response.status_code == 201
        invitations.append(response.json())
    responses = _parallel_accept([item["invite_token"] for item in invitations])
    assert sorted(response.status_code for response in responses) == [200, 401]
    winner = next(
        index for index, response in enumerate(responses) if response.status_code == 200
    )
    with new_session() as session:
        saved = session.get(UserRow, UUID(invitations[0]["mentor_id"]))
        assert _verify_password(f"concurrent-test-pass-{winner}", saved.password_hash)
