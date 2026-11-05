from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from test_agent.safety import redact


class MissingCredentials(RuntimeError):
    """The run needs a model and no credential was configured."""


def complete(system: str, user: str) -> str:
    if os.environ.get("TEST_AGENT_PROVIDER", "").strip() == "fixture":
        fixture = os.environ.get("TEST_AGENT_FIXTURE", "").strip()
        if not fixture:
            raise MissingCredentials("TEST_AGENT_PROVIDER=fixture requires TEST_AGENT_FIXTURE")
        return Path(fixture).read_text(encoding="utf-8")

    key = os.environ.get("TEST_AGENT_API_KEY", "").strip() or os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise MissingCredentials(
            "Set TEST_AGENT_API_KEY or OPENAI_API_KEY for an OpenAI-compatible chat completions API."
        )
    base = os.environ.get("TEST_AGENT_BASE_URL", "").strip() or "https://api.openai.com/v1"
    model = os.environ.get("TEST_AGENT_MODEL", "").strip() or "gpt-4.1-mini"
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        _chat_url(base),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"model request failed with HTTP {exc.code}: {redact(detail)}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"model request failed: {redact(str(exc.reason))}") from None

    data = json.loads(body)
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("model response did not contain text")
    return content


def _chat_url(base: str) -> str:
    trimmed = base.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return trimmed + "/chat/completions"
