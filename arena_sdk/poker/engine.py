"""Local NLHE engine (pokerkit) producing the SAME `table` JSON the dev.fun
Arena server hands to your agent — so a strategy you test here runs unchanged
on the server.

Vendored/hardened from the Arena starter-kit selfplay engine. No network.
"""
from __future__ import annotations

import random
import sys
import time
from typing import Any, Callable, Optional

from pokerkit import Automation, NoLimitTexasHoldem, State

_AUTO = (
    Automation.ANTE_POSTING, Automation.BET_COLLECTION,
    Automation.BLIND_OR_STRADDLE_POSTING, Automation.CARD_BURNING,
    Automation.HOLE_DEALING, Automation.BOARD_DEALING,
    Automation.RUNOUT_COUNT_SELECTION, Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
    Automation.HAND_KILLING, Automation.CHIPS_PUSHING, Automation.CHIPS_PULLING,
)


# ── built-in opponents (same act(table) contract) ───────────────────────────
def bot_call(table: dict, **_: Any) -> dict:
    a = (table.get("allowedActions") or {}).get("availableActions") or []
    if "check" in a:
        return {"action": "check"}
    if "call" in a:
        return {"action": "call"}
    return {"action": "fold"}


def bot_random(table: dict, **_: Any) -> dict:
    allowed = table.get("allowedActions") or {}
    avail = list(allowed.get("availableActions") or [])
    if not avail:
        return {"action": "fold"}
    pick = random.choice(avail)
    pot = int(table.get("potChips") or 0)
    if pick == "bet":
        br = allowed.get("betRange") or {}
        lo, hi = int(br.get("min") or 1), int(br.get("max") or 1)
        return {"action": "bet", "amount": max(lo, min(int(pot * 0.5), hi))}
    if pick == "raise":
        rr = allowed.get("raiseRange") or {}
        lo, hi = int(rr.get("min") or 1), int(rr.get("max") or 1)
        return {"action": "raise", "amount": max(lo, min(lo * 2, hi))}
    return {"action": pick}


def bot_tight(table: dict, **_: Any) -> dict:
    allowed = table.get("allowedActions") or {}
    avail = allowed.get("availableActions") or []
    call_chips = int(allowed.get("callChips") or 0)
    pot = int(table.get("potChips") or 0)
    seat = next((s for s in (table.get("seats") or [])
                 if s.get("seatNumber") == table.get("selfSeatNumber")), {})
    hole = list(seat.get("holeCards") or [])
    board = list(table.get("boardCards") or [])
    ranks = "23456789TJQKA"
    rk = lambda c: ranks.index(c[0].upper()) if c and c[0].upper() in ranks else 0
    pair = len(hole) == 2 and hole[0][0] == hole[1][0]
    hi = max((rk(c) for c in hole), default=0)
    suited = len(hole) == 2 and len(hole[0]) > 1 and len(hole[1]) > 1 and hole[0][-1] == hole[1][-1]
    if not board:
        strong = pair or hi >= 10 or (suited and hi >= 9)
        if not strong and call_chips > 0:
            return {"action": "fold"}
        if call_chips == 0:
            return {"action": "check"} if "check" in avail else {"action": "fold"}
        return {"action": "call"}
    connects = bool({c[0].upper() for c in hole} & {c[0].upper() for c in board}) or pair
    if call_chips == 0:
        return {"action": "check"} if "check" in avail else {"action": "fold"}
    if connects and call_chips <= max(int(pot * 0.5), 1):
        return {"action": "call"}
    return {"action": "fold"}


def bot_loose(table: dict, **_: Any) -> dict:
    allowed = table.get("allowedActions") or {}
    avail = allowed.get("availableActions") or []
    call_chips = int(allowed.get("callChips") or 0)
    pot = int(table.get("potChips") or 0)
    if call_chips == 0:
        return {"action": "check"} if "check" in avail else {"action": "fold"}
    if call_chips > pot * 2 and "fold" in avail:
        return {"action": "fold"}
    return {"action": "call"}


