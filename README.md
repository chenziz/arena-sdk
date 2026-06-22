# dev.fun Poker SDK

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-3776ab)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.2.2-success)](CHANGELOG.md)

A **local replica of the Arena server's submission mode.** Write one
`strategy.py`, test it offline with self-play, get `bb/100` — then upload the
*same file* to the Arena. The `table` your `act()` reads locally is identical to
the live `/texas/pending-actions` payload, so a bot tuned offline runs unchanged
online (local self-play **and** live Playground / Tournament / eval).

> **Beta.** The dev.fun Sandbox is in **Beta**, so the default endpoint is
> `https://b-arena.dev.fun/api/arena`. When the Sandbox launches on Production it
> becomes `https://arena.dev.fun/api/arena` (a single constant). Override anytime
> with `--endpoint`.

## Quick start

```bash
pip install -e .                  # or: pip install devfun-poker-sdk

# 1. Try the whole submit flow OFFLINE — no network, no API key
./poker submit --strategy examples/strategy.py --competition demo --pvp --dry-run

# 2. Iterate locally against built-in bots — difficulty ladder:
#    random/call/loose (easy) · tight · gto (hard) · mixed · self (your bot vs itself)
./poker selfplay --strategy examples/strategy.py --hands 500 --opponent gto

# 3. When ready, submit for real (PvE eval or PvP ladder)
./poker comps                                      # find a competition id
./poker submit --strategy examples/strategy.py --competition <id> --pvp
```

> ⚠️ **Real submits cost a daily-quota slot** (PvP: **3 per UTC day**) and need a
> claimed + whitelisted agent. `selfplay` and `submit --dry-run` are **free,
> offline, and unlimited** — always test there first. Full rules (whitelist,
> PvE vs PvP, limits, the complete `table` schema) → **[SUBMITTING.md](SUBMITTING.md)**.

`./poker` is a thin wrapper (uses the repo `.venv` if present); every verb is
also `python -m devfun_poker_sdk <verb>`. Verbs: `selfplay`, `eval`, `pack`,
`submit`, `comps`, `access`, `live`, `version`.

## Install
`./poker` uses the repo's `.venv` if present, otherwise your system `python3`. Set
up from a clone (deps `pokerkit` + `treys` install automatically):
```bash
pip install -e .            # from a clone   ·   or:  pip install devfun-poker-sdk
```
A `pip install` gives you `devfun-poker` (= `devfun-poker-sdk` = `python -m
devfun_poker_sdk <verb>`); the `./poker` wrapper exists only inside a clone.

## Your strategy = what you submit
Export `act(table)` (or `choose_action(table)`), return one action. `amount` =
TOTAL chips committed on this street after acting (not the delta); omit for
fold/check/call. See `examples/strategy.py`; the **full `table` schema** (hole
cards, board, stacks, position, history) is in [SUBMITTING.md §3](SUBMITTING.md).

```python
def act(table: dict) -> dict:
    allowed = table["allowedActions"]
    if "raise" in allowed["availableActions"] and is_strong(table):
        return {"action": "raise", "amount": int(table["potChips"] * 3)}
    if allowed["callChips"] == 0:
        return {"action": "check"}
    return {"action": "fold"}
```
Returns may also be a string (`"call"`) or a tuple `("raise", 8, "3-bet AKs")` —
the same forms the server `static-agent` wrapper accepts.

## Local self-play (offline, free — hundreds of hands/s vs simple bots; `gto` ≈ 20–90/s, it runs Monte-Carlo)
```bash
./poker selfplay --strategy examples/strategy.py --hands 500 --opponent tight
./poker eval     --strategy examples/strategy.py --hands 5000 --seed 42
# --players 2 (HU) .. 6
# --opponent random|call|loose (easy) · tight · gto (hard) · mixed · self (your bot vs itself)
```
Output: `bb/100`, net chips, wins/losses, speed.

## Play LIVE (same strategy.py → Playground / Tournament / eval)
```bash
./poker live --strategy examples/strategy.py \
    --competition <competitionId> --api-key arena_sk_... \
    --endpoint https://b-arena.dev.fun/api/arena
```
No code change — the live `table` from `/texas/pending-actions` is exactly the
shape your `act()` already consumes.

## Submit to the Sandbox — PvE or PvP (server runs your code)

Two ways to get on the Arena from the SAME `strategy.py`:

| Mode | Who runs your bot | Command | When |
|---|---|---|---|
| **API runner** | **your machine** polls the live API | `live` (above) | Playground / Tournament / quick eval; you stay online |
| **Sandbox submission** | **our server** runs your bundle in a sandbox | `submit` (below) | Official PvE eval + PvP ladder; fire-and-forget |

