# mesh-ham-bot Project Guidelines

See ~/CLAUDE.md for full infrastructure context.

## What This Is
A Meshtastic mesh radio bot forked from meshing-around (MIT) with the BBS
subsystem replaced by a SQLite-backed system adapted from TC2-BBS-mesh (Apache 2.0).
Runs on the Ionos VPS as systemd service `mesh-ham-bot`.

## Deployment
- This project runs on an Ionos Ubuntu VPS as a systemd service called `mesh-ham-bot`
- Deploy by SSHing to the VPS, then: `cd /root/mesh-ham-bot && git pull && systemctl restart mesh-ham-bot`

## Git Workflow
- After every change, always commit and push to GitHub immediately
- Never leave uncommitted changes on the VPS — the correct workflow is: edit locally → commit → push → pull on VPS
- Always save diffs for review before committing when making logic changes
- Commit messages must follow conventional commits format: `feat:`, `fix:`, `chore:`, `docs:`

## Database
- The BBS database is at `data/bbs.db`
- Never modify the schema without a migration plan
- Node IDs are always stored in `!hex` format (e.g. `!49b7a3c0`) in the database

## Key Paths (VPS)
- Project root: /root/mesh-ham-bot/
- BBS database: /root/mesh-ham-bot/data/bbs.db
- Config: /root/mesh-ham-bot/config.ini (gitignored)
- Watchdog: /usr/local/bin/check-mesh-ham-bot.sh (cron every 5 min)
- Node cache: /root/mesh-nodes-cache.txt (cron every 10 min)

## Architecture
- mesh_bot.py — main entry point, command dispatch table
- modules/system.py — trap_list, messageTrap(), settings, ban_hammer()
- modules/bbs/ — BBS package (commands.py, db.py, menu.py, admin.py, state.py)
- modules/settings.py — config.ini parsing

## CRITICAL: Adding a New BBS Command
When adding any new BBS command, it MUST be registered in ALL FOUR places:
1. `COMMAND_TRAP` list in modules/bbs/commands.py
2. Dispatch table (lambda) in mesh_bot.py
3. `trap_list_bbs` tuple in modules/system.py
4. `bbshelp` response string in modules/bbs/commands.py
Missing any one of these causes silent failures or "unknown command" errors.
This has burned us before — do not skip any of these four steps.

## Node ID Format
- ALL node IDs stored in database use !hex format: e.g. !49b7a3c0
- normalize_node_id() in db.py converts any format (raw int, decimal string,
  bare hex, !hex) to canonical !hex
- Call normalize_node_id() on any node ID before DB storage or query
- Admins table stores bare hex WITHOUT ! prefix: e.g. 49b7a3c0
- NEVER assume format — always normalize

## BBS Database Schema
Tables: bulletins, mail, admins, banned, channels
- bulletins: id, board, sender_short_name, sender_node_id, date, subject, content, unique_id
- mail: id, sender, sender_short_name, recipient, date, subject, content, unique_id
- admins: id, node_id, added_by, date
- banned: id, node_id, banned_by, date, reason
- channels: id, name, url

## Known Gotchas
- messageTrap() in system.py is case-insensitive; dispatch table uses message_lower
  — no extra case handling needed
- get_interface(deviceID) returns a real interface object; menu.py passes the
  integer rxNode — both are handled by _fuzzy_find_nodes()
- iOS MQTT proxy clients appear as duplicate connections — benign, not a bug
- meshtasticd must be running on port 4403 before starting mesh-ham-bot
- Routing errors (ROUTING_APP Reason:NONE) in logs are normal ACK behavior

## What Was Removed from meshing-around
Games (except joke.py), LLM, SMTP, survey, UDP, GPIO, inventory, bbstools.
The old file-based ban list (bbs_ban_list.txt) is replaced by the banned table in SQLite.

## Systemd Service
Name: mesh-ham-bot
Restart policy: always, RestartSec=10
After: network.target meshtasticd.service
