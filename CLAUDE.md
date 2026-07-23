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
- Node IDs are always stored in `!hex` format (e.g. `!a1b2c3d4`) in the database

## Key Paths (VPS)
- Project root: /root/mesh-ham-bot/
- BBS database: /root/mesh-ham-bot/data/bbs.db
- Node memory database: /root/mesh-ham-bot/data/nodes.db
- Config: /root/mesh-ham-bot/config.ini (gitignored)
- Watchdog: /usr/local/bin/check-mesh-ham-bot.sh (cron every 5 min)
- Node cache: /root/mesh-nodes-cache.txt — written by the bot itself every 10
  min via its own open connection (`nodeCacheLoop()` in modules/system.py,
  `[nodeCache]` in config.ini), not a cron job. A separate cron running
  `meshtastic --nodes` used to write this file, but meshtasticd's API only
  tolerates one TCP client and evicted the bot's own connection every time
  that cron fired — removed for that reason.

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
- ALL node IDs stored in database use !hex format: e.g. !a1b2c3d4
- normalize_node_id() in db.py converts any format (raw int, decimal string,
  bare hex, !hex) to canonical !hex
- Call normalize_node_id() on any node ID before DB storage or query
- Admins table stores bare hex WITHOUT ! prefix: e.g. a1b2c3d4
- NEVER assume format — always normalize

## BBS Database Schema
Tables: bulletins, mail, admins, banned, channels
- bulletins: id, board, sender_short_name, sender_node_id, date, subject, content, unique_id
- mail: id, sender, sender_short_name, recipient, date, subject, content, unique_id
- admins: id, node_id, added_by, date
- banned: id, node_id, banned_by, date, reason
- channels: id, name, url

## Node Memory Database (nodes.db)
`modules/nodes_db.py` — persistent per-node enrichment that meshtasticd's own
NodeDB doesn't track: callsign, active/seasonal location, public-key history,
greeted status. Pre-seeded from `interface1.nodes` on boot; `long_name`/
`short_name` kept fresh during ongoing operation via `sync_node_metadata()` in
modules/system.py (hooked into `consumeMetadata()`).

Tables: nodes, pubkey_history
- nodes: node_id (!hex PK), long_name, short_name, public_key, pubkey_flagged,
  callsign, callsign_source ('override'|'auto_extracted'|NULL),
  active_location_name, location_fallback_disclosed, greeted, first_seen,
  last_seen, notes
- pubkey_history: id, node_id, public_key, changed_date

Location resolution for "where is this node" commands (`wx`, `whereami`,
`grid`, etc.) goes through `resolve_location_with_disclosure()` in
modules/locationdata.py: fresh GPS → active saved location (`map active
<name>`) → callsign-derived QTH (explicit `setnodecallsign` override, or
auto-extracted from long_name) → `NO_GPS_OR_CALLSIGN` message. The fallback
disclosure line is shown once per node, then suppressed.

### Node Memory / Admin Commands
- `setnodecallsign <callsign>` — self-service callsign override, used as a
  location fallback when a node has no GPS fix (validated against FCC data,
  same lookup as `wxcall`)
- `map active <name>` — self-service: use a saved location as the fallback
  when this node has no GPS fix (seasonal/temporary QTH)
- `adminhelp` — admin command reference with argument syntax; non-admins get
  "Not authorized."
- `ackkey <nodeid>` — admin: clear a flagged public-key change after review
  (does not restore trust/admin status — that's a separate human decision)
- `admincallsign <nodeid> <callsign>` — admin: set/override another node's
  callsign on their behalf
- `adminlocation <nodeid> <lat>,<lon> [description]` — admin: set and
  activate a location for another node in one step (covers a node that can't
  self-service, e.g. DM broken from a pubkey mismatch)

## Known Gotchas
- messageTrap() in system.py is case-insensitive; dispatch table uses message_lower
  — no extra case handling needed
- get_interface(deviceID) returns a real interface object; menu.py passes the
  integer rxNode — both are handled by _fuzzy_find_nodes()
- iOS MQTT proxy clients appear as duplicate connections — benign, not a bug
- meshtasticd must be running on port 4403 before starting mesh-ham-bot
- Routing errors (ROUTING_APP Reason:NONE) in logs are normal ACK behavior

## What Was Removed from meshing-around
Games (except joke.py), LLM, SMTP, survey, UDP, GPIO, inventory, checklist/check-in, bbstools,
radio.py bridge (hamlib rig monitoring, WSJT-X/JS8Call digital-mode monitoring, VOX detection, TTS).
The old file-based ban list (bbs_ban_list.txt) is replaced by the banned table in SQLite.
The DX cluster spotter (modules/dxspot.py) is unrelated and was kept — its config moved from
the old `[radioMon] dxspotter_enabled` to its own `[dxspotter] enabled` section.

## Naming Note
The old `qrz` module (says hello to newly-seen nodes) was renamed to `greeter` —
it was never a QRZ.com integration, just a Q-code name ("who is calling me?") that
was easy to mistake for one. Config section is `[greeter]`. `modules/greeter.py`
itself was later retired; greeted status now lives in `nodes.db`'s `greeted`
column (see Node Memory Database above) — `data/greeter.db` is no longer used.

## Systemd Service
Name: mesh-ham-bot
Restart policy: always, RestartSec=10
After: network.target meshtasticd.service
