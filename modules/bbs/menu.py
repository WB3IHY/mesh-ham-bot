# modules/bbs/menu.py
# Stateful menu-driven BBS interface for mesh-ham-bot
# Adapted from TC2-BBS-mesh command_handlers.py (Apache 2.0)
# Integrated into mesh-ham-bot by WB3IHY
#
# Original TC2-BBS-mesh: Copyright (C) TheCommsChannel

import logging
from modules.bbs.db import (
    add_bulletin, get_bulletins, get_bulletin_content,
    delete_bulletin, get_bulletin_owner,
    add_mail, get_mail, get_mail_content,
    delete_mail_by_unique_id, delete_mail_by_id,
    add_channel, get_channels,
    is_admin, is_banned, normalize_board, normalize_node_id, VALID_BOARDS,
    get_bbs_stats
)
from modules.bbs.state import set_state, get_state, clear_state
from modules.bbs.commands import _resolve_node, _fuzzy_find_nodes

logger = logging.getLogger(__name__)

MENU_TRIGGER_COMMANDS = ('bbsmenu',)

_EXIT_MSG = "73! Type bbsmenu to return to the BBS."


def send(interface, node_id, text):
    """Send a DM to node_id. interface is the device ID integer (1-9)."""
    from modules.system import send_message
    node_int = interface if isinstance(interface, int) else 1
    send_message(text, 0, node_id, node_int)


def get_nodes(interface):
    """Return the nodes dict for a device ID integer or interface object."""
    node_int = interface if isinstance(interface, int) else 1
    try:
        from modules.system import get_interface
        iface = get_interface(node_int)
        if iface and hasattr(iface, 'nodes'):
            return iface.nodes
    except Exception:
        pass
    return {}


def get_short_name(node_id, interface):
    """Get short name for a node. interface is device ID integer."""
    from modules.system import get_name_from_number
    node_int = interface if isinstance(interface, int) else 1
    if isinstance(node_id, str) and node_id.startswith('!'):
        try:
            node_id = int(node_id[1:], 16)
        except ValueError:
            return f'Node{node_id}'
    name = get_name_from_number(node_id, 'short', node_int)
    return name if name else f'Node{node_id}'


def get_long_name(node_id, interface):
    """Get long name for a node. interface is device ID integer."""
    from modules.system import get_name_from_number
    node_int = interface if isinstance(interface, int) else 1
    if isinstance(node_id, str) and node_id.startswith('!'):
        try:
            node_id = int(node_id[1:], 16)
        except ValueError:
            return f'Node{node_id}'
    name = get_name_from_number(node_id, 'long', node_int)
    return name if name else f'Node{node_id}'


def handle_menu_message(message, node_id, interface):
    """
    Main dispatcher for menu-mode BBS.
    Returns True if message was consumed, False otherwise.
    """
    msg = message.strip()
    msg_lower = msg.lower()

    state = get_state(node_id)

    if state is None and msg_lower not in MENU_TRIGGER_COMMANDS:
        return False

    if state is None or msg_lower in MENU_TRIGGER_COMMANDS:
        _show_main_menu(node_id, interface)
        return True

    command = state.get('command')

    if command == 'MAIN_MENU':
        _handle_main_menu(msg_lower, node_id, interface)
    elif command == 'BBS_MENU':
        _handle_bbs_menu(msg_lower, node_id, state, interface)
    elif command == 'BULLETIN_BOARD':
        _handle_bulletin_board(msg, msg_lower, node_id, state, interface)
    elif command == 'BULLETIN_READ_LIST':
        _handle_bulletin_read_list(msg, node_id, state, interface)
    elif command == 'BULLETIN_POST_SUBJECT':
        _handle_bulletin_post_subject(msg, node_id, state, interface)
    elif command == 'BULLETIN_POST_CONTENT':
        _handle_bulletin_post_content(msg, node_id, state, interface)
    elif command == 'MAIL_MENU':
        _handle_mail_menu(msg_lower, node_id, state, interface)
    elif command == 'MAIL_READ_SELECT':
        _handle_mail_read_select(msg, node_id, state, interface)
    elif command == 'MAIL_READ_ACTION':
        _handle_mail_read_action(msg_lower, node_id, state, interface)
    elif command == 'MAIL_SEND_TO':
        _handle_mail_send_to(msg, node_id, state, interface)
    elif command == 'MAIL_SEND_TO_CONFIRM':
        _handle_mail_send_to_confirm(msg, node_id, state, interface)
    elif command == 'MAIL_SEND_SUBJECT':
        _handle_mail_send_subject(msg, node_id, state, interface)
    elif command == 'MAIL_SEND_CONTENT':
        _handle_mail_send_content(msg, node_id, state, interface)
    elif command == 'MAIL_REPLY_CONTENT':
        _handle_mail_reply_content(msg, node_id, state, interface)
    elif command == 'CHANNEL_MENU':
        _handle_channel_menu(msg_lower, node_id, state, interface)
    elif command == 'CHANNEL_VIEW':
        _handle_channel_view(msg, node_id, state, interface)
    elif command == 'CHANNEL_POST_NAME':
        _handle_channel_post_name(msg, node_id, state, interface)
    elif command == 'CHANNEL_POST_URL':
        _handle_channel_post_url(msg, node_id, state, interface)
    elif command == 'STATS_MENU':
        _handle_stats_menu(msg_lower, node_id, state, interface)
    else:
        clear_state(node_id)
        _show_main_menu(node_id, interface)

    return True


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def _show_main_menu(node_id, interface):
    mail = get_mail(str(node_id))
    mail_count = len(mail)
    menu = (
        f"📡 Ham-BBS 📡\n"
        f"✉️ Mail: {mail_count}\n"
        f"[B]ulletins\n"
        f"[M]ail\n"
        f"[C]hannels\n"
        f"[S]tats\n"
        f"[X] Exit"
    )
    send(interface, node_id, menu)
    set_state(node_id, {'command': 'MAIN_MENU'})


