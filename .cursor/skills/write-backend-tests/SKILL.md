---
name: write-backend-tests
description: Write Taskly backend pytest tests that match the existing suite. Use when creating or updating tests for FastAPI routes, repositories, config, or other Python modules under backend/app.
---

# Write backend tests

Use pytest, the fixtures in `backend/tests/conftest.py`, and `tests.mocks.make_repository_mock`. Do not open a database connection unless the existing suite already does so for that module. SQLite is acceptable for schema initialization. Mock sessions and repository boundaries everywhere else.

## Style

- One behavior per `test_` function. Prefer a long descriptive name and `@pytest.mark.parametrize` for input variants.
- Assert the status code, the response body, and whether the repository was called.
- For a missing task, assert the public detail `"Task not found."`.
- Keep existing assertions when updating a file. Add cases for the new behavior.
- Do not add dependencies, skip markers, or network calls.
- Return the complete file. Match the surrounding quote and import style.

## Boundaries

The orchestrator rejects writes outside `backend/tests/**/test_*.py`, files without `def test_`, and tests that call a shell, `eval`, `exec`, or a socket. If the production behavior cannot be proved with a unit test, skip that planned path with a reason instead of inventing a passing assertion.
