import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import COOKIE_NAME, require_role
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import Patient, Professional, Role, User
from scripts.ci_database import validate_ci_database

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "fake-password-123"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "synthetic-secret-for-tests-only-1234567890")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://unused:unused@localhost/unused")
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        validate_ci_database(url)
        engine = create_engine(url, hide_parameters=True)
    else:
        if os.environ.get("CI") == "true":
            pytest.fail("TEST_DATABASE_URL is required in CI")
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)

    def db_override():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = db_override
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()
    with Session(engine) as db:
        for model in (Patient, Professional, User):
            db.execute(delete(model))
        db.commit()
    engine.dispose()
    get_settings.cache_clear()


def register(client, role="PATIENT", email=" User@Example.test "):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": "Fake Person", "role": role,
    })


@pytest.mark.parametrize("role", ["PATIENT", "PROFESSIONAL"])
def test_register_login_and_me(client, role):
    response = register(client, role)
    assert response.status_code == 201
    assert response.json()["email"] == "user@example.test"
    assert "password_hash" not in response.text
    response = client.post("/api/v1/auth/login", headers=ORIGIN,
                           json={"email": "USER@example.test", "password": PASSWORD})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").json()["role"] == role
    assert register(client).status_code == 409


def test_invalid_credentials_and_origin(client):
    assert register(client).status_code == 201
    data = {"email": "user@example.test", "password": "incorrect-password"}
    assert client.post("/api/v1/auth/login", headers=ORIGIN, json=data).status_code == 401
    assert client.post("/api/v1/auth/login", json=data).status_code == 403
    invalid = client.post("/api/v1/auth/register", json={"password": "short"})
    assert invalid.status_code == 422
    assert "short" not in invalid.text


def test_missing_invalid_and_expired_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.set(COOKIE_NAME, "invalid")
    assert client.get("/api/v1/auth/me").status_code == 401
    settings = get_settings()
    now = datetime.now(UTC)
    token = jwt.encode({"sub": "00000000-0000-0000-0000-000000000001", "iat": now,
                        "exp": now - timedelta(seconds=1), "iss": settings.jwt_issuer,
                        "aud": settings.jwt_audience}, settings.secret_key.get_secret_value(),
                       algorithm="HS256")
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_role_dependency_rejects_wrong_role(client):
    assert register(client).status_code == 201
    assert client.post("/api/v1/auth/login", headers=ORIGIN,
                       json={"email": "user@example.test", "password": PASSWORD}).status_code == 200
    router = FastAPI()
    router.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    router.get("/professional", dependencies=[Depends(require_role(Role.PROFESSIONAL))])(
        lambda: {"ok": True}
    )
    with TestClient(router, base_url="https://testserver", cookies=client.cookies) as role_client:
        assert role_client.get("/professional").status_code == 403
