"""Beginner example: let an LLM (GPT / any OpenAI-compatible model) pick the action.

This is the "I have no strategy yet, just get me playing" starter. It builds a
short prompt from the `table`, asks the model for an action, validates it against
`allowedActions`, and **falls back to a tight heuristic on ANY error** (no key, no
network, bad reply) — so it never crashes a match.

WHERE IT WORKS
  • `selfplay` / `eval` / `live` — yes. Your machine has network + your API key.
  • Sandbox `submit` — the sandbox ALLOWS outbound network, so the model call can
    work server-side — BUT each decision is capped at ~10s, so provider latency
    risks a timeout (which forfeits the spot) and you must ship your key. For a
    reliable submission, distill the policy offline into a lookup table / weights
    under `assets/` and read it from a plain `act()` instead.

CONFIG (env): OPENAI_API_KEY, optional OPENAI_BASE_URL (default OpenAI),
              optional OPENAI_MODEL (default gpt-4o-mini).

SECURITY: this sends your OPENAI_API_KEY and the (public) table state to whatever
          OPENAI_BASE_URL points at. Keep it the official endpoint — a poisoned
          base URL would exfiltrate your model key. Your Arena key is never put in
          the prompt. This file is opt-in; the default strategy uses no network.
"""
from __future__ import annotations

import json
import os
import urllib.request


def _heuristic(table: dict) -> dict:
    """Safe fallback — tight/passive, never illegal."""
    a = (table.get("allowedActions") or {}).get("availableActions") or []
    call_chips = int((table.get("allowedActions") or {}).get("callChips") or 0)
    pot = int(table.get("potChips") or 0)
    if call_chips == 0:
        return {"action": "check"} if "check" in a else {"action": "fold"}
    if call_chips <= max(pot // 2, 1) and "call" in a:
        return {"action": "call"}
    return {"action": "fold"}


def _ask_llm(table: dict) -> dict:
    key = os.environ["OPENAI_API_KEY"]  # KeyError -> caught -> fallback
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    allowed = table.get("allowedActions") or {}
    prompt = (
        "You are a heads-up No-Limit Hold'em bot. Given the state, reply with ONLY "
        'a JSON object like {"action":"raise","amount":120} (amount = TOTAL chips '
        "committed this street; omit for fold/check/call).\n"
        f"legal actions: {allowed.get('availableActions')}\n"
        f"raiseRange: {allowed.get('raiseRange')} betRange: {allowed.get('betRange')}\n"
        f"state: {json.dumps({k: table.get(k) for k in ('street','boardCards','potChips','seats','selfSeatNumber')})}"
    )
    body = json.dumps({"model": model, "temperature": 0.2,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(f"{base}/chat/completions", data=body, method="POST",
                                 headers={"authorization": f"Bearer {key}",
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        out = json.loads(r.read())
    text = out["choices"][0]["message"]["content"]
    text = text[text.find("{"): text.rfind("}") + 1]   # strip ```json fences etc.
    return json.loads(text)


def act(table: dict) -> dict:
    allowed = (table.get("allowedActions") or {}).get("availableActions") or []
    try:
        a = _ask_llm(table)
        if isinstance(a, dict) and a.get("action") in allowed:
            return a
    except Exception:
        pass
    return _heuristic(table)
