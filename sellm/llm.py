"""One LLM call with a hard time limit, for the negotiator's writer and reader.

The 60-second rule makes a slow model worse than no model: `chat` returns within `timeout_s`
wall-clock seconds or raises `LLMError`, and the caller falls back to text written by code.
OpenAI-compatible chat completions through the kit's variables (`LLM_MODEL`, `LLM_API_KEY`,
`LLM_BASE_URL`); any other `LLM_PROVIDER` goes through the kit's `llm_from_env()`.
`SELLM_MODEL` overrides the model for our agent only.
"""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

import httpx

DEFAULT_TIMEOUT_S = 20.0
_POOL = ThreadPoolExecutor(max_workers=24, thread_name_prefix="sellm-llm")
_LOCK = threading.Lock()
_CLIENT = None
_KIT = None
STATS = {"calls": 0, "failed": 0, "latency_s": []}  # of this process, for run reports


class LLMError(Exception):
    """The call failed, timed out or returned something we cannot use."""


def model():
    return os.environ.get("SELLM_MODEL") or os.environ.get("LLM_MODEL") or ""


def configured():
    """Can we call a model at all? (Never raises: a missing key must not stop a negotiation.)"""
    if not model():
        return False
    provider = os.environ.get("LLM_PROVIDER", "openai")
    return bool(os.environ.get("LLM_API_KEY") or os.environ.get("LLM_BASE_URL")) if provider == "openai" else True


def _client():
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            _CLIENT = httpx.Client(limits=httpx.Limits(max_connections=32, max_keepalive_connections=16))
        return _CLIENT


def _openai(system, user, timeout_s, json_mode):
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    headers = {"Authorization": f"Bearer {os.environ.get('LLM_API_KEY', '')}"}
    body = {"model": model(), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = _client().post(f"{base}/chat/completions", json=body, headers=headers, timeout=timeout_s)
    if r.status_code == 400 and json_mode:  # an endpoint without JSON mode: ask in plain text
        body.pop("response_format")
        r = _client().post(f"{base}/chat/completions", json=body, headers=headers, timeout=timeout_s)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _kit(system, user, timeout_s, json_mode):
    global _KIT
    with _LOCK:
        if _KIT is None:
            from arena_kit.agents import llm_from_env

            _KIT = llm_from_env()
    return _KIT(system, user)


def chat(system, user, timeout_s=DEFAULT_TIMEOUT_S, json_mode=True):
    """(text, seconds). Raises LLMError after `timeout_s` wall-clock seconds at the latest; the
    abandoned request finishes in a worker thread and its answer is dropped."""
    if not configured():
        raise LLMError("no LLM configured (LLM_MODEL / LLM_API_KEY)")
    call = _openai if os.environ.get("LLM_PROVIDER", "openai") == "openai" else _kit
    t0 = time.monotonic()
    STATS["calls"] += 1
    future = _POOL.submit(call, system, user, timeout_s, json_mode)
    try:
        text = future.result(timeout=timeout_s)
    except FutureTimeout:
        STATS["failed"] += 1
        raise LLMError(f"no answer within {timeout_s:.0f} s") from None
    except Exception as e:  # HTTP error, bad key, rate limit, connection lost
        STATS["failed"] += 1
        raise LLMError(f"{type(e).__name__}: {str(e)[:200]}") from None
    took = time.monotonic() - t0
    STATS["latency_s"].append(took)
    if not isinstance(text, str) or not text.strip():
        STATS["failed"] += 1
        raise LLMError("empty answer")
    return text, took


def chat_json(system, user, timeout_s=DEFAULT_TIMEOUT_S):
    """(dict, seconds): the first JSON object in the model's answer."""
    text, took = chat(system, user, timeout_s, json_mode=True)
    match = re.search(r"\{.*\}", text, re.S)
    try:
        out = json.loads(match.group(0)) if match else None
    except ValueError:
        out = None
    if not isinstance(out, dict):
        STATS["failed"] += 1
        raise LLMError(f"no JSON object in the answer: {text[:120]!r}")
    return out, took
