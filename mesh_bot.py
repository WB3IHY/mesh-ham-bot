#!/usr/bin/env python3
# Meshtastic Autoresponder MESH Bot
# K7MHI Kelly Keeton 2025
try:
    from pubsub import pub
except ImportError:
    print(f"Important dependencies are not met, try install.sh\n\n Did you mean to './launch.sh mesh' using a virtual environment.")
    exit(1)

import asyncio
import time # for sleep, get some when you can :)
import random
from datetime import datetime
from modules.log import logger, CustomFormatter, msgLogger, getPrettyTime
import modules.settings as my_settings
from modules.system import *
import modules.system as system

# BBS imports — loaded conditionally to match bbs_enabled setting
if my_settings.bbs_enabled:
    from modules.bbs.db import is_banned, add_mail, has_pending_mail_alert, mark_mail_alerted
    from modules.bbs.menu import handle_menu_message
    from modules.bbs.commands import (
        handle_bbs_help, handle_bbs_list, handle_bbs_post,
        handle_bbs_read, handle_bbs_delete, handle_bbs_dm,
        handle_bbs_check_mail, handle_bbs_read_mail, handle_bbs_delete_mail,
        handle_bbs_chan, handle_bbs_add_chan, handle_bbs_info, handle_bbs_boards,
        handle_bbs_find,
        handle_quick_send_mail, handle_quick_check_mail,
        handle_quick_post_bulletin, handle_quick_check_bulletin,
    )
    from modules.bbs.admin import (
        require_admin, handle_admin_help, handle_admin_add, handle_admin_remove,
        handle_admin_list, handle_ban, handle_unban, handle_ban_list,
        handle_bulletin_delete, handle_mail_delete, handle_channel_delete,
        handle_bbs_stats,
    )
else:
    # Stubs so references in non-BBS code paths don't crash
    def is_banned(node_id): return False
    def handle_menu_message(message, node_id, interface): return False

# list of commands to remove from the default list for DM only
# (previously listed commands have been removed from the codebase; add future DM-only commands here)
restrictedCommands = []
restrictedResponse = "🤖only available in a Direct Message📵" # "" for none

# commands that "share <cmd>" is allowed to re-broadcast into the issuing channel
# whitelist by design: BBS/admin/mail commands and anything not listed here stay DM/normal-routed only
shareableCommands = {"wx", "wxa", "wxalert", "wxc", "wxfind", "wxcall", "sun", "moon", "tide", "mwx",
                      "solar", "hfcond", "satpass", "valert", "riverflow", "dx", "joke", "verse"}

def auto_response(message, snr, rssi, hop, pkiStatus, message_from_id, channel_number, deviceID, isDM):
    global cmdHistory
    #Auto response to messages
    message_lower = message.lower()
    bot_response = "🤖I'm sorry, I'm afraid I can't do that."

    # Command List processes system.trap_list. system.messageTrap() sends any commands to here
    default_commands = {
    "ack": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "bbsmenu": lambda: handle_bbs_help(message_from_id),
    "bbshelp": lambda: handle_bbs_help(message_from_id),
    "bbsinfo": lambda: handle_bbs_info(),
    "bbsboards": lambda: handle_bbs_boards(),
    "bbslist": lambda: handle_bbs_list(message, message_from_id),
    "bbspost": lambda: handle_bbs_post(message, message_from_id, get_name_from_number(message_from_id, 'short', deviceID)),
    "bbsread": lambda: handle_bbs_read(message, message_from_id),
    "bbsdelete": lambda: handle_bbs_delete(message, message_from_id),
    "bbsdm": lambda: handle_bbs_dm(message, message_from_id, get_name_from_number(message_from_id, 'short', deviceID), get_interface(deviceID)),
    "bbsfind": lambda: handle_bbs_find(message, message_from_id, get_interface(deviceID)),
    "bbscheckim": lambda: handle_bbs_check_mail(message_from_id),
    "bbsreadm": lambda: handle_bbs_read_mail(message, message_from_id),
    "bbsdelm": lambda: handle_bbs_delete_mail(message, message_from_id),
    "bbschan": lambda: handle_bbs_chan(message_from_id),
    "bbsaddchan": lambda: handle_bbs_add_chan(message, message_from_id, get_name_from_number(message_from_id, 'short', deviceID)),
    "sm,,": lambda: handle_quick_send_mail(message, message_from_id, get_name_from_number(message_from_id, 'short', deviceID), get_interface(deviceID)),
    "cm": lambda: handle_quick_check_mail(message_from_id),
    "pb,,": lambda: handle_quick_post_bulletin(message, message_from_id, get_name_from_number(message_from_id, 'short', deviceID)),
    "cb,,": lambda: handle_quick_check_bulletin(message, message_from_id),
    "adminadd": lambda: handle_admin_add(message, message_from_id) if require_admin(message_from_id) else "Not authorized.",
    "adminremove": lambda: handle_admin_remove(message, message_from_id) if require_admin(message_from_id) else "Not authorized.",
    "adminlist": lambda: handle_admin_list() if require_admin(message_from_id) else "Not authorized.",
    "ban": lambda: handle_ban(message, message_from_id) if require_admin(message_from_id) else "Not authorized.",
    "unban": lambda: handle_unban(message, message_from_id) if require_admin(message_from_id) else "Not authorized.",
    "banlist": lambda: handle_ban_list() if require_admin(message_from_id) else "Not authorized.",
    "bbsstats": lambda: handle_bbs_stats() if require_admin(message_from_id) else "Not authorized.",
    "maildelete": lambda: handle_mail_delete(message, message_from_id) if require_admin(message_from_id) else "Not authorized.",
    "chandel": lambda: handle_channel_delete(message, message_from_id) if require_admin(message_from_id) else "Not authorized.",
    "cmd": lambda: handle_cmd(message, message_from_id, deviceID),
    "cq": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "cqcq": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "cqcqcq": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "dx": lambda: handledxcluster(message, message_from_id, deviceID),
    "ea": lambda: handle_emergency_alerts(message, message_from_id, deviceID),
    "echo": lambda: handle_echo(message, message_from_id, deviceID, isDM, channel_number),
    "ealert": lambda: handle_emergency_alerts(message, message_from_id, deviceID),
    "earthquake": lambda: handleEarthquake(message, message_from_id, deviceID),
    "grid": lambda: handle_grid(message_from_id, deviceID, channel_number),
    "hfcond": hf_band_conditions,
    "history": lambda: handle_history(message, message_from_id, deviceID, isDM),
    "howfar": lambda: handle_howfar(message, message_from_id, deviceID, isDM),
    "howtall": lambda: handle_howtall(message, message_from_id, deviceID, isDM),
    "joke": lambda: tell_joke(message_from_id),
    "latest": lambda: get_newsAPI(message, message_from_id, deviceID, isDM),
    "leaderboard": lambda: get_mesh_leaderboard(message, message_from_id, deviceID),
    "lheard": lambda: handle_lheard(message, message_from_id, deviceID, isDM),
    "locator": lambda: handle_grid(message_from_id, deviceID, channel_number),
    "map": lambda: mapHandler(message_from_id, deviceID, channel_number, message, snr, rssi, hop),
    "messages": lambda: handle_messages(message, deviceID, channel_number, msg_history, isDM),
    "moon": lambda: handle_moon(message_from_id, deviceID, channel_number),
    "motd": lambda: handle_motd(message, message_from_id, isDM),
    "mwx": lambda: handle_mwx(message_from_id, deviceID, channel_number),
    "nodes": lambda: handle_nodes(message, message_from_id, deviceID, isDM),
    "ping": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "pinging": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "pong": lambda: "🏓PING!!🛜",
    "readnews": lambda: handleNews(message_from_id, deviceID, message, isDM),
    "readrss": lambda: get_rss_feed(message),
    "riverflow": lambda: handle_riverFlow(message, message_from_id, deviceID),
    "rlist": lambda: handle_repeaterQuery(message_from_id, deviceID, channel_number),
    "satpass": lambda: handle_satpass(message_from_id, deviceID, message),
    "share": lambda: handle_share(message, snr, rssi, hop, pkiStatus, message_from_id, channel_number, deviceID, isDM),
    "sitrep": lambda: handle_lheard(message, message_from_id, deviceID, isDM),
    "solar": lambda: drap_xray_conditions() + "\n" + solar_conditions() + "\n" + get_noaa_scales_summary(),
    "sun": lambda: handle_sun(message_from_id, deviceID, channel_number),
    "sysinfo": lambda: sysinfo(message, message_from_id, deviceID, isDM),
    "test": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "testing": lambda: handle_ping(message_from_id, deviceID, message, hop, snr, rssi, isDM, channel_number),
    "tide": lambda: handle_tide(message_from_id, deviceID, channel_number),
    "valert": lambda: get_volcano_usgs(),
    "verse": lambda: read_verse(),
    "whereami": lambda: handle_whereami(message_from_id, deviceID, channel_number),
    "whoami": lambda: handle_whoami(message_from_id, deviceID, hop, snr, rssi, pkiStatus),
    "whois": lambda: handle_whois(message, deviceID, channel_number, message_from_id),
    "wiki": lambda: handle_wiki(message, isDM),
    "wx": lambda: handle_wxc(message_from_id, deviceID, 'wx'),
    "wxa": lambda: handle_wxalert(message_from_id, deviceID, message),
    "wxalert": lambda: handle_wxalert(message_from_id, deviceID, message),
    "x:": lambda: handleShellCmd(message, message_from_id, channel_number, isDM, deviceID),
    "wxc": lambda: handle_wxc(message_from_id, deviceID, 'wxc'),
    "wxfind": lambda: handle_wxfind(message_from_id, deviceID, message),
    "wxcall": lambda: handle_wxcall(message_from_id, deviceID, message),
    "mynodecallsign": lambda: handle_mynodecallsign(message_from_id, deviceID, message),
    "📍": lambda: handle_whoami(message_from_id, deviceID, hop, snr, rssi, pkiStatus),
    "🔔": lambda: handle_alertBell(message_from_id, deviceID, message),
    "🐝": lambda: read_file("bee.txt", True),
    # any value from system.py:trap_list_emergency will trigger the emergency function
    "112": lambda: handle_emergency(message_from_id, deviceID, message),
    "911": lambda: handle_emergency(message_from_id, deviceID, message),
    "999": lambda: handle_emergency(message_from_id, deviceID, message),
    "ambulance": lambda: handle_emergency(message_from_id, deviceID, message),
    "emergency": lambda: handle_emergency(message_from_id, deviceID, message),
    "fire": lambda: handle_emergency(message_from_id, deviceID, message),
    "police": lambda: handle_emergency(message_from_id, deviceID, message),
    "rescue": lambda: handle_emergency(message_from_id, deviceID, message),
    }

    # set the command handler
    command_handler = default_commands
    cmds = [] # list to hold the commands found in the message
    # check the message for commands words list, processed after system.messageTrap
    for key in command_handler:
        word = message_lower.split(' ')
        if my_settings.cmdBang:
            # strip the !
            if word[0].startswith("!"):
                word[0] = word[0][1:]
        if key in word:
            # append all the commands found in the message to the cmds list
            cmds.append({'cmd': key, 'index': message_lower.index(key)})
        # check for commands with a question mark
        if key + "?" in word:
            # append all the commands found in the message to the cmds list
            cmds.append({'cmd': key, 'index': message_lower.index(key)})

    if len(cmds) > 0:
        # sort the commands by index value
        cmds = sorted(cmds, key=lambda k: k['index'])
    
        # Check if user is already playing a game
        playing, game = False, "None"
    
        # Block restricted commands if not DM
        if (cmds[0]['cmd'] in restrictedCommands and not isDM) or (cmds[0]['cmd'] in restrictedCommands and playing) or playing:
            logger.debug(f"System: Bot restricted Command:{cmds[0]['cmd']} From: {get_name_from_number(message_from_id)} isDM:{isDM} playing:{playing}")
            if playing:
                bot_response = f"🤖You are already playing {game}, finish that first."
            else:
                bot_response = restrictedResponse
        else:
            logger.debug(f"System: Bot detected Commands:{cmds} From: {get_name_from_number(message_from_id)} isDM:{isDM} playing:{playing}")
            # run the first command after sorting
            bot_response = command_handler[cmds[0]['cmd']]()
            # append the command to the cmdHistory list for lheard and history
            if len(cmdHistory) > 50:
                cmdHistory.pop(0)
            cmdHistory.append({'nodeID': message_from_id, 'cmd':  cmds[0]['cmd'], 'time': time.time()})

    if isDM and my_settings.bbs_enabled and has_pending_mail_alert(message_from_id):
        mark_mail_alerted(message_from_id)
        bot_response = f"📬 You have mail waiting. Reply CM to check.\n{bot_response}"

    return bot_response

