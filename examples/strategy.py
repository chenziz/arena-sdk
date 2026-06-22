"""Sample strategy — THIS is exactly what you upload to dev.fun Arena.

Export `act(table)` (or `choose_action(table)`). Read the `table` dict, return
one action. `amount` = TOTAL chips committed on this street after acting
(not the delta). For fold/check/call, omit `amount`.

This baseline is a simple tight-aggressive bot. Replace the logic with your own
(rule-based -> log analysis -> self-play -> RL). The SDK runs it locally exactly
as the server will.
"""
RANKS = "23456789TJQKA"


def _rank(card: str) -> int:
    return RANKS.index(card[0].upper()) if card and card[0].upper() in RANKS else 0


def act(table: dict) -> dict:
    allowed = table.get("allowedActions") or {}
    avail = allowed.get("availableActions") or []
    call_chips = int(allowed.get("callChips") or 0)
    pot = int(table.get("potChips") or 0)
    board = list(table.get("boardCards") or [])

    seat = next((s for s in (table.get("seats") or [])
                 if s.get("seatNumber") == table.get("selfSeatNumber")), {})
    hole = list(seat.get("holeCards") or [])

    pair = len(hole) == 2 and hole[0][0] == hole[1][0]
    high = max((_rank(c) for c in hole), default=0)
    suited = len(hole) == 2 and hole[0][-1] == hole[1][-1]

    def raise_to(frac: float) -> dict:
        rr = allowed.get("raiseRange") or {}
        lo, hi = int(rr.get("min") or 0), int(rr.get("max") or 0)
        if lo <= 0:
            return {"action": "call"} if "call" in avail else {"action": "check"}
        target = max(lo, min(int(pot * frac) or lo, hi))
        return {"action": "raise", "amount": target}

    # ── Preflop ──────────────────────────────────────────────────────────
    if not board:
        premium = pair and high >= 9      # 99+, plus
        strong = high >= 11 or (suited and high >= 9) or pair
        if "raise" in avail and (premium or strong):
            return raise_to(3.0)
        if call_chips == 0:
            return {"action": "check"} if "check" in avail else {"action": "fold"}
        if strong and call_chips <= pot:
            return {"action": "call"}
        return {"action": "fold"}

    # ── Postflop ─────────────────────────────────────────────────────────
    connects = pair or bool({c[0].upper() for c in hole} & {c[0].upper() for c in board})
    if call_chips == 0:
        if connects and "bet" in avail:
            br = allowed.get("betRange") or {}
            lo, hi = int(br.get("min") or 0), int(br.get("max") or 0)
            if lo > 0:
                return {"action": "bet", "amount": max(lo, min(int(pot * 0.5), hi))}
        return {"action": "check"} if "check" in avail else {"action": "fold"}
    if connects and call_chips <= max(int(pot * 0.6), 1):
        return {"action": "call"}
    return {"action": "fold"}
