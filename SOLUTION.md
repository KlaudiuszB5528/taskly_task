# Test agent

Pull requests to this repository run a custom test agent. It decides whether a change needs unit tests, writes or updates only those tests, runs them, and posts the decision on the pull request. The same skills are reusable in Cursor and are loaded by the agent at runtime.

The application tests added in this repository cover the modules the project measures. Backend coverage of `app` is 100% line and branch coverage under the existing `pyproject.toml` settings. Frontend coverage of the included `src` files is 96.42% statements and 97.35% lines.

## Decisions

The agent is a Python program in `agent/test_agent`, not a general coding agent with a shell. A model is used for one job: drafting test files the policy has already allowed. Classification, path checks, test execution, and the pull request comment are deterministic code. That split keeps the model from choosing its own write targets.

Skills live in `.cursor/skills/<name>/SKILL.md`. Cursor can apply them while editing this repo. The workflow loads the writer skills into the model prompt and the other skills are implemented by the modules below.

| Skill | Used for |
| --- | --- |
| `analyze-changes` | `analysis.py` classifies the diff before any model call |
| `write-backend-tests` | Prompt for pytest files when a backend target is selected |
| `write-frontend-tests` | Prompt for Vitest files when a frontend target is selected |
| `verify-tests` | `verify.py` runs pytest and Vitest, then allows one repair |
| `publish-pr-results` | `publish.py` updates one pull request comment and commits passing tests |

The model must return JSON. Each planned test path is either a complete file or an explicit skip. The response is rejected when it names any other path, omits a planned path, or contains a process, `eval`, `exec`, socket, or `process.env` call. Secrets are stripped from the test process environment and redacted from comments.

A pull request that edits `agent/`, `.cursor/skills/`, or `.github/workflows/` does not call the model. Those instructions would otherwise become the agent's own prompt. A person reviews them first.

The workflow uses `pull_request`, not `pull_request_target`, and only for branches in this repository. Forks do not receive write permission or secrets. Draft pull requests wait until they are marked ready. A commit whose message contains `[test-agent]` does not start another generation, which avoids a loop if a personal access token retriggers Actions. Pushes made with the default `GITHUB_TOKEN` do not retrigger workflows.

## How to run it

Prerequisites:

- GitHub Actions on this repository.
- Repository secret `TEST_AGENT_API_KEY`, or `OPENAI_API_KEY`, for an OpenAI-compatible chat completions API.
- Optional repository variable `TEST_AGENT_BASE_URL` (default `https://api.openai.com/v1`). The value may be the API root or the full `/chat/completions` URL.
- Optional repository variable `TEST_AGENT_MODEL` (default `gpt-4.1-mini`).
- Optional secret `TEST_AGENT_PUSH_TOKEN` with contents permission. When it is set, the agent pushes with that token so the normal CI workflows run on the new commit. Without it, the default token pushes the commit and GitHub does not start a new workflow. The agent has already run the tests it wrote.

Open a non-draft pull request whose branch belongs to this repository. `.github/workflows/test-agent.yml` checks out the branch, installs the backend and frontend test dependencies, and runs:

```sh
python -m test_agent run --base "$BASE_SHA" --head "$HEAD_SHA" --commit --push
```

The job log and the pull request conversation both receive the report. An existing comment that starts with `<!-- test-agent-report -->` is updated instead of duplicated. The check fails when the model is missing, the response violates policy, or the tests still fail after one repair. Nothing is committed in those cases. The check is skipped for draft pull requests and for forks.

Locally, from `agent/` with Python 3.11 or newer:

```sh
python -m pytest
python -m test_agent plan --base origin/main
python -m test_agent run --base origin/main
```

`plan` only classifies the diff. `run` writes tests into the worktree when a model credential is present. Add `--commit` to commit passing tests and `--push` to push them. `TEST_AGENT_PROVIDER=fixture` and `TEST_AGENT_FIXTURE=<file>` replay a saved model response instead of calling an API. Backend tests use `backend/.venv` when it exists.