def handle_cmd(message, message_from_id, deviceID):
    # why CMD? its just a command list. a terminal would normally use "Help"
    # I didnt want to invoke the word "help" in Meshtastic due to its possible emergency use
    if " " in message and message.split(" ")[1] in trap_list:
        return "🤖 just use the commands directly in chat"
    return help_message

def handle_share(message, snr, rssi, hop, pkiStatus, message_from_id, channel_number, deviceID, isDM):
    # "share <cmd>" runs <cmd> and forces the reply into the issuing channel,
    # overriding useDMForResponse/antiSpam DM routing for this one reply only.
    if isDM:
        return "🤖 'share' needs to be issued in a channel."

    words = message.split(' ')
    if my_settings.cmdBang and words and words[0].startswith('!'):
        words[0] = words[0][1:]
    if not words or words[0].lower() != 'share' or len(words) < 2:
        return "🤖 Usage: share <command>, e.g. share wx"

    sub_message = ' '.join(words[1:]).strip()
    sub_word = sub_message.lower().split(' ')[0].rstrip('?')
    # trap_list check ensures the command is actually enabled in this config,
    # not just on the static whitelist (disabled features' handlers may be unimported)
    if sub_word not in shareableCommands or sub_word not in trap_list:
        return "🤖 That command can't be shared to a channel."

    sub_response = auto_response(sub_message, snr, rssi, hop, pkiStatus, message_from_id, channel_number, deviceID, isDM)
    send_message(sub_response, channel_number, 0, deviceID)
    return ""

def isPlayingGame(message_from_id):
    # Games removed from mesh-ham-bot
    return False, "None"

def checkPlayingGame(message_from_id, message_string, rxNode, channel_number):
    # Games removed from mesh-ham-bot
    return False

def handle_ping(message_from_id, deviceID,  message, hop, snr, rssi, isDM, channel_number):
    global multiPing
    myNodeNum = globals().get(f'myNodeNum{deviceID}', 777)
    if  "?" in message and isDM:
        pingHelp = "🤖Ping Command Help:\n" \
        "🏓 Send 'ping' or 'ack' or 'test' to get a response.\n" \
        "🏓 Send 'ping <number>' to get multiple pings in DM\n" \
        "🏓 ping @USERID to send a Joke from the bot"
        return pingHelp
    
    msg = ""
    type = ''

    if "ping" in message.lower():
        msg = "🏓PONG"
        type = "🏓PING"
    elif "test" in message.lower() or "testing" in message.lower():
        msg = random.choice(["🎙Testing 1,2,3", "🎙Testing",\
                             "🎙Testing, testing",\
                             "🎙Ah-wun, ah-two...", "🎙Is this thing on?",\
                             "🎙Roger that!",])
        type = "🎙TEST"
    elif "ack" in message.lower():
        msg = random.choice(["✋ACK-ACK!\n", "✋Ack to you!\n"])
        type = "✋ACK"
    elif "cqcq" in message.lower() or "cq" in message.lower() or "cqcqcq" in message.lower():
        myname = get_name_from_number(myNodeNum, 'short', deviceID)
        msg = f"QSP QSL OM DE  {myname}   K\n"
    else:
        msg = "🔊 Can you hear me now?"

    # append SNR/RSSI or hop info
    if hop.startswith("Gateway") or hop.startswith("MQTT"):
        msg += " [GW]"
    elif hop.startswith("Direct"):
        msg += " [RF]"
    else:
        #flood
        msg += " [F]"
    
    if (float(snr) != 0 or float(rssi) != 0) and "Hop" not in hop:
        msg += f"\nSNR:{snr} RSSI:{rssi}"
    elif "Hop" in hop:
        # janky, remove the words Gateway or MQTT if present
        hop = hop.replace("Gateway", "").replace("Direct", "").replace("MQTT", "").strip()
        msg += f"\n{hop} "

    if "@" in message:
        msg = msg + " @" + message.split("@")[1]
        type = type + " @" + message.split("@")[1]

        # check for ping to @nodeID and allow BBS DM
        toNode = message.split("@")[1].strip().split(" ")[0]
        # validate toNode is shortname
        if len(toNode) <= 4:
            toNode = get_num_from_short_name(toNode, deviceID)
            if toNode and isinstance(toNode, int) and toNode != 0:
                if my_settings.bbs_enabled:
                    logger.debug(f"System: Sending joke as BBS mail to @{toNode} from {get_name_from_number(message_from_id, 'short', deviceID)}")
                    short_name = get_name_from_number(message_from_id, 'short', deviceID)
                    add_mail(str(message_from_id), short_name, str(toNode), "Joke for you!", tell_joke())
                    send_message(f"📬 New mail from {short_name}. Reply CM to check.", 0, toNode, deviceID)
                    return f"Joke sent to {get_name_from_number(toNode, 'short', deviceID)} via BBS mail!"

    elif "#" in message:
        msg = msg + " #" + message.split("#")[1]
        type = type + " #" + message.split("#")[1]

    # check for multi ping request
    if " " in message:
        # if stop multi ping
        if "stop" in message.lower():
            for i in range(0, len(multiPingList)):
                if multiPingList[i].get('message_from_id') == message_from_id:
                    multiPingList.pop(i)
                    msg = "🛑 auto-ping"

        # if 3 or more entries (2 or more active), throttle the multi-ping for congestion
        if len(multiPingList) > 2:
            msg = "🚫⛔️ auto-ping, service busy. ⏳Try again soon."
            pingCount = -1
        else:
            # set inital pingCount
            try:
                pingCount = int(message.split(" ")[1])
                if pingCount == 123 or pingCount == 1234:
                    pingCount =  1
                elif not my_settings.autoPingInChannel and not isDM:
                    # no autoping in channels
                    pingCount = 1

                if pingCount > 51 and pingCount <= 101:
                    pingCount = 50
                if pingCount > 800:
                    ban_hammer(message_from_id, deviceID, reason="Excessive auto-ping request")
                    return "🚫⛔️auto-ping request denied."
            except ValueError:
                pingCount = -1
    
        if pingCount > 1:
            multiPingList.append({'message_from_id': message_from_id, 'count': pingCount + 1, 'type': type, 'deviceID': deviceID, 'channel_number': channel_number, 'startCount': pingCount})
            logger.info(f"System: Starting auto-ping of type {type} for {pingCount} pings to {get_name_from_number(message_from_id, 'short', deviceID)}")
            if type == "🎙TEST":
                msg = f"🛜Initalizing BufferTest, using chunks of about {int(maxBuffer // pingCount)}, max length {maxBuffer} in {pingCount} messages"
            else:
                msg = f"🚦Initalizing {pingCount} auto-ping"

    # if not a DM add the username to the beginning of msg
    if not my_settings.useDMForResponse and not isDM:
        msg = "@" + get_name_from_number(message_from_id, 'short', deviceID) + " " + msg
            
    return msg

