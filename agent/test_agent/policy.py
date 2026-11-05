from __future__ import annotations

import json
import re

from test_agent.contracts import Plan, Proposal, ProposedFile, Skip

TEST_PATH = re.compile(
    r"^(backend/tests/(?:.+/)?test_[^/]+\.py|frontend/src/.+\.(?:test|spec)\.(?:ts|tsx))$"
)
DENY = ("subprocess", "os.system", "eval(", "exec(", "socket.", "__import__", "child_process", "process.env")
MAX_TEST_CHARS = 40_000


class PolicyError(ValueError):
    """The model asked for something the agent is not allowed to do."""


def normalize(path: str) -> str:
    cleaned = path.replace("\\", "/").strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if not cleaned or cleaned.startswith("/") or ".." in cleaned.split("/"):
        raise PolicyError(f"refusing path {path}")
    return cleaned


def parse_proposal(raw: str, plan: Plan) -> Proposal:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model response did not contain a JSON object")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"model response was not valid JSON: {exc.msg}") from None
    if not isinstance(data, dict):
        raise ValueError("model response must be a JSON object")

    summary = data.get("summary")
    files = data.get("files", [])
    skipped = data.get("skipped", [])
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary must be a non-empty string")
    if not isinstance(files, list) or not isinstance(skipped, list):
        raise ValueError("files and skipped must be arrays")

    planned = {target.test_path for target in plan.targets}
    seen: set[str] = set()
    accepted: list[ProposedFile] = []
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("each file entry must be an object")
        path = normalize(str(item.get("path", "")))
        content = item.get("content")
        if path not in planned:
            raise PolicyError(f"{path} is not one of the planned test files")
        if path in seen:
            raise PolicyError(f"duplicate test file {path}")
        if not isinstance(content, str):
            raise ValueError(f"{path} content must be a string")
        _check_content(path, content)
        seen.add(path)
        accepted.append(ProposedFile(path, content if content.endswith("\n") else content + "\n"))

    accepted_skips: list[Skip] = []
    for item in skipped:
        if not isinstance(item, dict):
            raise ValueError("each skipped entry must be an object")
        path = normalize(str(item.get("path", "")))
        reason = item.get("reason")
        if path not in planned:
            raise PolicyError(f"cannot skip unplanned path {path}")
        if path in seen:
            raise PolicyError(f"{path} was both written and skipped")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"skip reason for {path} must be a non-empty string")
        seen.add(path)
        accepted_skips.append(Skip(path, reason.strip()))

    missing = planned - seen
    if missing:
        raise ValueError("response omitted planned tests: " + ", ".join(sorted(missing)))
    safe_summary = summary.replace("<!--", "").replace("-->", "").strip()
    return Proposal(safe_summary[:1000], accepted, accepted_skips)


def _check_content(path: str, content: str) -> None:
    if not TEST_PATH.match(path):
        raise PolicyError(f"{path} is outside the test directories")
    if len(content) > MAX_TEST_CHARS:
        raise PolicyError(f"{path} exceeds {MAX_TEST_CHARS} characters")
    if "\x00" in content:
        raise PolicyError(f"{path} contains a NUL byte")
    lowered = content.lower()
    for token in DENY:
        if token.lower() in lowered:
            raise PolicyError(f"{path} contains forbidden token {token}")
    if path.endswith(".py") and "def test_" not in content:
        raise PolicyError(f"{path} does not define a pytest test")
    if path.endswith((".ts", ".tsx")) and not re.search(r"\b(?:it|test)\(", content):
        raise PolicyError(f"{path} does not define a vitest test")