def _handle_main_menu(msg, node_id, interface):
    if msg in ('b', 'bulletins'):
        _show_bbs_menu(node_id, interface)
    elif msg in ('m', 'mail'):
        _show_mail_menu(node_id, interface)
    elif msg in ('c', 'channels'):
        _show_channel_menu(node_id, interface)
    elif msg in ('s', 'stats'):
        _show_stats_menu(node_id, interface)
    elif msg in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
    else:
        send(interface, node_id, "Unknown option. Reply B, M, C, S, or X.")


# ---------------------------------------------------------------------------
# Bulletin board menu
# ---------------------------------------------------------------------------

def _show_bbs_menu(node_id, interface):
    menu = (
        "📰 Bulletins 📰\n"
        + "\n".join(f"[{i+1}] {b}" for i, b in enumerate(VALID_BOARDS))
        + "\n[B] Back  [X] Exit"
    )
    send(interface, node_id, menu)
    set_state(node_id, {'command': 'BBS_MENU'})


def _handle_bbs_menu(msg, node_id, state, interface):
    if msg in ('b', 'back'):
        _show_main_menu(node_id, interface)
        return
    if msg in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
        return
    try:
        idx = int(msg) - 1
        if 0 <= idx < len(VALID_BOARDS):
            board = VALID_BOARDS[idx]
            _show_bulletin_board(board, node_id, interface)
        else:
            send(interface, node_id, f"Choose 1-{len(VALID_BOARDS)}, B, or X.")
    except ValueError:
        send(interface, node_id, f"Choose 1-{len(VALID_BOARDS)}, B, or X.")


def _show_bulletin_board(board, node_id, interface):
    bulletins = get_bulletins(board)
    count = len(bulletins)
    menu = (
        f"[{board}] {count} bulletin(s)\n"
        f"[R]ead  [P]ost  [B] Back  [X] Exit"
    )
    send(interface, node_id, menu)
    set_state(node_id, {'command': 'BULLETIN_BOARD', 'board': board})


def _handle_bulletin_board(msg, msg_lower, node_id, state, interface):
    board = state.get('board')
    if msg_lower in ('b', 'back'):
        _show_bbs_menu(node_id, interface)
    elif msg_lower in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
    elif msg_lower == 'r':
        bulletins = get_bulletins(board)
        if not bulletins:
            send(interface, node_id, f"No bulletins on {board}.")
            _show_bulletin_board(board, node_id, interface)
        else:
            lines = [f"[{board}] — select #:"]
            for b in bulletins:
                lines.append(f"#{b['id']} {b['subject']} -{b['sender_short_name']}")
            lines.append("[B] Back  [X] Exit")
            send(interface, node_id, "\n".join(lines))
            set_state(node_id, {'command': 'BULLETIN_READ_LIST', 'board': board, 'bulletins': [dict(b) for b in bulletins]})
    elif msg_lower == 'p':
        if is_banned(node_id):
            send(interface, node_id, "You are not permitted to post.")
            _show_bulletin_board(board, node_id, interface)
            return
        send(interface, node_id, f"Post to [{board}]\nWhat is the subject? (Keep it short)")
        set_state(node_id, {'command': 'BULLETIN_POST_SUBJECT', 'board': board})
    else:
        send(interface, node_id, "Reply R, P, B, or X.")


