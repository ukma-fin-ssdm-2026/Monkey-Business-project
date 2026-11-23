"""Codex: HTTP regressions for FR-007–FR-014 and session expiry.

SQLite verifies HTTP contracts and transaction rollback; PostgreSQL concurrency
is covered separately in tests/integration/test_invitation_concurrency.py.
"""

from datetime import timedelta
from uuid import UUID
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from src.api import auth, db
from src.api.domain import utcnow
from src.api.main import app
from src.api.repositories.sql import (
    Base,
    BoardMentorRow,
    CardRow,
    CardLinkRow,
    CardNoteRow,
    SqlCardNoteRepository,
    UserRow,
)
from src.api.routers import mentors

UNUSED_TEST_PASSWORD = "unused-test-password"  # pragma: allowlist secret


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'phase-one.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(db, "_session_factory", lambda: factory)
    monkeypatch.setattr(mentors, "_send_invitation_email", lambda *args: None)
    monkeypatch.setenv("JWT_SECRET", "first-phase-test-secret-at-least-32-bytes")
    client = TestClient(app, raise_server_exceptions=False)
    registered = client.post(
        "/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "candidate-test-pass",  # pragma: allowlist secret
        },
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    board = client.get("/v1/boards", headers=headers).json()[0]["id"]
    stage = client.get(f"/v1/boards/{board}/stages", headers=headers).json()[0]["id"]
    yield client, factory, headers, board, stage
    client.close()
    engine.dispose()


def invite(env, email="mentor@example.com"):
    client, _, headers, board, _ = env
    response = client.post(
        f"/v1/boards/{board}/mentors", headers=headers, json={"email": email}
    )
    assert response.status_code == 201
    return response.json()


def accept(client, invitation, **kwargs):
    return client.post(f"/v1/invitations/{invitation['invite_token']}/accept", **kwargs)


def test_new_mentor_activation_returns_session_and_is_single_use(api_env):
    client, _, _, board, _ = api_env
    invitation = invite(api_env)
    details = client.get(f"/v1/invitations/{invitation['invite_token']}").json()
    assert details["requires_password"] is True
    assert details["expires_at"]
    activated = accept(client, invitation, json={"password": "mentor-test-pass"})
    assert activated.status_code == 200
    session = activated.json()
    assert session["user"]["id"] == invitation["mentor_id"]
    assert session["expires_in"] == 86400
    claims = jwt.decode(session["access_token"], auth._secret(), algorithms=["HS256"])
    assert 86395 <= claims["exp"] - utcnow().timestamp() <= 86400
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.get(f"/v1/boards/{board}/cards", headers=headers).status_code == 200
    assert (
        accept(client, invitation, json={"password": UNUSED_TEST_PASSWORD}).status_code
        == 403
    )
    assert (
        client.get(f"/v1/invitations/{invitation['invite_token']}").status_code == 404
    )


def test_existing_mentor_cannot_reset_password_via_reinvitation(api_env):
    client, factory, headers, board, _ = api_env
    first = invite(api_env)
    activated = accept(client, first, json={"password": "original-mentor-pass"}).json()
    with factory() as session:
        original_hash = session.get(UserRow, UUID(first["mentor_id"])).password_hash
    client.delete(f"/v1/boards/{board}/mentors/{first['mentor_id']}", headers=headers)
    second = invite(api_env)
    assert second["invite_token"] != first["invite_token"]
    details = client.get(f"/v1/invitations/{second['invite_token']}").json()
    assert details["requires_password"] is False
    assert (
        accept(client, second, json={"password": UNUSED_TEST_PASSWORD}).status_code
        == 401
    )
    with factory() as session:
        assert (
            session.get(UserRow, UUID(first["mentor_id"])).password_hash
            == original_hash
        )
    assert accept(client, second, headers=headers).status_code == 403
    mentor_headers = {"Authorization": f"Bearer {activated['access_token']}"}
    assert accept(client, second, headers=mentor_headers).status_code == 200


