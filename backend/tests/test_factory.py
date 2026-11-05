from app.factory import create_app


def test_create_app_mounts_the_http_api_and_stores_the_database_url():
    app = create_app("postgresql+psycopg://taskly:taskly@localhost:5432/taskly")
    paths = set(app.openapi()["paths"])
    assert "/api/health" in paths
    assert "/api/todos" in paths
    assert "/api/todos/{todo_id}" in paths
    assert app.state.database_url == "postgresql+psycopg://taskly:taskly@localhost:5432/taskly"
    assert app.title == "Taskly API"
    assert app.version == "1.0.0"


def test_create_app_resolves_the_database_url_when_none_is_given(monkeypatch):
    monkeypatch.setattr("app.factory.resolve_database_url", lambda database_url: "postgresql+psycopg://resolved/db")
    app = create_app()
    assert app.state.database_url == "postgresql+psycopg://resolved/db"
