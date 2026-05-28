# modules/bbs/db.py
# BBS SQLite database layer for mesh-ham-bot
# SQLite backend adapted from TC2-BBS-mesh (Apache 2.0)
# Integrated into mesh-ham-bot by WB3IHY
#
# Original TC2-BBS-mesh: Copyright (C) TheCommsChannel
# Modifications: mesh-ham-bot project

import logging
import sqlite3
import threading
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

thread_local = threading.local()


def normalize_node_id(node_id):
    """Normalize any node ID form to !hex string (e.g. 1235296192 → '!49b7a3c0').
    Accepts: None, int, decimal string, hex string with or without 0x/! prefix.
    Returns a lowercase !hex string, or None if node_id is None.
    Non-parseable values (e.g. 'config') are returned as-is.
    """
    if node_id is None:
        return None
    if isinstance(node_id, int):
        return f'!{node_id:08x}'
    s = str(node_id).strip()
    if s.startswith('!'):
        return s.lower()
    if s.lower().startswith('0x'):
        try:
            return f'!{int(s, 16):08x}'
        except ValueError:
            pass
    # Bare hex string (e.g. "49b7a3c0") — contains hex chars but is not purely decimal
    if all(c in '0123456789abcdefABCDEF' for c in s) and not s.isdigit():
        return f'!{s.lower()}'
    try:
        return f'!{int(s):08x}'
    except ValueError:
        return s
_db_path = 'data/bbs.db'


def set_db_path(path):
    global _db_path
    _db_path = path


def get_db_connection():
    if not hasattr(thread_local, 'connection') or thread_local.connection is None:
        thread_local.connection = sqlite3.connect(_db_path, check_same_thread=False)
        thread_local.connection.row_factory = sqlite3.Row
    return thread_local.connection


