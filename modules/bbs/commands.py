# modules/bbs/commands.py
# Command-style BBS interface for mesh-ham-bot
# Syntax: bbspost $subject #message, bbsread #, bbslist, etc.
# Adapted from meshing-around bbstools.py (MIT) and TC2-BBS-mesh (Apache 2.0)
# mesh-ham-bot project

import logging
from modules.bbs.db import (
    add_bulletin, get_bulletins, get_bulletin_content,
    delete_bulletin, get_bulletin_owner,
    add_mail, get_mail, get_mail_content, delete_mail_by_id,
    add_channel, get_channels,
    is_admin, is_banned, normalize_board, normalize_node_id, VALID_BOARDS,
    get_bbs_stats
)

logger = logging.getLogger(__name__)

COMMAND_TRAP = (
    'bbsmenu', 'bbshelp', 'bbslist', 'bbspost', 'bbsread', 'bbsdelete',
    'bbsinfo', 'bbsboards', 'bbsdm', 'bbscheckim', 'bbsreadm',
    'bbsdelm', 'bbschan', 'bbsaddchan', 'bbsfind',
    'sm,,', 'cm', 'pb,,', 'cb,,',
)


def handle_bbs_help(node_id):
    return (
        "BBS Commands:\n"
        "bbsmenu - Interactive Menu Mode\n"
        "Direct Commands:\n"
        "bbslist [board]\n"
        "bbsboards\n"
        "bbspost $subj #msg [^board]\n"
        "bbsread <id>\n"
        "bbsdelete <id>\n"
        "bbsdm @node #msg\n"
        "bbsfind <name or id>\n"
        "bbscheckim\n"
        "bbsreadm <id>\n"
        "bbsdelm <id>\n"
        "bbschan\n"
        "bbsaddchan $name #url\n"
        "bbsinfo"
    )


def handle_bbs_boards():
    return "Bulletin Boards:\n" + "\n".join(f"  {b}" for b in VALID_BOARDS)


def handle_bbs_info():
    stats = get_bbs_stats()
    return (
        f"📡 BBS Info:\n"
        f"Bulletins: {stats['bulletins']}\n"
        f"Mail msgs: {stats['mail']}\n"
        f"Channels: {stats['channels']}"
    )


def handle_bbs_list(message, node_id):
    parts = message.strip().split(None, 1)
    board = None
    if len(parts) > 1:
        board = normalize_board(parts[1])
        if not board:
            return f"Unknown board. Try: {', '.join(VALID_BOARDS)}"

    if board:
        bulletins = get_bulletins(board)
        if not bulletins:
            return f"No bulletins on {board}."
        lines = [f"[{board}]"]
        for b in bulletins:
            lines.append(f"#{b['id']} {b['subject']} -{b['sender_short_name']}")
        return "\n".join(lines)
    else:
        lines = []
        for b in VALID_BOARDS:
            bulletins = get_bulletins(b)
            if bulletins:
                lines.append(f"[{b}] {len(bulletins)} msgs")
        if not lines:
            return "No bulletins posted yet."
        return "Bulletin Boards:\n" + "\n".join(lines) + "\nUse: bbslist <board>"


def handle_bbs_post(message, node_id, short_name):
    if is_banned(node_id):
        return "Message posted."

    if '$' not in message or '#' not in message:
        return "Usage: bbspost $subject #message [^board]"

    try:
        after_cmd = message.split(None, 1)[1] if ' ' in message else ''
        subject_part = after_cmd.split('$', 1)[1].split('#')[0].strip()
        msg_part = after_cmd.split('#', 1)[1]

        board = 'General'
        if '^' in msg_part:
            msg_part, board_part = msg_part.rsplit('^', 1)
            board_name = normalize_board(board_part.strip())
            if board_name:
                board = board_name

        msg_part = msg_part.strip()

        if not subject_part or not msg_part:
            return "Usage: bbspost $subject #message [^board]"

        add_bulletin(board, short_name, str(node_id), subject_part, msg_part)
        return f"Posted to {board}."
    except Exception as e:
        logger.error(f"BBS: bbspost error: {e}")
        return "Error posting bulletin."


