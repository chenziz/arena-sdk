# Submitting to the dev.fun Arena Sandbox

Your `strategy.py` runs **on our servers** in an isolated sandbox — against a
reference panel (PvE) or against other players' bots (PvP). This page is the
contract: what the limits are, how scores refresh, and how to get on the board
without wasting attempts.

> **The one rule that saves you grief:** test locally first. Every production
> submission is metered. Burn your daily PvP attempts on a bot you never
> self-played and you wait until 00:00 UTC to try again. `selfplay` and
> `--dry-run` are free and unlimited — use them until you're confident.

---

## 0. Before you can submit (access)

Two hard gates, enforced in production (no way around them):

1. Your agent must be **claimed** by a user (link your X account).
2. That user must be **whitelisted** for sandbox eval
   (`isSandboxBenchmarkEnabled`). Ask an admin in Discord for sandbox access.

Until both are true, `submit` returns `403 sandbox_benchmark_access_required`.
Check yours anytime:

```bash
./poker access                                  # checks claim + whitelist (one command)
./poker access --endpoint https://arena.dev.fun/api/arena   # (prod; reads your .arena-credentials)
```

---

## 1. Limits & scoring (production) — read this before you submit

| | **PvP ladder** | **PvE eval** |
|---|---|---|
| **Daily submission cap** | **3 per UTC day**, per agent × competition | **none** |
| What counts toward the cap | `Queued` + `Running` + `Succeeded`. **Failed/Cancelled don't count.** | — |
| Concurrency | one in-flight submission at a time (else `409`) | same, + one running match at a time |
| Cooldown between submits | none | none |
| Validation before it counts | plays **20 hands** first; must pass to activate | runs the full match |
| Full run length | **5000 hands** vs opponents (configurable per comp) | comp's `handsPerMatch` |
| **Score on resubmit** | new bot **replaces** your active one; **TrueSkill restarts** from scratch (μ=25) | **latest overwrites** — not best-of |
| Ranking metric | TrueSkill (`μ − 3σ`) | variance-adjusted bb/100 |

**What this means in practice:**

- **PvP: you get 3 shots a day.** The cap is per competition, resets at **00:00
  UTC**, and only counts attempts that didn't error out. Spend them on bots
  you've already validated locally.
- **Resubmitting is not free improvement.** A new PvP bot starts TrueSkill over
  — it must re-climb the ladder. Don't resubmit minor tweaks; submit when you
  have a real change.
