#!/bin/bash
# OpenBoard keepalive: server + tunnel self-healing watchdog.
# - dashboard server on :8421 restarted if dead
# - exactly one serveo tunnel; fresh URL captured from banner on each reconnect
# - current public URL always in /tmp/openboard_url.txt
URLFILE=/tmp/openboard_url.txt
LOG=/tmp/openboard_keepalive.log
DASH=/a0/usr/projects/openboard-economy/dashboard

server_up() { curl -s -o /dev/null --max-time 3 http://localhost:8421/; }

while true; do
  # 1) server
  if ! server_up; then
    echo "[$(date '+%F %T')] server down -> starting" >> "$LOG"
    cd "$DASH" || exit 1
    setsid nohup /opt/venv/bin/python server.py >> /tmp/openboard_server.log 2>&1 < /dev/null &
    sleep 6
  fi
  # 2) tunnel (exactly one) — process alive AND public URL actually working
  U=$(cat "$URLFILE" 2>/dev/null)
  TUN_OK=0
  if [ -n "$U" ]; then
    C=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$U" 2>/dev/null)
    [ "$C" = "200" ] && TUN_OK=1
  fi
  if [ "$TUN_OK" = "0" ]; then
    # dead process OR zombie tunnel (process up but 502) -> full reconnect
    pkill -f 'ssh.*serveo.net' 2>/dev/null
    echo "[$(date '+%F %T')] tunnel unhealthy (code=$C) -> reconnecting" >> "$LOG"
    rm -f /tmp/serveo_banner.log
    setsid nohup ssh -T -R 80:localhost:8421 \
      -o UserKnownHostsFile=/root/.flaredantic/ssh/known_hosts \
      -o StrictHostKeyChecking=accept-new \
      -o ServerAliveInterval=60 -o ExitOnForwardFailure=yes \
      serveo.net > /tmp/serveo_banner.log 2>&1 < /dev/null &
    for i in $(seq 1 20); do
      sleep 2
      U=$(grep -oE 'https://[a-z0-9]+-194-106-238-221\.serveousercontent\.com' /tmp/serveo_banner.log 2>/dev/null | tail -1)
      if [ -n "$U" ]; then echo "$U" > "$URLFILE"; echo "[$(date '+%F %T')] URL: $U" >> "$LOG"; break; fi
    done
  fi
  sleep 20
done