def handle_bbs_read(message, node_id):
    parts = message.strip().split()
    if len(parts) < 2:
        return "Usage: bbsread <id>"
    try:
        bid = int(parts[1])
    except ValueError:
        return "Invalid ID."

    row = get_bulletin_content(bid)
    if not row:
        return f"Bulletin #{bid} not found."

    return (
        f"#{bid} [{row['subject']}]\n"
        f"From: {row['sender_short_name']}\n"
        f"Date: {row['date']}\n"
        f"---\n"
        f"{row['content']}"
    )


def handle_bbs_delete(message, node_id):
    parts = message.strip().split()
    if len(parts) < 2:
        return "Usage: bbsdelete <id>"
    try:
        bid = int(parts[1])
    except ValueError:
        return "Invalid ID."

    owner = get_bulletin_owner(bid)
    if owner is None:
        return f"Bulletin #{bid} not found."

    if normalize_node_id(owner) != normalize_node_id(node_id) and not is_admin(node_id):
        return "You can only delete your own bulletins."

    delete_bulletin(bid)
    return f"Bulletin #{bid} deleted."


def handle_bbs_dm(message, node_id, short_name, interface):
    if is_banned(node_id):
        return "Message sent."

    if '@' not in message or '#' not in message:
        return "Usage: bbsdm @nodeid #message"

    try:
        after_cmd = message.split(None, 1)[1] if ' ' in message else ''
        to_part = after_cmd.split('@', 1)[1].split('#')[0].strip()
        msg_part = after_cmd.split('#', 1)[1].strip()

        if not to_part or not msg_part:
            return "Usage: bbsdm @nodeid #message"

        recipient_id = _resolve_node(to_part, interface)
        if not recipient_id:
            candidates = _fuzzy_find_nodes(to_part, interface)
            if candidates:
                lines = [f"Node '{to_part}' not found. Did you mean:"]
                for nid, short, _ in candidates[:5]:
                    lines.append(f"{nid} {short}")
                lines.append("Use bbsfind for more.")
                return "\n".join(lines)
            return f"Node '{to_part}' not found."

        subject = f"DM from {short_name}"
        add_mail(str(node_id), short_name, str(recipient_id), subject, msg_part)
        try:
            from modules.system import send_message
            node_int = interface if isinstance(interface, int) else 1
            recip_num = int(recipient_id[1:], 16)
            send_message(f"📬 New mail from {short_name}. Reply CM to check.", 0, recip_num, node_int)
        except Exception:
            pass
        return f"Mail sent to {to_part}."
    except Exception as e:
        logger.error(f"BBS: bbsdm error: {e}")
        return "Error sending mail."


def handle_bbs_check_mail(node_id):
    mail = get_mail(str(node_id))
    if not mail:
        return "No mail waiting. 📭"
    lines = [f"📬 {len(mail)} message(s):"]
    for m in mail:
        lines.append(f"#{m['id']} From:{m['sender_short_name']} - {m['subject']}")
    lines.append("Use: bbsreadm <id>")
    return "\n".join(lines)


def handle_bbs_read_mail(message, node_id):
    parts = message.strip().split()
    if len(parts) < 2:
        return "Usage: bbsreadm <id>"
    try:
        mid = int(parts[1])
    except ValueError:
        return "Invalid ID."

    row = get_mail_content(mid, str(node_id))
    if not row:
        return f"Mail #{mid} not found."

    return (
        f"Mail #{mid}\n"
        f"From: {row['sender_short_name']}\n"
        f"Date: {row['date']}\n"
        f"Subj: {row['subject']}\n"
        f"---\n"
        f"{row['content']}"
    )


def handle_bbs_delete_mail(message, node_id):
    parts = message.strip().split()
    if len(parts) < 2:
        return "Usage: bbsdelm <id>"
    try:
        mid = int(parts[1])
    except ValueError:
        return "Invalid ID."

    row = get_mail_content(mid, str(node_id))
    if not row and not is_admin(node_id):
        return f"Mail #{mid} not found."

    if delete_mail_by_id(mid):
        return f"Mail #{mid} deleted."
    return f"Mail #{mid} not found."


