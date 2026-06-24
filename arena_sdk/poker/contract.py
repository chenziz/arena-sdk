"""Load a user strategy file and adapt it to ONE uniform callable, matching the
dev.fun Arena server's `static-agent` contract.

Server contract: a strategy file exports
`choose_action(table)` or `act(table)`. It may return:
  - an action string                      -> {"action": "..."}
  - a tuple/list (action, amount, reason) -> {"action","amount","reasoning"}
  - a dict {action, amount?, reasoning?}  -> as-is
Legacy `decide(table, deadline_s, research_context)` is also accepted.

So the SAME strategy.py you test locally is what you upload — byte for byte.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

ENTRYPOINTS = ("act", "choose_action", "decide")  # server priority order


def normalize_action(ret: Any) -> dict:
    if isinstance(ret, str):
        return {"action": ret}
    if isinstance(ret, (tuple, list)):
        out: dict = {}
        if len(ret) >= 1 and ret[0] is not None:
            out["action"] = str(ret[0])              # coerce: ("raise",8) or (verb,)
        if len(ret) >= 2 and ret[1] is not None:
            out["amount"] = ret[1]
        if len(ret) >= 3 and ret[2] is not None:
            out["reasoning"] = ret[2]
        return out if out.get("action") else {"action": "fold"}
    if isinstance(ret, dict):
        return ret if ret.get("action") else {"action": "fold"}
    return {"action": "fold"}


def clamp_to_range(allowed: dict, kind: str, frac: float, pot: int):
    """Build a legal bet/raise sized to `frac` of pot, clamped into the server's
    range; returns None if `kind` ('bet'|'raise') isn't a currently-legal action.
    `amount` = TOTAL chips committed this street (the server's convention)."""
    allowed = allowed or {}
    avail = allowed.get("availableActions")
    if avail is not None and kind not in avail:    # not a legal verb right now
        return None
    rng = allowed.get("raiseRange" if kind == "raise" else "betRange") or {}
    lo, hi = int(rng.get("min") or 0), int(rng.get("max") or 0)
    if lo <= 0:
        return None
    return {"action": kind, "amount": max(lo, min(int(pot * frac) or lo, hi))}


def load_strategy(path: str) -> Callable[[dict], dict]:
    p = Path(path).resolve()
    if not p.exists():
        raise SystemExit(f"strategy file not found: {p}")
    # Resolve sibling imports for a multi-file bot (strategy.py + helper.py) when
    # running LOCALLY — but SCOPED: add the strategy's dir to sys.path only for the
    # duration of the import, then remove it and purge any sibling modules it
    # pulled in. This (a) doesn't leave a user dir on sys.path (no shadowing of
    # later imports, no security-scanner noise) and (b) stops two bots that each
    # ship a same-named helper.py from colliding via the global module cache.
    # Import helpers at module top (standard) so they bind before this scope ends.
    # For submission, the bundle must carry the siblings — use `--harness <dir>`.
    parent = str(p.parent)
    before = set(sys.modules)
    sys.path.insert(0, parent)
    try:
        spec = importlib.util.spec_from_file_location("user_strategy", str(p))
        if not spec or not spec.loader:
            raise SystemExit(f"could not import {p}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        try:
            sys.path.remove(parent)
        except ValueError:
            pass
        for _name in set(sys.modules) - before:
            sys.modules.pop(_name, None)

    fn = name = None
    for ep in ENTRYPOINTS:
        cand = getattr(mod, ep, None)
        if callable(cand):
            fn, name = cand, ep
            break
    if fn is None:
        raise SystemExit(f"{p} must define act(table) or choose_action(table)")

    def wrapped(table: dict) -> dict:
        if name == "decide":
            # Legacy decide(table, deadline_s, research_context); fall back to
            # decide(table) if the user defined the shorter signature.
            try:
                ret = fn(table, deadline_s=table.get("secondsUntilDeadline", 10.0),
                         research_context=None)
            except TypeError:
                ret = fn(table)
        else:
            # act()/choose_action(): call directly so real TypeErrors inside the
            # user's strategy surface instead of being masked as a signature retry.
            ret = fn(table)
        return normalize_action(ret)

    wrapped.entrypoint = name  # type: ignore[attr-defined]
    return wrapped
