---
name: publish-pr-results
description: Publish the Taskly test agent's decision, skills, and test output on the GitHub pull request. Use after analysis, test generation, or verification finishes.
---

# Publish pull request results

Write one comment that starts with `<!-- test-agent-report -->`. If a comment with that marker already exists, update it instead of adding another.

The comment states the result, every skill that ran, the planned test files, skipped files and why, the test command output, and the commit id when one was created. Do not include raw diffs, `.env` contents, or tokens.

## Commit

Commit only after the selected tests pass. The message contains `[test-agent]`. Set the author with per-command git configuration; do not change git config. Stage only the test files the agent wrote, using a temporary index so unrelated staged work is not included.

Push only when the workflow asks. A `TEST_AGENT_PUSH_TOKEN` is optional and is redacted from errors. Never force-push.

A later run whose head commit contains `[test-agent]` stops immediately, so an agent commit does not generate another one.