def handle_alertBell(message_from_id, deviceID, message):
    msg = ["the only prescription is more 🐮🔔🐄🛎️", "what this 🤖 needs is more 🐮🔔🐄🛎️", "🎤ring my bell🛎️🔔🎶"]
    return random.choice(msg)

def handle_emergency(message_from_id, deviceID, message):
    myNodeNum = globals().get(f'myNodeNum{deviceID}', 777)
    # if user is banned return
    if my_settings.bbs_enabled and is_banned(message_from_id):
        # silent discard
        hammer_value = ban_hammer(message_from_id, deviceID, reason="Emergency Alert from banned node")
        logger.warning(f"System: {message_from_id} on spam list, no emergency responder alert sent. Ban hammer value: {hammer_value}")
        return ''
    # trgger alert to emergency_responder_alert_channel
    if message_from_id != 0:
        nodeLocation = get_node_location(message_from_id, deviceID)
        # if default location is returned set to Unknown
        if nodeLocation[0] == my_settings.latitudeValue and nodeLocation[1] == my_settings.longitudeValue:
            nodeLocation = ["?", "?"]
        nodeInfo = f"{get_name_from_number(message_from_id, 'short', deviceID)} detected by {get_name_from_number(myNodeNum, 'short', deviceID)} lastGPS {nodeLocation[0]}, {nodeLocation[1]}"
        msg = f"🔔🚨Intercepted Possible Emergency Assistance needed for: {nodeInfo}"
        # alert the emergency_responder_alert_channel
        send_message(msg, my_settings.emergency_responder_alert_channel, 0, my_settings.emergency_responder_alert_interface)
        logger.warning(f"System: {message_from_id} Emergency Assistance Requested in {message}")
        return my_settings.EMERGENCY_RESPONSE

def handle_motd(message, message_from_id, isDM):
    msg = my_settings.MOTD
    isAdmin = isNodeAdmin(message_from_id)
    if  "?" in message:
        msg = "Message of the day, set with 'motd $ HelloWorld!'"
    elif "$" in message and isAdmin:
        my_settings.MOTD = message.split("$")[1]
        my_settings.MOTD = my_settings.MOTD.rstrip()
        logger.debug(f"System: {message_from_id} temporarly changed my_settings.MOTD: {my_settings.MOTD}")
        msg = "my_settings.MOTD changed to: " + my_settings.MOTD
    return msg

def handle_echo(message, message_from_id, deviceID, isDM, channel_number):
    # Check if user is admin
    isAdmin = isNodeAdmin(message_from_id)

    # Admin extended syntax: echo <string> c=<channel> d=<device>
    if isAdmin and message.strip().lower().startswith("echo ") and not message.strip().endswith("?"):
        msg_to_echo = message.split(" ", 1)[1]
        target_channel = channel_number
        target_device = deviceID

        # Split into words to find c= and d=, but preserve spaces in message
        words = msg_to_echo.split()
        new_words = []
        for w in words:
            if w.startswith("c=") and w[2:].isdigit():
                target_channel = int(w[2:])
            elif w.startswith("d=") and w[2:].isdigit():
                target_device = int(w[2:])
            else:
                new_words.append(w)
        msg_to_echo = " ".join(new_words).strip()
        # Replace motd/MOTD with the current MOTD from settings
        msg_to_echo = " ".join(my_settings.MOTD if w.lower() == "motd" else w for w in msg_to_echo.split())
        # Replace welcome! with the current welcome_message from settings
        msg_to_echo = " ".join(my_settings.welcome_message if w.lower() == "welcome!" else w for w in msg_to_echo.split())

        # Send echo to specified channel/device
        logger.debug(f"System: Admin Echo to channel {target_channel} device {target_device} message: {msg_to_echo}")
        time.sleep(splitDelay) # throttle for 2x send
        send_message(msg_to_echo, target_channel, 0, target_device)
        time.sleep(splitDelay) # throttle for 2x send
        return f"🐬echoed to channel {target_channel} device {target_device}"

    # dev echoBinary off
    echoBinary = False
    if echoBinary:
        try:
            port_num = 256
            synch_word = b"echo:"
            parts = message.split("echo ", 1)
            if len(parts) > 1 and parts[1].strip() != "":
                msg_to_echo = parts[1]
                raw_bytes = synch_word + msg_to_echo.encode('utf-8')
                send_raw_bytes(message_from_id, raw_bytes, nodeInt=deviceID, channel=channel_number, portnum=port_num)
                return f"Sent binary echo message to {message_from_id} to {port_num} on channel {channel_number} device {deviceID}"
        except Exception as e:
            logger.error(f"System: Echo Exception {e}")

    if "?" in message:
        isAdmin = isNodeAdmin(message_from_id)
        if isAdmin:
            return (
                "Admin usage: echo <message> c=<channel> d=<device>\n"
                "Example: echo Hello world c=1 d=2"
            )
        return "command returns your message back to you. Example: echo Hello World"

    # process normal echo back to user
    elif message.strip().lower().startswith("echo "):
        parts = message.split("echo ", 1)
        if len(parts) > 1 and parts[1].strip() != "":
            echo_msg = parts[1]
            if channel_number != my_settings.echoChannel and not isDM:
                echo_msg = "@" + get_name_from_number(message_from_id, 'short', deviceID) + " " + echo_msg
            return echo_msg
        else:
            return "Please provide a message to echo back to you. Example: echo Hello World"
    return "🐬echo.."

def handle_wxalert(message_from_id, deviceID, message):
    if my_settings.use_meteo_wxApi:
        return "wxalert is not supported"
    else:
        result = resolve_location_with_disclosure(message_from_id, deviceID)
        if result is None:
            return my_settings.NO_GPS_OR_CALLSIGN
        lat, lon, disclosure = result
        if "wxalert" in message:
            # Detailed weather alert
            weatherAlert = getActiveWeatherAlertsDetailNOAA(str(lat), str(lon))
        else:
            weatherAlert = getWeatherAlertsNOAA(str(lat), str(lon))

        if my_settings.NO_ALERTS not in weatherAlert:
            weatherAlert = weatherAlert[0]
        if disclosure:
            weatherAlert = disclosure + "\n" + weatherAlert
        return weatherAlert

def _get_weather_for_location(lat, lon, cmd, days=None):
    # Shared NOAA/Open-Meteo source selection, used by handle_wxc, handle_wxfind, handle_wxcall
    if my_settings.use_meteo_wxApi and not "wxc" in cmd and not use_metric:
        return get_wx_meteo(str(lat), str(lon))
    elif my_settings.use_meteo_wxApi:
        return get_wx_meteo(str(lat), str(lon), 1)
    elif not my_settings.use_meteo_wxApi and "wxc" in cmd or my_settings.use_metric:
        return get_NOAAweather(str(lat), str(lon), 1, report_days=days)
    else:
        return get_NOAAweather(str(lat), str(lon), report_days=days)

def handle_wxc(message_from_id, deviceID, cmd, days=None, vox=False):
    # Weather from NOAA or Open-Meteo
    result = resolve_location_with_disclosure(message_from_id, deviceID)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    weather = _get_weather_for_location(lat, lon, cmd, days)
    if disclosure:
        return disclosure + "\n" + weather
    return weather

def handle_wxfind(message_from_id, deviceID, message, cmd='wx'):
    # Weather for a city/state/zip lookup, for nodes with no location on file
    parts = message.strip().split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or "?" in message:
        return "Usage: wxfind <city, state or zip code>, e.g. wxfind 90210"
    query = parts[1].strip()
    coords = geocode_location(query)
    if coords == my_settings.ERROR_FETCHING_DATA:
        return my_settings.ERROR_FETCHING_DATA
    if coords is None:
        return f"Could not find '{query}'. Try a zip code or 'City, State'."
    lat, lon = coords
    return _get_weather_for_location(lat, lon, cmd)

def handle_wxcall(message_from_id, deviceID, message, cmd='wx'):
    # Weather for a US amateur radio callsign's address of record (via callook.info/FCC ULS)
    parts = message.strip().split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or "?" in message:
        return "Usage: wxcall <callsign>, e.g. wxcall W1AW"
    callsign = parts[1].strip()
    result = get_callsign_location(callsign)
    if result == my_settings.ERROR_FETCHING_DATA:
        return my_settings.ERROR_FETCHING_DATA
    if result is None:
        return f"Callsign '{callsign.upper()}' not found in the FCC database."
    lat, lon, city_state = result
    weather = _get_weather_for_location(lat, lon, cmd)
    if city_state:
        return f"{callsign.upper()} QTH: {city_state}\n{weather}"
    return weather

def handle_mynodecallsign(message_from_id, deviceID, message):
    # Self-service callsign override, used as a location fallback when this node has no GPS fix
    parts = message.strip().split(None, 1)
    if len(parts) < 2 or not parts[1].strip() or "?" in message:
        return "Usage: mynodecallsign <callsign>, e.g. mynodecallsign W1AW"
    callsign = parts[1].strip()
    result = get_callsign_location(callsign)
    if result == my_settings.ERROR_FETCHING_DATA:
        return my_settings.ERROR_FETCHING_DATA
    if result is None:
        return f"Callsign '{callsign.upper()}' not found in the FCC database."
    _, _, city_state = result
    set_callsign(message_from_id, callsign.upper(), 'override')
    if city_state:
        return f"✅ Callsign set to {callsign.upper()} ({city_state}). Location commands will use this QTH when you have no GPS fix."
    return f"✅ Callsign set to {callsign.upper()}. Location commands will use this QTH when you have no GPS fix."

