"""Minimal xAI (Grok) client: JSON-mode chat with model fallback and cost/token accounting. Stdlib only."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.x.ai/v1/chat/completions"
MODELS = [m for m in os.environ.get("BUIDL_MODELS", "grok-4.7,grok-4.5").split(",") if m]


class GrokError(RuntimeError):
    pass


class Usage:
    """Accumulates tokens, cost (xAI returns cost_in_usd_ticks, 1 tick = 1e-10 USD) and wall time per call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, purpose: str, model: str, usage: dict, seconds: float) -> None:
        self.calls.append({
            "purpose": purpose, "model": model, "seconds": round(seconds, 1),
            "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
            "usd": round(usage.get("cost_in_usd_ticks", 0) / 1e10, 4),
        })

    def summary(self) -> dict:
        return {
            "calls": len(self.calls),
            "prompt_tokens": sum(c["prompt_tokens"] for c in self.calls),
            "completion_tokens": sum(c["completion_tokens"] for c in self.calls),
            "usd": round(sum(c["usd"] for c in self.calls), 4),
            "seconds": round(sum(c["seconds"] for c in self.calls), 1),
            "detail": self.calls,
        }


USAGE = Usage()


def available() -> bool:
    return bool(os.environ.get("XAI_API_KEY"))


def chat_json(purpose: str, system: str, user: str, *, max_tokens: int = 16000, temperature: float = 0.3, retries: int = 2, effort: str | None = None) -> dict:
    """Call Grok in JSON mode and return the parsed object. Falls back across MODELS; raises GrokError."""
    key = os.environ.get("XAI_API_KEY")
    if not key:
        raise GrokError("XAI_API_KEY is not set")
    last = None
    for model in MODELS:
        for attempt in range(retries + 1):
            payload = {
                "model": model, "temperature": temperature, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }
            eff = effort or os.environ.get("BUIDL_REASONING", "low")
            if eff and eff != "none":
                payload["reasoning_effort"] = eff
            body = json.dumps(payload).encode()
            req = urllib.request.Request(API, data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=int(os.environ.get('BUIDL_GROK_TIMEOUT', '900'))) as r:
                    data = json.load(r)
            except urllib.error.HTTPError as e:
                print(f"[grok] {purpose} {model} HTTP {e.code} after {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
                detail = e.read().decode(errors="replace")[:300]
                last = f"{model} HTTP {e.code}: {detail}"
                if e.code == 403:
                    raise GrokError(f"xAI credits needed or key not permitted ({last})")
                if e.code == 400 and "reasoning" in detail.lower() and effort != "none":
                    effort = "none"  # model does not accept reasoning_effort -> retry without it
                    continue
                if e.code in (400, 404):
                    break  # model not available -> next model
                time.sleep(5 * (attempt + 1))
                continue
            except Exception as e:  # network / timeout
                print(f"[grok] {purpose} {model} error after {time.time() - t0:.0f}s: {e}", file=sys.stderr, flush=True)
                last = f"{model}: {e}"
                time.sleep(5 * (attempt + 1))
                continue
            USAGE.add(purpose, data.get("model", model), data.get("usage") or {}, time.time() - t0)
            c = USAGE.calls[-1]
            print(f"[grok] {purpose} {c['model']} {c['seconds']}s {c['prompt_tokens']}+{c['completion_tokens']} tok ${c['usd']}", file=sys.stderr, flush=True)
            text = data["choices"][0]["message"]["content"] or ""
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                s, e2 = text.find("{"), text.rfind("}")
                if s >= 0 and e2 > s:
                    try:
                        return json.loads(text[s:e2 + 1])
                    except json.JSONDecodeError:
                        pass
                last = f"{model}: response was not JSON"
    raise GrokError(last or "no model answered")
