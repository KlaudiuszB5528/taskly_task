---
name: analyze-changes
description: Classify a Taskly pull request diff and decide whether backend or frontend unit tests should be created, updated, only run, or skipped. Use when a pull request changes application code, tests, or the test agent.
---

# Analyze changes

Decide before writing anything. The executable policy is `agent/test_agent/analysis.py`; keep it aligned with the coverage settings in `backend/pyproject.toml` and `frontend/vite.config.ts`.

## Select a test target

- Backend modules under `backend/app/` map to `backend/tests/.../test_<module>.py`.
- Frontend modules under `frontend/src/` map to a sibling `*.test.ts` or `*.test.tsx`.
- Create the test when it does not exist. Update it when it does.
- A behavioral change is an added or renamed file, or a diff line that is not a comment or blank line.
- A changed test file is run. It is not rewritten unless its source module also changed.
- A deleted test stays deleted unless that source module also changed.

## Do not invent a test file

Skip files outside `backend/app` and `frontend/src`, sensitive files (`.env`, keys, credentials), and files the coverage config already omits: design-system, stories, styles, type declarations, barrels, constants, `queryKeys.ts`, `queryClient.ts`, `main.tsx`, `main.py`, models, and schemas.

When an omitted backend module still has tests that import it, update those existing tests instead of creating a new file.

Changes to `backend/tests/conftest.py`, `backend/tests/mocks.py`, `backend/pyproject.toml`, `frontend/src/test/setup.ts`, or `frontend/vite.config.ts` run that side's full suite.

## Stop without a model

If the diff touches `agent/`, `.cursor/skills/`, or `.github/workflows/`, do not generate tests in that pull request. A person reviews agent changes before the agent follows them.

At most 8 test files are updated in one run. Record the rest as deferred.