def handle_riverFlow(message, message_from_id, deviceID, vox=False):
    # River Flow from NOAA or Open-Meteo
    disclosure = None
    if vox:
        location = (my_settings.latitudeValue, my_settings.longitudeValue)
        message = "riverflow"
    else:
        result = resolve_location_with_disclosure(message_from_id, deviceID)
        if result is None:
            return my_settings.NO_GPS_OR_CALLSIGN
        location = (result[0], result[1])
        disclosure = result[2]
    msg_lower = message.lower()
    if "riverflow " in msg_lower:
        user_input = msg_lower.split("riverflow ", 1)[1].strip()
        if user_input:
            userRiver = [r.strip() for r in user_input.split(",") if r.strip()]
        else:
            userRiver = riverListDefault
    else:
        userRiver = riverListDefault

    if use_meteo_wxApi:
        result_msg = get_flood_openmeteo(location[0], location[1])
    else:
        if not userRiver:
            return "No river gauge configured. Provide a NOAA/NWPS gauge ID: riverflow <gauge id>[,<gauge id2>...]"
        result_msg = ""
        for river in userRiver:
            result_msg += get_flood_noaa(location[0], location[1], river)
    if disclosure:
        return disclosure + "\n" + result_msg
    return result_msg

def handle_emergency_alerts(message, message_from_id, deviceID):
    if my_settings.enableDEalerts:
        # nina Alerts
        return get_nina_alerts()
    result = resolve_location_with_disclosure(message_from_id, deviceID)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    if message.lower().startswith("ealert"):
        # Detailed alert FEMA
        alert = getIpawsAlert(str(lat), str(lon))
    else:
        # Headlines only FEMA
        alert = getIpawsAlert(str(lat), str(lon), shortAlerts=True)
    if disclosure:
        return disclosure + "\n" + alert
    return alert

def handleEarthquake(message, message_from_id, deviceID):
    if "earthquake" in message.lower():
        result = resolve_location_with_disclosure(message_from_id, deviceID)
        if result is None:
            return my_settings.NO_GPS_OR_CALLSIGN
        lat, lon, disclosure = result
        quake = checkUSGSEarthQuake(str(lat), str(lon))
        if disclosure:
            return disclosure + "\n" + quake
        return quake

def handleNews(message_from_id, deviceID, message, isDM):
    news = ''
    if "?" in message.lower():
        return "returns the news. Add a source e.g. 📰readnews mesh"
    elif "readnews" in message.lower():
        source = message.lower().replace("readnews", "").strip()
        if source:
            # if news source is provided pass that to read_news()
            if my_settings.news_block_mode:
                news = read_news(source=source, news_block_mode=True)
            elif my_settings.news_random_line_only:
                news = read_news(source=source, random_line_only=True)
            else:
                news = read_news(source=source)
        else:
            # no source provided, use news.txt
            if my_settings.news_block_mode:
                news = read_news(news_block_mode=True)
            elif my_settings.news_random_line_only:
                news = read_news(random_line_only=True)
            else:
                news = read_news()

    if news:
        # if not a DM add the username to the beginning of msg
        if not my_settings.useDMForResponse and not isDM:
            news = "@" + get_name_from_number(message_from_id, 'short', deviceID) + " " + news
        return news
    else:
        return "No news for you!"
    
def handle_howfar(message, message_from_id, deviceID, isDM):
    msg = ''
    location = get_node_location(message_from_id, deviceID)
    lat = location[0]
    lon = location[1]
    # if ? in message
    if "?" in message.lower():
        return "command returns the distance you have traveled since your last HowFar-command. Add 'reset' to reset your starting point."
    
    # if no GPS location return
    if lat == my_settings.latitudeValue and lon == my_settings.longitudeValue:
        logger.debug(f"System: HowFar: No GPS location for {message_from_id}")
        return "No GPS location available"
    
    if "reset" in message.lower():
        msg = distance(lat,lon,message_from_id, reset=True)
    else:
        msg = distance(lat,lon,message_from_id)
    
    # if not a DM add the username to the beginning of msg
    if not my_settings.useDMForResponse and not isDM:
        msg = "@" + get_name_from_number(message_from_id, 'short', deviceID) + " " + msg

    return msg

def handle_howtall(message, message_from_id, deviceID, isDM):
    msg = ''
    location = get_node_location(message_from_id, deviceID)
    lat = location[0]
    lon = location[1]
    if lat == my_settings.latitudeValue and lon == my_settings.longitudeValue:
        # add guessing tot he msg
        msg += "Guessing:"
    if my_settings.use_metric:
            measure = "meters" 
    else:
            measure = "feet"
    # if ? in message
    if "?" in message.lower():
        return f"command estimates your height based on the shadow length you provide in {measure}. Example: howtall 5.5"
    # get the shadow length from the message split after howtall
    try:
        shadow_length = float(message.lower().split("howtall ")[1].split(" ")[0])
    except (IndexError, ValueError):
        return f"Please provide a shadow length in {measure} example: howtall 5.5"

    # get data
    msg += measureHeight(lat, lon, shadow_length)

    # if data has NO_ALERTS return help
    if my_settings.NO_ALERTS in msg:
        return f"Please provide a shadow length in {measure} example: howtall 5.5"
    
    return msg

def handle_wiki(message, isDM):
    # location = get_node_location(message_from_id, deviceID)
    msg = "Wikipedia search function. \nUsage example:📲wiki travelling gnome"
    if "?" in message.lower():
        return msg
    if "wiki" in message.lower():
        parts = message.split(" ", 1)
        if len(parts) < 2 or not parts[1].strip():
            return "Please add a search term example:📲wiki travelling gnome"
        search = parts[1].strip()
        if search:
            return get_wikipedia_summary(search)
        
    return msg

# Runtime Variables for LLM
llmRunCounter = 0
llmTotalRuntime = []
llmLocationTable = [{'nodeID': 1234567890, 'location': 'No Location'},]

# Runtime safety caps to avoid unbounded growth on long-lived systems.
MAX_SEEN_NODES = 5000
MAX_LLM_LOCATION_ENTRIES = 50
MAX_LLM_RUNTIME_SAMPLES = 50

def handle_satpass(message_from_id, deviceID, message='', vox=False):
    disclosure = None
    if vox:
        location = (my_settings.latitudeValue, my_settings.longitudeValue)
        message = 'satpass'
    else:
        result = resolve_location_with_disclosure(message_from_id, deviceID)
        if result is None:
            return my_settings.NO_GPS_OR_CALLSIGN
        location = (result[0], result[1])
        disclosure = result[2]
    passes = ''
    satList = my_settings.satListConfig
    message = message.lower()

    # check api_throttle
    check_throttle = api_throttle(message_from_id, deviceID, apiName='satpass')
    if check_throttle:
        return check_throttle

    # if user has a NORAD ID in the message
    if "satpass " in message:
        try:
            userList = message.split("satpass ")[1].split(" ")[0]
            #split userList and make into satList overrided the config.ini satList
            satList = userList.split(",")
        except Exception as e:
            logger.error(f"Exception occurred: {e}")
            return "example use:🛰️satpass 25544,33591"

    # Detailed satellite pass
    for bird in satList:
        satPass = getNextSatellitePass(bird, str(location[0]), str(location[1]))
        if satPass:
            # append to passes
            passes = passes + satPass + "\n"
    # remove the last newline
    passes = passes[:-1]

    if passes == '':
        passes = "No 🛰️ anytime soon"
    if disclosure:
        return disclosure + "\n" + passes
    return passes
        
# handle_llm removed - LLM not included in mesh-ham-bot
# handle_bbspost, handle_bbsread, handle_bbsdelete removed -- replaced by modules/bbs/
def handle_messages(message, deviceID, channel_number, msg_history, isDM):
    if  "?" in message and isDM:
        return message.split("?")[0].title() + " command returns the last " + str(storeFlimit) + " messages sent on a channel."
    else:
        # Filter messages for this device/channel
        filtered_msgs = [
            msgH for msgH in msg_history
            if msgH[4] == deviceID and msgH[2] == channel_number
        ]

        # Most recent N entries, newest first
        filtered_msgs = filtered_msgs[-storeFlimit:][::-1]
        if my_settings.reverseSF:
            # reverse that
            filtered_msgs = filtered_msgs[::-1]

        response = ""
        header = f"📨Msgs:\n"
        for msgH in filtered_msgs:
            ts = msgH[3].split()[-1]
            new_line = f"\n[{ts}] {msgH[0]}: {msgH[1]}"
            test_response = response + new_line
            if len(test_response.encode('utf-8')) > maxBuffer:
                # Truncate message if needed
                msg_text = msgH[1]
                truncated = False
                trunc_marker = "..."
                while len(msg_text) > 0 and len((response + f"\n[{ts}] {msgH[0]}: {msg_text}{trunc_marker}").encode('utf-8')) > maxBuffer:
                    msg_text = msg_text[:-1]
                    truncated = True
                if len(msg_text) > 10:
                    if truncated:
                        response += f"\n[{ts}] {msgH[0]}: {msg_text}{trunc_marker}"
                    else:
                        response += f"\n[{ts}] {msgH[0]}: {msg_text}"
                    break
                continue
            else:
                response += new_line

        if len(response) > 0:
            return header + response
        else:
            return "No 📭messages in history"

