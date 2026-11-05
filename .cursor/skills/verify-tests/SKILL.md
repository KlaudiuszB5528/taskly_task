---
name: verify-tests
description: Run the Taskly unit tests selected for a pull request and decide whether one repair is justified. Use after drafting tests, or when a pull request only changes existing tests.
---

# Verify tests

Run the smallest command that proves the change:

- Backend: `python -m pytest -q --tb=short` plus the selected files, from `backend/`. Use `backend/.venv` when it exists.
- Frontend: `npm test --` plus the selected files, from `frontend/`.
- When `conftest.py`, `mocks.py`, `pyproject.toml`, `src/test/setup.ts`, or `vite.config.ts` changes, run that side's full suite instead.

The test process environment has tokens, passwords, and API keys removed. Do not print those values back into the report.

## Repair

There is one repair. Send the failure text to the writer skill and run the tests again. Fix the test when its expectation does not match the code under test. Do not delete or loosen assertions to force a pass, and do not edit production code.

A pull request that only changes tests is run as-is. Do not rewrite those tests when they fail; report the failure.

If the command cannot start or still fails after the repair, restore the worktree and do not commit.
