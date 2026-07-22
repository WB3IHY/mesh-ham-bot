# modules/nodes_db.py
# Persistent per-node enrichment memory for mesh-ham-bot: callsign overrides,
# active/seasonal location, public key history, and greeted status — everything
# meshtasticd's own NodeDB doesn't track. See CLAUDE.md / design discussion for
# why this exists separately from locations.db and the (retired) greeter.db.

import logging
import sqlite3
import threading
from datetime import datetime

from modules.bbs.db import normalize_node_id

logger = logging.getLogger(__name__)

thread_local = threading.local()

_db_path = 'data/nodes.db'


def set_db_path(path):
    global _db_path
    _db_path = path


def get_db_connection():
    if not hasattr(thread_local, 'connection') or thread_local.connection is None:
        thread_local.connection = sqlite3.connect(_db_path, check_same_thread=False)
        thread_local.connection.row_factory = sqlite3.Row
    return thread_local.connection


def initialize_nodes_database():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
                    node_id              TEXT PRIMARY KEY,
                    long_name            TEXT,
                    short_name           TEXT,
                    public_key           TEXT,
                    pubkey_flagged       INTEGER DEFAULT 0,
                    callsign             TEXT,
                    callsign_source      TEXT,
                    active_location_name TEXT,
                    location_fallback_disclosed INTEGER DEFAULT 0,
                    greeted              INTEGER DEFAULT 0,
                    first_seen           TEXT,
                    last_seen            TEXT,
                    notes                TEXT
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pubkey_history (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id      TEXT NOT NULL,
                    public_key   TEXT NOT NULL,
                    changed_date TEXT NOT NULL
                )''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_pubkey_history_node ON pubkey_history(node_id)''')

    conn.commit()
    logger.info("NodesDB: Database initialized.")


def get_node(node_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM nodes WHERE node_id = ?", (normalize_node_id(node_id),))
    return c.fetchone()


def _ensure_node_row(normalized_id):
    """
    Make sure a row exists for this (already-normalized) node_id before a setter
    UPDATEs it — every setter below only UPDATEs, so a node with no row yet
    (e.g. one that joined after the last boot pre-seed) would otherwise have the
    update silently do nothing.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO nodes (node_id, first_seen, last_seen) VALUES (?, ?, ?)",
        (normalized_id, now, now)
    )
    conn.commit()


def upsert_node_seen(node_id, long_name=None, short_name=None, public_key=None, greeted=None):
    """
    Record that we've seen this node, updating cached name/key fields and last_seen.
    Inserts a new row (greeted defaults to 0) if the node isn't already known.
    greeted is only written when explicitly passed (True/False) — pass greeted=True
    for bulk pre-seeding of already-known nodes; leave it None for ordinary traffic
    so the existing greeter flow still owns when a genuinely new node gets marked greeted.
    """
    normalized = normalize_node_id(node_id)
    if not normalized:
        return
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT node_id, greeted FROM nodes WHERE node_id = ?", (normalized,))
        existing = c.fetchone()
        if existing:
            greeted_value = int(bool(greeted)) if greeted is not None else existing['greeted']
            c.execute(
                '''UPDATE nodes SET long_name = COALESCE(?, long_name),
                                     short_name = COALESCE(?, short_name),
                                     public_key = COALESCE(?, public_key),
                                     greeted = ?,
                                     last_seen = ?
                   WHERE node_id = ?''',
                (long_name, short_name, public_key, greeted_value, now, normalized)
            )
        else:
            c.execute(
                '''INSERT INTO nodes (node_id, long_name, short_name, public_key,
                                       greeted, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (normalized, long_name, short_name, public_key,
                 int(bool(greeted)), now, now)
            )
        conn.commit()
    except Exception as e:
        logger.error(f"NodesDB: Error upserting node {node_id}: {e}")


def mark_greeted(node_id):
    normalized = normalize_node_id(node_id)
    _ensure_node_row(normalized)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE nodes SET greeted = 1 WHERE node_id = ?", (normalized,))
    conn.commit()


def set_callsign(node_id, callsign, source):
    normalized = normalize_node_id(node_id)
    _ensure_node_row(normalized)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE nodes SET callsign = ?, callsign_source = ? WHERE node_id = ?",
              (callsign, source, normalized))
    conn.commit()


def set_active_location(node_id, location_name):
    normalized = normalize_node_id(node_id)
    _ensure_node_row(normalized)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE nodes SET active_location_name = ? WHERE node_id = ?",
              (location_name, normalized))
    conn.commit()


def mark_location_fallback_disclosed(node_id):
    normalized = normalize_node_id(node_id)
    _ensure_node_row(normalized)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE nodes SET location_fallback_disclosed = 1 WHERE node_id = ?", (normalized,))
    conn.commit()


def record_pubkey_change(node_id, new_public_key):
    normalized = normalize_node_id(node_id)
    _ensure_node_row(normalized)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO pubkey_history (node_id, public_key, changed_date) VALUES (?, ?, ?)",
            (normalized, new_public_key, now)
        )
        c.execute(
            "UPDATE nodes SET public_key = ?, pubkey_flagged = 1 WHERE node_id = ?",
            (new_public_key, normalized)
        )
        conn.commit()
    except Exception as e:
        logger.error(f"NodesDB: Error recording pubkey change for {node_id}: {e}")


def clear_pubkey_flag(node_id):
    normalized = normalize_node_id(node_id)
    _ensure_node_row(normalized)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE nodes SET pubkey_flagged = 0 WHERE node_id = ?", (normalized,))
    conn.commit()