def handle_sun(message_from_id, deviceID, channel_number, vox=False):
    if vox:
        # return a default message if vox is enabled
        return get_sun(str(my_settings.latitudeValue), str(my_settings.longitudeValue))
    result = resolve_location_with_disclosure(message_from_id, deviceID, channel_number)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    sun_info = get_sun(str(lat), str(lon))
    if disclosure:
        return disclosure + "\n" + sun_info
    return sun_info

def sysinfo(message, message_from_id, deviceID, isDM):
    if "?" in message:
        return "sysinfo command returns system information."
    else:
        if enable_runShellCmd and file_monitor_enabled:
            # get the system information from the shell script
            # this is an example of how to run a shell script and return the data
            shellData = call_external_script('', "script/sysEnv.sh")
            # check if the script returned data
            if shellData == "" or shellData == None:
                # no data returned from the script
                shellData = "shell script data missing"
            # if not an admin remove any line in the shellData that had 'IP:' in it
            if (not isNodeAdmin(message_from_id)) or (not isDM):
                shell_lines = shellData.splitlines()
                filtered_lines = [line for line in shell_lines if 'IP:' not in line]
                shellData = "\n".join(filtered_lines)
            return get_sysinfo(message_from_id, deviceID) + "\n" + shellData.rstrip()
        else:
            return get_sysinfo(message_from_id, deviceID)

def handle_lheard(message, nodeid, deviceID, isDM):
    if  "?" in message and isDM:
        return message.split("?")[0].title() + " command returns a list of the nodes that have been heard recently"

    # display last heard nodes add to response
    bot_response = "Last Heard\n"
    bot_response += str(get_node_list(1))

    # show last users of the bot with the cmdHistory list
    history = handle_history(message, nodeid, deviceID, isDM, lheard=True)
    if history:
        bot_response += f'LastSeen\n{history}'
    else:
        # trim the last \n
        bot_response = bot_response[:-1]

    # get count of nodes heard
    bot_response += f"\n👀In Mesh: {len(seenNodes)}"

    # bot_response += getNodeTelemetry(deviceID)
    return bot_response

def handle_nodes(message, nodeid, deviceID, isDM):
    if "?" in message and isDM:
        return message.split("?")[0].title() + " command returns a list of all nodes the bot knows about, sorted by last heard"

    nodes = get_all_nodes(deviceID)
    if not nodes:
        return "No nodes known."

    bot_response = f"Known Nodes: {len(nodes)}\n"
    for long_name, short_name, hex_id, battery, last_heard in nodes:
        battery_str = f"{battery}%" if battery is not None else "?%"
        if last_heard:
            ago_str = f"{getPrettyTime(time.time() - last_heard)} ago"
        else:
            ago_str = "never"
        bot_response += f"{long_name}, {short_name}, {hex_id}, {battery_str}, {ago_str}\n"

    return bot_response.rstrip()

def handle_history(message, nodeid, deviceID, isDM, lheard=False):
    global cmdHistory, lheardCmdIgnoreNode, bbs_admin_list
    msg = ""
    buffer = []

    if  "?" in message and isDM:
        return message.split("?")[0].title() + " command returns a list of commands received."

    # show the last commands from the user to the bot
    if not lheard:
        for i in range(len(cmdHistory)):
            cmdTime = round((time.time() - cmdHistory[i]['time']) / 600) * 5
            prettyTime = getPrettyTime(cmdTime)

            # history display output
            if isNodeAdmin(nodeid) and normalize_node_id(cmdHistory[i]['nodeID']) not in lheardCmdIgnoreNode:
                buffer.append((get_name_from_number(cmdHistory[i]['nodeID'], 'short', deviceID), cmdHistory[i]['cmd'], prettyTime))
            elif cmdHistory[i]['nodeID'] == nodeid and normalize_node_id(cmdHistory[i]['nodeID']) not in lheardCmdIgnoreNode:
                buffer.append((get_name_from_number(nodeid, 'short', deviceID), cmdHistory[i]['cmd'], prettyTime))
        # message for output of the last commands
        buffer.reverse()
        # only return the last 4 commands
        if len(buffer) > 4:
            buffer = buffer[-4:]
        # create the message from the buffer list
        for i in range(0, len(buffer)):
            msg += f"{buffer[i][0]}: {buffer[i][1]} :{buffer[i][2]} ago"
            if i < len(buffer) - 1:
                msg += "\n" # add a new line if not the last line
    else:
        # sort the cmdHistory list by time, return the username and time into a new list which used for display
        for i in range(len(cmdHistory)):
            cmdTime = round((time.time() - cmdHistory[i]['time']) / 600) * 5
            prettyTime = getPrettyTime(cmdTime)

            if normalize_node_id(cmdHistory[i]['nodeID']) not in lheardCmdIgnoreNode:
                # add line to a new list for display
                nodeName = get_name_from_number(cmdHistory[i]['nodeID'], 'short', deviceID)
                if not any(d[0] == nodeName for d in buffer):
                    buffer.append((nodeName, prettyTime))
                else:
                    # update the time for the node in the buffer for the latest time in cmdHistory
                    for j in range(len(buffer)):
                        if buffer[j][0] == nodeName:
                            buffer[j] = (nodeName, prettyTime)

        # create the message from the buffer list
        buffer.reverse() # reverse the list to show the latest first
        for i in range(0, len(buffer)):
            msg += f"{buffer[i][0]}, {buffer[i][1]} ago"
            if i < len(buffer) - 1:
                msg += "\n" # add a new line if not the last line
            if i > 3:
                break # only return the last 4 nodes
    return msg

def handle_whereami(message_from_id, deviceID, channel_number):
    result = resolve_location_with_disclosure(message_from_id, deviceID, channel_number)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    # check api_throttle
    check_throttle = api_throttle(message_from_id, deviceID, apiName='whereami')
    if check_throttle:
        return check_throttle
    whereIam = where_am_i(str(lat), str(lon))
    if disclosure:
        return disclosure + "\n" + whereIam
    return whereIam

def handle_grid(message_from_id, deviceID, channel_number):
    result = resolve_location_with_disclosure(message_from_id, deviceID, channel_number)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    grid = get_grid_square(str(lat), str(lon))
    if disclosure:
        return disclosure + "\n" + grid
    return grid

def handle_repeaterQuery(message_from_id, deviceID, channel_number):
    result = resolve_location_with_disclosure(message_from_id, deviceID, channel_number)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    # check api_throttle
    check_throttle = api_throttle(message_from_id, deviceID, apiName='repeaterQuery')
    if check_throttle:
        return check_throttle
    if repeater_lookup == "rbook":
        repeaters = getRepeaterBook(str(lat), str(lon))
    elif repeater_lookup == "artsci":
        repeaters = getArtSciRepeaters(str(lat), str(lon))
    else:
        return "Repeater lookup not enabled"
    if disclosure:
        return disclosure + "\n" + repeaters
    return repeaters

def handle_tide(message_from_id, deviceID, channel_number, vox=False):
    if vox:
        return get_NOAAtide(str(my_settings.latitudeValue), str(my_settings.longitudeValue))
    result = resolve_location_with_disclosure(message_from_id, deviceID, channel_number)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    tide = get_NOAAtide(str(lat), str(lon))
    if disclosure:
        return disclosure + "\n" + tide
    return tide

def handle_moon(message_from_id, deviceID, channel_number, vox=False):
    if vox:
        return get_moon(str(my_settings.latitudeValue), str(my_settings.longitudeValue))
    result = resolve_location_with_disclosure(message_from_id, deviceID, channel_number)
    if result is None:
        return my_settings.NO_GPS_OR_CALLSIGN
    lat, lon, disclosure = result
    moon_info = get_moon(str(lat), str(lon))
    if disclosure:
        return disclosure + "\n" + moon_info
    return moon_info

def handle_whoami(message_from_id, deviceID, hop, snr, rssi, pkiStatus):
    try:
        loc = []
        msg = "You are " + str(message_from_id) + " AKA " +\
                str(get_name_from_number(message_from_id, 'long', deviceID) + " AKA, " +\
                str(get_name_from_number(message_from_id, 'short', deviceID)) + " AKA, " +\
                str(decimal_to_hex(message_from_id)) + f"\n")
        msg += f"I see the signal strength is {rssi} and the SNR is {snr} with hop count of {hop}"
        if pkiStatus[1] != 'ABC':
            msg += f"\nYour PKI bit is {pkiStatus[0]} pubKey: {pkiStatus[1]}"

        loc = get_node_location(message_from_id, deviceID)
        if loc != [my_settings.latitudeValue, my_settings.longitudeValue]:
            msg += f"\nYou are at: lat:{loc[0]} lon:{loc[1]}"

            # check the positionMetadata for nodeID and get metadata
            if positionMetadata and message_from_id in positionMetadata:
                metadata = positionMetadata[message_from_id]
                msg += f" alt:{metadata.get('altitude')}, speed:{metadata.get('groundSpeed')} bit:{metadata.get('precisionBits')}"
    except Exception as e:
        logger.error(f"System: Error in whoami: {e}")
        msg = "Error in whoami"
    return msg

