from __future__ import annotations

import re
from pathlib import Path

from test_agent.contracts import FileChange, Plan, Skip, Target

MAX_TARGETS = 8
PROTECTED_PREFIXES = ("agent/", ".cursor/skills/", ".github/workflows/")
HARNESS = {
    "backend/tests/conftest.py": "backend",
    "backend/tests/mocks.py": "backend",
    "backend/pyproject.toml": "backend",
    "frontend/src/test/setup.ts": "frontend",
    "frontend/vite.config.ts": "frontend",
}
BACKEND_EXCLUDED_NAMES = {
    "__init__.py",
    "main.py",
    "schemas.py",
    "models.py",
    "types.py",
    "constants.py",
}
FRONTEND_EXCLUDED_FILES = {
    "frontend/src/main.tsx",
    "frontend/src/features/todos/api/queryKeys.ts",
    "frontend/src/lib/queryClient.ts",
}


def parse_name_status(text: str) -> list[FileChange]:
    changes: list[FileChange] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        status = parts[0]
        if status[:1] in {"R", "C"} and len(parts) == 3:
            changes.append(FileChange(path=parts[2], status="R", old_path=parts[1]))
        elif len(parts) == 2:
            changes.append(FileChange(path=parts[1], status=status[:1]))
    return changes


def has_behavioral_change(change: FileChange) -> bool:
    if change.status in {"A", "R"}:
        return True
    for line in change.patch.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
            continue
        body = line[1:].strip()
        if not body or body.startswith("#") or body.startswith("//"):
            continue
        return True
    return False


def is_sensitive(path: str) -> bool:
    name = path.lower().rsplit("/", 1)[-1]
    return name.startswith(".env") or "credential" in path.lower() or name.endswith(
        (".pem", ".key", ".p12", ".pfx")
    )


def included_backend(path: str) -> bool:
    if not path.startswith("backend/app/") or not path.endswith(".py"):
        return False
    name = path.rsplit("/", 1)[-1]
    return name not in BACKEND_EXCLUDED_NAMES and ".constants." not in name


def included_frontend(path: str) -> bool:
    if not path.startswith("frontend/src/"):
        return False
    if not path.endswith((".ts", ".tsx")) or path.endswith(".d.ts"):
        return False
    name = path.rsplit("/", 1)[-1]
    relative = path.removeprefix("frontend/src/")
    if path in FRONTEND_EXCLUDED_FILES or relative.startswith(("test/", "design-system/")):
        return False
    if any(token in name for token in (".test.", ".spec.", ".stories.", ".styles.")):
        return False
    if name in {"types.ts", "index.ts", "index.tsx"} or name.endswith(".types.ts"):
        return False
    if name.startswith("constants.") or ".constants." in name:
        return False
    return True


def is_backend_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("backend/tests/") and name.startswith("test_") and name.endswith(".py")


def is_frontend_test(path: str) -> bool:
    return path.startswith("frontend/src/") and (
        ".test." in path or ".spec." in path
    ) and path.endswith((".ts", ".tsx"))


def backend_test_path(source: str) -> str:
    relative = source.removeprefix("backend/app/")
    parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
    filename = "test_" + name
    return f"backend/tests/{parent}/{filename}" if parent else f"backend/tests/{filename}"


def frontend_test_path(source: str) -> str:
    if source.endswith(".tsx"):
        return source[:-4] + ".test.tsx"
    if source.endswith(".ts"):
        return source[:-3] + ".test.ts"
    raise ValueError(f"{source} is not a frontend module")


def backend_module(source: str) -> str:
    relative = source.removeprefix("backend/app/")[:-3]
    return "app." + relative.replace("/", ".")


def tests_importing(repo: Path, module: str) -> list[str]:
    root = repo / "backend" / "tests"
    if not root.is_dir():
        return []
    pattern = re.compile(rf"(?<![\w.]){re.escape(module)}(?![\w.])")
    hits: list[str] = []
    for file in sorted(root.rglob("test_*.py")):
        text = file.read_text(encoding="utf-8", errors="replace")
        if pattern.search(text):
            hits.append(file.relative_to(repo).as_posix())
    return hits


