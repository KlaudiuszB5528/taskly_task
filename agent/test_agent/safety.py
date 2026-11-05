from __future__ import annotations

import os
import re

SECRET_ENV_PARTS = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "CREDENTIAL", "PRIVATE_KEY")
SECRET_TEXT = re.compile(
    r"(?i)((?:api[_-]?key|token|password|secret)\s*[:=]\s*)(\S+)"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9]{20,}"
)


def redact(text: str) -> str:
    """Remove credential-shaped text before it can reach a log or pull request."""
    redacted = SECRET_TEXT.sub(lambda match: (match.group(1) or "") + "[redacted]", text)
    for name in ("TEST_AGENT_API_KEY", "OPENAI_API_KEY", "TEST_AGENT_PUSH_TOKEN", "GITHUB_TOKEN"):
        secret = os.environ.get(name, "").strip()
        if secret:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def command_env() -> dict[str, str]:
    """Environment for generated tests and git commands, without inherited secrets."""
    cleaned: dict[str, str] = {}
    for key, value in os.environ.items():
        if any(part in key.upper() for part in SECRET_ENV_PARTS):
            continue
        cleaned[key] = value
    cleaned["GIT_TERMINAL_PROMPT"] = "0"
    cleaned["PYTHONDONTWRITEBYTECODE"] = "1"
    return cleaned
