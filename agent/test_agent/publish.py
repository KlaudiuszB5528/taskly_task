from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from test_agent.contracts import Plan, TestResult
from test_agent.safety import command_env, redact

MARKER = "<!-- test-agent-report -->"
COMMIT_TAG = "[test-agent]"
API = "https://api.github.com"


def commit_message() -> str:
    return (
        "test: cover pull request changes [test-agent]\n\n"
        "The test agent added or updated unit tests and ran them successfully."
    )


def head_subject(repo: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=command_env(),
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def commit_paths(repo: Path, paths: list[str], message: str) -> str | None:
    index = repo / ".git" / "test-agent.index"
    env = command_env()
    env["GIT_INDEX_FILE"] = str(index)

    def git(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=check,
        )

    try:
        git(["read-tree", "HEAD"])
        git(["add", "--", *paths])
        if git(["diff", "--cached", "--quiet"], check=False).returncode == 0:
            return None
        completed = subprocess.run(
            [
                "git",
                "-c",
                "user.name=github-actions[bot]",
                "-c",
                "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "-C",
                str(repo),
                "commit",
                "-m",
                message,
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            detail = redact((completed.stderr or "") + (completed.stdout or ""))
            raise RuntimeError(detail.strip() or "git commit failed")
        return git(["rev-parse", "--short", "HEAD"]).stdout.strip()
    finally:
        index.unlink(missing_ok=True)


def push_refspec(branch: str) -> str:
    if (
        not re.fullmatch(r"[A-Za-z0-9._/-]+", branch)
        or branch == "HEAD"
        or branch.startswith("/")
        or ".." in branch.split("/")
    ):
        raise RuntimeError("the test agent can only push from a named branch")
    return f"HEAD:refs/heads/{branch}"


def push_head(repo: Path) -> None:
    token = os.environ.get("TEST_AGENT_PUSH_TOKEN", "").strip()
    remote = os.environ.get("GITHUB_REPOSITORY", "").strip()
    branch = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=command_env(),
    )
    if branch.returncode != 0:
        raise RuntimeError(redact(branch.stderr).strip() or "could not read the current branch")
    spec = push_refspec(branch.stdout.strip())
    if token and remote:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", remote):
            raise RuntimeError("GITHUB_REPOSITORY must look like owner/name")
        args = [
            "git",
            "-C",
            str(repo),
            "push",
            f"https://x-access-token:{token}@github.com/{remote}.git",
            spec,
        ]
    else:
        args = ["git", "-C", str(repo), "push", "origin", spec]
    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=command_env(),
    )
    if completed.returncode != 0:
        detail = (completed.stderr or "") + (completed.stdout or "")
        if token:
            detail = detail.replace(token, "[redacted]")
        raise RuntimeError(redact(detail).strip() or "git push failed")


def render_report(
    *,
    status: str,
    summary: str,
    plan: Plan,
    skills: list,
    test_result: TestResult | None = None,
    commit: str | None = None,
    error: str | None = None,
) -> str:
    lines = [MARKER, "## Test agent", "", f"**Result:** {status}", "", summary.strip(), "", "### Skills used", ""]
    if skills:
        for skill in skills:
            lines.append(f"- **{skill.name}** — {skill.detail}")
    else:
        lines.append("- The agent stopped before a skill could run.")
    lines.extend(["", "### Decisions", ""])
    if plan.targets:
        lines.append("| Source | Test | Action | Why |")
        lines.append("| --- | --- | --- | --- |")
        for target in plan.targets:
            lines.append(
                f"| `{_cell(target.source_path)}` | `{_cell(target.test_path)}` | {target.action} | {_cell(target.reason)} |"
            )
    else:
        lines.append("No test file was selected.")
    if plan.skipped:
        lines.extend(["", "### Skipped", ""])
        for item in plan.skipped:
            lines.append(f"- `{item.path}` — {item.reason}")
    if test_result is not None:
        lines.extend(["", "### Tests", "", "```text", test_result.output.strip() or "(no output)", "```"])
    if commit:
        lines.extend(["", f"Committed `{commit}`."])
    if error:
        lines.extend(["", "### Error", "", redact(error).strip()[:4000]])
    body = "\n".join(lines).strip() + "\n"
    return body[:60_000]


def publish_comment(body: str) -> None:
    print(body)
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n")
            handle.write(body)
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    number = os.environ.get("PR_NUMBER", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if repository and number and token:
        upsert_comment(repository, number, token, body)


def upsert_comment(repository: str, number: str, token: str, body: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise RuntimeError("GITHUB_REPOSITORY must look like owner/name")
    if not re.fullmatch(r"\d+", number):
        raise RuntimeError("PR_NUMBER must be numeric")
    comments = _github("GET", f"/repos/{repository}/issues/{number}/comments?per_page=100", token)
    existing = next(
        (comment for comment in comments if str(comment.get("body", "")).startswith(MARKER)),
        None,
    )
    if existing:
        _github("PATCH", f"/repos/{repository}/issues/comments/{existing['id']}", token, {"body": body})
    else:
        _github("POST", f"/repos/{repository}/issues/{number}/comments", token, {"body": body})


def _github(method: str, path: str, token: str, payload: dict | None = None) -> list | dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(API + path, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "taskly-test-agent")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"GitHub comment failed with HTTP {exc.code}: {redact(detail)}") from None
    return json.loads(raw or "null")


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