from .gto import act as bot_gto  # GTO-approx opponent (MC equity + pot odds)

OPPONENTS = {"tight": bot_tight, "loose": bot_loose, "random": bot_random,
             "call": bot_call, "gto": bot_gto}


# ── pokerkit State → Arena `table` JSON (server-identical shape) ─────────────
def _street_label(state: State) -> str:
    n = len(state.board_cards)
    return "Preflop" if n <= 0 else ("Flop", "Turn", "River")[min(max(n - 3, 0), 2)]


def build_table(state: State, hero: int, table_id: str, big_blind: int) -> dict:
    is_my_turn = state.actor_index == hero
    pot = (sum(p.amount for p in state.pots) if state.pots else 0) + sum(state.bets or [])
    bets = list(state.bets) if state.bets else []
    seats = []
    for i in range(len(state.stacks)):
        hole = list(state.hole_cards[i]) if i < len(state.hole_cards) else []
        seats.append({
            "seatNumber": i + 1,
            "agentHandle": "hero" if i == hero else f"bot_{i+1}",
            "stackChips": int(state.stacks[i]),
            "holeCards": [repr(c) for c in hole] if (i == hero and hole) else [],
        })
    avail: list[str] = []
    call_chips = call_to = 0
    can_check = can_bet = can_raise = False
    bmin = bmax = rmin = rmax = 0
    if is_my_turn:
        if state.can_fold():
            avail.append("fold")
        if state.can_check_or_call():
            call_chips = int(state.checking_or_calling_amount or 0)
            if call_chips == 0:
                avail.append("check"); can_check = True
            else:
                avail.append("call")
                call_to = (bets[hero] if hero < len(bets) else 0) + call_chips
        if state.can_complete_bet_or_raise_to():
            try:
                lo = int(state.min_completion_betting_or_raising_to_amount or 0)
                hi = int(state.max_completion_betting_or_raising_to_amount or 0)
            except Exception:
                lo = hi = 0
            # Match the server: the aggressive verb is decided by currentBet, not
            # by "> big_blind". currentBet>0 ⇒ raise (preflop the posted blind is a
            # wager, so the BB-option spot is a RAISE); currentBet==0 ⇒ bet.
            if (max(bets) if bets else 0) > 0:
                avail.append("raise"); can_raise, rmin, rmax = True, lo, hi
            else:
                avail.append("bet"); can_bet, bmin, bmax = True, lo, hi
    return {
        "tableId": table_id,
        "potChips": int(pot),
        "street": _street_label(state),
        "boardCards": [repr(c) for c in state.board_cards],
        "selfSeatNumber": hero + 1,
        "seats": seats,
        "allowedActions": {
            "availableActions": avail,
            "callChips": int(call_chips), "callToAmount": int(call_to),
            "canCheck": can_check, "canBet": can_bet, "canRaise": can_raise,
            "betRange": {"min": int(bmin), "max": int(bmax)},
            "raiseRange": {"min": int(rmin), "max": int(rmax)},
        },
        "secondsUntilDeadline": 10.0,
    }


def _apply(state: State, action: dict, big_blind: int) -> None:
    name = (action.get("action") or "").lower().replace("_", "-")
    amt = action.get("amount")
    try:
        if name == "fold":
            state.fold()
        elif name in ("check", "call"):
            state.check_or_call()
        elif name in ("bet", "raise", "all-in"):
            try:
                lo = int(state.min_completion_betting_or_raising_to_amount or big_blind)
                hi = int(state.max_completion_betting_or_raising_to_amount or lo)
            except Exception:
                lo, hi = big_blind, big_blind * 100
            if name == "all-in":
                amt = hi
            amt = max(lo, min(int(amt if amt is not None else lo), hi))
            state.complete_bet_or_raise_to(amt)
        else:
            state.fold()
    except Exception:
        try:
            state.fold()
        except Exception:
            pass


