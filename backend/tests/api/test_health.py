from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_repository
from app.api.health import router


def _client(session):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_repository] = lambda: SimpleNamespace(session=session)
    return app


def test_health_reports_ok_when_the_database_answers():
    session = Mock()
    with TestClient(_client(session)) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    session.execute.assert_called_once()


def test_health_fails_when_the_database_check_fails():
    session = Mock()
    session.execute.side_effect = RuntimeError("database unavailable")
    with TestClient(_client(session), raise_server_exceptions=False) as client:
        response = client.get("/api/health")
    assert response.status_code == 500