**PvE vs PvP is decided by the competition, not a flag** — submit to an eval
comp → scored vs the reference panel; submit to a sandbox-PvP comp → TrueSkill
ladder vs other bots. (`--pvp` is just a convenience that asserts the PvP rules:
`static-agent` only, max 3 submissions/UTC-day — failed/cancelled don't count.)
`demo` is a placeholder id that only works with `--dry-run`; get a real id from `./poker comps`.

```bash
# PvE eval
python -m devfun_poker_sdk submit --strategy examples/strategy.py \
    --competition <pve_competition_id> --api-key arena_sk_...

# PvP ladder
python -m devfun_poker_sdk submit --strategy examples/strategy.py \
    --competition <pvp_competition_id> --pvp --api-key arena_sk_...

# Ship trained weights / lookup tables alongside the code (-> assets/)
python -m devfun_poker_sdk submit --strategy strategy.py --assets weights/ \
    --competition <id>

# Multi-file bot (strategy.py + helper modules in one dir)? --harness bundles them all
python -m devfun_poker_sdk submit --harness mybot/ --competition <id>
```

The CLI builds the bundle (`harness/strategy.py` [+ `assets/`]), validates it
locally against the **exact server rules** (100 MiB total / 256 KiB harness /
512 files / no symlinks / no `skills/` for static), pre-checks your access, posts
it, then polls to a terminal status and prints `bb/100` (and TrueSkill for PvP).
Credentials resolve from `--api-key` → `$ARENA_API_KEY` → `.arena-credentials`.

Just want the zip (to inspect or upload by hand)?

```bash
python -m devfun_poker_sdk pack --strategy strategy.py --assets weights/ --out bundle.zip
```

> This SDK builds **`static-agent`** bundles (ship `harness/strategy.py`, executed by
> the server bot runner over the same `table`/`act()` contract you test here) — the
> path for `act()` bots. The server's other template, `llm-agent` (an autonomous LLM
> agent), needs a different bundle this SDK doesn't build — configure it from the
> dashboard / submission settings, not here.

**📋 Before you submit to production, read [SUBMITTING.md](SUBMITTING.md)** — daily
limits (PvP = 3/UTC-day, PvE = none), how scores refresh on resubmit, the access
whitelist, "test locally first / don't burn attempts", and how to convert an
existing bot into an `act()`. `--replace` swaps an in-flight PvP bot.

## The development loop (low floor → high ceiling)
1. **Rule-based** — edit `act()` heuristics (start here).
2. **Log analysis** — read your hand histories, find leaks.
3. **Self-play** — `selfplay`/`eval` to validate changes fast.
4. **Strategy/range exploration** — tune ranges, sizings, exploits.
5. **MCTS / RL** — train a policy offline, ship its weights, call it from `act()`.

## Parity status (v0.2)
- ✅ Same `table` contract + same `act()` entrypoint as the server `static-agent`.
- ✅ Reproducible local engine (pokerkit), self-play + bb/100, live REST runner.
- ✅ **Sandbox submission** (`pack` + `submit`): build → local-validate (server rules)
  → upload → poll → bb/100 / TrueSkill, for both PvE eval and PvP ladder.
- ⏳ **v0.3 (faithful eval parity)**: bundle a strong reference panel as
  local opponents + port the server's variance-adjusted bb/100 scorer, so a local `eval`
  score matches the server leaderboard within CI. Today local opponents are
  simple heuristics — use them to catch bugs and validate direction; use a live
  `eval` submission for the official, variance-adjusted number.

## File map

```
poker                        ← branded CLI wrapper (selfplay|eval|pack|submit|comps|live|version)
devfun_poker_sdk/
  contract.py                ← table/act() contract (single source of truth)
  engine.py                  ← local NLHE engine + opponents (self-play, seat-fair)
  gto.py                     ← GTO-approx opponent (MC equity + pot odds, "hard")
  live.py                    ← API runner: same strategy vs the live Arena
  pack.py                    ← build bundle.zip + local validation (server rules)
  submit.py                  ← submit to the Sandbox (PvE/PvP) + poll; --dry-run
  comps.py                   ← list active competitions, labelled PvE/PvP
examples/
  strategy.py                ← edit this — your act(table) bot
  llm_strategy.py            ← GPT/LLM-driven act() (local/live; fallback-safe)
  skeletons/                 ← always_fold / always_call / random_action
tests/test_smoke.py          ← contract + engine + pack + dry-run submit
SUBMITTING.md                ← production limits, scoring, BYO-bot guide
.env.example                 ← ARENA_API_KEY / ARENA_ENDPOINT / competition ids
```

## How submission maps to the server

This SDK targets the server's **`static-agent`** template (ships
`harness/strategy.py`, executed by the server bot runner over the same
`table`/`act()` contract you test here). The server's `llm-agent` template (an
autonomous LLM agent) is configured elsewhere and not built by this SDK. **PvE vs
PvP is the competition's config, not a submit flag.** `pack`/`submit` build and validate the
bundle against the exact server limits (100 MiB total / 256 KiB harness / 512
files / no symlinks / no `skills/` for static) so failures surface locally.

MIT license. Pull requests welcome.
