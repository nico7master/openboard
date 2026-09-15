#!/bin/bash
# Society in Motion study — sequential 51-run chain (one world at a time).
# Every run goes through scripts/memrun.sh (project safety rule: 14 GiB cap,
# 2 cores, nice 19). Resumable: completed cells are skipped by the harness.
set -u
cd "$(dirname "$0")/.."
LOG=/tmp/society_chain.log
PY=/opt/venv/bin/python

run() { # arm seed
  local arm=$1 seed=$2
  local out=sweeps/society/${arm}_s${seed}.json
  if [[ -f "$out" ]]; then
    echo "[chain] SKIP $arm s$seed (exists)" >> "$LOG"
    return 0
  fi
  echo "[chain] START $arm s$seed $(date +%H:%M:%S)" >> "$LOG"
  bash scripts/memrun.sh 14 "/tmp/society_${arm}_s${seed}.log" \
       "$PY" scripts/society_probe.py "$arm" "$seed"
  echo "[chain] DONE  $arm s$seed rc=$? $(date +%H:%M:%S)" >> "$LOG"
}

SEEDS="7 42 123"

# ---- Part A pair1: spoilage-long x disasters
for s in $SEEDS; do run base $s; done
for s in $SEEDS; do run spoil_long $s; done
for s in $SEEDS; do run disaster $s; done
for s in $SEEDS; do run spoil_disaster $s; done
# ---- Part A pair2: skills x research(fixed+floor)
for s in $SEEDS; do run base2 $s; done
for s in $SEEDS; do run skills_on $s; done
for s in $SEEDS; do run research_fixed $s; done
for s in $SEEDS; do run skills_research $s; done
# ---- Part A pair3: tax800 x land dump
for s in $SEEDS; do run base3 $s; done
for s in $SEEDS; do run tax800 $s; done
for s in $SEEDS; do run land_dump $s; done
for s in $SEEDS; do run tax_dump $s; done
# ---- Part B: research timing (p4 all_on + floor 1B)
for s in $SEEDS; do run research_early $s; done
for s in $SEEDS; do run research_late $s; done
for s in $SEEDS; do run research_never $s; done
# ---- Part B: crisis timing
for s in $SEEDS; do run crisis_onset $s; done
for s in $SEEDS; do run crisis_late100 $s; done

echo "[chain] ALL DONE $(date +%H:%M:%S)" >> "$LOG"