def handle_whois(message, deviceID, channel_number, message_from_id):
    #return data on a node name or number
    if  "?" in message:
        return message.split("?")[0].title() + " command returns information on a node."
    else:
        # get the nodeID from the message
        msg = ''
        node = ''
        # find the requested node in db
        if " " in message:
            node = message.split(" ")[1]
        if node.startswith("!") and len(node) == 9:
            # mesh !hex
            try:
                node = int(node.strip("!"),16)
            except ValueError as e:
                node = 0
        elif node.isalpha() or not node.isnumeric():
            # try short name
            node = get_num_from_short_name(node, deviceID)

        # get details on the node
        for i in range(len(seenNodes)):
            if seenNodes[i]['nodeID'] == int(node):
                msg = f"Node: {seenNodes[i]['nodeID']} is {get_name_from_number(seenNodes[i]['nodeID'], 'long', deviceID)}\n"
                msg += f"Last 👀: {time.ctime(seenNodes[i]['lastSeen'])} "
                break

        if msg == '':
            msg = "Provide a valid node number or short name"
        else:
            # if the user is an admin show the channel and interface and location
            if isNodeAdmin(message_from_id):
                location = get_node_location(seenNodes[i]['nodeID'], deviceID, channel_number)
                msg += f"Ch: {seenNodes[i]['channel']}, Int: {seenNodes[i]['rxInterface']}"
                msg += f"Lat: {location[0]}, Lon: {location[1]}\n"
                if location != [my_settings.latitudeValue, my_settings.longitudeValue]:
                    msg += f"Loc: {where_am_i(str(location[0]), str(location[1]))}"
        return msg

def handle_boot(mesh=True):
    try:
        print (CustomFormatter.bold_white + f"\nMeshtastic Autoresponder Bot CTL+C to exit\n" + CustomFormatter.reset)
        if mesh:
            
            for i in range(1, 10):
                if globals().get(f'interface{i}_enabled', False):
                    myNodeNum = globals().get(f'myNodeNum{i}', 0)
                    logger.info(f"System: Autoresponder Started for Device{i} {get_name_from_number(myNodeNum, 'long', i)},"
                                f"{get_name_from_number(myNodeNum, 'short', i)}. NodeID: {myNodeNum}, {decimal_to_hex(myNodeNum)}")
                    
            if my_settings.bbs_enabled:
                from modules.bbs.db import initialize_database, set_db_path
                set_db_path(my_settings.bbsdb)
                initialize_database(seed_admins=my_settings.bbs_admin_list)
                logger.debug(f"System: BBS Enabled, SQLite db ready at {my_settings.bbsdb}")

            try:
                from modules.nodes_db import initialize_nodes_database, set_db_path as set_nodes_db_path, upsert_node_seen
                set_nodes_db_path(my_settings.nodes_db)
                initialize_nodes_database()
                seeded = 0
                for i in range(1, 10):
                    iface = globals().get(f'interface{i}')
                    if iface is not None and getattr(iface, 'nodes', None):
                        for node in iface.nodes.values():
                            try:
                                user = node.get('user', {})
                                upsert_node_seen(
                                    node.get('num'),
                                    user.get('longName'),
                                    user.get('shortName'),
                                    user.get('publicKey'),
                                    greeted=True
                                )
                                seeded += 1
                            except Exception as e:
                                logger.warning(f"System: Node Memory pre-seed skipped a node: {e}")
                logger.debug(f"System: Node Memory Enabled, SQLite db ready at {my_settings.nodes_db} ({seeded} nodes pre-seeded/updated)")
            except Exception as e:
                logger.error(f"System: Error initializing Node Memory database: {e}")

            if my_settings.solar_conditions_enabled:
                logger.debug("System: Celestial Telemetry Enabled")

            if my_settings.location_enabled:
                if my_settings.use_meteo_wxApi:
                    logger.debug("System: Location Telemetry Enabled using Open-Meteo API")
                else:
                    logger.debug("System: Location Telemetry Enabled using NOAA API")
                    
            if my_settings.dad_jokes_enabled:
                logger.debug("System: Dad Jokes Enabled!")
            
            if my_settings.coastalEnabled:
                logger.debug("System: Coastal Forecast and Tide Enabled!")
            
            if my_settings.wikipedia_enabled:
                if my_settings.use_kiwix_server:
                    logger.debug(f"System: Wikipedia search Enabled using Kiwix server at {my_settings.kiwix_url}")
                else:
                    logger.debug("System: Wikipedia search Enabled")
            
            if my_settings.rssEnable:
                logger.debug(f"System: RSS Feed Reader Enabled for feeds: {my_settings.rssFeedNames}")
            if my_settings.enable_headlines:
                logger.debug("System: News Headlines Enabled from NewsAPI.org")
            
            if my_settings.file_monitor_enabled:
                logger.warning(f"System: File Monitor Enabled for {my_settings.file_monitor_file_path}, broadcasting to channels: {my_settings.file_monitor_broadcastCh}")
            if my_settings.enable_runShellCmd:
                logger.debug("System: Shell Command monitor enabled")
                if my_settings.allowXcmd:
                    logger.warning("System: File Monitor shell XCMD Enabled")
            if my_settings.read_news_enabled:
                logger.debug(f"System: File Monitor News Reader Enabled for {my_settings.news_file_path}")
            if my_settings.bee_enabled:
                logger.debug("System: File Monitor Bee Monitor Enabled for 🐝bee.txt")
            if my_settings.bible_enabled:
                logger.debug("System: File Monitor Bible Verse Enabled for bible.txt")
            if my_settings.usAlerts:
                logger.debug(f"System: Emergency Alert Broadcast Enabled on channel {my_settings.emergency_responder_alert_channel} for interface {my_settings.emergency_responder_alert_interface}")
            if my_settings.enableDEalerts:
                logger.debug(f"System: NINA Alerts Enabled with counties {my_settings.myRegionalKeysDE}")
            if my_settings.volcanoAlertBroadcastEnabled:
                logger.debug(f"System: Volcano Alert Broadcast Enabled on channels {my_settings.emergency_responder_alert_channel} ignoreUSGSWords {my_settings.ignoreUSGSWords}")
            if my_settings.ipawsAlertEnabled:
                logger.debug(f"System: iPAWS Alerts Enabled with FIPS codes {my_settings.myStateFIPSList} ignorelist {my_settings.ignoreFEMAwords}")
            if my_settings.enableDEalerts:
                logger.debug(f"System: NINA Alerts Enabled with counties {my_settings.myRegionalKeysDE}")
            if my_settings.wxAlertBroadcastEnabled:
                logger.debug(f"System: Weather Alert Broadcast Enabled on channels {my_settings.emergency_responder_alert_channel} ignoreEASwords {my_settings.ignoreEASwords}")
            if my_settings.emergency_responder_enabled:
                logger.debug(f"System: Emergency Responder Enabled on channels {my_settings.emergency_responder_alert_channel}")
            
            if my_settings.greeter_enabled:
                if my_settings.train_greeter:
                    logger.debug("System: Greeter Welcome/Hello Enabled with training mode")
                else:
                    logger.debug("System: Greeter Welcome/Hello Enabled")

        # Default Options
        if my_settings.useDMForResponse:
            logger.debug("System: Respond by DM only")

        if my_settings.autoBanEnabled:
            logger.debug(f"System: Auto-Ban Enabled for {my_settings.autoBanThreshold} messages in {my_settings.autoBanTimeframe} seconds")
            pass  # ban list now managed in BBS SQLite db

        if my_settings.log_messages_to_file:
            logger.debug("System: Logging Messages to disk")
        if my_settings.syslog_to_file:
            logger.debug("System: Logging System Logs to disk")

        if my_settings.motd_enabled:
            logger.debug(f"System: MOTD Enabled using {my_settings.MOTD} scheduler:{my_settings.schedulerMotd}")
        
        if my_settings.sentry_enabled:
            logger.debug(f"System: Sentry Mode Enabled {my_settings.sentry_radius}m radius reporting to channel:{my_settings.secure_channel} requestLOC:{reqLocationEnabled}")
            if my_settings.sentryIgnoreList:
                logger.debug(f"System: Sentry BlockList Enabled for nodes: {my_settings.sentryIgnoreList}")
            if my_settings.sentryWatchList:
                logger.debug(f"System: Sentry WatchList Enabled for nodes: {my_settings.sentryWatchList}")

        if my_settings.highfly_enabled:
            logger.debug(f"System: HighFly Enabled using {my_settings.highfly_altitude}m limit reporting to channel:{my_settings.highfly_channel}")
        
        if my_settings.store_forward_enabled:
            logger.debug(f"System: S&F(messages command) Enabled using limit: {storeFlimit} and reverse queue:{my_settings.reverseSF}")
        
        if my_settings.enableEcho:
            logger.debug("System: Echo command Enabled")
        
        if my_settings.repeater_enabled and multiple_interface:
            logger.debug(f"System: Repeater Enabled for Channels: {my_settings.repeater_channels}")
        
        if my_settings.ignoreChannels:
            logger.debug(f"System: Ignoring Channels: {my_settings.ignoreChannels}")
        
        if my_settings.noisyNodeLogging:
            logger.debug("System: Noisy Node Logging Enabled")
        
        if my_settings.logMetaStats:
            logger.debug("System: Logging Metadata Stats Enabled, leaderboard")
        
        if my_settings.scheduler_enabled:
            logger.debug(f"System: Scheduler Enabled. Default Device:{my_settings.schedulerInterface} Channel:{my_settings.schedulerChannel}")

    except Exception as e:
        logger.error(f"System: Error during boot: {e}")

