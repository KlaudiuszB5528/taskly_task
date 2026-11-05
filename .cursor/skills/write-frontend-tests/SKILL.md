---
name: write-frontend-tests
description: Write Taskly frontend Vitest tests with Testing Library. Use when creating or updating tests for React components, hooks, or API helpers under frontend/src, excluding the design system.
---

# Write frontend tests

Use Vitest and Testing Library. Colocate the test beside the module: `Component.tsx` gets `Component.test.tsx`, and a non-JSX module gets `.test.ts`.

## Style

- Import `expect`, `it`, and `vi` from `vitest`, as the existing tests do.
- Mock the design system with `vi.mock('<relative>/design-system', () => import('<relative>/design-system/mocks'))`.
- Use `userEvent` for clicks and typing. Use `renderHook` for hooks.
- Give hook tests a fresh `QueryClient` with `retry: false`. Mock `todosApi` in hook tests. Stub `fetch` only in `http` tests.
- Assert what the user sees or the cache update the hook promises. Keep existing tests when updating a file.
- Format with Prettier: single quotes, no semicolons, trailing commas.

## Boundaries

Do not modify production code or add dependencies. The orchestrator rejects writes outside `frontend/src/**/*.test.ts(x)`, files without `it(` or `test(`, and tests that read `process.env` or spawn a process. If the change is only styling, skip the planned path with a reason.
