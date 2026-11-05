import pytest

from app.core.config import resolve_database_url


@pytest.fixture(autouse=True)
def ignore_local_dotenv(monkeypatch):
    monkeypatch.setattr("app.core.config.load_dotenv", lambda *args, **kwargs: False)


def test_explicit_url_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env.example/db")
    assert resolve_database_url("postgresql+psycopg://explicit.example/db") == (
        "postgresql+psycopg://explicit.example/db"
    )


def test_database_url_from_the_environment_wins_over_parts(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env.example/db")
    monkeypatch.setenv("POSTGRES_HOST", "unused.example")
    assert resolve_database_url() == "postgresql+psycopg://env.example/db"


def test_builds_a_url_from_postgres_settings(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "taskly")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "taskly")
    assert resolve_database_url() == "postgresql+psycopg://taskly:secret@db.internal:5432/taskly"


def test_missing_postgres_settings_raise(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for name in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "DB_PORT", "POSTGRES_DB"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(KeyError):
        resolve_database_url()
