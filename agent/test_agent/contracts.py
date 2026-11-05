from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str
    patch: str = ""
    old_path: str | None = None


@dataclass(frozen=True)
class Skip:
    path: str
    reason: str


@dataclass(frozen=True)
class Target:
    source_path: str
    test_path: str
    language: str
    action: str
    reason: str


@dataclass
class Plan:
    outcome: str
    targets: list[Target] = field(default_factory=list)
    skipped: list[Skip] = field(default_factory=list)
    backend_tests: list[str] = field(default_factory=list)
    frontend_tests: list[str] = field(default_factory=list)
    full_backend: bool = False
    full_frontend: bool = False


@dataclass(frozen=True)
class ProposedFile:
    path: str
    content: str


@dataclass(frozen=True)
class Proposal:
    summary: str
    files: list[ProposedFile]
    skipped: list[Skip]


@dataclass(frozen=True)
class TestResult:
    __test__ = False

    ok: bool
    output: str
    commands: list[str]


@dataclass(frozen=True)
class SkillTrace:
    name: str
    detail: str


@dataclass
class AgentResult:
    status: str
    exit_code: int
    report: str
    skills: list[SkillTrace]
    commit: str | None = None
