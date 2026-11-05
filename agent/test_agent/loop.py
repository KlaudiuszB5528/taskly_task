from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from test_agent.analysis import _normalize, build_plan
from test_agent.contracts import AgentResult, FileChange, Plan, SkillTrace, TestResult
from test_agent.gitdiff import collect_changes
from test_agent.llm import MissingCredentials, complete
from test_agent.policy import PolicyError, parse_proposal
from test_agent.prompt import build_repair_prompt, build_user_prompt, skills_for, system_prompt
from test_agent.publish import (
    COMMIT_TAG,
    commit_message,
    commit_paths,
    head_subject,
    publish_comment,
    push_head,
    render_report,
)
from test_agent.safety import redact
from test_agent.verify import run_tests

MAX_ATTEMPTS = 2


class RunContext:
    def __init__(
        self,
        repo: Path,
        base: str,
        head: str,
        *,
        commit: bool = False,
        push: bool = False,
        changes: list[FileChange] | None = None,
        completer: Callable[[str, str], str] = complete,
        verifier: Callable[[Path, Plan, list[str] | None], TestResult] = run_tests,
        commenter: Callable[[str], None] = publish_comment,
        committer: Callable[[Path, list[str], str], str | None] = commit_paths,
        pusher: Callable[[Path], None] = push_head,
    ) -> None:
        self.repo = repo
        self.base = base
        self.head = head
        self.commit = commit
        self.push = push
        self.changes = changes
        self.completer = completer
        self.verifier = verifier
        self.commenter = commenter
        self.committer = committer
        self.pusher = pusher


def execute(ctx: RunContext) -> AgentResult:
    if ctx.changes is None and _skip_agent_commit(ctx.repo):
        return AgentResult("ignored", 0, "", [])

    skills: list[SkillTrace] = []
    try:
        changes = ctx.changes if ctx.changes is not None else collect_changes(ctx.repo, ctx.base, ctx.head)
    except Exception as exc:
        plan = Plan(outcome="failed")
        return _finish(ctx, "failed", 1, plan, skills, "The agent could not read the diff.", error=str(exc))

    plan = build_plan(changes, ctx.repo)
    skills.append(SkillTrace("analyze-changes", _analysis_detail(plan, len(changes))))
    patches = {_normalize(change.path): change.patch for change in changes}

    if plan.outcome == "protected":
        return _finish(
            ctx,
            "protected",
            0,
            plan,
            skills,
            "This pull request changes the agent, a skill, or the workflow. A person reviews those edits before the agent acts.",
        )
    if plan.outcome == "skip":
        return _finish(
            ctx,
            "skipped",
            0,
            plan,
            skills,
            "No application behavior in this pull request needs a new or updated unit test.",
        )
    if plan.outcome == "verify":
        return _verify_existing(ctx, plan, skills)

    for name in skills_for(plan):
        skills.append(SkillTrace(name, "draft the planned test files"))

    feedback: str | None = None
    proposal = None
    test_result: TestResult | None = None
    written: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        if attempt:
            skills.append(SkillTrace("verify-tests", "send the rejection back for one repair"))
        try:
            user = (
                build_user_prompt(ctx.repo, plan, patches)
                if feedback is None
                else build_repair_prompt(ctx.repo, plan, patches, feedback)
            )
            raw = ctx.completer(system_prompt(), user)
        except MissingCredentials as exc:
            return _finish(ctx, "blocked", 1, plan, skills, str(exc))
        except Exception as exc:
            return _finish(ctx, "failed", 1, plan, skills, "The model request failed.", error=str(exc))
        try:
            proposal = parse_proposal(raw, plan)
        except (ValueError, PolicyError) as exc:
            feedback = str(exc)
            proposal = None
            continue

        originals = _write(ctx.repo, proposal.files)
        written = [item.path for item in proposal.files]
        skills.append(SkillTrace("verify-tests", "run the selected unit tests"))
        try:
            test_result = ctx.verifier(ctx.repo, plan, written)
        except Exception as exc:
            _restore(ctx.repo, originals)
            return _finish(ctx, "failed", 1, plan, skills, "The test command could not be started.", error=str(exc))
        if test_result.ok:
            break
        _restore(ctx.repo, originals)
        written = []
        feedback = test_result.output
    else:
        if proposal is None:
            return _finish(
                ctx,
                "failed",
                1,
                plan,
                skills,
                "The model did not return an acceptable test change.",
                error=feedback,
            )
        return _finish(
            ctx,
            "failed",
            1,
            plan,
            skills,
            proposal.summary,
            test_result=test_result,
            error="Tests still failed after one repair, so nothing was committed.",
        )

    assert proposal is not None
    commit = None
    if proposal.files and ctx.commit:
        try:
            commit = ctx.committer(ctx.repo, written, commit_message())
            if commit and ctx.push:
                ctx.pusher(ctx.repo)
        except Exception as exc:
            return _finish(
                ctx,
                "failed",
                1,
                plan,
                skills,
                proposal.summary,
                test_result=test_result,
                commit=commit,
                error=str(exc),
            )
    status = "updated" if proposal.files else "skipped"
    summary = proposal.summary
    if proposal.files and not ctx.commit:
        summary += " The files are in the working tree and were not committed."
    return _finish(ctx, status, 0, plan, skills, summary, test_result=test_result, commit=commit)


