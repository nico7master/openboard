#!/bin/bash
# memrun — run heavy sims with a bounded memory budget WITHOUT starving A0.
#
# Usage: memrun <GiB> <logfile> <cmd...>
#   memrun 14 /tmp/elec966.log python /tmp/probe.py
#
# Behavior:
# - caps the process at <GiB> GiB of virtual memory (RLIMIT_AS)
# - if the probe exceeds it, the PROBE gets MemoryError (contained, logged)
#   — the framework's event loop never starves
# - exit code 134/1 with MemoryError in log => probe hit the cap;
#   resume from checkpoint instead of restarting from zero
#
# Physics note: memory must come from somewhere. This makes the failure
# mode "probe dies early, framework fine" instead of "everything freezes".

GIB="${1:?usage: memrun <GiB> <logfile> <cmd...>}"
LOG="${2:?usage: memrun <GiB> <logfile> <cmd...>}"
shift 2

KB=$((GIB * 1048576))

echo "[memrun] cap=${GIB}GiB log=$LOG cmd=$*"
(
  ulimit -v "$KB"
  exec "$@"
) >> "$LOG" 2>&1
rc=$?
if grep -q MemoryError "$LOG" 2>/dev/null; then
  echo "[memrun] PROBE HIT MEMORY CAP (rc=$rc). Data before death is valid."
  echo "[memrun] Resume from checkpoint or split the run — do NOT just relaunch bigger."
else
  echo "[memrun] probe finished rc=$rc"
fi
exit $rc
