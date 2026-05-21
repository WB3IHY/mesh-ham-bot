# modules/bbs/state.py
# User state management for stateful BBS menu navigation
# mesh-ham-bot project

import time
import logging

logger = logging.getLogger(__name__)

STATE_TIMEOUT_SECONDS = 300  # 5 minutes

_user_states = {}  # {node_id: {'state': {...}, 'timestamp': float}}


def set_state(node_id, state):
    if state is None:
        _user_states.pop(node_id, None)
    else:
        _user_states[node_id] = {
            'state': state,
            'timestamp': time.time()
        }


def get_state(node_id):
    entry = _user_states.get(node_id)
    if entry is None:
        return None
    if time.time() - entry['timestamp'] > STATE_TIMEOUT_SECONDS:
        logger.debug(f"BBS: State timed out for {node_id}")
        _user_states.pop(node_id, None)
        return None
    return entry['state']


def clear_state(node_id):
    _user_states.pop(node_id, None)


def touch_state(node_id):
    entry = _user_states.get(node_id)
    if entry:
        entry['timestamp'] = time.time()


def is_in_menu(node_id):
    return get_state(node_id) is not None


def cleanup_expired():
    now = time.time()
    expired = [
        nid for nid, entry in _user_states.items()
        if now - entry['timestamp'] > STATE_TIMEOUT_SECONDS
    ]
    for nid in expired:
        _user_states.pop(nid, None)
    if expired:
        logger.debug(f"BBS: Pruned {len(expired)} expired user states")