def handle_bbs_chan(node_id):
    channels = get_channels()
    if not channels:
        return "No channels in directory."
    lines = ["📻 Channel Directory:"]
    for ch in channels:
        lines.append(f"#{ch['id']} {ch['name']}")
    lines.append("Use: bbsaddchan $name #url")
    return "\n".join(lines)


def handle_bbs_add_chan(message, node_id, short_name):
    if '$' not in message or '#' not in message:
        return "Usage: bbsaddchan $name #url"
    try:
        after_cmd = message.split(None, 1)[1] if ' ' in message else ''
        name_part = after_cmd.split('$', 1)[1].split('#')[0].strip()
        url_part = after_cmd.split('#', 1)[1].strip()
        if not name_part or not url_part:
            return "Usage: bbsaddchan $name #url"
        add_channel(name_part, url_part)
        return f"Channel '{name_part}' added."
    except Exception as e:
        logger.error(f"BBS: bbsaddchan error: {e}")
        return "Error adding channel."


# --- TC2-style quick commands ---

def handle_quick_send_mail(message, node_id, short_name, interface):
    parts = message.split(',,', 3)
    if len(parts) != 4:
        return "Format: SM,,<shortname>,,<subject>,,<message>"
    _, target_name, subject, content = parts
    recipient_id = _resolve_node(target_name.strip(), interface)
    if not recipient_id:
        candidates = _fuzzy_find_nodes(target_name.strip(), interface)
        if candidates:
            lines = [f"Node '{target_name.strip()}' not found. Did you mean:"]
            for nid, short, _ in candidates[:5]:
                lines.append(f"{nid} {short}")
            lines.append("Use bbsfind for more.")
            return "\n".join(lines)
        return f"Node '{target_name.strip()}' not found."
    add_mail(str(node_id), short_name, str(recipient_id), subject.strip(), content.strip())
    try:
        from modules.system import send_message
        node_int = interface if isinstance(interface, int) else 1
        recip_num = int(recipient_id[1:], 16)
        send_message(f"📬 New mail from {short_name}. Reply CM to check.", 0, recip_num, node_int)
    except Exception:
        pass
    return f"Mail sent to {target_name.strip()}."


def handle_quick_check_mail(node_id):
    return handle_bbs_check_mail(node_id)


def handle_quick_post_bulletin(message, node_id, short_name):
    if is_banned(node_id):
        return "Posted."
    parts = message.split(',,', 3)
    if len(parts) != 4:
        return "Format: PB,,<board>,,<subject>,,<content>"
    _, board_name, subject, content = parts
    board = normalize_board(board_name.strip())
    if not board:
        return f"Unknown board. Try: {', '.join(VALID_BOARDS)}"
    add_bulletin(board, short_name, str(node_id), subject.strip(), content.strip())
    return f"Posted to {board}."


def handle_quick_check_bulletin(message, node_id):
    parts = message.split(',,', 1)
    if len(parts) != 2 or not parts[1].strip():
        return "Format: CB,,<board>"
    board = normalize_board(parts[1].strip())
    if not board:
        return f"Unknown board. Try: {', '.join(VALID_BOARDS)}"
    bulletins = get_bulletins(board)
    if not bulletins:
        return f"No bulletins on {board}."
    lines = [f"[{board}] {len(bulletins)} bulletin(s):"]
    for b in bulletins:
        lines.append(f"#{b['id']} {b['subject']} -{b['sender_short_name']}")
    return "\n".join(lines)


def handle_bbs_find(message, node_id, interface):
    parts = message.strip().split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return "Usage: bbsfind <name or node ID fragment>"
    partial = parts[1].strip()
    if len(partial) < 2:
        return "Search term must be at least 2 characters."
    matches = _fuzzy_find_nodes(partial, interface)
    if not matches:
        return f"No nodes found matching '{partial}'."
    lines = [f"Nodes matching '{partial}':"]
    for nid, short, long_name in matches[:10]:
        lines.append(f"{nid} {short} - {long_name}")
    if len(matches) > 10:
        lines.append(f"({len(matches) - 10} more — refine search)")
    return "\n".join(lines)


