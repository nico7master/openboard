# Remote Sim Workflow — User's GPU PC (LAN)

**Status:** ACTIVE since 2026-09-17. Security model approved by the founder (sandboxed SSH, Option B).

## Host facts

| Item | Value |
|---|---|
| Address | `sims@192.168.178.46` (LAN only; host key already accepted) |
| Machine | Pop!_OS, i9-9900K (16 threads), 31 GB RAM, 227 GB free |
| Access | Dedicated unprivileged user `sims`, key-auth only, **no sudo** (verified blocked) |
| Fence (verified 2026-09-17) | founder's home dir unreadable, /etc/shadow unreadable; sims can only touch its own home |
| Remote layout | `~/openboard` (project copy) · `~/openboard-venv` (Python 3.12 + flask + pytest) · `~/gate_logs/` |
| Boot caveat | **PC is often but NOT always on.** Always probe before relying on it. |

## Golden rules

1. **Probe first, always** (short timeout, BatchMode — never hang, never prompt):
   ```bash
   ssh -o BatchMode=yes -o ConnectTimeout=6 sims@192.168.178.46 'echo ok'
   ```
   Unreachable → **fall back to local memrun** per project memory discipline. Never block on the PC.
2. **Re-sync after engine changes.** Remote copy is only as fresh as the last push. Sync (from project root):
   ```bash
   tar czf - --exclude=.git --exclude=__pycache__ --exclude=.pytest_cache --exclude=venv --exclude=sweeps . \
     | ssh -o BatchMode=yes sims@192.168.178.46 'tar xzf - -C ~/openboard'
   ```
3. **Run with the venv interpreter**: `~/openboard-venv/bin/python` (system python3 lacks flask).
4. **Parallelism**: ~5–8 worlds at once is safe (16 threads, ~580 MB RSS per world, RAM headroom verified). One host process batch at a time; check `pgrep -f stage6_scale_gate` before launching more.
5. **Verify before trusting**: remote results must match the canonical profiles (money conservation `inv_bad=0`, gate PASS). Seed-42/7/123 2,000-tick gates were byte-identical to container runs on 2026-09-17.

## Standard patterns

**Parallel study batch (the main win — 3-seed gate: 8.3 min vs 32 min local):**
```bash
ssh -o BatchMode=yes sims@192.168.178.46 'cd ~/openboard && mkdir -p ~/gate_logs && \
  for s in 42 7 123; do nohup ~/openboard-venv/bin/python scripts/stage6_scale_gate.py 2000 $s \
    > ~/gate_logs/gate_s$s.log 2>&1 & done'
```

**Poll (output mode or short polls):**
```bash
ssh -o BatchMode=yes sims@192.168.178.46 'pgrep -f stage6_scale_gate >/dev/null && echo RUNNING || echo DONE; \
  tail -3 ~/gate_logs/gate_s*.log'
```

**Retrieve results** (into `sweeps/<study>/` locally):
```bash
scp -o BatchMode=yes 'sims@192.168.178.46:~/gate_logs/*.json' sweeps/<study>/
```

## What goes where

- Heavy parallel batches (gates, seed sweeps, atlas grids) → **PC**
- Quick probes / anything needing live repo state between syncs → local memrun
- GPU: unused by this engine (CPU branchy logic). Only relevant if ML/LLM bots are ever added.

## Teardown (founder's kill switch)

Removing the `sims` user or its `~/.ssh/authorized_keys` on the PC ends access instantly.
