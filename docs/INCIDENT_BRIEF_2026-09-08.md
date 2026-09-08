# Incident Brief: Backend Freezes & Probe Memory Discipline (2026-09-08)

> Share this with anyone (or any agent session) working on OpenBoard Economy simulations.

## What happened

Twice today (14:17 and 17:20 CEST), the entire Agent Zero backend froze: all chats stopped responding, the UI spun forever, and user messages typed during the freeze were lost. The container itself never crashed (no OOM kills, no restarts) — the framework's main event loop was starved and hung.

## Root cause (verified by timeline)

Heavy simulation probes launched by this project ran **uncapped inside the same container** as the live framework:

1. Probe `elec966` (966-agent economy sim) died with a `MemoryError` during a giant `json.dumps` (transient memory doubling)
2. The chat agent immediately relaunched a bigger probe (`elec966b`, `scale_world(966)`) 14 seconds before the whole backend froze
3. Memory pressure from the probe starved the framework's event loop → **hard freeze for ~10 minutes** → only a restart recovered it

The kernel never fired an OOM kill (peaks stayed under the 20 GiB cgroup limit) — the failure mode was **allocation starvation**, which is why it looked like a mystery hang instead of a crash.

## What was fixed

| Fix | Status |
|---|---|
| Compression-stall bug (chats dying silently, upstream #1881) | ✅ Patched + fallback model live |
| Corrupt Time Travel git objects (8 empty files) | ✅ Removed, repo verified |
| Probe containment: `scripts/memrun.sh` | ✅ Built and tested |
| Project rule: probes MUST use memrun | ✅ Added to project instructions |
| Wedge forensics (upstream issue #1889) | ✅ Filed with measured evidence |

## ⚠️ New mandatory rule for ALL probes and heavy scripts

**Never launch a probe bare.** Always:

```bash
bash scripts/memrun.sh 14 /tmp/<probe_name>.log /opt/venv/bin/python /tmp/<probe>.py
```

- **14 GiB budget** — generous; most sims complete without touching it
- If a probe hits the cap: **read its log first** (data before death is usually valid), then **checkpoint & resume** — do not blindly relaunch bigger
- Never run a new probe while a previous one may still hold memory (`pgrep -f <probe>` first)
- Never `json.dumps` a huge structure in one call — stream chunks to file instead
- Clear ledgers/batches per tick (`applied.clear()`, `trim_retention`)

## Why this matters

An uncapped probe doesn't just risk its own death — it **freezes every chat, drops every websocket, and swallows user input** across the whole instance. The capped failure mode ("probe dies early, framework fine") is strictly better than the old one ("everything hangs, no logs, data lost").

## If a freeze happens again

Fingerprints are now captured automatically in `/a0/tmp/`: `turn_trace.jsonl` (which chat/turn was active), `task_snapshots.jsonl` (which coroutines hung), `loop_stalls.log` (loop freeze timeline), `exceptions_capture.jsonl` (raised exceptions). Any future incident self-documents — check these files before guessing.