def onReceive(packet, interface):
    global seenNodes, msg_history, cmdHistory
    # Priocess the incoming packet, handles the responses to the packet with auto_response()
    # Sends the packet to the correct handler for processing

    if not isinstance(packet, dict):
        logger.warning(f"System: Ignoring malformed packet type: {type(packet).__name__}")
        return

    decoded = packet.get('decoded')
    if not isinstance(decoded, dict):
        decoded = {}

    # extract interface details from inbound packet
    rxType = type(interface).__name__

    # Values assinged to the packet
    packet_id = None
    rxNode = message_from_id = snr = rssi = hop = hop_away = channel_number = hop_start = hop_count = hop_limit = 0
    pkiStatus = (False, 'ABC')
    rxNodeHostName = None
    replyIDset = None
    simulator_flag = False
    isDM = False
    channel_name = "unknown"
    session_passkey = None
    playingGame = False

    if my_settings.DEBUGpacket:
        # Debug print the interface object
        for item in interface.__dict__.items(): intDebug = f"{item}\n"
        logger.debug(f"System: Packet Received on {rxType} Interface\n {intDebug} \n END of interface \n")
        # Debug print the packet for debugging
        logger.debug(f"Packet Received\n {packet} \n END of packet \n")

    # determine the rxNode based on the interface type
    if rxType == 'TCPInterface':
        rxHost = interface.__dict__.get('hostname', 'unknown')
        rxNodeHostName = interface.__dict__.get('ip', None)
        rxNode = next(
            (i for i in range(1, 10)
            if multiple_interface and rxHost and
            globals().get(f'hostname{i}', '').split(':', 1)[0] in rxHost and
            globals().get(f'interface{i}_type', '') == 'tcp'),None)

    if rxType == 'SerialInterface':
        rxInterface = interface.__dict__.get('devPath', 'unknown')
        rxNode = next(
            (i for i in range(1, 10)
            if globals().get(f'port{i}', '') in rxInterface),None)

    if rxType == 'BLEInterface':
        rxNode = next(
            (i for i in range(1, 10)
            if globals().get(f'interface{i}_type', '') == 'ble'),0)
        
    if rxNode is None:
        # default to interface 1 ## FIXME needs better like a default interface setting or hash lookup
        if decoded.get('portnum') in ['ADMIN_APP', 'SIMULATOR_APP']:
            session_passkey = decoded.get('admin', {}).get('sessionPasskey', None)
        rxNode = 1

    # check if the packet has a channel flag use it ## FIXME needs to be channel hash lookup
    if packet.get('channel'):
        channel_number = packet.get('channel')
        channel_name = "unknown"
        try:
            res = resolve_channel_name(channel_number, rxNode, interface)
            if res:
                try:
                    channel_name, _ = res
                except Exception:
                    channel_name = "unknown"
            else:
                # Search all interfaces for this channel
                cache = build_channel_cache()
                found_on_other = None
                for device in cache:
                    for chan_name, info in device.get("channels", {}).items():
                        if str(info.get('number')) == str(channel_number) or str(info.get('hash')) == str(channel_number):
                            found_on_other = device.get("interface_id")
                            found_chan_name = chan_name
                            break
                    if found_on_other:
                        break
                if found_on_other and found_on_other != rxNode:
                    logger.debug(
                        f"System: Received Packet on Channel:{channel_number} ({found_chan_name}) on Interface:{rxNode}, but this channel is configured on Interface:{found_on_other}"
                    )
        except Exception as e:
            logger.debug(f"System: channel resolution error: {e}")
    
        #debug channel info
        # if "unknown" in str(channel_name):
        #     logger.debug(f"System: Received Packet on Channel:{channel_number} on Interface:{rxNode}")
        # else:
        #     logger.debug(f"System: Received Packet on Channel:{channel_number} Name:{channel_name} on Interface:{rxNode}")

    # check if the packet has a simulator flag
    simulator_flag = decoded.get('simulator', False)
    if isinstance(simulator_flag, dict):
        # assume Software Simulator
        simulator_flag = True

    # set the message_from_id
    message_from_id = packet.get('from')
    if message_from_id is None:
        logger.warning(f"System: Ignoring packet missing 'from' field on Device:{rxNode}")
        return

    # if message_from_id is not in the seenNodes list add it
    if not any(node.get('nodeID') == message_from_id for node in seenNodes):
        seenNodes.append({'nodeID': message_from_id, 'rxInterface': rxNode, 'channel': channel_number, 'welcome': False, 'first_seen': time.time(), 'lastSeen': time.time()})
        if len(seenNodes) > MAX_SEEN_NODES:
            seenNodes = seenNodes[-MAX_SEEN_NODES:]
    else:
        # update lastSeen time
        for node in seenNodes:
            if node.get('nodeID') == message_from_id:
                node['lastSeen'] = time.time()
                break
    # CHECK with ban_hammer() if the node is banned
    if (my_settings.bbs_enabled and is_banned(message_from_id)) or str(message_from_id) in my_settings.autoBanlist:
        logger.warning(f"System: Banned Node {message_from_id} tried to send a message. Ignored. Try adding to node firmware-blocklist")
        return

    # handle TEXT_MESSAGE_APP
    try:
        if decoded.get('portnum') == 'TEXT_MESSAGE_APP':
            message_bytes = decoded.get('payload', b'')
            if isinstance(message_bytes, bytes):
                message_string = message_bytes.decode('utf-8', errors='replace')
            elif isinstance(message_bytes, str):
                message_string = message_bytes
            else:
                logger.warning(f"System: Ignoring TEXT_MESSAGE_APP with invalid payload type: {type(message_bytes).__name__}")
                return
            message_log_string = message_string.replace('\r', ' ').replace('\n', ' ')
            via_mqtt = decoded.get('viaMqtt', False)
            transport_mechanism = (
                packet.get('transport_mechanism')
                or packet.get('transportMechanism')
                or decoded.get('transport_mechanism')
                or decoded.get('transportMechanism')
                or 'unknown'
            )
            rx_time = decoded.get('rxTime', time.time())

            # check if the packet is from us
            if message_from_id in [myNodeNum1, myNodeNum2, myNodeNum3, myNodeNum4, myNodeNum5, myNodeNum6, myNodeNum7, myNodeNum8, myNodeNum9]:
                logger.warning(f"System: Packet from self {message_from_id} loop or traffic replay detected")

            # get the signal strength and snr if available
            if packet.get('rxSnr') or packet.get('rxRssi'):
                snr = packet.get('rxSnr', 0)
                rssi = packet.get('rxRssi', 0)

            # check if the packet has a publicKey flag use it
            if packet.get('publicKey'):
                pkiStatus = packet.get('pkiEncrypted', False), packet.get('publicKey', 'ABC')
            
            # Use packet id for threaded replies;
            packet_id = packet.get('id', None)

            # existing reply - unused for tracking
            replyIDSet = packet.get('replyIDSet', None)
            
            # check if the packet has emoji flag set it // currently unused in the code
            # emoji flag check removed (wordOfTheDay removed)
            # check if the packet has a hop count flag use it
            if packet.get('hopsAway'):
                hop_away = packet.get('hopsAway', 0)

            if packet.get('hopStart'):
                hop_start = packet.get('hopStart', 0)

            if packet.get('hopLimit'):
                hop_limit = packet.get('hopLimit', 0)
            
            # calculate hop count
            hop = ""
            if hop_limit > 0 and hop_start >= hop_limit:
                hop_count = hop_away + (hop_start - hop_limit)
            elif hop_limit > 0 and hop_start < hop_limit:
                hop_count = hop_away + (hop_limit - hop_start)
            else:
                hop_count = hop_away

            if hop_count > 0:
                # set hop string from calculated hop count
                hop = f"{hop_count} Hop" if hop_count == 1 else f"{hop_count} Hops"

            if hop_start == hop_limit and "lora" in str(transport_mechanism).lower() and (snr != 0 or rssi != 0) and hop_count == 0:
                # 2.7+ firmware direct hop over LoRa
                hop = "Direct"

            if via_mqtt or "mqtt" in str(transport_mechanism).lower():
                hop = "MQTT"
                via_mqtt = True
            elif "udp" in str(transport_mechanism).lower():
                hop = "Gateway"
            
            if hop in ("MQTT", "Gateway") and hop_count > 0:
                hop = f" {hop_count} Hops"

            # Add relay node info if present
            if packet.get('relayNode') is not None:
                relay_val = packet['relayNode']
                last_byte = relay_val & 0xFF
                if last_byte == 0x00:
                    hex_val = 'OldFW'
                else:
                    hex_val = f"{last_byte:02X}"
                hop += f" Relay:{hex_val}"

            if enableHopLogs:
                logger.debug(f"System: Packet HopDebugger: hop_away:{hop_away} hop_limit:{hop_limit} hop_start:{hop_start} calculated_hop_count:{hop_count} final_hop_value:{hop} via_mqtt:{via_mqtt} transport_mechanism:{transport_mechanism} Hostname:{rxNodeHostName}")

            # check with stringSafeChecker if the message is safe
            if stringSafeCheck(message_string, message_from_id) is False:
                logger.warning(f"System: Possibly Unsafe Message from {get_name_from_number(message_from_id, 'long', rxNode)}")

            if help_message in message_string or welcome_message in message_string or "CMD?:" in message_string:
                # ignore help and welcome messages
                logger.warning(f"Got Own Welcome/Help header. From: {get_name_from_number(message_from_id, 'long', rxNode)}")
                return
        
            # If the packet is a DM (Direct Message) respond to it, otherwise validate its a message for us on the channel
            if packet.get('to') in [myNodeNum1, myNodeNum2, myNodeNum3, myNodeNum4, myNodeNum5, myNodeNum6, myNodeNum7, myNodeNum8, myNodeNum9]:
                # message is DM to us
                isDM = True
                # check if the message contains a trap word, DMs are always responded to
                # BBS menu handler intercepts bbsmenu and in-menu responses first
                if my_settings.bbs_enabled and handle_menu_message(message_string, message_from_id, rxNode):
                    logger.info(f"Device:{rxNode} BBS menu handled: {message_log_string} From: {get_name_from_number(message_from_id, 'long', rxNode)}")
                elif messageTrap(message_string) or messageTrap(message_string.split()[0]):
                    # log the message to stdout
                    logger.info(f"Device:{rxNode} Channel: {channel_number} " + CustomFormatter.green + f"Received DM: " + CustomFormatter.white + f"{message_log_string} " + CustomFormatter.purple +\
                                "From: " + CustomFormatter.white + f"{get_name_from_number(message_from_id, 'long', rxNode)}")
                    # respond with DM
                    send_message(auto_response(message_string, snr, rssi, hop, pkiStatus, message_from_id, channel_number, rxNode, isDM), channel_number, message_from_id, rxNode)
                else:
                    if not playingGame:
                        # respond with welcome message on DM
                        logger.warning(f"Device:{rxNode} Ignoring DM: {message_log_string} From: {get_name_from_number(message_from_id, 'long', rxNode)}")
                        
                        # if seenNodes list is not marked as welcomed send welcome message
                        if not any(node['nodeID'] == message_from_id and node['welcome'] == True for node in seenNodes):
                            # send welcome message
                            send_message(welcome_message, channel_number, message_from_id, rxNode)
                            # mark the node as welcomed
                            for node in seenNodes:
                                if node['nodeID'] == message_from_id:
                                    node['welcome'] = True
                        else:
                            # Unknown command - tell them explicitly
                            send_message("Unknown command. Try 'cmd' for a list or 'bbsmenu' for the BBS menu.", channel_number, message_from_id, rxNode)
                    
                    # log the message to the message log
                    if log_messages_to_file:
                        msgLogger.info(f"Device:{rxNode} Channel:{channel_number} | {get_name_from_number(message_from_id, 'long', rxNode)} | DM | " + message_log_string)
            else:
                # message is on a channel
                if messageTrap(message_string):
                    # message is for us to respond to, or is it...
                    if my_settings.ignoreDefaultChannel and channel_number == my_settings.publicChannel:
                        logger.debug(f"System: Ignoring CMD:{message_log_string} From: {get_name_from_number(message_from_id, 'short', rxNode)} Default Channel:{channel_number}")
                    elif my_settings.bbs_enabled and is_banned(message_from_id):
                        logger.debug(f"System: Ignoring CMD:{message_log_string} From: {get_name_from_number(message_from_id, 'short', rxNode)} Cantankerous Node")
                    elif str(channel_number) in my_settings.ignoreChannels:
                        logger.debug(f"System: Ignoring CMD:{message_log_string} From: {get_name_from_number(message_from_id, 'short', rxNode)} Ignored Channel:{channel_number}")
                    elif my_settings.cmdBang and not message_string.startswith("!"):
                        logger.debug(f"System: Ignoring CMD:{message_log_string} From: {get_name_from_number(message_from_id, 'short', rxNode)} Didnt sound like they meant it")
                    else:
                        # message is for bot to respond to, seriously this time..
                        logger.info(f"Device:{rxNode} Channel:{channel_number} " + CustomFormatter.green + "ReceivedChannel: " + CustomFormatter.white + f"{message_log_string} " + CustomFormatter.purple +\
                                    "From: " + CustomFormatter.white + f"{get_name_from_number(message_from_id, 'long', rxNode)}")
                        if my_settings.useDMForResponse:
                            # respond to channel message via direct message
                            send_message(auto_response(message_string, snr, rssi, hop, pkiStatus, message_from_id, channel_number, rxNode, isDM), channel_number, message_from_id, rxNode, reply_id=packet_id)
                        else:
                            # or respond to channel message on the channel itself
                            if channel_number == my_settings.publicChannel and my_settings.antiSpam:
                                # warning user spamming default channel
                                logger.warning(f"System: AntiSpam protection, sending DM to: {get_name_from_number(message_from_id, 'long', rxNode)}")
                            
                                # respond to channel message via direct message
                                send_message(auto_response(message_string, snr, rssi, hop, pkiStatus, message_from_id, channel_number, rxNode, isDM), channel_number, message_from_id, rxNode, reply_id=packet_id)
                            else:
                                # respond to channel message on the channel itself
                                send_message(auto_response(message_string, snr, rssi, hop, pkiStatus, message_from_id, channel_number, rxNode, isDM), channel_number, 0, rxNode, reply_id=packet_id)

                else:
                    # message is not for us to respond to
                    # ignore the message but add it to the message history list
                    if my_settings.zuluTime:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S%p")

                    # trim the history list if it exceeds max_history
                    if len(msg_history) >= my_settings.MAX_MSG_HISTORY:
                        # Always keep only the most recent MAX_MSG_HISTORY entries
                        msg_history = msg_history[-my_settings.MAX_MSG_HISTORY:]

                    # add the message to the history list
                    msg_history.append((get_name_from_number(message_from_id, 'long', rxNode), message_string, channel_number, timestamp, rxNode))

                    # print the message to the log and sdout
                    logger.info(f"Device:{rxNode} Channel:{channel_number} " + CustomFormatter.green + "Ignoring Message:" + CustomFormatter.white +\
                                f" {message_log_string} " + CustomFormatter.purple + "From:" + CustomFormatter.white + f" {get_name_from_number(message_from_id)}")
                    if my_settings.log_messages_to_file:
                        msgLogger.info(f"Device:{rxNode} Channel:{channel_number} | {get_name_from_number(message_from_id, 'long', rxNode)} | " + message_log_string)

                    # repeat the message on the other device
                    if my_settings.repeater_enabled and my_settings.multiple_interface:
                        # wait a responseDelay to avoid message collision from lora-ack.
                        time.sleep(my_settings.responseDelay)
                        if len(message_string) > (3 * my_settings.MESSAGE_CHUNK_SIZE):
                            logger.warning(f"System: Not repeating message, exceeds size limit ({len(message_string)} > {3 * MESSAGE_CHUNK_SIZE})")
                        else:
                            rMsg = (f"{message_string} From:{get_name_from_number(message_from_id, 'short', rxNode)}")
                            # if channel found in the repeater list repeat the message
                            if str(channel_number) in my_settings.repeater_channels:
                                for i in range(1, 10):
                                    if globals().get(f'interface{i}_enabled', False) and i != rxNode:
                                        logger.debug(f"Repeating message on Device{i} Channel:{channel_number}")
                                        send_message(rMsg, channel_number, 0, i)
                                        time.sleep(my_settings.responseDelay)
                    
                    # if Greeter enabled check if we have said hello
                    if my_settings.greeter_enabled:
                        if never_seen_before(message_from_id):
                            name = get_name_from_number(message_from_id, 'short', rxNode)
                            if isinstance(name, str) and name.startswith("!") and len(name) == 9:
                                # we didnt get a info packet yet so wait and ingore this go around
                                logger.debug(f"System: Greeter Hello ignored, no info packet yet")
                            else:
                                # record that we've greeted this node
                                hello(message_from_id, name)
                                # send a hello message as a DM
                                if not my_settings.train_greeter:
                                    send_message(f"Hello {name} {greeter_hello_string}", channel_number, message_from_id, rxNode, reply_id=packet_id)

        else:
            # Evaluate non TEXT_MESSAGE_APP packets
            consumeMetadata(packet, rxNode, channel_number)
    except Exception as e:
        logger.exception(f"System: Error processing packet: {e} Device:{rxNode}")
        logger.debug(f"System: Error Packet = {packet}")