def play_one_hand(hero_fn: Callable, opponents: list[Callable], *, starting_stack: int,
                  small_blind: int, big_blind: int, hand_id: int, hero: int = 0,
                  max_actions: int = 300, warn: Optional[dict] = None) -> int:
    n = 1 + len(opponents)
    state: State = NoLimitTexasHoldem.create_state(
        automations=_AUTO, ante_trimming_status=True, raw_antes=0,
        raw_blinds_or_straddles=(small_blind, big_blind) + (0,) * (n - 2),
        min_bet=big_blind, raw_starting_stacks=tuple([starting_stack] * n), player_count=n,
    )
    tid = f"local-{hand_id:05d}"
    # seat -> decision fn; hero sits at `hero`, opponents fill the rest in order.
    seat_fn = {hero: hero_fn}
    for idx, s in enumerate(s for s in range(n) if s != hero):
        seat_fn[s] = opponents[idx % len(opponents)]
    steps = 0
    while state.status and state.actor_index is not None and steps < max_actions:
        actor = state.actor_index
        table = build_table(state, actor, tid, big_blind)
        fn = seat_fn[actor]
        try:
            action = fn(table)
        except Exception as e:
            if actor == hero and warn is not None and not warn.get("shown"):
                print(f"[selfplay] ⚠ your act() raised {type(e).__name__}: "
                      f"{str(e)[:120]} — folding this hand (and likely others). "
                      "Fix it before submitting.", file=sys.stderr)
                warn["shown"] = True
            action = {"action": "fold"}
        if not isinstance(action, dict):
            if actor == hero and warn is not None and not warn.get("shown"):
                print(f"[selfplay] ⚠ your act() returned {type(action).__name__}, not a "
                      "dict — folding. Return {'action': 'fold'|'check'|'call'|'bet'|"
                      "'raise', 'amount'?: int}. Fix it before submitting.", file=sys.stderr)
                warn["shown"] = True
            action = {"action": "fold"}
        _apply(state, action, big_blind)
        steps += 1
    return int(state.stacks[hero]) - starting_stack


def run_match(hero_fn: Callable, *, hands: int = 500, opponent: str = "tight",
              players: int = 2, starting_stack: int = 200, small_blind: int = 1,
              big_blind: int = 2, seed: Optional[int] = None, mirror: bool = True) -> dict:
    """Run `hands` hands; hero seat rotates; optional duplicate (mirror) hands to
    cut variance. Returns bb/100 + stats."""
    if not 2 <= players <= 6:
        raise SystemExit(f"--players must be 2..6 (got {players})")
    if hands < 1:
        raise SystemExit(f"--hands must be >= 1 (got {hands})")
    if seed is not None:
        random.seed(seed)
    if opponent == "self":
        opps = [hero_fn] * (players - 1)            # your bot vs your bot
    elif opponent == "mixed":
        rot = [bot_gto, bot_tight, bot_loose, bot_random, bot_call]
        opps = rot[: players - 1]
    else:
        opps = [OPPONENTS.get(opponent, bot_tight)] * (players - 1)
    deltas: list[int] = []
    t0 = time.time()
    warn = {"shown": False}   # one-shot diagnostic if the hero's act() misbehaves
    for i in range(hands):
        try:
            # Rotate hero's seat each hand so positional (blind) bias cancels out
            # — without this, the hero always sits on the button and bb/100 is skewed.
            d = play_one_hand(hero_fn, opps, starting_stack=starting_stack,
                              small_blind=small_blind, big_blind=big_blind,
                              hand_id=i + 1, hero=i % players, warn=warn)
        except Exception:
            d = 0
        deltas.append(d)
    net = sum(deltas)
    elapsed = time.time() - t0
    return {
        "hands": hands, "opponent": opponent, "players": players,
        "net_chips": net,
        "bb_per_100": (net / big_blind) / max(hands, 1) * 100,
        "wins": sum(1 for d in deltas if d > 0),
        "losses": sum(1 for d in deltas if d < 0),
        "elapsed_s": round(elapsed, 2),
        "hands_per_s": round(hands / max(elapsed, 1e-3), 1),
    }