def initialize_database(seed_admins=None):
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS bulletins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board TEXT NOT NULL,
                    sender_short_name TEXT NOT NULL,
                    sender_node_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    unique_id TEXT NOT NULL
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS mail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    sender_short_name TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    date TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    unique_id TEXT NOT NULL
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL UNIQUE,
                    added_by TEXT NOT NULL,
                    date TEXT NOT NULL
                )''')

    c.execute('''CREATE TABLE IF NOT EXISTS banned (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL UNIQUE,
                    banned_by TEXT NOT NULL,
                    date TEXT NOT NULL,
                    reason TEXT
                )''')

    conn.commit()

    if seed_admins:
        for raw_id in seed_admins:
            normalized = normalize_node_id(raw_id)
            if not normalized:
                continue
            try:
                c.execute("SELECT 1 FROM admins WHERE node_id = ?", (normalized,))
                if c.fetchone():
                    continue  # already present in canonical form
                # Remove any stale entry stored under the un-normalized original
                original_str = str(raw_id).strip()
                if original_str != normalized:
                    c.execute("DELETE FROM admins WHERE node_id = ?", (original_str,))
                c.execute(
                    "INSERT OR IGNORE INTO admins (node_id, added_by, date) VALUES (?, ?, ?)",
                    (normalized, 'config', datetime.now().strftime('%Y-%m-%d %H:%M'))
                )
            except Exception as e:
                logger.error(f"BBS: Error seeding admin {raw_id}: {e}")
        conn.commit()

    logger.info("BBS: Database initialized.")


# --- Admin management ---

def is_admin(node_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE node_id = ?", (normalize_node_id(node_id),))
    return c.fetchone() is not None


def add_admin(node_id, added_by):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO admins (node_id, added_by, date) VALUES (?, ?, ?)",
            (normalize_node_id(node_id), normalize_node_id(added_by), datetime.now().strftime('%Y-%m-%d %H:%M'))
        )
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        logger.error(f"BBS: Error adding admin {node_id}: {e}")
        return False


def remove_admin(node_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE node_id = ?", (normalize_node_id(node_id),))
    conn.commit()
    return c.rowcount > 0


def list_admins():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT node_id, added_by, date FROM admins ORDER BY date")
    return c.fetchall()


# --- Ban management ---

def is_banned(node_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned WHERE node_id = ?", (normalize_node_id(node_id),))
    return c.fetchone() is not None


def ban_node(node_id, banned_by, reason=None):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO banned (node_id, banned_by, date, reason) VALUES (?, ?, ?, ?)",
            (normalize_node_id(node_id), normalize_node_id(banned_by), datetime.now().strftime('%Y-%m-%d %H:%M'), reason)
        )
        conn.commit()
        return c.rowcount > 0
    except Exception as e:
        logger.error(f"BBS: Error banning node {node_id}: {e}")
        return False


def unban_node(node_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM banned WHERE node_id = ?", (normalize_node_id(node_id),))
    conn.commit()
    return c.rowcount > 0


def list_banned():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT node_id, banned_by, date, reason FROM banned ORDER BY date")
    return c.fetchall()


# --- Bulletins ---

VALID_BOARDS = ['General', 'Info', 'News', 'Urgent']


def normalize_board(board_name):
    for b in VALID_BOARDS:
        if b.lower() == board_name.strip().lower():
            return b
    return None


def add_bulletin(board, sender_short_name, sender_node_id, subject, content, unique_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    date = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not unique_id:
        unique_id = str(uuid.uuid4())
    c.execute(
        "INSERT INTO bulletins (board, sender_short_name, sender_node_id, date, subject, content, unique_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (board, sender_short_name, normalize_node_id(sender_node_id), date, subject, content, unique_id)
    )
    conn.commit()
    logger.info(f"BBS: Bulletin posted to {board} by {sender_short_name}: {subject}")
    return unique_id


def get_bulletins(board):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, subject, sender_short_name, date FROM bulletins WHERE board = ? COLLATE NOCASE ORDER BY id",
        (board,)
    )
    return c.fetchall()


def get_bulletin_content(bulletin_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT sender_short_name, sender_node_id, date, subject, content, unique_id "
        "FROM bulletins WHERE id = ?",
        (bulletin_id,)
    )
    return c.fetchone()


def delete_bulletin(bulletin_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM bulletins WHERE id = ?", (bulletin_id,))
    conn.commit()
    return c.rowcount > 0


def get_bulletin_owner(bulletin_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT sender_node_id FROM bulletins WHERE id = ?", (bulletin_id,))
    row = c.fetchone()
    return row['sender_node_id'] if row else None


# --- Mail ---

def add_mail(sender_id, sender_short_name, recipient_id, subject, content, unique_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    date = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not unique_id:
        unique_id = str(uuid.uuid4())
    c.execute(
        "INSERT INTO mail (sender, sender_short_name, recipient, date, subject, content, unique_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (normalize_node_id(sender_id), sender_short_name, normalize_node_id(recipient_id), date, subject, content, unique_id)
    )
    conn.commit()
    logger.info(f"BBS: Mail from {sender_short_name} to {recipient_id}: {subject}")
    return unique_id


def get_mail(recipient_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, sender_short_name, subject, date, unique_id FROM mail WHERE recipient = ? ORDER BY id",
        (normalize_node_id(recipient_id),)
    )
    return c.fetchall()


def get_mail_content(mail_id, recipient_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT sender, sender_short_name, date, subject, content, unique_id "
        "FROM mail WHERE id = ? AND recipient = ?",
        (mail_id, normalize_node_id(recipient_id))
    )
    return c.fetchone()


def delete_mail_by_unique_id(unique_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM mail WHERE unique_id = ?", (unique_id,))
    conn.commit()
    return c.rowcount > 0


def delete_mail_by_id(mail_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM mail WHERE id = ?", (mail_id,))
    conn.commit()
    return c.rowcount > 0


def get_mail_sender(mail_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT sender FROM mail WHERE id = ?", (mail_id,))
    row = c.fetchone()
    return row['sender'] if row else None


# --- Channels ---

def add_channel(name, url):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO channels (name, url) VALUES (?, ?)", (name, url))
    conn.commit()
    logger.info(f"BBS: Channel added: {name}")


def get_channels():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, url FROM channels ORDER BY id")
    return c.fetchall()


def delete_channel(channel_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    conn.commit()
    return c.rowcount > 0


# --- Stats ---

def get_bbs_stats():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as cnt FROM bulletins")
    bulletins = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM mail")
    mail = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM channels")
    channels = c.fetchone()['cnt']
    c.execute("SELECT COUNT(*) as cnt FROM admins")
    admins = c.fetchone()['cnt']
    return {
        'bulletins': bulletins,
        'mail': mail,
        'channels': channels,
        'admins': admins
    }
