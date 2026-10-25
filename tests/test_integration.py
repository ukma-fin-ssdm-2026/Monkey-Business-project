"""
Інструмент: Antigravity
Застосування: Написання інтеграційних тестів згідно з вимогами, використано in memory sqlite як тестову бд.
Верифікація: Тести перевірені на віповідність, перевірено створння бд та звертання, виконано згідно вимог.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.db import get_repositories
from src.api.repositories.sql import Base, build_repositories
from src.api.auth import _issue_token
from src.api.domain import User, Board, Stage, Card, BoardMentor
from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    session = SessionLocal()
    
    yield session
    
    session.close()

@pytest.fixture
def repos(db_session):
    return build_repositories(db_session)

@pytest.fixture
def client(db_session):
    def override_get_repositories():
        yield build_repositories(db_session)

    app.dependency_overrides[get_repositories] = override_get_repositories
    
    with TestClient(app) as test_client:
        yield test_client
        
    app.dependency_overrides.clear()
    
@pytest.fixture
def setup_data(repos, db_session):
    candidate = repos.users.add(User(email="owner@example.com", password_hash="hash", role="candidate"))
    board = repos.boards.add(Board(owner_id=candidate.id))
    
    stage = repos.stages.add(Stage(board_id=board.id, name="Скрінінг", order_index=0))
    
    card = repos.cards.add(Card(
        board_id=board.id,
        stage_id=stage.id,
        company="Acme Corp",
        position="Backend Engineer",
        position_index=0
    ))
    
    mentor = repos.users.add(User(email="mentor@example.com", password_hash="hash", role="mentor"))
    repos.mentors.add(BoardMentor(
        board_id=board.id,
        mentor_id=mentor.id,
        invite_token="token-123",
        status="accepted"
    ))
    
    db_session.commit()
    
    return board, card, mentor

@pytest.mark.integration
def test_api_mentor_creates_comment_in_real_db(client, setup_data, repos, monkeypatch):
    board, card, mentor = setup_data
    
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-that-is-long-enough-32-bytes")
    
    token_response = _issue_token(mentor)
    headers = {"Authorization": f"Bearer {token_response.access_token}"}
    
    payload = {"content": "Це коментар, збережений у справжній SQL БД"}

    response = client.post(
        f"/v1/boards/{board.id}/cards/{card.id}/comments",
        json=payload,
        headers=headers
    )

    assert response.status_code in (200, 201), f"Помилка API: {response.text}"
    data = response.json()
    assert data["content"] == "Це коментар, збережений у справжній SQL БД"
    assert data["author_id"] == str(mentor.id)

    comments_in_db = repos.comments.list_for_card(card.id)
    assert len(comments_in_db) == 1
    assert comments_in_db[0].content == "Це коментар, збережений у справжній SQL БД"
    assert comments_in_db[0].author_id == mentor.id

@pytest.mark.integration
def test_api_owner_adds_link_to_card(client, setup_data, repos, monkeypatch):
    board, card, _ = setup_data
    
    owner = repos.users.get(board.owner_id)
    
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-that-is-long-enough-32-bytes")
    token_response = _issue_token(owner)
    headers = {"Authorization": f"Bearer {token_response.access_token}"}
    
    payload = {"url": "https://example.com/task"}
    
    post_response = client.post(
        f"/v1/boards/{board.id}/cards/{card.id}/links",
        json=payload,
        headers=headers
    )
    
    assert post_response.status_code in (200, 201), f"Помилка POST API: {post_response.text}"
    post_data = post_response.json()
    assert post_data["url"] == "https://example.com/task"
    
    get_response = client.get(
        f"/v1/boards/{board.id}/cards/{card.id}/links",
        headers=headers
    )
    
    assert get_response.status_code == 200, f"Помилка GET API: {get_response.text}"
    get_data = get_response.json()
    urls = [item["url"] for item in get_data]
    assert "https://example.com/task" in urls
    
    links_in_db = repos.links.list_for_card(card.id)
    assert len(links_in_db) >= 1
    
    added_link = next((link for link in links_in_db if link.url == "https://example.com/task"), None)
    assert added_link is not None, "Посилання не знайдено в базі даних"
    assert added_link.card_id == card.id