def _verify_existing(ctx: RunContext, plan: Plan, skills: list[SkillTrace]) -> AgentResult:
    skills.append(SkillTrace("verify-tests", "run the tests touched by this pull request"))
    try:
        result = ctx.verifier(ctx.repo, plan, None)
    except Exception as exc:
        return _finish(ctx, "failed", 1, plan, skills, "The test command could not be started.", error=str(exc))
    if result.ok:
        return _finish(ctx, "verified", 0, plan, skills, "Existing tests were run. No new test was required.", test_result=result)
    return _finish(
        ctx,
        "failed",
        1,
        plan,
        skills,
        "Existing tests failed. The agent does not rewrite a test-only change.",
        test_result=result,
    )


def _finish(
    ctx: RunContext,
    status: str,
    code: int,
    plan: Plan,
    skills: list[SkillTrace],
    summary: str,
    *,
    test_result: TestResult | None = None,
    commit: str | None = None,
    error: str | None = None,
) -> AgentResult:
    skills.append(SkillTrace("publish-pr-results", "post the decision and test results on the pull request"))
    report = render_report(
        status=status,
        summary=summary,
        plan=plan,
        skills=skills,
        test_result=test_result,
        commit=commit,
        error=error,
    )
    try:
        ctx.commenter(report)
    except Exception as exc:
        print(redact(str(exc)))
        if code == 0:
            code = 1
            status = "failed"
    return AgentResult(status, code, report, list(skills), commit)


def _analysis_detail(plan: Plan, count: int) -> str:
    changed = "file" if count == 1 else "files"
    selected = "test file" if len(plan.targets) == 1 else "test files"
    return (
        f"classified {count} changed {changed} and selected {len(plan.targets)} {selected}; "
        f"outcome {plan.outcome}"
    )


def _skip_agent_commit(repo: Path) -> bool:
    if os.environ.get("TEST_AGENT_ALLOW_RERUN") == "1":
        return False
    return COMMIT_TAG in head_subject(repo)


def _write(repo: Path, files) -> dict[str, str | None]:
    originals: dict[str, str | None] = {}
    for item in files:
        path = repo / item.path
        originals[item.path] = path.read_text(encoding="utf-8") if path.is_file() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.content, encoding="utf-8")
    return originals


def _restore(repo: Path, originals: dict[str, str | None]) -> None:
    for relative, previous in originals.items():
        path = repo / relative
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(previous, encoding="utf-8")