CI for the application and for the agent's own tests is `.github/workflows/ci.yml`. It does not call a model.

## Example run

This is a local run of the same loop the workflow uses. The diff adds `backend/app/sample.py`. A fixture model returns one pytest file. The verifier is the real pytest from this environment, not a stub. No commit was requested, so the passing file stays in the worktree.

Skills used, in order: `analyze-changes`, `write-backend-tests`, `verify-tests`, `publish-pr-results`.

```text
<!-- test-agent-report -->
## Test agent

**Result:** updated

Added a unit test for answer(). The files are in the working tree and were not committed.

### Skills used

- **analyze-changes** — classified 1 changed file and selected 1 test file; outcome generate
- **write-backend-tests** — draft the planned test files
- **verify-tests** — run the selected unit tests
- **publish-pr-results** — post the decision and test results on the pull request

### Decisions

| Source | Test | Action | Why |
| --- | --- | --- | --- |
| `backend/app/sample.py` | `backend/tests/test_sample.py` | create | backend behavior changed |

### Tests

$ python -m pytest -q --tb=short tests/test_sample.py
.
1 passed in 0.02s
```

The agent decided the new module needed a test, loaded the backend writer skill, accepted only `backend/tests/test_sample.py`, and kept the result because pytest passed. On a pull request with `--commit --push`, that file would be committed with the message `test: cover pull request changes [test-agent]`.

A diff that only changes a test file is outcome `verify`: the model is not called and the existing test command is run. A documentation diff is outcome `skip`. A diff that includes the agent or a workflow is outcome `protected`.

## Assumptions

- The coverage exclusions in `backend/pyproject.toml` and `frontend/vite.config.ts` are the set of files worth a generated test. Design-system, stories, styles, models, and type-only modules are reported as skipped.
- A removed test file is intentional unless the same pull request also changes its source module.
- Comment-only and whitespace-only diffs do not need a test update.
- One model repair is enough to correct a bad assertion. A second failure means the change should be reviewed by a person.
- The model endpoint speaks the OpenAI chat completions format.
- Generated tests follow the current pytest and Vitest style closely enough that the existing commands can run them without new dependencies.
- `GITHUB_TOKEN` can write contents, issues, and pull request comments. The workflow sets those permissions and no others. Issue permission is required because the pull request conversation uses the issue comment API.

## Limitations

- The model can still write a test that passes without proving the behavior. The policy checks the path and a few dangerous calls. It does not judge assertion quality beyond running the file.
- Test execution is not sandboxed beyond a secret-free environment and a timeout. A generated test on a GitHub-hosted runner can still use the network.
- At most eight test files are updated per run. The rest are listed as deferred.
- Schema and model changes are tested only when an existing test imports that module. Frontend files excluded from coverage are not given new tests.
- A pull request that mixes agent edits with product code is not processed at all.
- A push with the default `GITHUB_TOKEN` does not start CI on the agent's commit. Set `TEST_AGENT_PUSH_TOKEN` when that second CI run matters.
- The workflow needs a paid model API. It does not fall back to a hidden generator.
- The head checkout does not always contain the current base branch. The workflow fetches that branch before comparing commits. A missing base commit makes the run fail with the git error in the pull request comment.

## Production changes

- Pin the GitHub Actions by commit SHA and review those upgrades.
- Run generated tests in a sandbox without network access, with a separate least-privilege job that does not have the model key.
- Require a human approval label before the first run on a repository that accepts untrusted contributors. Forks stay excluded.
- Replace the single JSON response with a recorded tool trace, and store the prompt, the model version, and the test output as a check run artifact.
- Add a coverage gate so a repair cannot delete assertions and still pass.
- Split agent changes onto a protected branch so product pull requests cannot be blocked by the protected-path rule.
- Use a GitHub App for the push token, with access limited to this repository, and rotate it.
