
import os
from datetime import date, timedelta

# Test-only secret; production secret ko replace nahi karega.
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-key-not-for-production"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_user(client, email="test@example.com"):
    register_response = client.post(
        "/register",
        json={
            "email": email,
            "password": "TestPass123!",
        },
    )

    assert register_response.status_code in (200, 201), (
        register_response.text
    )

    login_response = client.post(
        "/login",
        json={
            "email": email,
            "password": "TestPass123!",
        },
    )

    assert login_response.status_code == 200, login_response.text

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_success(client):
    headers = create_user(client)

    response = client.get("/me", headers=headers)

    assert response.status_code == 200


def test_zero_amount_rejected(client):
    headers = create_user(client)

    response = client.post(
        "/transactions",
        headers=headers,
        json={
            "amount_paise": 0,
            "type": "expense",
            "date": date.today().isoformat(),
            "note": "Invalid amount",
            "payment_method": "cash",
        },
    )

    assert response.status_code == 422


def test_future_date_rejected(client):
    headers = create_user(client)
    future_date = (date.today() + timedelta(days=1)).isoformat()

    response = client.post(
        "/transactions",
        headers=headers,
        json={
            "amount_paise": 10000,
            "type": "expense",
            "date": future_date,
            "note": "Future date",
            "payment_method": "cash",
        },
    )

    assert response.status_code == 400


def test_user_cannot_see_another_users_transactions(client):
    headers1 = create_user(client, "first@example.com")

    categories_response = client.get(
        "/categories",
        headers=headers1,
    )
    assert categories_response.status_code == 200

    category_id = categories_response.json()[0]["id"]

    transaction_response = client.post(
        "/transactions",
        headers=headers1,
        json={
            "amount_paise": 20000,
            "type": "expense",
            "date": date.today().isoformat(),
            "note": "Private transaction",
            "payment_method": "cash",
            "category_id": category_id,
        },
    )

    assert transaction_response.status_code in (200, 201), (
        transaction_response.text
    )
    transaction_id = transaction_response.json()["id"]

    headers2 = create_user(client, "second@example.com")

    response = client.get("/transactions", headers=headers2)

    assert response.status_code == 200
    assert all(
        item["id"] != transaction_id
        for item in response.json()
    )

    edit_response = client.patch(
        f"/transactions/{transaction_id}",
        headers=headers2,
        json={"note": "Unauthorized edit"},
    )

    assert edit_response.status_code == 404