def _handle_bulletin_read_list(msg, node_id, state, interface):
    board = state.get('board')

    # Delete confirmation from a previous read
    if msg.lower() == 'd' and state.get('last_read'):
        bid = state['last_read']
        owner = get_bulletin_owner(bid)
        if normalize_node_id(owner) == normalize_node_id(node_id) or is_admin(node_id):
            delete_bulletin(bid)
            send(interface, node_id, f"Bulletin #{bid} deleted.")
        else:
            send(interface, node_id, "Not authorized.")
        _show_bulletin_board(board, node_id, interface)
        return

    if msg.lower() in ('b', 'back'):
        _show_bulletin_board(board, node_id, interface)
        return

    if msg.lower() in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
        return

    try:
        bid = int(msg.lstrip('#'))
        row = get_bulletin_content(bid)
        if not row:
            send(interface, node_id, f"Bulletin #{bid} not found.")
            _show_bulletin_board(board, node_id, interface)
            return

        text = (
            f"#{bid} [{row['subject']}]\n"
            f"From: {row['sender_short_name']}\n"
            f"Date: {row['date']}\n"
            f"---\n{row['content']}"
        )
        send(interface, node_id, text)

        owner = get_bulletin_owner(bid)
        if normalize_node_id(owner) == normalize_node_id(node_id) or is_admin(node_id):
            send(interface, node_id, f"[D]elete #{bid}  [B] Back  [X] Exit")
            set_state(node_id, {
                'command': 'BULLETIN_READ_LIST',
                'board': board,
                'last_read': bid,
                'bulletins': state.get('bulletins', [])
            })
        else:
            send(interface, node_id, "[B] Back  [X] Exit")
            set_state(node_id, {
                'command': 'BULLETIN_READ_LIST',
                'board': board,
                'bulletins': state.get('bulletins', [])
            })

    except ValueError:
        send(interface, node_id, "Enter a bulletin # or B.")


def _handle_bulletin_post_subject(msg, node_id, state, interface):
    if msg.lower() in ('x', 'cancel'):
        _show_bulletin_board(state.get('board'), node_id, interface)
        return
    send(interface, node_id, "Now send the content of your bulletin.\nSend END when finished.")
    set_state(node_id, {
        'command': 'BULLETIN_POST_CONTENT',
        'board': state['board'],
        'subject': msg,
        'content': ''
    })


def _handle_bulletin_post_content(msg, node_id, state, interface):
    if msg.lower() == 'end':
        board = state['board']
        subject = state['subject']
        content = state['content'].strip()
        if not content:
            send(interface, node_id, "No content received. Post cancelled.")
            _show_bulletin_board(board, node_id, interface)
            return
        short_name = get_short_name(node_id, interface)
        add_bulletin(board, short_name, str(node_id), subject, content)
        send(interface, node_id, f"✅ Posted to [{board}]: {subject}")
        _show_bulletin_board(board, node_id, interface)
    elif msg.lower() in ('x', 'cancel'):
        send(interface, node_id, "Post cancelled.")
        _show_bulletin_board(state.get('board'), node_id, interface)
    else:
        state['content'] += msg + '\n'
        set_state(node_id, state)


# ---------------------------------------------------------------------------
# Mail menu
# ---------------------------------------------------------------------------

def _show_mail_menu(node_id, interface):
    mail = get_mail(str(node_id))
    menu = (
        f"✉️ Mail ✉️\n"
        f"{len(mail)} message(s)\n"
        f"[R]ead  [S]end  [B] Back  [X] Exit"
    )
    send(interface, node_id, menu)
    set_state(node_id, {'command': 'MAIL_MENU'})


