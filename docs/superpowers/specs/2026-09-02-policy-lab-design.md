# Policy Lab — Design Spec (2026-09-02)

## Purpose
The game loop of OpenBoard is **change the rules → watch what happens**. The Policy Lab makes that loop a first-class product: a player (the government) picks plain-language policy options, the engine forks the live world into two deterministic shadow runs (baseline vs policy), and the dashboard shows an honest before/after comparison.

## Core principle: honest counterfactuals via determinism
The engine is deterministic and replay-identical. Forking the same world snapshot twice — once with current rules, once with the proposed rule change — and driving both with the same bot cast means **every difference in outcome is caused by the policy change**. No randomness, no hand-waving.

## Components

### 1. `src/openboard/policy.py` — knob registry + fork runner
- `KNOBS`: registry mapping plain-language policy questions to rule params. Each knob: `id`, `question` (plain sentence), `options` (list of {label, param_patch, explanation}), `param` (underlying rule key), `default_label`.
  - v1 knobs (all map to existing OPTIONAL_PARAMS): wealth tax strength (`wealth_tax.rate_bp`), surplus dividend share (`surplus_spending.dividend_share_bp`), science funding share (`surplus_spending` research slice), work-week length (`max_work_hours_cumulative`), labor pool cap (`labor_pool_cap`), credit access (`credit` on/off + caps), essential generosity (`needs` quotas ×1/×1.5), founding equipment grant (`capital_backstop.founding_equipment`).
- `fork_world(run) -> (baseline_run, policy_run)`: deep-copies the live state twice; applies the knob's param change to the policy fork's active ruleset (new ruleset_version — constitutional guard applies as in live governance); returns two headless Run instances.
- `run_experiment(run, knob_id, option_id, ticks=200)`: forks, drives both worlds with the bot cast (no human actions — apples-to-apples), collects per-tick metrics, returns a comparison dict.
- `compare(...)`: needs met %, worst unmet streak, Gini + top-10 share, avg prices vs fair cost, essential-chain treasuries, dividend flow, flag counts, population. Output: per-metric {baseline, policy, verdict: better/worse/same, plain_sentence}.

### 2. Server API (dashboard/server.py)
- `GET /api/policy/knobs` — knob registry (plain language) + current live setting per knob.
- `POST /api/policy/experiment` — body {knob_id, option_id, ticks?}. Runs the fork experiment synchronously for short ticks (200 ≈ seconds in-process; guard max 500). Returns the comparison JSON.
- `POST /api/policy/adopt` — applies the chosen option to the LIVE world's active ruleset (ledger-recorded rule change, same path as democratic rule changes; constitutional rules still require the 2/3 guard — the Lab proposes, democracy adopts).
- Experiments run on a snapshot: the live world keeps ticking; results are stamped with the fork tick.

### 3. Dashboard tab: 🧪 Policy Lab
- Knob cards: plain question + option buttons (None → Light → Firm → Heavy style), current setting badge.
- "Run 200-tick experiment" button → spinner → before/after results.
- Results view: per-metric rows with two bars (baseline vs policy) and plain verdict sentences ("Inequality fell 12% under the heavier wealth tax, but meat shortages appeared in 2 windows"). No raw number walls — numbers inside bars/tooltips per the dashboard story-first rule.
- Adopt button on each verdict → records the change in the live ledger.

### 4. Anomaly digest integration
The Lab's results view includes the oversight digest: 3–5 plain sentences of what the recalibrated flags saw during the experiment window (reuse story.py signals; HOARD multiplier 8 and market-power producer-count scaling are already live).

## Design decisions
- **D-PL.1 Fork-based comparison** (not single-run before/after): determinism makes it honest and cheap.
- **D-PL.2 Bots-only drives in experiments**: human seat actions would contaminate the counterfactual; the Lab simulates 'if rules changed, society as-is reacts'.
- **D-PL.3 Adopt = ledger event**: the Lab never edits params silently; adoption goes through the same recorded rule-change path as votes (replay-safe, constitutional guard respected).
- **D-PL.4 Experiment ticks capped at 500** and run synchronously: bounded memory under the 10 GB cgroup; long studies remain Stage-6-style batch scripts.
- **D-PL.5 Knobs are a registry, not hardcoded UI**: adding a policy = one dict entry.

## Testing (tests/test_policy_lab.py)
- Knob registry: every knob's param mapping exists in OPTIONAL_PARAMS/active params; every option produces a valid ruleset (schema-validated).
- Fork determinism: baseline fork replayed 50 ticks == live snapshot advanced 50 ticks (byte-identical state hash).
- Experiment: a known-effective change (wealth tax up) moves Gini direction as the sweep data predicts; a no-op change (same option as current) yields identical baseline/policy states.
- API: knobs endpoint shape; experiment endpoint returns comparison with plain sentences; adopt endpoint writes a ledger rule-change event and respects the constitutional guard.

## Non-goals
No multiplayer voting flows, no new economic rules, no geography — the Lab rides existing rule params only.
