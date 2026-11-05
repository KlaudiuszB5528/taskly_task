from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from test_agent.contracts import Plan, TestResult
from test_agent.safety import command_env, redact

TIMEOUT_SECONDS = 180


def python_executable(repo: Path) -> str:
    for candidate in (
        repo / "backend" / ".venv" / "Scripts" / "python.exe",
        repo / "backend" / ".venv" / "bin" / "python",
    ):
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def build_commands(repo: Path, plan: Plan, written: list[str] | None) -> list[tuple[list[str], Path]]:
    """Build the verify-tests commands. Shared harness changes run that side's full suite."""
    commands: list[tuple[list[str], Path]] = []
    backend = _selected(plan.backend_tests, plan.targets, written, "python") if not plan.full_backend else []
    frontend = _selected(plan.frontend_tests, plan.targets, written, "typescript") if not plan.full_frontend else []
    if plan.full_backend or backend:
        args = [python_executable(repo), "-m", "pytest", "-q", "--tb=short"]
        if not plan.full_backend:
            args.extend(_relative(path, "backend") for path in backend)
        commands.append((args, repo / "backend"))
    if plan.full_frontend or frontend:
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("npm is not installed, so frontend tests cannot run")
        args = [npm, "test"]
        if not plan.full_frontend:
            args.append("--")
            args.extend(_relative(path, "frontend") for path in frontend)
        commands.append((args, repo / "frontend"))
    return commands


def run_tests(repo: Path, plan: Plan, written: list[str] | None = None) -> TestResult:
    commands = build_commands(repo, plan, written)
    if not commands:
        return TestResult(True, "No test command was required.", [])
    chunks: list[str] = []
    rendered: list[str] = []
    ok = True
    for args, cwd in commands:
        display = " ".join(args)
        rendered.append(display)
        try:
            completed = subprocess.run(
                args,
                cwd=cwd,
                env=command_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            ok = False
            chunks.append(f"$ {display}\nTimed out after {TIMEOUT_SECONDS} seconds.")
            continue
        output = (completed.stdout or "") + (completed.stderr or "")
        chunks.append(f"$ {display}\n{output.strip()}".rstrip())
        if completed.returncode != 0:
            ok = False
    return TestResult(ok, redact("\n\n".join(chunks))[-12000:], rendered)


def _selected(paths: list[str], targets, written: list[str] | None, language: str) -> list[str]:
    if written is None:
        return paths
    planned = {target.test_path for target in targets if target.language == language}
    written_set = set(written)
    return [path for path in paths if path not in planned or path in written_set]


def _relative(path: str, root: str) -> str:
    prefix = root + "/"
    if not path.startswith(prefix):
        raise ValueError(f"{path} is not under {root}")
    return path[len(prefix) :]
