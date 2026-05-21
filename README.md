# mesh-ham-bot

A Meshtastic mesh radio bot forked from meshing-around, with a SQLite-backed BBS adapted from TC2-BBS-mesh. Includes bulletins, mail, channels, admin commands, and ban management.

---

## Credits

- **[meshing-around](https://github.com/SpudGunMan/meshing-around)** — K7MHI Kelly Keeton (MIT)
- **[TC2-BBS-mesh](https://github.com/TheCommsChannel/TC2-BBS-mesh)** — TheCommsChannel (Apache 2.0)
- **WB3IHY** — chunk numbering and section separator patches

---

## What's Different from meshing-around

- `bbstools.py` replaced entirely by `modules/bbs/` — a proper Python package with a SQLite backend
- Bulletin boards, direct mail, channel directory, admin management, and ban management
- Both interaction modes: command-style (`bbspost`, `bbsread`, etc.) and stateful menu (`HELP`)
- Removed: games (except `joke.py`), LLM, SMTP, survey, UDP, GPIO, inventory, bbstools
- Kept: ham radio tools, WX, APRS, checklist, scheduler, DX, QRZ, ping/ACK

---

## Requirements

- Ubuntu 22.04+ or Debian 12+
- Python 3.10+
- A running `meshtasticd` instance (TCP on port 4403)
- The existing meshing-around Python dependencies (see `requirements.txt`)

---

## Installation

```bash
git clone https://github.com/WB3IHY/mesh-ham-bot.git
cd mesh-ham-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.template config.ini
# Edit config.ini for your node and callsign
```

---

## Running

### Manual (foreground, for testing)

```bash
./launch.sh mesh
```

### systemd service

```bash
sudo cp mesh-ham-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mesh-ham-bot
```

Example service file:

```ini
[Unit]
Description=Mesh Ham Bot
After=network.target meshtasticd.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/mesh-ham-bot
ExecStart=/root/mesh-ham-bot/venv/bin/python3 /root/mesh-ham-bot/mesh_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## BBS Commands

Users interact with the BBS by sending direct messages to the bot node.

### Command-style interface

| Command | Description |
|---|---|
| `bbshelp` | Show command reference |
| `bbsboards` | List available bulletin boards |
| `bbslist [board]` | List bulletins, optionally filtered by board |
| `bbspost $subject #message [^board]` | Post a bulletin |
| `bbsread <id>` | Read a bulletin by ID |
| `bbsdelete <id>` | Delete your own bulletin |
| `bbsdm @node #message` | Send a direct mail to a node |
| `bbscheckim` | Check your incoming mail |
| `bbsreadm <id>` | Read a mail message by ID |
| `bbsdelm <id>` | Delete a mail message |
| `bbschan` | List channel directory entries |
| `bbsaddchan $name #url` | Add a channel to the directory |
| `bbsinfo` | Show BBS statistics |

### Menu-style interface

Send `HELP` to enter the interactive menu. Navigate with the numbered options shown. Sessions time out after inactivity.

---

## Admin Commands

Admin commands are only available to nodes listed in the admins table. The first admin must be seeded directly in the SQLite database or via the bootstrap process described below.

| Command | Description |
|---|---|
| `adminadd <nodeid>` | Add a node to the admin list |
| `adminremove <nodeid>` | Remove a node from the admin list |
| `adminlist` | List all admins |
| `ban <nodeid> [reason]` | Ban a node from the BBS |
| `unban <nodeid>` | Remove a ban |
| `banlist` | List all banned nodes |
| `bbsdelete <id>` | Delete any bulletin by ID |
| `maildelete <id>` | Delete any mail message by ID |
| `chandel <id>` | Delete a channel directory entry |
| `bbsstats` | Show full database statistics |

### Seeding the first admin

```bash
sqlite3 /path/to/bbs.db \
  "INSERT INTO admins (node_id, added_by) VALUES ('!yournodeid', 'bootstrap');"
```

---

## Watchdog

A watchdog script is included at `scripts/check-mesh-ham-bot.sh`. It checks:

1. Whether `meshtasticd` is reachable on port 4403
2. Whether the bot has produced any log output recently (detects frozen/stuck states)

Install as a cron job:

```bash
sudo cp scripts/check-mesh-ham-bot.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/check-mesh-ham-bot.sh
# Add to root crontab:
# */5 * * * * /usr/local/bin/check-mesh-ham-bot.sh
```

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for full terms and third-party attributions.
