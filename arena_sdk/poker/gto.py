"""A GTO-approximate opponent — meaningfully stronger than the rule-of-thumb bots.

Pure Python, no weights, no network. It plays by **Monte-Carlo equity + pot
odds + position-aware sizing**: roll out the hand against a random villain to
estimate equity, then value-bet / call / fold by equity vs the price, with a
little semi-bluffing. Uses `treys` (pure-Python MIT hand evaluator) when present,
and falls back to a tight-passive heuristic on any error so it never crashes.

This is the SDK's `gto` opponent (the `hard` tier). Register: it's added to
`engine.OPPONENTS` and exposed via `--opponent gto`.
"""
from __future__ import annotations

import random

from .contract import clamp_to_range

try:
    from treys import Card as _TCard, Evaluator as _TEval
    _EVAL = _TEval()
    _HAVE_TREYS = True
except Exception:                       # treys not installed → heuristic fallback
    _HAVE_TREYS = False

_RANKS = "23456789TJQKA"
_SUITS = "shdc"
_FULL_DECK = [r + s for r in _RANKS for s in _SUITS]


def _norm(card: str) -> str:
    rank, suit = card[:-1], card[-1]              # suit = LAST char ("10h" stays safe)
    if rank == "10":
        rank = "T"                                # treys uses 'T' for ten
    return rank.upper() + suit.lower()


def _equity(hole: list, board: list, num_villains: int = 1,
            iters: int = 200) -> float | None:
    """Hero's equity vs `num_villains` uniformly-random villains (hero must beat
    ALL of them), Monte-Carlo. 0..1. HU (num_villains=1) is the common case."""
    if not _HAVE_TREYS or len(hole) != 2:
        return None
    try:
        used = {_norm(c) for c in hole} | {_norm(c) for c in board}
        deck = [c for c in _FULL_DECK if c not in used]
        hero = [_TCard.new(_norm(c)) for c in hole]
        bcards = [_TCard.new(_norm(c)) for c in board]
        need = 5 - len(bcards)
        nv = max(1, num_villains)
        win = tie = 0
        for _ in range(iters):
            s = random.sample(deck, need + 2 * nv)
            full = bcards + [_TCard.new(c) for c in s[:need]]
            hs = _EVAL.evaluate(full, hero)         # treys: lower score = stronger
            best_v = min(_EVAL.evaluate(full,
                            [_TCard.new(s[need + 2 * k]), _TCard.new(s[need + 2 * k + 1])])
                         for k in range(nv))
            if hs < best_v:
                win += 1
            elif hs == best_v:
                tie += 1
        return (win + tie / 2) / iters
    except Exception:
        return None


def _fallback(avail, call_chips, pot) -> dict:
    if call_chips == 0:
        return {"action": "check"} if "check" in avail else {"action": "fold"}
    if call_chips <= max(pot // 2, 1) and "call" in avail:
        return {"action": "call"}
    return {"action": "fold"} if "fold" in avail else {"action": "call"}


def act(table: dict) -> dict:
    allowed = table.get("allowedActions") or {}
    avail = allowed.get("availableActions") or []
    if not avail:
        return {"action": "fold"}
    call_chips = int(allowed.get("callChips") or 0)
    pot = int(table.get("potChips") or 0)
    seat = next((s for s in (table.get("seats") or [])
                 if s.get("seatNumber") == table.get("selfSeatNumber")), {})
    hole = list(seat.get("holeCards") or [])
    board = list(table.get("boardCards") or [])

    nplayers = len(table.get("seats") or []) or 2
    eq = _equity(hole, board, num_villains=max(1, nplayers - 1))
    if eq is None:
        return _fallback(avail, call_chips, pot)

    def _sized(kind: str, frac: float):
        return clamp_to_range(allowed, kind, frac, pot)

    # ── checked to us / no bet to call ──────────────────────────────────────
    if call_chips == 0:
        if eq > 0.66:
            r = _sized("raise", 0.75) or _sized("bet", 0.7)
            if r:
                return r
        if eq > 0.56:
            b = _sized("bet", 0.6) or _sized("raise", 0.6)
            if b:
                return b
        if eq > 0.45 and random.random() < 0.18:      # thin semi-bluff
            b = _sized("bet", 0.5)
            if b:
                return b
        return {"action": "check"} if "check" in avail else {"action": "fold"}

    # ── facing a bet ────────────────────────────────────────────────────────
    pot_odds = call_chips / (pot + call_chips) if (pot + call_chips) > 0 else 0.0
    if eq > 0.75:
        r = _sized("raise", 0.8)
        if r:
            return r
    if eq >= pot_odds + 0.03:
        if "call" in avail:
            return {"action": "call"}
        return {"action": "check"} if "check" in avail else {"action": "fold"}
    if "fold" in avail:
        return {"action": "fold"}
    return {"action": "check"} if "check" in avail else {"action": "call"}
