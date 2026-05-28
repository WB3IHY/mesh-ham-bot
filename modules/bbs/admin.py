# modules/bbs/admin.py
# Admin commands for mesh-ham-bot BBS
# mesh-ham-bot project

import logging
from modules.bbs.db import (
    is_admin, add_admin, remove_admin, list_admins,
    ban_node, unban_node, list_banned,
    delete_bulletin, get_bulletin_content,
    delete_mail_by_id,
    delete_channel,
    get_bbs_stats,
    normalize_node_id,
)

logger = logging.getLogger(__name__)


def require_admin(node_id):
    return is_admin(node_id)


def handle_admin_help():
    return (
        "BBS Admin Commands:\n"
        "adminadd <nodeid>\n"
        "adminremove <nodeid>\n"
        "adminlist\n"
        "ban <nodeid> [reason]\n"
        "unban <nodeid>\n"
        "banlist\n"
        "bbsdelete <id>\n"
        "maildelete <id>\n"
        "chandel <id>\n"
        "bbsstats"
    )


def handle_admin_add(message, caller_node_id):
    parts = message.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: adminadd <nodeid>"
    target = parts[1].strip()
    if is_admin(target):
        return f"{target} is already an admin."
    if add_admin(target, str(caller_node_id)):
        logger.info(f"BBS Admin: {caller_node_id} added {target} as admin")
        return f"Admin added: {target}"
    return "Failed to add admin."


def handle_admin_remove(message, caller_node_id):
    parts = message.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: adminremove <nodeid>"
    target = parts[1].strip()
    if normalize_node_id(target) == normalize_node_id(caller_node_id):
        return "You cannot remove yourself as admin."
    if remove_admin(target):
        logger.info(f"BBS Admin: {caller_node_id} removed {target} from admins")
        return f"Admin removed: {target}"
    return f"{target} was not an admin."


def handle_admin_list():
    admins = list_admins()
    if not admins:
        return "No admins configured."
    lines = ["BBS Admins:"]
    for row in admins:
        lines.append(f"  {row['node_id']} (by {row['added_by']})")
    return "\n".join(lines)


def handle_ban(message, caller_node_id):
    parts = message.strip().split(None, 2)
    if len(parts) < 2:
        return "Usage: ban <nodeid> [reason]"
    target = parts[1].strip()
    reason = parts[2].strip() if len(parts) > 2 else None
    if ban_node(target, str(caller_node_id), reason):
        logger.info(f"BBS Admin: {caller_node_id} banned {target} reason={reason}")
        return f"Node {target} banned."
    return f"{target} is already banned."


def handle_unban(message, caller_node_id):
    parts = message.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: unban <nodeid>"
    target = parts[1].strip()
    if unban_node(target):
        logger.info(f"BBS Admin: {caller_node_id} unbanned {target}")
        return f"Node {target} unbanned."
    return f"{target} was not banned."


def handle_ban_list():
    banned = list_banned()
    if not banned:
        return "No banned nodes."
    lines = ["Banned nodes:"]
    for row in banned:
        reason_str = f" ({row['reason']})" if row['reason'] else ""
        lines.append(f"  {row['node_id']}{reason_str}")
    return "\n".join(lines)


def handle_bulletin_delete(message, caller_node_id):
    parts = message.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: bbsdelete <bulletin_id>"
    try:
        bulletin_id = int(parts[1].strip())
    except ValueError:
        return "Invalid bulletin ID."
    row = get_bulletin_content(bulletin_id)
    if not row:
        return f"Bulletin #{bulletin_id} not found."
    if delete_bulletin(bulletin_id):
        logger.info(f"BBS Admin: {caller_node_id} deleted bulletin #{bulletin_id}")
        return f"Bulletin #{bulletin_id} deleted."
    return "Delete failed."


def handle_mail_delete(message, caller_node_id):
    parts = message.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: maildelete <mail_id>"
    try:
        mail_id = int(parts[1].strip())
    except ValueError:
        return "Invalid mail ID."
    if delete_mail_by_id(mail_id):
        logger.info(f"BBS Admin: {caller_node_id} deleted mail #{mail_id}")
        return f"Mail #{mail_id} deleted."
    return f"Mail #{mail_id} not found."


def handle_channel_delete(message, caller_node_id):
    parts = message.strip().split(None, 1)
    if len(parts) < 2:
        return "Usage: chandel <channel_id>"
    try:
        channel_id = int(parts[1].strip())
    except ValueError:
        return "Invalid channel ID."
    if delete_channel(channel_id):
        logger.info(f"BBS Admin: {caller_node_id} deleted channel #{channel_id}")
        return f"Channel #{channel_id} deleted."
    return f"Channel #{channel_id} not found."


def handle_bbs_stats():
    stats = get_bbs_stats()
    return (
        f"📊 BBS Stats:\n"
        f"Bulletins: {stats['bulletins']}\n"
        f"Mail: {stats['mail']}\n"
        f"Channels: {stats['channels']}\n"
        f"Admins: {stats['admins']}"
    )