def _normalize(path: str) -> str:
    cleaned = path.replace("\\", "/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def build_plan(changes: list[FileChange], repo: Path) -> Plan:
    """Decide which tests to create, update, or only run. This is the analyze-changes skill."""
    normalized = [
        FileChange(_normalize(change.path), change.status, change.patch, change.old_path)
        for change in changes
    ]
    if any(change.path.startswith(PROTECTED_PREFIXES) for change in normalized):
        skipped = [
            Skip(
                change.path,
                "agent, skill, or workflow edits are reviewed by a person"
                if change.path.startswith(PROTECTED_PREFIXES)
                else "not processed because this pull request also changes the agent",
            )
            for change in normalized
        ]
        return Plan(outcome="protected", skipped=skipped)

    skipped: list[Skip] = []
    targets: dict[str, Target] = {}
    verify_backend: list[str] = []
    verify_frontend: list[str] = []
    full_backend = False
    full_frontend = False

    for change in normalized:
        path = change.path
        if is_sensitive(path):
            skipped.append(Skip(path, "sensitive file is never sent to the model"))
            continue
        if path in HARNESS and change.status != "D":
            if HARNESS[path] == "backend":
                full_backend = True
            else:
                full_frontend = True
            skipped.append(Skip(path, "shared test harness changed, so that side's full suite will run"))
            continue
        if is_backend_test(path) or is_frontend_test(path):
            if change.status == "D":
                skipped.append(Skip(path, "removed test is left removed unless its source also changed"))
                continue
            if is_backend_test(path):
                verify_backend.append(path)
            else:
                verify_frontend.append(path)
            continue
        if change.status == "D":
            skipped.append(Skip(path, "deleted source does not get a new test"))
            continue
        if not has_behavioral_change(change):
            skipped.append(Skip(path, "no behavioral text change"))
            continue
        if included_backend(path):
            test_path = backend_test_path(path)
            _add_target(targets, repo, path, test_path, "python", "backend behavior changed", change.old_path)
            continue
        if included_frontend(path):
            test_path = frontend_test_path(path)
            _add_target(targets, repo, path, test_path, "typescript", "frontend behavior changed", change.old_path)
            continue
        if path.startswith("backend/app/") and path.endswith(".py"):
            module = backend_module(path)
            related = tests_importing(repo, module)
            if not related:
                skipped.append(Skip(path, "outside backend coverage scope and no test imports it"))
                continue
            for test_path in related:
                targets.setdefault(
                    test_path,
                    Target(path, test_path, "python", "update", f"imports {module}, which changed"),
                )
            continue
        if path.startswith("frontend/src/design-system/") or ".stories." in path or path.endswith(".styles.ts"):
            skipped.append(Skip(path, "outside the frontend coverage scope"))
            continue
        skipped.append(Skip(path, "outside the tested application source"))

    ordered = sorted(targets.values(), key=lambda item: (item.action != "create", item.test_path))
    if len(ordered) > MAX_TARGETS:
        for extra in ordered[MAX_TARGETS:]:
            skipped.append(
                Skip(extra.source_path, f"deferred; at most {MAX_TARGETS} test files are updated per run")
            )
        ordered = ordered[:MAX_TARGETS]

    for target in ordered:
        if target.language == "python":
            verify_backend.append(target.test_path)
        else:
            verify_frontend.append(target.test_path)

    if ordered:
        outcome = "generate"
    elif full_backend or full_frontend or verify_backend or verify_frontend:
        outcome = "verify"
    else:
        outcome = "skip"
    return Plan(
        outcome=outcome,
        targets=ordered,
        skipped=skipped,
        backend_tests=sorted(set(verify_backend)),
        frontend_tests=sorted(set(verify_frontend)),
        full_backend=full_backend,
        full_frontend=full_frontend,
    )


def _add_target(
    targets: dict[str, Target],
    repo: Path,
    source: str,
    test_path: str,
    language: str,
    reason: str,
    old_path: str | None,
) -> None:
    action = "update" if (repo / test_path).is_file() else "create"
    if old_path:
        reason = f"{reason}; renamed from {old_path}"
    targets.setdefault(test_path, Target(source, test_path, language, action, reason))