def _handle_mail_menu(msg, node_id, state, interface):
    if msg in ('b', 'back'):
        _show_main_menu(node_id, interface)
    elif msg in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
    elif msg == 'r':
        mail = get_mail(str(node_id))
        if not mail:
            send(interface, node_id, "No mail. 📭")
            _show_mail_menu(node_id, interface)
        else:
            lines = ["📬 Your mail — select #:"]
            for m in mail:
                lines.append(f"#{m['id']} {m['subject']} -{m['sender_short_name']}")
            lines.append("[B] Back  [X] Exit")
            send(interface, node_id, "\n".join(lines))
            set_state(node_id, {'command': 'MAIL_READ_SELECT', 'mail': [dict(m) for m in mail]})
    elif msg == 's':
        if is_banned(node_id):
            send(interface, node_id, "You are not permitted to send mail.")
            _show_mail_menu(node_id, interface)
            return
        send(interface, node_id, "Send mail to (short name or !nodeid):")
        set_state(node_id, {'command': 'MAIL_SEND_TO'})
    else:
        send(interface, node_id, "Reply R, S, B, or X.")


def _handle_mail_read_select(msg, node_id, state, interface):
    if msg.lower() in ('b', 'back'):
        _show_mail_menu(node_id, interface)
        return
    if msg.lower() in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
        return
    try:
        mid = int(msg.lstrip('#'))
        row = get_mail_content(mid, str(node_id))
        if not row:
            send(interface, node_id, f"Mail #{mid} not found.")
            _show_mail_menu(node_id, interface)
        else:
            text = (
                f"Mail #{mid}\n"
                f"From: {row['sender_short_name']}\n"
                f"Date: {row['date']}\n"
                f"Subj: {row['subject']}\n"
                f"---\n{row['content']}"
            )
            send(interface, node_id, text)
            send(interface, node_id, "[K]eep  [D]elete  [R]eply  [B] Back  [X] Exit")
            set_state(node_id, {
                'command': 'MAIL_READ_ACTION',
                'mail_id': mid,
                'unique_id': row['unique_id'],
                'sender': row['sender'],
                'sender_name': row['sender_short_name'],
                'subject': row['subject']
            })
    except ValueError:
        send(interface, node_id, "Enter a mail # or B.")


def _handle_mail_read_action(msg, node_id, state, interface):
    mid = state.get('mail_id')
    if msg in ('k', 'keep', 'b', 'back'):
        send(interface, node_id, "Message kept. ✉️")
        _show_mail_menu(node_id, interface)
    elif msg in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
    elif msg == 'd':
        delete_mail_by_id(mid)
        send(interface, node_id, f"Mail #{mid} deleted. 🗑️")
        _show_mail_menu(node_id, interface)
    elif msg == 'r':
        send(interface, node_id,
             f"Reply to {state.get('sender_name')}.\nSend content, then END.")
        set_state(node_id, {
            'command': 'MAIL_REPLY_CONTENT',
            'recipient_id': state.get('sender'),
            'recipient_name': state.get('sender_name'),
            'subject': f"Re: {state.get('subject', '')}",
            'content': '',
            'original_id': mid
        })
    else:
        send(interface, node_id, "Reply K, D, R, B, or X.")


def _handle_mail_send_to(msg, node_id, state, interface):
    if msg.lower() in ('x', 'cancel'):
        _show_mail_menu(node_id, interface)
        return
    recipient_id = _resolve_node(msg.strip(), interface)
    if recipient_id:
        recipient_name = get_short_name(recipient_id, interface)
        send(interface, node_id, f"To: {recipient_name}\nSubject?")
        set_state(node_id, {
            'command': 'MAIL_SEND_SUBJECT',
            'recipient_id': str(recipient_id),
            'recipient_name': recipient_name
        })
        return
    candidates = _fuzzy_find_nodes(msg.strip(), interface)
    if not candidates:
        send(interface, node_id, f"Node '{msg.strip()}' not found. Try again or X.")
        return
    if len(candidates) == 1:
        nid, short, _ = candidates[0]
        send(interface, node_id, f"To: {short}\nSubject?")
        set_state(node_id, {
            'command': 'MAIL_SEND_SUBJECT',
            'recipient_id': nid,
            'recipient_name': short
        })
        return
    lines = [f"Multiple matches for '{msg.strip()}':"]
    for i, (nid, short, long_name) in enumerate(candidates[:8], 1):
        lines.append(f"{i}. {short} ({long_name}) {nid}")
    lines.append("Enter number or X.")
    send(interface, node_id, "\n".join(lines))
    set_state(node_id, {
        'command': 'MAIL_SEND_TO_CONFIRM',
        'candidates': [{'node_id': nid, 'short': s, 'long': l} for nid, s, l in candidates[:8]]
    })