@pytest.mark.parametrize(
    "invalid_state", ["expired", "revoked", "blocked", "wrong-role"]
)
def test_invalid_invitation_never_activates_account(api_env, invalid_state):
    client, factory, _, _, _ = api_env
    invitation = invite(api_env)
    with factory.begin() as session:
        row = session.get(BoardMentorRow, UUID(invitation["id"]))
        user = session.get(UserRow, UUID(invitation["mentor_id"]))
        if invalid_state == "expired":
            row.invited_at = utcnow() - mentors.INVITATION_TTL
        elif invalid_state == "revoked":
            row.status = "revoked"
        elif invalid_state == "blocked":
            user.is_active = False
        else:
            user.role = "candidate"
    assert (
        client.get(f"/v1/invitations/{invitation['invite_token']}").status_code == 404
    )
    assert (
        accept(client, invitation, json={"password": UNUSED_TEST_PASSWORD}).status_code
        == 403
    )
    with factory() as session:
        assert session.get(UserRow, UUID(invitation["mentor_id"])).password_hash == ""


def test_expired_pending_invitation_can_be_reissued(api_env):
    client, factory, _, _, _ = api_env
    first = invite(api_env)
    with factory.begin() as session:
        session.get(BoardMentorRow, UUID(first["id"])).invited_at = (
            utcnow() - timedelta(days=8)
        )
    second = invite(api_env)
    assert second["id"] == first["id"]
    assert second["invite_token"] != first["invite_token"]
    assert (
        accept(client, first, json={"password": UNUSED_TEST_PASSWORD}).status_code
        == 403
    )
    assert (
        accept(client, second, json={"password": UNUSED_TEST_PASSWORD}).status_code
        == 200
    )


def create_full_card(env):
    client, _, headers, board, stage = env
    response = client.post(
        f"/v1/boards/{board}/cards",
        headers=headers,
        json={
            "stage_id": stage,
            "company": "Acme",
            "position": "Engineer",
            "vacancy_url": "https://example.com/job",
            "requirements_text": "Python",
            "deadline": "2026-12-10T12:30:00+02:00",
            "notifications_enabled": False,
            "links": ["https://example.com/task", "https://example.com/repo"],
            "notes": [{"content": "Initial feedback", "source": "recruiter"}],
        },
    )
    assert response.status_code == 201, response.text
    return f"/v1/boards/{board}/cards/{response.json()['id']}"


def test_full_card_edit_clear_and_reload(api_env):
    client, _, headers, _, _ = api_env
    path = create_full_card(api_env)
    links = client.get(f"{path}/links", headers=headers).json()
    notes = client.get(f"{path}/notes", headers=headers).json()
    assert len(links) == 2 and len(notes) == 1
    assert (
        client.patch(
            path,
            headers=headers,
            json={
                "vacancy_url": None,
                "requirements_text": None,
                "deadline": None,
            },
        ).status_code
        == 200
    )
    saved = client.get(path, headers=headers).json()
    assert saved["company"] == "Acme" and saved["notifications_enabled"] is False
    assert all(
        saved[field] is None
        for field in ("vacancy_url", "requirements_text", "deadline")
    )
    assert (
        client.patch(
            f"{path}/links/{links[0]['id']}",
            headers=headers,
            json={"url": "https://example.com/revised"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{path}/notes/{notes[0]['id']}",
            headers=headers,
            json={"content": "Revised feedback"},
        ).status_code
        == 200
    )
    revised_links = client.get(f"{path}/links", headers=headers).json()
    assert revised_links[0]["url"] == "https://example.com/revised"
    assert revised_links[0]["created_at"] == links[0]["created_at"]
    revised_notes = client.get(f"{path}/notes", headers=headers).json()
    assert revised_notes[0]["content"] == "Revised feedback"
    assert revised_notes[0]["created_at"] == notes[0]["created_at"]


@pytest.mark.parametrize(
    "payload",
    [
        {"company": None},
        {"position": "   "},
        {"status": None},
        {"notifications_enabled": None},
        {"vacancy_url": "invalid"},
    ],
)
def test_patch_rejects_invalid_required_fields(api_env, payload):
    client, _, headers, _, _ = api_env
    path = create_full_card(api_env)
    assert client.patch(path, headers=headers, json=payload).status_code == 422
    assert client.get(path, headers=headers).json()["company"] == "Acme"


def test_card_creation_rolls_back_children_on_storage_failure(api_env, monkeypatch):
    client, factory, headers, board, stage = api_env

    def fail(*args):
        raise SQLAlchemyError("injected note storage failure")

    monkeypatch.setattr(SqlCardNoteRepository, "add", fail)
    response = client.post(
        f"/v1/boards/{board}/cards",
        headers=headers,
        json={
            "stage_id": stage,
            "company": "Acme",
            "position": "Engineer",
            "links": ["https://example.com/task"],
            "notes": [{"content": "Feedback"}],
        },
    )
    assert response.status_code == 500
    with factory() as session:
        for table in (CardRow, CardLinkRow, CardNoteRow):
            assert session.scalar(select(func.count()).select_from(table)) == 0


def test_invalid_children_prevent_card_creation(api_env):
    client, factory, headers, board, stage = api_env
    for extra in ({"links": ["not-url"]}, {"notes": [{"content": "   "}]}):
        result = client.post(
            f"/v1/boards/{board}/cards",
            headers=headers,
            json={
                "stage_id": stage,
                "company": "Acme",
                "position": "Engineer",
                **extra,
            },
        )
        assert result.status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(CardRow)) == 0