async def start_rx():
    # Start the receive subscriber using pubsub via meshtastic library
    pub.subscribe(onReceive, 'meshtastic.receive')
    pub.subscribe(onDisconnect, 'meshtastic.connection.lost')
    logger.debug("System: RX Subscriber started")
    # here we go loopty loo
    while True:
        await asyncio.sleep(0.5)
        pass

# Game trackers removed from mesh-ham-bot

# Hello World 
async def main():
    tasks = []
    
    try:
        system.main_loop = asyncio.get_event_loop()
        handle_boot()
        # Create core tasks
        tasks.append(asyncio.create_task(start_rx(), name="mesh_rx"))
        tasks.append(asyncio.create_task(watchdog(), name="watchdog"))

        # Add optional tasks
        if my_settings.dataPersistence_enabled:
            tasks.append(asyncio.create_task(dataPersistenceLoop(), name="data_persistence"))

        if my_settings.file_monitor_enabled:
            tasks.append(asyncio.create_task(handleFileWatcher(), name="file_monitor"))

        if my_settings.scheduler_enabled:
            from modules.scheduler import run_scheduler_loop, setup_scheduler
            setup_scheduler(schedulerMotd, MOTD, schedulerMessage, schedulerChannel, schedulerInterface,
    schedulerValue, schedulerTime, schedulerInterval)
            tasks.append(asyncio.create_task(run_scheduler_loop(), name="scheduler"))
        
        logger.debug(f"System: Starting {len(tasks)} async tasks")
        
        # Wait for all tasks with proper exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for exceptions in results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {tasks[i].get_name()} failed with: {result}")
        
    except Exception as e:
        logger.error(f"Main loop error: {e}")
    finally:
        # Cleanup tasks
        logger.debug("System: Cleaning up async tasks")
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug(f"Task {task.get_name()} cancelled successfully")
                except Exception as e:
                    logger.warning(f"Error cancelling task {task.get_name()}: {e}")

    await asyncio.sleep(0.01)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        exit_handler()
    except SystemExit:
        pass
# EOF
