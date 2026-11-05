import asyncio
from unittest.mock import Mock

import pytest
from fastapi import FastAPI

from app.core.lifespan import lifespan


def _app():
    app = FastAPI()
    app.state.database_url = "postgresql+psycopg://taskly:taskly@localhost:5432/taskly"
    return app


def test_lifespan_initializes_the_database_and_disposes_the_engine(monkeypatch):
    engine = Mock()
    factory = Mock()
    initialize = Mock()
    monkeypatch.setattr("app.core.lifespan.create_database_engine", lambda url: engine)
    monkeypatch.setattr("app.core.lifespan.initialize", initialize)
    monkeypatch.setattr("app.core.lifespan.create_session_factory", lambda bound: factory)
    app = _app()

    async def scenario():
        async with lifespan(app):
            assert app.state.session_factory is factory

    asyncio.run(scenario())
    initialize.assert_called_once_with(engine)
    engine.dispose.assert_called_once_with()


def test_lifespan_disposes_the_engine_when_startup_fails(monkeypatch):
    engine = Mock()
    monkeypatch.setattr("app.core.lifespan.create_database_engine", lambda url: engine)
    monkeypatch.setattr(
        "app.core.lifespan.initialize", Mock(side_effect=RuntimeError("database unavailable"))
    )
    app = _app()

    async def scenario():
        async with lifespan(app):
            pass

    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(scenario())
    engine.dispose.assert_called_once_with()
