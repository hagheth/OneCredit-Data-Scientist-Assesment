"""The only module that calls the LLM API (Groq). Every response is cached on disk.

Same model + messages + settings -> same cache file, so re-running a version or re-scoring never calls the API again.
The free tier allows 8,000 tokens per minute, so rate-limit errors are expected: we wait and retry.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import groq
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "runs" / "cache"

_client: groq.Groq | None = None


def client() -> groq.Groq:
    global _client  # noqa: PLW0603 - one shared client
    if _client is None:
        load_dotenv(ROOT / ".env")
        # timeout: a request that hangs is abandoned after 2 minutes and retried (one run hung for 25+ minutes without it)
        _client = groq.Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=0, timeout=120)
    return _client


def _key(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:24]


def _wait_seconds(err: groq.RateLimitError, attempt: int) -> float:
    retry_after = err.response.headers.get("retry-after")
    try:
        wait = float(retry_after) + 1 if retry_after else 15.0 * attempt
    except ValueError:
        wait = 15.0 * attempt
    return min(wait, 90.0)  # never sleep longer than 90s in one go; retry instead


def complete(model: str, messages: list[dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 1500,
             extra: dict[str, Any] | None = None, max_attempts: int = 8,
             cache_only: bool = False) -> dict[str, Any] | None:
    """Return {"content", "usage", "model", "cached", "params"} for one chat completion.

    cache_only=True never calls the API: returns None when the response is not cached.
    """
    params: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature,
                              "max_tokens": max_tokens, **(extra or {})}
    path = CACHE / f"{_key(params)}.json"
    if path.exists():
        return {**json.loads(path.read_text(encoding="utf-8")), "cached": True}
    if cache_only:
        return None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = client().chat.completions.create(**params)
            break
        except groq.RateLimitError as err:
            wait = _wait_seconds(err, attempt)
            print(f"    rate limited, waiting {wait:.0f}s (attempt {attempt}/{max_attempts})")
            time.sleep(wait)
        except (groq.APIConnectionError, groq.APITimeoutError, groq.InternalServerError) as err:
            print(f"    {type(err).__name__}, retrying in {5 * attempt}s")
            time.sleep(5 * attempt)
    else:
        raise RuntimeError(f"Gave up after {max_attempts} attempts")

    choice = resp.choices[0]
    result = {
        "content": (choice.message.content or "").strip(),
        "finish_reason": choice.finish_reason,
        "usage": resp.usage.model_dump() if resp.usage else None,
        "model": resp.model,
        "created": resp.created,
        "params": params,
    }
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**result, "cached": False}