# --- Internal helpers ---

def _contains_emoji(text):
    """Return True if text contains one or more emoji characters.
    Checks standard Unicode emoji and symbol ranges.
    """
    for ch in text:
        cp = ord(ch)
        if (
            0x1F600 <= cp <= 0x1F64F or  # Emoticons
            0x1F300 <= cp <= 0x1F5FF or  # Misc Symbols and Pictographs
            0x1F680 <= cp <= 0x1F6FF or  # Transport and Map
            0x1F700 <= cp <= 0x1F77F or  # Alchemical Symbols
            0x1F780 <= cp <= 0x1F7FF or  # Geometric Shapes Extended
            0x1F800 <= cp <= 0x1F8FF or  # Supplemental Arrows-C
            0x1F900 <= cp <= 0x1F9FF or  # Supplemental Symbols and Pictographs
            0x1FA00 <= cp <= 0x1FA6F or  # Chess Symbols
            0x1FA70 <= cp <= 0x1FAFF or  # Symbols and Pictographs Extended-A
            0x2600 <= cp <= 0x26FF or    # Misc Symbols (☀ ☁ ⚡ etc.)
            0x2700 <= cp <= 0x27BF or    # Dingbats
            0xFE00 <= cp <= 0xFE0F or    # Variation Selectors
            0x1F1E0 <= cp <= 0x1F1FF or  # Regional Indicators (flag sequences)
            0x1F000 <= cp <= 0x1F02F or  # Mahjong Tiles
            0x1F0A0 <= cp <= 0x1F0FF or  # Playing Cards
            0x1F100 <= cp <= 0x1F1FF or  # Enclosed Alphanumeric Supplement
            0x1F200 <= cp <= 0x1F2FF or  # Enclosed Ideographic Supplement
            cp == 0x200D or              # Zero Width Joiner (emoji sequences)
            cp == 0x20E3                 # Combining Enclosing Keycap
        ):
            return True
    return False


def _fuzzy_find_nodes(partial, interface):
    """Case-insensitive substring match against short name, long name, and !hex node ID.
    Returns list of (nid_hex, short_name, long_name) sorted by short name.
    """
    if isinstance(interface, int):
        try:
            from modules.system import get_interface
            iface_obj = get_interface(interface)
            nodes = iface_obj.nodes if iface_obj and hasattr(iface_obj, 'nodes') else {}
        except Exception:
            nodes = {}
    else:
        nodes = getattr(interface, 'nodes', {})
    needle = partial.lower()
    results = []
    for node_id, node in nodes.items():
        user = node.get('user', {})
        short = user.get('shortName', '')
        long_name = user.get('longName', '')
        nid_hex = normalize_node_id(node_id) or ''
        if needle in short.lower() or needle in long_name.lower() or needle in nid_hex.lower():
            results.append((nid_hex, short, long_name))
    results.sort(key=lambda x: x[1].lower())
    return results


def _resolve_node(name_or_id, interface):
    """Resolve a short name or node ID string to a !hex node ID.
    interface may be a meshtastic interface object or an integer device ID.
    """
    if interface is None:
        return None
    if isinstance(interface, int):
        try:
            from modules.system import get_interface
            iface_obj = get_interface(interface)
            nodes = iface_obj.nodes if iface_obj and hasattr(iface_obj, 'nodes') else {}
        except Exception:
            nodes = {}
    else:
        nodes = getattr(interface, 'nodes', {})

    name_lower = name_or_id.lower().strip()
    for node_id, node in nodes.items():
        short = node.get('user', {}).get('shortName', '')
        if short.lower() == name_lower:
            if _contains_emoji(short):
                return None
            return normalize_node_id(node_id)
    try:
        if name_or_id.startswith('!'):
            num = int(name_or_id[1:], 16)
        else:
            num = int(name_or_id, 16)
        return f'!{num:08x}'
    except ValueError:
        pass
    return None
