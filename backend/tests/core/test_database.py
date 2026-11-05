from datetime import datetime, timezone

from sqlalchemy import create_engine

from app.core.database import create_database_engine, create_session_factory, initialize
from app.features.todos.models import TodoRecord
from app.features.todos.schemas import Priority


def test_engine_uses_the_postgresql_psycopg_driver():
    url = "postgresql+psycopg://taskly:taskly@localhost:5432/taskly"
    engine = create_database_engine(url)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        assert engine.url.database == "taskly"
    finally:
        engine.dispose()


def test_initialize_creates_todos_and_sessions_keep_loaded_values():
    engine = create_engine("sqlite://")
    session = None
    try:
        initialize(engine)
        session = create_session_factory(engine)()
        now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        record = TodoRecord(
            title="Plan the sprint",
            description="",
            priority=Priority.high,
            due_date=None,
            completed=False,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.commit()
        assert record.id is not None
        assert record.title == "Plan the sprint"
        assert record.priority == Priority.high
    finally:
        if session is not None:
            session.close()
        engine.dispose()
