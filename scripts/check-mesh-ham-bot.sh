#!/bin/bash
# /usr/local/bin/check-mesh-ham-bot.sh
# Watchdog: restart mesh-ham-bot if port down OR bot appears frozen

LOGFILE="/var/log/mesh-ham-bot-watchdog.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
STALE_MINUTES=12  # bot saves every 5 min; 12 min means at least 2 missed saves

# Check 1: Is meshtasticd listening? Checked via the kernel socket table (ss), not a live
# TCP connect (nc -z) — meshtasticd's API only tolerates one client at a time and evicts
# whoever's already connected (i.e. mesh-ham-bot) the instant anything else connects, so a
# connecting probe here was itself bumping the bot's connection every 5 minutes.
if ! ss -H -ltn "sport = :4403" 2>/dev/null | grep -q LISTEN; then
    echo "$TIMESTAMP | Port 4403 not listening, restarting mesh-ham-bot" >> "$LOGFILE"
    systemctl stop mesh-ham-bot
    sleep 3
    systemctl start mesh-ham-bot
    echo "$TIMESTAMP | mesh-ham-bot restarted" >> "$LOGFILE"
    exit 0
fi

# Check 2: Is the bot actually alive and processing? Look for recent persistence saves.
# The bot writes to its log via journald; check if systemd has seen output recently.
LAST_LOG=$(journalctl -u mesh-ham-bot --no-pager -n 1 --output=short-unix 2>/dev/null | awk '{print $1}')
LAST_LOG=${LAST_LOG%.*}  # short-unix includes fractional seconds; bash arithmetic needs an integer
NOW=$(date +%s)

if [ -n "$LAST_LOG" ]; then
    AGE=$(( (NOW - LAST_LOG) / 60 ))
    if [ "$AGE" -gt "$STALE_MINUTES" ]; then
        echo "$TIMESTAMP | Bot stuck in retry loop (last output ${AGE}m ago), restarting mesh-ham-bot" >> "$LOGFILE"
        systemctl stop mesh-ham-bot
        sleep 3
        systemctl start mesh-ham-bot
        echo "$TIMESTAMP | mesh-ham-bot restarted" >> "$LOGFILE"
    fi
fi
