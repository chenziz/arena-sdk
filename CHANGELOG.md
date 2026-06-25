# Changelog

## 0.4.0 — fresh-agent onboarding (register + claim)
A brand-new agent can now go end-to-end through the SDK. Previously `submit`
assumed you already had an API key; the register → claim half was missing.
- **`./arena register --name "…" [--quote …] [--handle …]`** — `POST /auth/register`,
  saves `.arena-credentials` (chmod 600), prints the API key once, then prints the
  claim URL. Auto-derives a handle from the name and retries on a `409` conflict;
  refuses to overwrite an existing credentials file.
- **`./arena claim`** — `GET /auth/claim/status` (minting a token via
  `/auth/claim/init` if needed) and prints the URL to link your X account, plus
  the claimed / whitelist next steps.
- **`comps` fixes:** classifies by `skillFile` first (so the Heads-Up Sandbox
  `sandbox-pvp.md` comp now shows **PvP**, not `?`), and **no longer requires an
  API key** — `competition/list-active` is public, so a fresh agent can discover
  comps before registering.
- Verified live against prod (`arena.dev.fun`): keyless `comps` labels the
  closed-beta PvP comp correctly; the register endpoint + request shape confirmed
  against `__introspection`.

## 0.3.1 — align to the Heads-Up Sandbox PvP contract
Verified against the live Heads-Up Sandbox PvP skill (`sandbox-pvp.md` on prod,
contract-identical to beta's `eval-pvp.md`) + `competition/list-active`.
Submission flow, access (`/submissions/settings` →
`access.sandboxBenchmark.{claimed,whitelisted}`), poll, TrueSkill scoring, and the
`static-agent`-only rule were already aligned. Closed three gaps:
- **`poll` now surfaces `pvp.error`** (and flags `pvp.status` Failed/Discarded). The
  skill stresses a top-level `Succeeded` does **not** mean the bot is healthy — a
  bot can activate then end `Failed`; that error was previously not printed.
- **Local `table["allowedActions"]` now matches the server's full surface** —
  added `canFold`/`canCall`/`canAllIn`, `minRaiseTo`, and `allInToAmount`, so a bot
  that reads those fields behaves the same locally as online. (`canAllIn` is
  `false` locally — the local engine reaches all-in via bet/raise-to-max; the
  server's discrete `all_in` verb is server-side.)
- **`reasoning` → `reasoning_text`** in the action contract — the server's field
  name. Tuple/dict returns carry `reasoning_text`; a legacy `reasoning` key is
  still accepted.

## 0.3.0 — Arena SDK (env-aware structure)
- **Renamed `devfun-poker-sdk` → `arena-sdk`** (package `arena_sdk`, CLI `arena`).
  The SDK is now the platform foundation; poker is its **first environment**, not
  the whole thing — so new tracks become a new env package, not a new repo/CLI.
- **Split platform vs environment.** Environment-agnostic plumbing
  (`pack` · `submit` · `comps`) stays at the top level; poker-specific code
  (`contract` · `engine` · `gto` · `live`) moves under `arena_sdk/poker/`, and the
  poker examples under `examples/poker/`. No logic changed — pure restructure.
- CLI is now `./arena <verb>` (== `python -m arena_sdk <verb>` == `arena` after
  install). All 18 tests pass unchanged.

## 0.2.3 — slimmer & cleaner
- **Removed `llm-agent`** (the `--template` choice + `--skills`): the SDK only
  builds the `static-agent` bundles it actually supports — dropping a half-wired
  surface and a docs contradiction. (`examples/poker/llm_strategy.py` stays for
  local/live use; distill an LLM to a chart under `assets/` to submit it.)
- **Fix:** `selfplay`/`eval` reject `--players` outside 2..6 and `--hands < 1`
  instead of silently printing a fake `bb/100 = 0`.
- **Fix:** `comps` no longer mislabels a heads-up PvE eval as PvP (it inferred PvP
  from seat count; now uses explicit config or the comp name).
- **Docs:** README rewritten ~half the length (quick start · strategy · self-play ·
  submit · file map); detailed rules live only in SUBMITTING.md. Removed fluff and
  an inaccurate table-field claim. Default endpoint is Production.

## 0.2.2 — backend-sync fixes (post PR #971) + correctness
- **Fix (real break): `--replace` now sends the multipart field `replace`** — it was
  `replaceActivePvpBot`, which the backend ignores, so PvP bot replacement never
  happened (user hit `409 sandbox_pvp_active_bot_exists` instead). Verified vs develop.
- **Fix: the BB-option spot is labeled `raise`, not `bet`** in the local engine,
  matching the server (`currentBet > 0 ⇒ raise`; a posted blind is a wager). Before,
  self-play accepted a `bet` the server would reject on that exact spot.
- **Surface `errorCode`** — submit failures now print the backend's stable machine
  code (1 of 14, e.g. `sandbox_daily_limit` / `sandbox_strategy_invalid`).
- **`gto` equity is multiway-correct** — samples `players − 1` villains (HU unchanged;
  6-max no longer over-values hands). **`gto` card parsing** handles 3-char `"10h"`.
- **`normalize_action`** coerces a non-str action and folds on a dict with no `action`.
- **multipart** strips CR/LF from field values (no header injection). Shared
  `clamp_to_range` helper added (kills sizing-logic drift).
- Backend sync verified: TrueSkill response field names unchanged (poll output intact);
  `MAX_FILES` counts files only (SDK matches).
- **Golden contract fixtures** — real PvE + PvP submission responses captured from Beta
  (`tests/fixtures/`), with tests asserting the SDK parses the live contract and that
  the dry-run mock matches the real response shape (no silent drift).
- **Forward-compat PvP rating read** — `trueskillScore/Mu/Sigma` first, falling back to
  `scaleRating/rating/mu/sigma`, so a future server-side rename won't break `poll`.
- `comps` now labels `PVE`-named competitions correctly (was `?`).
- 18 tests total (+9 this release).
- Release prep (CodeX review): golden fixtures sanitized (no real backend ids);
  `clamp_to_range` respects `availableActions`; `_pvp_rating` is null-safe across a
  renamed field; `examples/poker/byo/` bring-your-own-bot worked example; docs narrowed to
  the `static-agent` path; `.gitignore` hardened (.DS_Store, caches).

## 0.2.1 — robustness, safety & UX hardening
- **Import-isolation bundle validation** — `pack`/`submit` extract the bundle and
  import `harness/strategy.py` in a `python -I` subprocess (only the bundle on the
  path, like the server) and run `act()` once. Catches the #1 silent failure — a
  strategy that imports a sibling module not in the bundle — **locally**, before you
  spend a metered submission. Timeout fails closed.
- **`--harness <dir>`** — bundle a multi-file bot (strategy.py + helper modules).
- **`./arena access`** — one-command claim + whitelist check (the 403 gate).
- **dry-run scores labelled** `(simulated, not your bot)` so a canned number can't be
  mistaken for a real score.
- **submit aborts before upload** when access is explicitly denied (avoids a 403).
- **Precise `pack` errors** — distinguishes syntax error / no entrypoint / missing
  module, each pointing at the real fix.
- **selfplay diagnostic** — one stderr warning when your `act()` raises or returns a
  non-dict (no more silent fold-and-bad-bb/100).
- **Multi-file local runs** — sibling imports resolve during selfplay/live (scoped
  sys.path: no persistent mutation / no cross-bot module collision).
- **CLI** — top-level `--help` lists subcommands; `--endpoint` shows its default.
- **Docs** — README first screen carries the daily-quota / test-first callout + a
  pointer to SUBMITTING.md; SUBMITTING §3 has the full annotated `table` schema
  (hole cards live under `seats[]`) + a sizing recipe.
- **Hygiene** — `.gitignore` excludes internal scaffolding; credentials only ever
  travel in the `x-arena-api-key` header (never URLs/logs).

## 0.2.0
- **Sandbox submission** — `submit` and `pack` commands. Build a bundle
  (`harness/strategy.py` [+ `assets/`]), validate it locally against the exact
  server rules, upload via multipart to `POST /submissions/`, poll to a terminal
  status, and print `bb/100` (and TrueSkill for PvP).
- **PvE and PvP** from the same `strategy.py` — the competition decides which.
  `--pvp` asserts the PvP rules (static-agent only, 3 submissions/UTC-day).
- **`--dry-run`** — exercise the whole submit→poll flow offline (no network, no
  API key), mirroring the real endpoint shapes.
- **`comps`** — list active competitions, labelled PvE/PvP.
- **`--replace`** — PvP: swap an in-flight active bot (else `409`).
- **`SUBMITTING.md`** — production limits (PvP 3/UTC-day, PvE none), score-refresh
  semantics, access whitelist, local-first guidance, bring-your-own-bot guide.
- **`examples/poker/llm_strategy.py`** — GPT/LLM-driven `act()` with a safe fallback.
- **`gto` opponent** — a GTO-approx bot (Monte-Carlo equity + pot odds, via
  `treys`) that beats every heuristic; the "hard" tier of the local ladder.
- **`--opponent self`** — play your bot vs your bot.
- **Fix:** hero's seat now rotates each hand in local play, so `bb/100` is
  position-fair (a symmetric bot nets ~0 instead of a button-bias skew).
- **`./arena`** branded CLI wrapper + `version` command.
- Packaging: `pyproject.toml` (`pip install arena-sdk`, `arena-sdk`
  console script). MIT license. Smoke tests under `tests/`.

## 0.1.0
- Local replica of the server submission mode: `table`/`act()` contract,
  reproducible pokerkit engine, `selfplay`/`eval` → `bb/100`, live REST runner.
