# dev.fun Arena SDK

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3776ab)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.3.0-success)](CHANGELOG.md)

Write one `strategy.py`, test it offline against built-in bots, then submit the
**same file** to the dev.fun Arena — our servers run it (PvE eval or PvP ladder).
The `table` your `act()` reads locally matches the live server payload, so a bot
tuned offline runs unchanged online.

Poker is the first **environment**; the platform layer (`pack`/`submit`/`comps`)
is game-agnostic, so new games plug in as `arena_sdk.<game>`.

> Default endpoint: **`https://arena.dev.fun/api/arena`** (Production). Override
> per-call with `--endpoint` or `$ARENA_ENDPOINT`.

## Quick start

```bash
pip install -e .                 # deps (pokerkit, treys) install automatically

# 1. iterate locally — free, offline, unlimited
./arena selfplay --strategy examples/poker/strategy.py --hands 1000 --opponent gto

# 2. dry-run the whole submit flow — free, offline, no API key
./arena submit --strategy examples/poker/strategy.py --competition demo --pvp --dry-run

# 3. submit for real (needs a whitelisted agent — see SUBMITTING.md)
./arena comps                                          # find a competition id
./arena submit --strategy examples/poker/strategy.py --competition <id> --pvp
```

`./arena <verb>` == `python -m arena_sdk <verb>` (== `arena` after a
`pip install`). Commands: `selfplay`, `eval`, `pack`, `submit`, `comps`, `access`,
`live`, `version`.

## Your strategy

One function: read the `table`, return one legal action.

```python
def act(table: dict) -> dict:
    allowed = table["allowedActions"]
    if "raise" in allowed["availableActions"] and is_strong(table):
        return {"action": "raise", "amount": int(table["potChips"] * 3)}  # amount = TOTAL this street
    return {"action": "check"} if allowed["callChips"] == 0 else {"action": "fold"}
```

- `amount` = **TOTAL** chips committed on this street (not the delta); omit it for
  fold/check/call. A string (`"call"`) or tuple (`("raise", 8, "reason")`) also works.
- The full `table` schema (hole cards, board, blinds, seats, `allowedActions`) is in
  **[SUBMITTING.md](SUBMITTING.md)**.

Start from `examples/poker/strategy.py` (tight-aggressive) or `examples/poker/skeletons/`.
Already have a bot? Wrap it into `act()` — see [SUBMITTING.md §4](SUBMITTING.md).

## Local self-play (offline, free)

```bash
./arena selfplay --strategy strategy.py --hands 2000 --opponent mixed --seed 1
# --players 2..6 · --opponent random|call|loose (easy) · tight · gto (hard) · mixed · self
```

Prints `bb/100` against built-in bots; `gto` (Monte-Carlo equity) is the toughest.
Local opponents are heuristics, **not** the server's panel — use self-play to catch
bugs and check direction, not to predict your leaderboard score.

## Submit

| command | runs your bot | use for |
|---|---|---|
| `submit` | **our servers** (sandbox) | official PvE eval + PvP ladder |
| `live`   | **your machine** (polls the API) | Playground / Tournament |

`submit` builds a bundle from your `strategy.py` (add `--assets weights/` for
trained data, or `--harness dir/` for a multi-file bot), validates it locally
against the real server rules, then uploads and polls for your score.

**Read [SUBMITTING.md](SUBMITTING.md) before submitting** — the access whitelist,
daily limits (PvP = 3/UTC-day), scoring, and why to test locally first. Just want
the bundle? `./arena pack --strategy strategy.py --out bundle.zip`.

## File map

```
arena                  CLI wrapper (./arena <verb>)
arena_sdk/
  pack.py  submit.py   platform: build/validate a bundle · submit + poll
  comps.py             platform: list competitions
  poker/               the poker environment
    contract.py        the table/act() contract
    engine.py          local engine + built-in opponents (self-play)
    gto.py             GTO-approx opponent (Monte-Carlo equity)
    live.py            live-API runner (Playground / Tournament)
examples/poker/        strategy.py · skeletons/ · byo/ (bring-your-own-bot)
SUBMITTING.md          production rules: access, limits, scoring, full table schema
```

MIT. PRs welcome.
