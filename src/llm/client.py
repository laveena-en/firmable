"""Anthropic client wrapper: model tiering, structured output, cost + latency tracing.

The Trace schema here is the observability contract for Part 5.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import anthropic

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # .env wins over any stale key in the shell env
except ImportError:
    pass

# Model tiering — pin exact versions in prod, never `-latest`.
MODELS = {
    "cheap": "claude-haiku-4-5-20251001",  # high-volume binary classification
    "judge": "claude-sonnet-4-6",          # nuanced judgement
    "hard":  "claude-opus-4-8",            # hard edge cases / escalation
}

# $ per 1M tokens (input, output). Update from current pricing before cost runs.
PRICING = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-6":         (3.00, 15.00),
    "claude-opus-4-8":           (5.00, 25.00),
}

TRACE_PATH = Path(os.environ.get("TRACE_PATH", "traces/llm_calls.jsonl"))

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


@dataclass
class Trace:
    """One row per LLM call — the observability contract (Part 5)."""
    ts: str
    check: str            # which judge, e.g. "semantic_accuracy"
    prompt_version: str   # e.g. "v1"
    prompt_hash: str      # sha256 of rendered prompt — detects silent drift
    model: str
    record_id: str
    request: dict
    response: dict        # parsed {verdict, reason, confidence}
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    decision: str         # pass | fail | escalate | error


def cost_usd(model: str, in_tok: int, out_tok: int) -> float:
    pin, pout = PRICING[model]
    return (in_tok * pin + out_tok * pout) / 1_000_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def call_judge(*, check: str, tier: str, system: str, user: str, version: str,
               record_id: str, max_retries: int = 3) -> dict:
    """Call a judge, force JSON output, write a trace, return parsed {verdict, reason, confidence}.

    `system` is the rubric/instructions; `user` is the rendered record. The model is told to
    respond with ONLY a JSON object. On parse/API failure we retry with backoff, then return
    an error verdict (and still trace it).
    """
    model = MODELS[tier]
    prompt_hash = hashlib.sha256((system + "\n---\n" + user).encode()).hexdigest()[:16]

    if os.environ.get("MOCK_LLM") == "1":
        return _mock_judge(check, model, version, prompt_hash, record_id, user)

    client = _get_client()

    last_err = ""
    for attempt in range(max_retries):
        t0 = time.monotonic()
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=256,
                system=system + "\n\nRespond with ONLY a JSON object, no prose, no markdown fences.",
                messages=[{"role": "user", "content": user}],
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            raw = msg.content[0].text.strip()
            parsed = _parse_json(raw)
            in_tok, out_tok = msg.usage.input_tokens, msg.usage.output_tokens
            decision = parsed.get("verdict", "error")
            c = round(cost_usd(model, in_tok, out_tok), 6)
            _append_trace(Trace(
                ts=_now_iso(), check=check, prompt_version=version, prompt_hash=prompt_hash,
                model=model, record_id=record_id,
                request={"system_len": len(system), "user": user[:2000]},
                response=parsed, input_tokens=in_tok, output_tokens=out_tok,
                cost_usd=c, latency_ms=latency_ms, decision=decision,
            ))
            return {**parsed, "_model": model, "_prompt_version": version,
                    "_cost_usd": c, "_latency_ms": latency_ms}
        except (anthropic.APIStatusError, anthropic.APIConnectionError, json.JSONDecodeError, ValueError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)

    err = {"verdict": "error", "reason": last_err, "confidence": 0.0}
    _append_trace(Trace(
        ts=_now_iso(), check=check, prompt_version=version, prompt_hash=prompt_hash,
        model=model, record_id=record_id, request={"user": user[:2000]},
        response=err, input_tokens=0, output_tokens=0, cost_usd=0.0,
        latency_ms=0, decision="error",
    ))
    return {**err, "_model": model, "_prompt_version": version, "_cost_usd": 0.0, "_latency_ms": 0}


def _mock_judge(check: str, model: str, version: str, prompt_hash: str,
                record_id: str, user: str) -> dict:
    """Offline stand-in so the pipeline/harness run end-to-end without a live key.

    Heuristic only — NOT a real judge. Flags hedging/intent language as fail.
    Set MOCK_LLM=1 to enable. Real run requires a valid ANTHROPIC_API_KEY.
    """
    hedges = ("would like", "plans to", "plan to", "may ", "could ", "intends to", "is leaving")
    low = user.lower()
    fail = any(h in low for h in hedges)
    parsed = {
        "verdict": "fail" if fail else "pass",
        "reason": "MOCK: hedging/intent language" if fail else "MOCK: heuristic pass",
        "confidence": 0.55,
    }
    _append_trace(Trace(
        ts=_now_iso(), check=check, prompt_version=version, prompt_hash=prompt_hash,
        model=f"MOCK:{model}", record_id=record_id, request={"user": user[:2000]},
        response=parsed, input_tokens=0, output_tokens=0, cost_usd=0.0,
        latency_ms=0, decision=parsed["verdict"],
    ))
    return {**parsed, "_model": f"MOCK:{model}", "_prompt_version": version,
            "_cost_usd": 0.0, "_latency_ms": 0}


def _parse_json(raw: str) -> dict:
    """Tolerate accidental markdown fences around the JSON object."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
    s = s.strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in response: {raw[:200]}")
    return json.loads(s[start:end + 1])


def _append_trace(t: Trace) -> None:
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a") as f:
        f.write(json.dumps(asdict(t)) + "\n")
