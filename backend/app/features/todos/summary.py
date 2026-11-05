from pydantic import BaseModel

from .schemas import Todo


class TodoSummary(BaseModel):
    open: int
    completed: int


def summarize(todos: list[Todo]) -> TodoSummary:
    completed = sum(1 for todo in todos if todo.completed)
    return TodoSummary(open=len(todos) - completed, completed=completed)
