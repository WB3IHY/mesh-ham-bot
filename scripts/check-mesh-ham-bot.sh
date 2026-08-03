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
        exit 0
    fi
fi

# Check 3: Is the bot stuck mid-reconnect? onDisconnect schedules retry_interface() on the
# asyncio loop, but that scheduling has been observed to silently fail to run at all (no
# "Retrying interfaceN" log line ever follows) — the bot sits disconnected indefinitely
# without erroring, which Check 2 wouldn't catch for up to STALE_MINUTES. A normal, working
# retry cycle logs "InterfaceN Opened!" within ~15-20s of the disconnect, so if the most
# recent disconnect is newer than the most recent successful reopen and it's been over a
# minute, the reconnect is stuck.
LAST_DISCONNECT=$(journalctl -u mesh-ham-bot --no-pager --since "10 minutes ago" --output=short-unix 2>/dev/null | grep "Abrupt disconnection detected" | tail -1 | awk '{print $1}')
LAST_DISCONNECT=${LAST_DISCONNECT%.*}
LAST_REOPEN=$(journalctl -u mesh-ham-bot --no-pager --since "10 minutes ago" --output=short-unix 2>/dev/null | grep -E "Interface[0-9]+ Opened!" | tail -1 | awk '{print $1}')
LAST_REOPEN=${LAST_REOPEN%.*}

if [ -n "$LAST_DISCONNECT" ]; then
    if [ -z "$LAST_REOPEN" ] || [ "$LAST_DISCONNECT" -gt "$LAST_REOPEN" ]; then
        STUCK_AGE=$(( NOW - LAST_DISCONNECT ))
        if [ "$STUCK_AGE" -gt 60 ]; then
            echo "$TIMESTAMP | Stuck mid-reconnect (disconnected ${STUCK_AGE}s ago, never reopened), restarting mesh-ham-bot" >> "$LOGFILE"
            systemctl stop mesh-ham-bot
            sleep 3
            systemctl start mesh-ham-bot
            echo "$TIMESTAMP | mesh-ham-bot restarted" >> "$LOGFILE"
            exit 0
        fi
    fi
fi

# Heartbeat: every restart branch above exits before reaching here, so getting here means
# all checks passed. Logged once/hour rather than every 5-min run so the log stays readable
# while still proving the watchdog itself hasn't silently stopped firing.
if [ "$(date '+%M')" = "00" ]; then
    echo "$TIMESTAMP | Watchdog check OK" >> "$LOGFILE"
fi