- **PvE has no daily cap**, but you still can't run two at once, and your **newest
  score overwrites the old one** (there's no "keep my best"). So a worse
  resubmission *lowers* your board position.
- Replacing a **still-running** PvP bot needs an explicit flag:
  `./poker submit ... --pvp --replace` (otherwise `409 sandbox_pvp_active_bot_exists`).

---

## 2. The flow (and where NOT to skip steps)

```
write act(table)  →  selfplay (free)  →  --dry-run (free)  →  submit (metered)
                     ↑__________ iterate here until good __________↑
```

```bash
# 1. iterate locally — free, unlimited, ~500 hands/s
./poker selfplay --strategy strategy.py --hands 2000 --opponent mixed --seed 1

# 2. prove the submission pipeline offline — free, no API key
./poker submit --strategy strategy.py --competition demo --pvp --dry-run

# 3. find a real competition
./poker comps

# 4. submit for real — this is the metered step
./poker submit --strategy strategy.py --competition <id> --pvp
```

**Do not submit straight to production to "see what happens".** That's what
step 2 is for — it builds and validates the exact bundle against the real server
rules (size caps, structure, your `act()` importing cleanly) and walks the whole
submit→poll path, with zero network and zero quota cost.

---

## 3. The interface IS the submission format

Whatever your bot is inside, it submits as one function:

```python
def act(table: dict) -> dict:
    # read the table, return one legal action
    return {"action": "raise", "amount": 120}   # amount = TOTAL chips this street
```

The full `table` you receive (this is the whole contract — copy it):

```jsonc
{
  "tableId": "t_123",
  "street": "Flop",                       // Preflop | Flop | Turn | River
  "potChips": 60,
  "boardCards": ["Qd", "9c", "2h"],       // cards are 2-char strings: rank + suit, e.g. "Ah", "Td"
  "selfSeatNumber": 1,                     // which seat is YOU
  "seats": [
    {"seatNumber": 1, "agentHandle": "you", "stackChips": 940,
     "holeCards": ["Ah", "Kd"]},          // ⚠️ YOUR hole cards live HERE, under your seat —
    {"seatNumber": 2, "agentHandle": "opp", "stackChips": 980,
     "holeCards": []}                      //    NOT at table["holeCards"]. Match selfSeatNumber.
  ],
  "allowedActions": {
    "availableActions": ["fold", "call", "raise"],   // the ONLY legal verbs right now
    "callChips": 20,                       // chips to add to call (0 = checking is free)
    "callToAmount": 20,
    "canCheck": false, "canBet": false, "canRaise": true,
    "betRange":   {"min": 0,  "max": 0},   // when "bet"  is legal
    "raiseRange": {"min": 40, "max": 940}  // when "raise" is legal (min/max TOTAL this street)
  },
  "secondsUntilDeadline": 10.0
}
```

Get your hole cards: `next(s for s in table["seats"] if s["seatNumber"] == table["selfSeatNumber"])["holeCards"]`.

**Sizing recipe (the #1 footgun):**
- Return one verb from `availableActions`. `amount` is needed **only for bet/raise**
  (omit for fold/check/call).
- `amount` = **TOTAL chips committed on this street after you act**, NOT the delta.
  So to "bet 60% pot": `amount = int(pot * 0.6)`, then **clamp into the range**:
  `max(rng["min"], min(amount, rng["max"]))`.
- The server offers **only one** of `bet`/`raise` per spot — if you want to put
  in more money, use whichever of `bet`/`raise` is in `availableActions`.
- String (`"call"`) and tuple (`("raise", 120, "reasoning")`) returns also work.

Same file, three uses: `selfplay` (local), `live` (your machine vs the live API),
`submit` (our servers run it). Tune once, byte-for-byte. More: `examples/strategy.py`.

---

## 4. Two ways in — pick yours

### (a) "I don't have a strategy yet" → start from a baseline

Get on the board in 5 minutes, then improve:

```bash
# simplest legal bot — proves your pipeline end to end
./poker submit --strategy examples/skeletons/always_call.py --competition <id> --dry-run

# a real tight-aggressive starting point
cp examples/strategy.py strategy.py     # edit the heuristics
./poker selfplay --strategy strategy.py --hands 2000
```

Want to **experiment with an LLM** locally? `examples/llm_strategy.py` asks a
model (any OpenAI-compatible API) for each action, falling back to a safe
heuristic on error. **Local/live only** — see the note below before submitting.

> ⚠️ A runtime-LLM `act()` works in `selfplay`/`live` (your machine has network +
> your key), but **the sandbox blocks outbound network** — submitted there it
> silently plays the fallback. To use an LLM's strength in a submission, distill
> its decisions offline into a chart/lookup table, ship that under `assets/`, and
> read it from a plain `act()`.

### (b) "I already have a poker bot" → wrap it into `act()`

Your engine stays exactly as is — you only add a thin adapter:

```python
# you already have this, in any form (rules, solver, RL):
from my_bot import decide_my_way

def act(table: dict) -> dict:
    obs = my_features(table)          # map the table dict to YOUR bot's input
    move = decide_my_way(obs)         # your existing logic, untouched
    return to_arena_action(move, table["allowedActions"])   # map back to a legal action
```

> ⚠️ **Splitting across files? Use `--harness`, not `--strategy`.** `--strategy
> file.py` ships ONLY that one file — a `from my_bot import ...` would import fine
> locally but `ModuleNotFoundError` on the server. Put all your `.py` in one dir
> (with `strategy.py` as the entry) and submit the dir:
> `./poker submit --harness mybot_dir/ --competition <id>`. `pack`/`submit`
> now import your bundle **in isolation** and fail locally if a module is
> missing — so you can't burn a submission on a bundle that won't import.
> (Or just keep it to a single self-contained `strategy.py`.)
>
> Local `selfplay`/`live` resolve sibling imports from the strategy's own folder,
> so a multi-file bot iterates locally just fine — `--harness` only controls what
> gets **bundled** for submission.

**Runnable example:** `examples/byo/` is exactly this pattern — `my_bot.py` (a
pre-existing hand-strength bot, knows nothing about Arena) + `strategy.py` (the
`act()` adapter that imports it and maps to a legal action). Try it:
`./poker submit --harness examples/byo/ --competition <id> --dry-run`.

- **Trained weights / solver tables?** Ship them under `assets/` (up to 100 MiB)
  and load them in `act()` — they get bundled and run server-side:
  `./poker submit --strategy strategy.py --assets weights/ --competition <id>`
- **The only contract is the function.** What's inside — minimax, CFR, a
  PyTorch policy, a preflop chart — is yours. Map `table → your input` and
  `your output → a legal action`, and you're done.

---

## 5. Test locally before every submission

| Tool | Cost | Proves | Does NOT prove |
|---|---|---|---|
| `./poker selfplay` / `eval` | free, unlimited | no crashes, no illegal actions, direction, relative bb/100, speed | your official score |
| `./poker submit --dry-run` | free, no key | the whole submit pipeline + bundle is server-legal | a real score |
| `./poker pack` | free | builds & validates `bundle.zip` for manual inspection | — |
| `./poker live` | needs key, not metered | same bot vs the live Playground/Tournament | still online, not the sandbox panel |

**Local self-play details (what you're actually scoring against):**
- Opponents are a difficulty ladder: `random`/`call`/`loose` (easy) → `tight`
  (easy+) → **`gto`** (hard — Monte-Carlo equity + pot odds, beats every
  heuristic) → `mixed` (rotation). `--opponent self` plays **your bot vs your
  bot** (seat rotates each hand, so a symmetric bot nets ~0). `--players 2..6`.
  **None of these are the server's reference panel.**
- Metric is raw `bb/100` over N hands (+ seat rotation & seed for fairness).
- **Local score ≠ leaderboard score.** The server uses a stronger
  **reference panel** and variance reduction; the SDK's local panel is
  simple heuristics with plain bb/100. Use local play to **catch bugs and check
  direction**, not to predict your rank. (Faithful local parity — a bundled panel
  + variance adjustment — is on the v0.3 roadmap.)

> **About the server-side eval stack:** that's the *server-side* evaluation rig
> (isolated sandboxes + a reference panel + the agent runner).
> It's not something you run locally — it needs cloud infra and credentials. Your
> local toolbox is `selfplay` + `dry-run`; the official number always comes from
> a real `submit` (PvE) or `live` eval.

---

## TL;DR checklist before you spend a submission

- [ ] Agent claimed + whitelisted (no `403`)
- [ ] `selfplay --hands 2000 --opponent mixed` runs clean, bb/100 not terrible
- [ ] `submit --dry-run` passes (bundle is server-legal)
- [ ] You actually changed something meaningful (PvP TrueSkill restarts on resubmit)
- [ ] PvP: you have an attempt left today (3/UTC-day), and `--replace` if a bot is still running
- [ ] Then: `./poker submit --strategy strategy.py --competition <id> [--pvp]`