def _handle_mail_send_to_confirm(msg, node_id, state, interface):
    if msg.lower() in ('x', 'cancel'):
        _show_mail_menu(node_id, interface)
        return
    candidates = state.get('candidates', [])
    try:
        idx = int(msg.strip()) - 1
        if 0 <= idx < len(candidates):
            chosen = candidates[idx]
            send(interface, node_id, f"To: {chosen['short']}\nSubject?")
            set_state(node_id, {
                'command': 'MAIL_SEND_SUBJECT',
                'recipient_id': chosen['node_id'],
                'recipient_name': chosen['short']
            })
        else:
            send(interface, node_id, f"Enter 1-{len(candidates)} or X.")
    except ValueError:
        send(interface, node_id, f"Enter 1-{len(candidates)} or X.")


def _handle_mail_send_subject(msg, node_id, state, interface):
    if msg.lower() in ('x', 'cancel'):
        _show_mail_menu(node_id, interface)
        return
    send(interface, node_id, "Send your message. Send END when done.")
    set_state(node_id, {
        'command': 'MAIL_SEND_CONTENT',
        'recipient_id': state['recipient_id'],
        'recipient_name': state['recipient_name'],
        'subject': msg,
        'content': ''
    })


def _handle_mail_send_content(msg, node_id, state, interface):
    if msg.lower() == 'end':
        content = state['content'].strip()
        if not content:
            send(interface, node_id, "No content. Mail cancelled.")
            _show_mail_menu(node_id, interface)
            return
        short_name = get_short_name(node_id, interface)
        add_mail(str(node_id), short_name,
                 state['recipient_id'], state['subject'], content)
        send(interface, node_id, f"📨 Mail sent to {state['recipient_name']}.")
        try:
            rid = state['recipient_id']
            recip_num = int(rid[1:], 16) if isinstance(rid, str) and rid.startswith('!') else int(rid)
            from modules.system import send_message
            node_int = interface if isinstance(interface, int) else 1
            send_message(
                f"📬 New mail from {short_name}. Reply CM to check.",
                0, recip_num, node_int
            )
        except Exception:
            pass
        _show_mail_menu(node_id, interface)
    elif msg.lower() in ('x', 'cancel'):
        send(interface, node_id, "Mail cancelled.")
        _show_mail_menu(node_id, interface)
    else:
        state['content'] += msg + '\n'
        set_state(node_id, state)


def _handle_mail_reply_content(msg, node_id, state, interface):
    if msg.lower() == 'end':
        content = state['content'].strip()
        if not content:
            send(interface, node_id, "No content. Reply cancelled.")
            _show_mail_menu(node_id, interface)
            return
        short_name = get_short_name(node_id, interface)
        add_mail(str(node_id), short_name,
                 state['recipient_id'], state['subject'], content)
        send(interface, node_id, f"📨 Reply sent to {state['recipient_name']}.")
        _show_mail_menu(node_id, interface)
    elif msg.lower() in ('x', 'cancel'):
        send(interface, node_id, "Reply cancelled.")
        _show_mail_menu(node_id, interface)
    else:
        state['content'] += msg + '\n'
        set_state(node_id, state)


# ---------------------------------------------------------------------------
# Channel directory menu
# ---------------------------------------------------------------------------

def _show_channel_menu(node_id, interface):
    channels = get_channels()
    menu = (
        f"📻 Channels 📻\n"
        f"{len(channels)} listed\n"
        f"[V]iew  [P]ost  [B] Back  [X] Exit"
    )
    send(interface, node_id, menu)
    set_state(node_id, {'command': 'CHANNEL_MENU'})


def _handle_channel_menu(msg, node_id, state, interface):
    if msg in ('b', 'back'):
        _show_main_menu(node_id, interface)
    elif msg in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
    elif msg == 'v':
        channels = get_channels()
        if not channels:
            send(interface, node_id, "No channels listed yet.")
            _show_channel_menu(node_id, interface)
        else:
            lines = ["Channels — select #:"]
            for ch in channels:
                lines.append(f"#{ch['id']} {ch['name']}")
            lines.append("[B] Back  [X] Exit")
            send(interface, node_id, "\n".join(lines))
            set_state(node_id, {'command': 'CHANNEL_VIEW', 'channels': [dict(c) for c in channels]})
    elif msg == 'p':
        send(interface, node_id, "Channel name?")
        set_state(node_id, {'command': 'CHANNEL_POST_NAME'})
    else:
        send(interface, node_id, "Reply V, P, B, or X.")


