from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.todos.models import TodoRecord
from app.features.todos.repository import TodoRepository
from app.features.todos.schemas import TodoCreate, TodoUpdate


def test_list_maps_models_and_orders_tasks_newest_first(model_factory, todo_values, todo):
    session = Mock(spec=Session)
    session.scalars.return_value = [model_factory(todo_values)]
    assert TodoRepository(session).list() == [todo]
    statement = session.scalars.call_args.args[0]
    expected = select(TodoRecord).order_by(TodoRecord.created_at.desc(), TodoRecord.id.desc())
    assert statement.compare(expected)
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY todos.created_at DESC, todos.id DESC" in compiled


def test_get_returns_none_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).get(404) is None
    session.get.assert_called_once_with(TodoRecord, 404)


def test_get_maps_a_stored_task(model_factory, todo_values, todo):
    session = Mock(spec=Session)
    session.get.return_value = model_factory(todo_values)
    assert TodoRepository(session).get(7) == todo
    session.get.assert_called_once_with(TodoRecord, 7)


def test_create_persists_the_task_and_maps_it(monkeypatch):
    fixed = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr("app.features.todos.repository.datetime", FrozenDateTime)
    session = Mock(spec=Session)

    def assign_id(record):
        record.id = 7

    session.refresh.side_effect = assign_id
    created = TodoRepository(session).create(TodoCreate(title="Plan the sprint", priority="high"))
    record = session.add.call_args.args[0]
    assert record.title == "Plan the sprint"
    assert record.priority == "high"
    assert record.created_at == fixed
    assert record.updated_at == fixed
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(record)
    assert created.id == 7
    assert created.title == "Plan the sprint"
    assert created.created_at == fixed


def test_update_applies_only_the_sent_fields(monkeypatch, model_factory, todo_values, todo):
    fixed = datetime(2026, 10, 2, 8, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr("app.features.todos.repository.datetime", FrozenDateTime)
    session = Mock(spec=Session)
    record = model_factory(todo_values)
    session.get.return_value = record
    updated = TodoRepository(session).update(7, TodoUpdate(title="Renamed task"))
    assert record.title == "Renamed task"
    assert record.description == todo.description
    assert record.updated_at == fixed
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(record)
    assert updated is not None
    assert updated.title == "Renamed task"
    assert updated.updated_at == fixed


def test_update_missing_task_does_not_commit():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).update(404, TodoUpdate(title="Renamed task")) is None
    session.commit.assert_not_called()
    session.delete.assert_not_called()


def test_delete_removes_a_stored_task(model_factory, todo_values):
    session = Mock(spec=Session)
    record = model_factory(todo_values)
    session.get.return_value = record
    assert TodoRepository(session).delete(7) is True
    session.delete.assert_called_once_with(record)
    session.commit.assert_called_once_with()


def test_delete_missing_task_does_not_commit():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).delete(404) is False
    session.delete.assert_not_called()
    session.commit.assert_not_called()
