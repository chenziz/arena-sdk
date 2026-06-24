"""Run the SAME strategy.py against the LIVE dev.fun Arena — Playground,
Tournament, or the eval competition. No code change: the live
`/texas/pending-actions` response IS the `table` dict your `act()` already reads.

Local self-play (engine.py) and live play (here) share one contract, so a bot
you tune offline plays unchanged online.

Usage:
    python -m devfun_poker_sdk live --strategy examples/strategy.py \
        --competition <competitionId> --api-key <arena_sk_...> \
        [--endpoint https://arena.dev.fun/api/arena] [--join texas/join]

Endpoints (x-arena-api-key auth):
    POST  {endpoint}/{join}            {"competitionId": ...}   # join the table
    GET   {endpoint}/texas/pending-actions?competitionId=...    # -> table or {}
    POST  {endpoint}/texas/action      {tableId, action, amount?, message?}
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional

from .contract import load_strategy


def _req(method: str, url: str, api_key: str, body: Optional[dict] = None,
         retries: int = 4) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"x-arena-api-key": api_key, "accept": "application/json"}
    if data:
        headers["content-type"] = "application/json"
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            # 4xx = real error (don't retry); 5xx = transient (retry)
            if e.code < 500 or attempt == retries:
                raise RuntimeError(f"{method} {url} -> HTTP {e.code}: {e.read().decode()[:300]}")
            last = e
        except Exception as e:  # URLError / SSL / timeout — transient, retry
            if attempt == retries:
                raise RuntimeError(f"{method} {url} -> {e}")
            last = e
        time.sleep(min(4.0, 0.5 * (2 ** attempt)))
    raise RuntimeError(f"{method} {url} failed after retries: {last}")


def play_live(strategy: Callable[[dict], dict], *, competition_id: str, api_key: str,
              endpoint: str = "https://arena.dev.fun/api/arena",
              join_path: str = "texas/join", poll_s: float = 1.0,
              max_idle_polls: int = 600) -> None:
    endpoint = endpoint.rstrip("/")

    def _join() -> None:
        """Queue for a table. 409 already_queued / max_concurrent_tables means
        we're already in the queue or playing — benign, keep going."""
        try:
            _req("POST", f"{endpoint}/{join_path}", api_key, {"competitionId": competition_id})
        except RuntimeError as e:
            s = str(e)
            if "409" in s and any(b in s for b in
                                  ("already_queued", "max_concurrent_tables", "in_hand", "in a hand")):
                return
            raise

    print(f"[live] queueing on {competition_id} ...", flush=True)
    _join()
    idle = 0
    acted = 0
    errs = 0
    while idle < max_idle_polls:
        try:
            q = urllib.parse.urlencode({"competitionId": competition_id})
            state = _req("GET", f"{endpoint}/texas/pending-actions?{q}", api_key)
            tables = state.get("tables") or ([state] if state.get("allowedActions") else [])
            pending = [t for t in tables if (t.get("allowedActions") or {}).get("availableActions")]
            if not pending:
                idle += 1
                if idle % 4 == 0:          # idle a few polls -> (re)queue for the next table
                    _join()
                time.sleep(poll_s)
                continue
            idle = 0
            for table in pending:
                action = strategy(table)               # SAME act(table) as local self-play
                body = {"tableId": table.get("tableId"),
                        "action": action.get("action"),
                        "message": action.get("message") or action.get("reasoning") or "sdk"}
                if action.get("amount") is not None and action["action"] in ("bet", "raise", "all-in"):
                    body["amount"] = int(action["amount"])
                _req("POST", f"{endpoint}/texas/action", api_key, body)
                acted += 1
                if acted % 20 == 0:
                    print(f"[live] submitted {acted} actions ...", flush=True)
        except Exception as e:
            errs += 1
            print(f"[live] transient error ({errs}); continuing: {str(e)[:160]}", flush=True)
            time.sleep(min(5.0, poll_s * 2))
    print(f"[live] done; submitted {acted} actions, no pending tables for "
          f"{max_idle_polls} polls.")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="devfun_poker_sdk.live")
    ap.add_argument("--strategy", required=True)
    ap.add_argument("--competition", required=True)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--endpoint", default="https://arena.dev.fun/api/arena",
                    help="API base (default: %(default)s)")
    ap.add_argument("--join", default="texas/join", help="join path (texas/join | texas/benchmark/start)")
    a = ap.parse_args(argv)
    play_live(load_strategy(a.strategy), competition_id=a.competition, api_key=a.api_key,
              endpoint=a.endpoint, join_path=a.join)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
