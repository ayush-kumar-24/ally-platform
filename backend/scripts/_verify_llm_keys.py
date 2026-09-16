"""One-off: check ANTHROPIC_API_KEY and OPENAI_API_KEY in .env are actually
valid, with one minimal real request each -- in seconds, instead of finding
out 2 minutes into a full diagnosis run that every call 401'd.

Usage:
    python scripts/_verify_llm_keys.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _read_env_var(name: str) -> str | None:
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(rf'^{name}=(.*)$', line.strip())
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def check_anthropic(key: str | None) -> bool:
    if not key:
        print("ANTHROPIC_API_KEY: not set in .env")
        return False
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 8,
            "messages": [{"role": "user", "content": "say hi"}],
        },
        timeout=15,
    )
    if r.status_code == 200:
        print(f"ANTHROPIC_API_KEY: VALID (...{key[-6:]})")
        return True
    print(f"ANTHROPIC_API_KEY: INVALID -- HTTP {r.status_code} {r.text[:200]}")
    return False


def check_openai(key: str | None) -> bool:
    if not key:
        print("OPENAI_API_KEY: not set in .env")
        return False
    r = httpx.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={"model": "text-embedding-3-small", "input": "hi"},
        timeout=15,
    )
    if r.status_code == 200:
        print(f"OPENAI_API_KEY: VALID (...{key[-6:]})")
        return True
    print(f"OPENAI_API_KEY: INVALID -- HTTP {r.status_code} {r.text[:200]}")
    return False


def main() -> int:
    anthropic_ok = check_anthropic(_read_env_var("ANTHROPIC_API_KEY"))
    openai_ok = check_openai(_read_env_var("OPENAI_API_KEY"))
    return 0 if (anthropic_ok and openai_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
