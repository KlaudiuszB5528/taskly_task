from __future__ import annotations

import argparse
import os
from pathlib import Path

from test_agent.analysis import build_plan
from test_agent.gitdiff import collect_changes
from test_agent.loop import RunContext, execute


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="test_agent")
    parser.add_argument("--repo", help="repository root; defaults to the current checkout")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="classify a diff without calling a model")
    _add_refs(plan)
    run = sub.add_parser("run", help="create or update tests, run them, and publish the result")
    _add_refs(run)
    run.add_argument("--commit", action="store_true", help="commit test files after they pass")
    run.add_argument("--push", action="store_true", help="push the test commit to the current branch")

    args = parser.parse_args(argv)
    repo = find_repo(Path(args.repo) if args.repo else None)
    if args.command == "plan":
        changes = collect_changes(repo, args.base, args.head)
        print(render_plan(build_plan(changes, repo)))
        return 0

    result = execute(
        RunContext(
            repo=repo,
            base=args.base,
            head=args.head,
            commit=args.commit or args.push,
            push=args.push,
        )
    )
    if result.status == "ignored":
        print("Skipping a commit created by the test agent.")
    return result.exit_code


def find_repo(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "backend" / "app").is_dir() and (candidate / "frontend" / "package.json").is_file():
            return candidate
    raise SystemExit("Run the test agent from the Taskly repository.")


def render_plan(plan) -> str:
    lines = [f"outcome: {plan.outcome}"]
    if plan.full_backend:
        lines.append("full backend suite: yes")
    if plan.full_frontend:
        lines.append("full frontend suite: yes")
    for target in plan.targets:
        lines.append(f"{target.action}: {target.test_path} <= {target.source_path} ({target.reason})")
    for item in plan.skipped:
        lines.append(f"skip: {item.path} ({item.reason})")
    if not plan.targets and not plan.skipped:
        lines.append("no files")
    return "\n".join(lines)


def _add_refs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base", default=os.environ.get("BASE_SHA") or "origin/main")
    parser.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
