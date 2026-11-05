from __future__ import annotations

import subprocess
from pathlib import Path

from test_agent.analysis import parse_name_status
from test_agent.contracts import FileChange
from test_agent.safety import command_env, redact


def collect_changes(repo: Path, base: str, head: str) -> list[FileChange]:
    spec = f"{base}...{head}"
    status = _git(repo, ["diff", "--name-status", "-M", spec])
    changes = parse_name_status(status)
    for index, change in enumerate(changes):
        if change.status == "D":
            continue
        patch = _git(repo, ["diff", "--unified=20", spec, "--", change.path])
        changes[index] = FileChange(change.path, change.status, patch, change.old_path)
    return changes


def _git(repo: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=command_env(),
    )
    if completed.returncode != 0:
        detail = redact((completed.stderr or completed.stdout or "git diff failed").strip())
        raise RuntimeError(detail)
    return completed.stdout
