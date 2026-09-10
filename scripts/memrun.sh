#!/bin/bash
# memrun — run heavy sims with bounded memory AND bounded CPU WITHOUT starving A0.
#
# Usage: memrun <GiB> <logfile> <cmd...>
#   memrun 14 /tmp/elec966.log python /tmp/probe.py
#
# Behavior:
# - MEMORY: caps the process at <GiB> GiB of virtual memory (RLIMIT_AS); if the
#   probe exceeds it, the PROBE gets MemoryError (contained, logged) — the
#   framework's event loop never starves. Exit 134/1 with MemoryError in log =>
#   probe hit the cap; resume from checkpoint instead of restarting from zero.
# - CPU (2026-09-10, user request): every run is pinned to 2 cores at lowest
#   priority (nice 19), so the live framework keeps ~2 full cores of the
#   4-core container. Heavy = slower, never CPU-starves the WebUI/chats.
#   Full pytest suites MUST also go through memrun for the same reason.
# - Overrides: MEMRUN_CPUS="0,1" MEMRUN_NICE=19

GIB="${1:?usage: memrun <GiB> <logfile> <cmd...>}"
LOG="${2:?usage: memrun <GiB> <logfile> <cmd...>}"
shift 2

KB=$((GIB * 1048576))
CPUS="${MEMRUN_CPUS:-0,1}"
NICE="${MEMRUN_NICE:-19}"

echo "[memrun] cap=${GIB}GiB cpus=${CPUS} nice=${NICE} log=$LOG cmd=$*"
(
  ulimit -v "$KB"
  exec nice -n "$NICE" taskset -c "$CPUS" "$@"
) >> "$LOG" 2>&1
rc=$?
if grep -q MemoryError "$LOG" 2>/dev/null; then
  echo "[memrun] PROBE HIT MEMORY CAP (rc=$rc). Data before death is valid."
  echo "[memrun] Resume from checkpoint or split the run — do NOT just relaunch bigger."
else
  echo "[memrun] probe finished rc=$rc"
fi
exit $rc