def _handle_channel_view(msg, node_id, state, interface):
    if msg.lower() in ('b', 'back'):
        _show_channel_menu(node_id, interface)
        return
    if msg.lower() in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
        return
    channels = state.get('channels', [])
    try:
        cid = int(msg.lstrip('#'))
        match = next((c for c in channels if c['id'] == cid), None)
        if match:
            send(interface, node_id, f"📻 {match['name']}\n{match['url']}\n[B] Back  [X] Exit")
        else:
            send(interface, node_id, f"Channel #{cid} not found. Enter # or B.")
    except ValueError:
        send(interface, node_id, "Enter a channel # or B.")


def _handle_channel_post_name(msg, node_id, state, interface):
    if msg.lower() in ('x', 'cancel'):
        _show_channel_menu(node_id, interface)
        return
    send(interface, node_id, f"URL or PSK for '{msg}'?")
    set_state(node_id, {'command': 'CHANNEL_POST_URL', 'channel_name': msg})


def _handle_channel_post_url(msg, node_id, state, interface):
    if msg.lower() in ('x', 'cancel'):
        _show_channel_menu(node_id, interface)
        return
    name = state['channel_name']
    add_channel(name, msg.strip())
    send(interface, node_id, f"✅ Channel '{name}' added.")
    _show_channel_menu(node_id, interface)


# ---------------------------------------------------------------------------
# Stats menu
# ---------------------------------------------------------------------------

def _show_stats_menu(node_id, interface):
    menu = (
        "📊 Stats 📊\n"
        "[N]odes\n"
        "[H]ardware\n"
        "[R]oles\n"
        "[W]all (low battery)\n"
        "[D]B stats\n"
        "[B] Back  [X] Exit"
    )
    send(interface, node_id, menu)
    set_state(node_id, {'command': 'STATS_MENU'})


def _handle_stats_menu(msg, node_id, state, interface):
    import time
    if msg in ('b', 'back'):
        _show_main_menu(node_id, interface)
        return
    if msg in ('x', 'exit', 'quit'):
        clear_state(node_id)
        send(interface, node_id, _EXIT_MSG)
        return

    if msg == 'n':
        current_time = int(time.time())
        timeframes = [
            ("All time", None),
            ("24h", 86400),
            ("8h", 28800),
            ("1h", 3600),
        ]
        lines = ["Nodes seen:"]
        for label, secs in timeframes:
            if secs is None:
                count = len(get_nodes(interface))
            else:
                cutoff = current_time - secs
                count = sum(
                    1 for n in get_nodes(interface).values()
                    if n.get('lastHeard') and n['lastHeard'] >= cutoff
                )
            lines.append(f"  {label}: {count}")
        send(interface, node_id, "\n".join(lines))
        _show_stats_menu(node_id, interface)

    elif msg == 'h':
        hw = {}
        for n in get_nodes(interface).values():
            model = n['user'].get('hwModel', 'Unknown')
            hw[model] = hw.get(model, 0) + 1
        lines = ["Hardware:"] + [f"  {m}: {c}" for m, c in sorted(hw.items())]
        send(interface, node_id, "\n".join(lines))
        _show_stats_menu(node_id, interface)

    elif msg == 'r':
        roles = {}
        for n in get_nodes(interface).values():
            role = n['user'].get('role', 'Unknown')
            roles[role] = roles.get(role, 0) + 1
        lines = ["Roles:"] + [f"  {r}: {c}" for r, c in sorted(roles.items())]
        send(interface, node_id, "\n".join(lines))
        _show_stats_menu(node_id, interface)

    elif msg == 'w':
        low = []
        for nid, n in get_nodes(interface).items():
            bat = n.get('deviceMetrics', {}).get('batteryLevel', 101)
            if bat < 20:
                low.append(f"  {n['user']['longName']}: {bat}%")
        if low:
            send(interface, node_id, "🔋 Below 20%:\n" + "\n".join(low))
        else:
            send(interface, node_id, "✅ No nodes below 20%.")
        _show_stats_menu(node_id, interface)

    elif msg == 'd':
        stats = get_bbs_stats()
        send(interface, node_id,
             f"BBS DB:\n"
             f"  Bulletins: {stats['bulletins']}\n"
             f"  Mail: {stats['mail']}\n"
             f"  Channels: {stats['channels']}\n"
             f"  Admins: {stats['admins']}")
        _show_stats_menu(node_id, interface)

    else:
        send(interface, node_id, "Reply N, H, R, W, D, B, or X.")