def test_mentor_author_survives_revocation_and_writes_are_forbidden(api_env):
    client, _, headers, board, _ = api_env
    path = create_full_card(api_env)
    invitation = invite(api_env)
    session = accept(client, invitation, json={"password": "mentor-test-pass"}).json()
    mentor_headers = {"Authorization": f"Bearer {session['access_token']}"}
    pending = invite(api_env, "other-mentor@example.com")
    listed = client.get(f"/v1/boards/{board}/mentors", headers=mentor_headers).json()
    assert all(item["invite_token"] is None for item in listed)
    assert pending["invite_token"]
    links = client.get(f"{path}/links", headers=headers).json()
    notes = client.get(f"{path}/notes", headers=headers).json()
    assert (
        client.patch(
            path, headers=mentor_headers, json={"company": "Changed"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{path}/links/{links[0]['id']}",
            headers=mentor_headers,
            json={"url": "https://example.com/no"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{path}/notes/{notes[0]['id']}",
            headers=mentor_headers,
            json={"content": "Changed"},
        ).status_code
        == 403
    )
    comment = client.post(
        f"{path}/comments", headers=mentor_headers, json={"content": "Prepare SQL"}
    )
    assert comment.status_code == 201
    assert comment.json()["author_name"] == "mentor@example.com"
    client.delete(
        f"/v1/boards/{board}/mentors/{invitation['mentor_id']}", headers=headers
    )
    assert client.get(path, headers=mentor_headers).status_code == 403
    assert (
        client.post(
            f"{path}/comments", headers=mentor_headers, json={"content": "More"}
        ).status_code
        == 403
    )
    saved = client.get(f"{path}/comments", headers=headers).json()[0]
    assert (
        saved["author_name"] == "mentor@example.com"
        and saved["author_role"] == "mentor"
    )


def test_expired_or_missing_session_cannot_open_board(api_env):
    client, _, headers, board, _ = api_env
    claims = jwt.decode(
        headers["Authorization"].split()[1], auth._secret(), algorithms=["HS256"]
    )
    claims["exp"] = utcnow() - timedelta(seconds=1)
    expired = jwt.encode(claims, auth._secret(), algorithm="HS256")
    assert client.get(f"/v1/boards/{board}/cards").status_code == 401
    assert (
        client.get(
            f"/v1/boards/{board}/cards", headers={"Authorization": f"Bearer {expired}"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("sandbox", ["true", "false"])
def test_email_uses_configured_delivery_mode(monkeypatch, sandbox):
    monkeypatch.setattr(mentors, "MAILTRAP_API_TOKEN", "test-token")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "board@example.com")
    monkeypatch.setenv("MAIL_FROM_NAME", "Test Board")
    monkeypatch.setenv("MAILTRAP_SANDBOX", sandbox)
    monkeypatch.setenv("MAILTRAP_INBOX_ID", "1234")
    constructor = MagicMock()
    monkeypatch.setattr(mentors.mt, "MailtrapClient", constructor)
    mentors._send_invitation_email("mentor@example.com", "test-invite", UUID(int=1))
    assert constructor.call_args.kwargs == {
        "token": "test-token",
        "sandbox": sandbox == "true",
        "inbox_id": "1234" if sandbox == "true" else None,
    }
    mail = constructor.return_value.send.call_args.args[0]
    assert mail.sender.email == "board@example.com"


def test_missing_sender_never_calls_email_provider(monkeypatch):
    monkeypatch.setattr(mentors, "MAILTRAP_API_TOKEN", "test-token")
    monkeypatch.delenv("MAIL_FROM_EMAIL", raising=False)
    constructor = MagicMock()
    monkeypatch.setattr(mentors.mt, "MailtrapClient", constructor)
    with pytest.raises(mentors.ServiceUnavailableError):
        mentors._send_invitation_email("mentor@example.com", "test-invite", UUID(int=1))
    constructor.assert_not_called()
