import math
import re
import textwrap
import threading
import time
import traceback
from collections import deque
from datetime import datetime

import xbmc
import xbmcgui

from .api import RemoteTermAPI
from .ws_client import RemoteTermEventStream

# -- Control IDs -- resources/skins/Default/1080i/script-remoteterm-main.xml --

ID_STATUS_DOT = 101
ID_STATUS_TEXT = 102
ID_REFRESH = 103

ID_NAV_DASHBOARD = 9001
ID_NAV_CHATS = 9002
ID_NAV_CONTACTS = 9005
ID_NAV_MAP = 9006
ID_NAV_PACKETS = 9007
ID_NAV_ANALYTICS = 9008
ID_NAV_REPEATERS = 9009
ID_REPEATER_SORT_RECENT = 960
ID_REPEATER_SORT_DISTANCE = 961
ID_REPEATER_SORT_HOPS_NEAR = 962
ID_REPEATER_SORT_HOPS_FAR = 963

# Dashboard
ID_STAT_CONTACTS = 700
ID_STAT_CHANNELS = 701
ID_STAT_REPEATERS = 702
ID_STAT_PACKETS = 703
ID_STAT_DECRYPTED = 704
ID_STAT_DMS = 705
ID_STAT_CHANMSG = 706
ID_STAT_OUTGOING = 707
ID_BUSIEST_LIST = 710
ID_DECRYPT_PROGRESS = 720
ID_OUTGOING_PROGRESS = 721
ID_DECRYPT_PCT_LABEL = 722
ID_OUTGOING_PCT_LABEL = 723
ID_ACTIVITY_LIST = 730

# Chats
ID_CONVO_LIST = 200
ID_CONVO_TITLE = 300
ID_FAVORITE_TOGGLE = 330
ID_FAVORITES_FILTER = 340
ID_MESSAGE_LIST = 310
ID_COMPOSE = 320

# Repeater Console (category 3 -- replaces the old empty Favorites tab)
ID_REPEATER_PICKER = 950
ID_REPEATER_NEIGHBORS = 951
ID_REPEATER_ACL = 952
ID_REPEATER_INFO = 953
ID_REPEATER_TERMINAL = 958
ID_REPEATER_COMMAND = 954
ID_REPEATER_REFRESH = 955
ID_REPEATER_MORE_INFO = 956
ID_REPEATER_LOGIN = 957
ID_NOTIFY_TOGGLE = 331

# Search
ID_SEARCH_BUTTON = 800

# Contacts
ID_CONTACTS_LIST = 900
ID_CONTACTS_FILTER_ALL = 901
ID_CONTACTS_FILTER_CLIENTS = 902
ID_CONTACTS_FILTER_REPEATERS = 903
ID_CONTACTS_FILTER_ROOMS = 904
ID_CONTACTS_FILTER_SENSORS = 905
ID_SORT_RECENT = 911
ID_SORT_DISTANCE = 912
ID_SORT_HOPS_NEAR = 913
ID_SORT_HOPS_FAR = 914

# Map
ID_MAP_LIST = 1000
ID_MAP_REFRESH = 1001
ID_MAP_LABEL = 1003
ID_MAP_REGIONAL_BTN = 1012
ID_MAP_LOCAL_BTN = 1013
ID_MAP_PAN_NORTH = 1015
ID_MAP_PAN_SOUTH = 1016
ID_MAP_PAN_EAST = 1017
ID_MAP_PAN_WEST = 1018
ID_MAP_HOME = 1019
ID_MAP_TILE_BASE = 1300
ID_MAP_GRID_COLS = 4
ID_MAP_GRID_ROWS = 3
ID_MAP_GRID_LEFT = 170
ID_MAP_GRID_TOP = 230
ID_MAP_MARKER_BASE = 1320
ID_MAP_MARKER_COUNT = 150  # Raised from 30: confirmed via the log that
                            # EVERY render was hitting the 30-marker cap
                            # ("placed 30 of 820 located nodes") in a
                            # dense area like LA, which is exactly why
                            # real repeaters were missing from the map.
                            # The earlier FPS regression that motivated
                            # dropping to 30 was root-caused to blocking,
                            # sequential NETWORK tile fetches (since
                            # fixed with parallel fetching + a working
                            # tile provider) -- plain property-setting
                            # calls on more marker controls is a much
                            # cheaper operation than that was, so this
                            # should be safe to raise substantially.

# Packets
ID_PACKET_LIST = 1010
ID_PACKET_STATUS = 1011
ID_PACKET_MY_NODES_BTN = 1020

# Analytics (category 8) -- gauges are Window.Property driven (see
# _load_analytics), these ids are just the text readouts layered on top
ID_ANALYTICS_GAUGE_DECRYPT_LABEL = 1100
ID_ANALYTICS_GAUGE_BATTERY_LABEL = 1101
ID_ANALYTICS_GAUGE_OUTGOING_LABEL = 1102
ID_ANALYTICS_GAUGE_SNR_LABEL = 1103
ID_ANALYTICS_STAT_UPTIME = 1110
ID_ANALYTICS_STAT_NOISE_FLOOR = 1111
ID_ANALYTICS_STAT_LAST_RSSI = 1112
ID_ANALYTICS_STAT_LAST_SNR = 1113
ID_ANALYTICS_STAT_TX_AIR = 1114
ID_ANALYTICS_STAT_RX_AIR = 1115
ID_ANALYTICS_STAT_PACKETS_RECV = 1116
ID_ANALYTICS_STAT_PACKETS_SENT = 1117
ID_ANALYTICS_STAT_DB_SIZE = 1122
ID_ANALYTICS_STAT_ERRORS = 1123
ID_ANALYTICS_STAT_QUEUE = 1124
ID_ANALYTICS_FANOUT_LIST = 1125
ID_ANALYTICS_STAT_BATTERY = 1126
ID_ANALYTICS_BATTERY_FILL = 1128
ID_ANALYTICS_BAR_TX = 1140
ID_ANALYTICS_BAR_TX_LABEL = 1141
ID_ANALYTICS_BAR_TX_COUNTS = 1142
ID_ANALYTICS_BAR_RX = 1143
ID_ANALYTICS_BAR_RX_LABEL = 1144
ID_ANALYTICS_BAR_RX_COUNTS = 1145
ID_ANALYTICS_INTENSITY_BAR = 1146
ID_ANALYTICS_LIVE_FEED = 1170
ID_WATERFALL_TOGGLE = 1175
ID_WATERFALL_BACKDROP = 1176
ID_WATERFALL_LIVE_LABEL = 1177
ID_WATERFALL_LABEL = 1178
ID_WATERFALL_SUBTITLE = 1932
ID_WATERFALL_DOT = 1179
ID_WATERFALL_ON_INDICATOR = 1931
ID_WATERFALL_WAITING_LABEL = 1930
WATERFALL_BAR_IDS = tuple(range(1900, 1930))
ID_ANALYTICS_INTENSITY_LABEL = 1147
ID_ANALYTICS_UTIL_BAR = 1180
ID_ANALYTICS_UTIL_LABEL = 1183

ID_NAV_TRENDS_BTN = 1500
ID_TRENDS_BACK = 1501
ID_TRENDS_BAR_BASE = 1600  # 1600..1623, one per 3-hour bucket (24 total)
ID_TRENDS_AXIS_LEFT = 1650
ID_TRENDS_AXIS_RIGHT = 1651
ID_TRENDS_PEAK_LABEL = 1652
# Network Activity grid value labels: contacts/repeaters/channels heard,
# each x last-hour/24h/week -- 9 values total.
ID_TRENDS_CONTACTS_1H = 1660
ID_TRENDS_CONTACTS_24H = 1661
ID_TRENDS_CONTACTS_7D = 1662
ID_TRENDS_REPEATERS_1H = 1663
ID_TRENDS_REPEATERS_24H = 1664
ID_TRENDS_REPEATERS_7D = 1665
ID_TRENDS_CHANNELS_1H = 1666
ID_TRENDS_CHANNELS_24H = 1667
ID_TRENDS_CHANNELS_7D = 1668

TAB_DASHBOARD = "dashboard"
TAB_CHATS = "chats"
TAB_REPEATERS = "repeaters"
TAB_CONTACTS = "contacts"
TAB_MAP = "map"
TAB_PACKETS = "packets"
TAB_ANALYTICS = "analytics"
TAB_TRENDS = "trends"

# Single source of truth for "which nav-rail icon represents this tab" --
# used by Back/Backspace handling (_dispatch_action) to return focus to
# the icon for whatever tab the user is actually on, rather than always
# jumping to Dashboard's icon. TAB_TRENDS is deliberately absent: Trends
# is a Dashboard drill-down reached via its own button (ID_NAV_TRENDS_BTN),
# not a nav-rail tab in its own right, so it has no icon to map to.
TAB_NAV_ID = {
    TAB_DASHBOARD: ID_NAV_DASHBOARD,
    TAB_CHATS: ID_NAV_CHATS,
    TAB_CONTACTS: ID_NAV_CONTACTS,
    TAB_REPEATERS: ID_NAV_REPEATERS,
    TAB_MAP: ID_NAV_MAP,
    TAB_PACKETS: ID_NAV_PACKETS,
    TAB_ANALYTICS: ID_NAV_ANALYTICS,
}

GREEN = "FF00FF66"
RED = "FFFF1744"
AMBER = "FFFFD500"
BLUE = "FF2A6DF4"


def _rssi_to_waterfall_color(rssi):
    """Classic SDR-waterfall-style colormap (the same visual language as
    e.g. GQRX/SDR#'s default palette): weak signal fades through dark
    blue/purple, mid-strength through magenta/orange, strong through
    yellow to near-white. Deliberately continuous rather than the 4
    discrete tiers used elsewhere on this page (green/amber/red/darkred)
    -- a waterfall's whole visual point is showing gradual change, and
    four flat bands would look like a bar chart wearing a waterfall's
    name rather than an actual one. Uses the same -120..-30 dBm range
    already established for the RSSI gauge elsewhere on this page, so
    "strong" means the same thing here that it does there. Returns an
    "FF"-prefixed ARGB hex string, ready for setColorDiffuse()."""
    t = max(0.0, min(1.0, (rssi + 120) / 90))
    stops = [
        (0.00, (10, 8, 40)),
        (0.25, (40, 10, 110)),
        (0.50, (160, 20, 110)),
        (0.72, (240, 100, 30)),
        (0.88, (250, 200, 40)),
        (1.00, (255, 255, 230)),
    ]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            r, g, b = (int(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
            return f"FF{r:02X}{g:02X}{b:02X}"
    r, g, b = stops[-1][1]
    return f"FF{r:02X}{g:02X}{b:02X}"


def _bar_tier_color(tier):
    """Maps a tier name to its solid hex color, for controls driven
    directly via setColorDiffuse() rather than a stack of pre-colored
    <visible>-toggled controls -- same palette as the gauges/glow strips
    elsewhere on this page, just centralized here since two call sites
    need the plain hex value rather than a texture reference."""
    return {"green": "FF00FF66", "amber": "FFFFD500", "red": "FFFF1744", "darkred": "FF960A1E"}.get(tier, "FF00FF66")


def _pct_tier(pct):
    """Uniform tiering rule applied to every intensity-style gauge and
    bar chart on the Analytics page: the control's own fill percentage
    decides the color. Widened from 3 tiers to 4 (each ~25% wide instead
    of ~33%) specifically because a single color spanning half the gauge
    (e.g. the old 67-100% red band) meant a lot of real, meaningful
    movement in that range never produced any visible change beyond the
    needle position itself -- more, narrower color bands means more
    frequent, noticeable transitions as a value climbs or falls, which
    is exactly the "more action" being asked for."""
    if pct <= 25:
        return "green"
    elif pct <= 50:
        return "amber"
    elif pct <= 75:
        return "red"
    else:
        return "darkred"


def _snr_tier(snr_db):
    """MeshCore/LoRa-specific SNR quality tiers, using real documented
    thresholds rather than an arbitrary percentage split. Confirmed via
    LoRa engineering sources covering MeshCore specifically: Semtech's
    SX12xx datasheet puts the demodulation floor at roughly -7.5dB SNR
    for SF7 down to -20dB for SF12 (MeshCore commonly runs SF9/SF10,
    floor around -12.5 to -15dB); above that floor, 0-7dB is documented
    as a "marginal" link that works in good conditions but is vulnerable
    to weather, vegetation, and interference, while +7dB or higher is
    described as a reliable working target for a MeshCore link. That
    gives three real, physically-grounded zones instead of an evenly-
    split percentage scale: at/below the reliable margin, marginal, and
    reliable."""
    if snr_db <= 0:
        return "red"
    elif snr_db <= 7:
        return "amber"
    else:
        return "green"


def _rssi_tier(rssi_dbm):
    """RSSI quality tiers using the standard, widely-cited practical LoRa
    RSSI range: multiple independent sources (LoRa RSSI field studies,
    IoT gateway troubleshooting guides) describe -30dBm as "solid"/
    "screaming loud" and -120dBm as "weak"/"a whisper" -- confirmed as
    the conventional -30..-120dBm span used for describing and
    displaying LoRa signal strength, not derived from a chip's absolute
    theoretical demodulation floor (which is deeper, e.g. -148dBm for
    the SX1262 in this hardware, but isn't what "RSSI range" normally
    refers to in practice). Like SNR, RSSI reads as a quality metric
    (less negative = better) rather than an intensity one, so low
    magnitude reads red and high reads green -- the opposite direction
    from the packet-rate-driven gauges/bars on this page. Four real
    bands (matching researched dBm brackets): -120 to -98 bad/dropping,
    -97 to -75 marginal, -74 to -53 good/stable, -52dBm and stronger a
    distinctly better "excellent" tier of its own."""
    if rssi_dbm <= -98:
        return "red"
    elif rssi_dbm <= -75:
        return "amber"
    elif rssi_dbm <= -53:
        return "green"
    else:
        return "darkgreen"


def _rate_tier(rate, low, med, high):
    """Direct packets/min tiering, using the actual rate rather than a
    percentage. Confirmed bug: feeding the log-scaled arc-position
    percentage into the generic uniform tier function meant a modest,
    everyday rate (8.7/min, confirmed directly from a screenshot) landed
    at 55% -- deep in the "red" band under the 25/50/75 split -- purely
    because log-scaling deliberately over-expands low values for visual
    movement. That expansion is exactly right for how far the needle
    sweeps, but it should never have been reused to decide the color too;
    the two need separate scales. This tiers directly off the real
    packets/min or airtime-rate value, with thresholds picked from every
    rate actually observed across many real sessions (0, 3.8, 8.7, 13.7,
    15, 19.8, 23.7, 49.7, 61.8/min) so a genuinely everyday, low-to-
    moderate rate reads green or amber, and only a real burst reads red
    or darkred."""
    if rate <= low:
        return "green"
    elif rate <= med:
        return "amber"
    elif rate <= high:
        return "red"
    else:
        return "darkred"


def _log_pct(value, max_ref):
    """Log-scaled percentage for packet-rate-driven gauges/bars. Real
    traffic on this mesh is bursty and close to bimodal -- confirmed
    directly from a screenshot sequence showing 0, 49.7, and 61.8
    packets/min with apparently nothing captured in between. A LINEAR
    scale that fairly represents the busy end (needs a large max_ref to
    avoid saturating red on every burst) compresses all moderate
    activity into a narrow band near zero, which is exactly why amber
    was still almost never appearing even after widening the reference
    max. Log scaling expands the low end instead: a modest burst (a
    handful of packets/min) already registers as a meaningfully higher
    percentage than 0, without needing to approach max_ref, while still
    naturally compressing (and eventually saturating) at the high end
    where finer distinction matters less."""
    if value <= 0:
        return 0
    return max(0, min(100, int(round(math.log1p(value) / math.log1p(max_ref) * 100))))

SENDER_COLORS = ("FF6DD3FF", "FFFFC96D", "FF9EE37D", "FFE39EFF", "FFFF8A8A", "FF7DE3D0", "FFB8A6FF")
OUTGOING_BUBBLE = "CC1F7A44"
INCOMING_BUBBLE = "CC1B2130"

CONTACT_TYPE_NAMES = {0: "Unknown", 1: "Client", 2: "Repeater", 3: "Room Server", 4: "Sensor"}

DASHBOARD_REFRESH_SECS = 15
ANALYTICS_REFRESH_SECS = 3  # Confirmed real bug: Analytics shared
                             # Dashboard's 15s cadence, so gauges lagged
                             # visibly behind packets actually arriving
                             # over the WS every few seconds -- a live
                             # radio page should refresh close to that
                             # rate, not wait on Dashboard's slower,
                             # more expensive refresh needs.
NOTIFICATION_SYNC_SECS = 30  # how often push-enabled conversations and
                              # unread counts are re-fetched from the
                              # server in the background, independent of
                              # which tab is open -- toggling a
                              # conversation's notifications on the
                              # browser frontend (or another client)
                              # should reach this addon within this
                              # window, not only the next time the user
                              # happens to open the Chats tab.
PACKET_FEED_MAXLEN = 250
MESSAGE_POLL_SECS = 4  # cheap check (50-row peek) -- fine to run often
MESSAGE_RELOAD_MIN_INTERVAL = 4  # hard floor between full-history reloads,
                                 # no matter how many push events/polls fire
MESSAGE_DISPLAY_DEFAULT = 100  # initial render cap -- "Load More" grows this
                                # from an in-memory cache, no extra network
                                # call needed to show more history
MESSAGE_DISPLAY_STEP = 100
# Forcing conservative line breaks in Python rather than trusting Kodi's
# own proportional-font wrap calculation to fit the available bubble
# width: two rounds of increasing the bubble height purely on an estimate
# of how many wrapped lines a message "should" need still let real
# messages clip, confirmed by screenshot. 40 characters/line is
# deliberately narrow for this bubble's ~770px width (comfortably wide
# enough that Kodi should never need to further subdivide a line this
# short), which makes the resulting line count a reliable upper bound to
# size the fixed bubble height against, rather than another guess.
MESSAGE_WRAP_WIDTH = 40
FOCUS_SETTLE_MS = 120  # lets Kodi re-evaluate <visible> before we move focus

# Bare filenames don't reliably resolve through Kodi's texture manager for a
# script's WindowXMLDialog, so any image handed to a Python-side API
# (ListItem art/icons, ControlImage, etc.) must use an absolute path too.
SKIN_DIR = "special://home/addons/plugin.program.remoteterm/resources/skins/Default/1080i/"


def _skin_asset(filename):
    return SKIN_DIR + filename


def _sender_color(name):
    # Python's built-in hash() is randomized per-process for str (security
    # feature since 3.3), so the same sender got a different color every
    # time the addon restarted. A deterministic sum keeps colors stable.
    h = sum(ord(c) for c in (name or "")) if name else 0
    return SENDER_COLORS[h % len(SENDER_COLORS)]


# Kodi's label markup parser scans literal "[" / "]" characters in ANY
# label text looking for [COLOR]/[B]/etc tags -- including inside message
# text that never asked to be formatted. Real mesh messages regularly
# contain literal brackets (e.g. "@[Foo] ok rotting" was seen verbatim in
# a live packet capture). An earlier fix swapped them for fullwidth
# lookalikes (\uff3b/\uff3d), but screenshots showed those rendering as
# missing-glyph "tofu" boxes -- the skin's font doesn't have them. Plain
# ASCII parentheses aren't a perfect visual match but are guaranteed to
# render in any font.
_BRACKET_ESCAPE = str.maketrans({"[": "(", "]": ")"})

# ASCII control characters (other than tab/newline) have no business in
# chat text and are stripped outright.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _safe_label_text(text):
    """Applied to every piece of free-form (message/mesh-controlled) text
    embedded in a formatted label anywhere in the addon.

    CONFIRMED root cause (via a direct side-by-side comparison against the
    real RemoteTerm web UI): astral-plane Unicode characters -- which is
    what almost all emoji are (U+10000 and above) -- truncate a Kodi label
    at the exact point they occur, silently dropping everything after
    them, including closing [B]/[COLOR] tags and the rest of the message.
    The evidence was unambiguous: a sender genuinely named "KR1IS-C Solar
    \U0001F4E1" (trailing satellite emoji) rendered in the real web UI, and
    in the Kodi addon showed as "[COLOR ...][B]KR1IS-C Solar" -- cut off
    exactly before the emoji, nothing else. An earlier fix targeted
    *invalid* surrogate characters (encode/decode round-trip with
    errors='replace'), which does nothing for a well-formed emoji and did
    not fix this. Stripping astral-plane characters outright does."""
    if not text:
        return text
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = "".join(ch for ch in text if ord(ch) <= 0xFFFF)
    return text.translate(_BRACKET_ESCAPE)


def _safe_message_text(text):
    """For message BODY text specifically -- as opposed to sender/channel
    names, which go through _safe_label_text above.

    REVERTED: an earlier version of this function preserved emoji here,
    on the theory that the confirmed truncation bug was specific to emoji
    appearing inside an already-tagged [COLOR]/[B] region (sender names),
    and that message body text -- untagged, coming after those closing
    tags -- wouldn't be affected the same way. A follow-up screenshot
    showed that theory was wrong: preserved emoji in message bodies were
    leaving parts of real messages blank and unreadable. Given direct
    evidence of breakage, this now strips astral-plane characters (almost
    all emoji) here too, the same as sender names, replacing each with a
    single space rather than deleting outright so words don't run
    together where an emoji used to sit between them.

    Note on a real font-level fix: a genuine monochrome-emoji fallback
    (e.g. bundling Noto Emoji's plain .ttf and mapping it into Font.xml)
    is the right idea in principle, but isn't achievable here for two
    concrete reasons: (1) this environment has no network access to fetch
    a font file, and (2) Kodi's Font.xml maps exactly one font file to
    each named font id -- it does not support chaining a fallback font
    for glyphs missing from the primary one the way a browser or OS text
    stack does, so even with the file in hand, mixed text+emoji within a
    single label couldn't render both from different font files at once.
    That's a limitation of Kodi's text rendering, not something this
    addon's code can route around."""
    if not text:
        return text
    text = text.encode("utf-8", errors="replace").decode("utf-8")
    text = _CONTROL_CHARS_RE.sub("", text)
    text = "".join((ch if ord(ch) <= 0xFFFF else " ") for ch in text)
    text = re.sub(r" {2,}", " ", text).strip()
    return text.translate(_BRACKET_ESCAPE)


def _wrap_for_bubble(text):
    """Forces conservative line breaks so the chat bubble's fixed height
    can be sized against a KNOWN worst-case line count instead of another
    guess at how Kodi's own proportional-font wrapping will lay out a
    given message -- see MESSAGE_WRAP_WIDTH. break_long_words guards
    against a single unbroken run (a long hex path, a URL like
    WCMESH.COM) skipping past the width unwrapped; break_on_hyphens is
    off so hyphenated callsigns/names (e.g. "KR1IS-C") aren't split
    awkwardly just because they contain a hyphen."""
    if not text:
        return text
    lines = textwrap.wrap(text, width=MESSAGE_WRAP_WIDTH, break_long_words=True, break_on_hyphens=False)
    return "[CR]".join(lines) if lines else text


def _ago(ts):
    if not ts:
        return "never"
    delta = max(0, int(time.time()) - int(ts))
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


def _format_duration(secs):
    """Formats a raw seconds count (uptime, TX/RX air time) as a compact
    human string. Used on the Analytics tab for radio_stats fields that
    are confirmed to arrive as plain integer seconds."""
    if secs is None:
        return "--"
    secs = int(secs)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, rem = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {rem}s"
    return f"{rem}s"


def _format_key_value_dict(d, indent=0, max_list_items=5):
    """Generic "show every field" formatter for a live API response whose
    exact shape isn't (or wasn't yet) fully confirmed -- used for the
    repeater live-status dialog specifically, since a side-by-side
    comparison against the real web frontend showed it has many more
    fields than this addon was cherry-picking by name. Field names are
    turned from snake_case into Title Case for readability; nested dicts
    are shown indented rather than skipped, so nothing is silently
    dropped just because its exact structure wasn't anticipated.

    Confirmed real bug (now fixed): list-of-dict fields used to be
    expanded in full with no limit at all -- if a live status response
    happens to include something like a historical reading/packet log
    with hundreds of entries, that alone was enough to blow Kodi's
    textviewer dialog up to hundreds of pages (confirmed: one such
    dialog reported "1/398 pages"), which is not remotely what "show me
    this repeater's live status" should look like. This addon wants the
    LATEST snapshot, not a full historical dump, so list-of-dict fields
    now cap at max_list_items entries with a plain count of how many
    were left out -- still real data, just not an unbounded one."""
    if not isinstance(d, dict):
        return str(d)
    lines = []
    pad = "  " * indent
    for key, value in d.items():
        label = str(key).replace("_", " ").title()
        if isinstance(value, dict):
            lines.append(f"{pad}{label}:")
            lines.append(_format_key_value_dict(value, indent + 1, max_list_items))
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                lines.append(f"{pad}{label}: ({len(value)} entries)")
                for i, item in enumerate(value[:max_list_items]):
                    lines.append(f"{pad}  [{i}]")
                    lines.append(_format_key_value_dict(item, indent + 2, max_list_items))
                if len(value) > max_list_items:
                    lines.append(f"{pad}  ...and {len(value) - max_list_items} more (showing latest {max_list_items} only)")
            else:
                lines.append(f"{pad}{label}: {', '.join(str(v) for v in value) if value else '(none)'}")
        else:
            lines.append(f"{pad}{label}: {value}")
    return "\n".join(lines)


def _hops_label(n):
    if n is None:
        return "unknown"
    if n < 0:
        return "flood"
    if n == 0:
        return "direct"
    return f"{n} hop" + ("s" if n != 1 else "")


def _pct(part, whole):
    try:
        if not whole:
            return None
        return f"{(part / whole) * 100:.2f}%"
    except (TypeError, ZeroDivisionError):
        return None


def _format_repeater_telemetry(status):
    """Human-readable Telemetry section matching the browser frontend's
    layout, built from RepeaterStatusResponse. Every field is optional in
    the schema, so each line is skipped rather than shown as blank/None
    if the repeater's firmware didn't report it."""
    if not isinstance(status, dict):
        return None
    g = status.get
    lines = []

    def add(label, value):
        if value is not None:
            lines.append(f"{label}: {value}")

    battery = g("battery_volts")
    add("Battery", f"{battery}V" if battery is not None else None)
    add("Uptime", _format_duration(g("uptime_seconds")) if g("uptime_seconds") is not None else None)

    uptime = g("uptime_seconds")
    airtime = g("airtime_seconds")
    if airtime is not None:
        pct = _pct(airtime, uptime)
        add("TX Airtime", f"{_format_duration(airtime)}" + (f" ({pct})" if pct else ""))
    rx_airtime = g("rx_airtime_seconds")
    if rx_airtime is not None:
        pct = _pct(rx_airtime, uptime)
        add("RX Airtime", f"{_format_duration(rx_airtime)}" + (f" ({pct})" if pct else ""))

    add("Noise Floor", f"{g('noise_floor_dbm')} dBm" if g("noise_floor_dbm") is not None else None)
    add("Last RSSI", f"{g('last_rssi_dbm')} dBm" if g("last_rssi_dbm") is not None else None)
    add("Last SNR", f"{g('last_snr_db')} dB" if g("last_snr_db") is not None else None)

    recv, sent = g("packets_received"), g("packets_sent")
    if recv is not None or sent is not None:
        add("Packets", f"{recv:,} rx / {sent:,} tx" if recv is not None and sent is not None else f"{recv or sent:,}")

    fr, ft = g("recv_flood"), g("sent_flood")
    if fr is not None or ft is not None:
        add("Flood", f"{fr:,} rx / {ft:,} tx" if fr is not None and ft is not None else None)
    dr, dt = g("recv_direct"), g("sent_direct")
    if dr is not None or dt is not None:
        add("Direct", f"{dr:,} rx / {dt:,} tx" if dr is not None and dt is not None else None)
    fd, dd = g("flood_dups"), g("direct_dups")
    if fd is not None or dd is not None:
        add("Duplicates", f"{fd:,} flood / {dd:,} direct" if fd is not None and dd is not None else None)

    errs = g("recv_errors")
    if errs is not None:
        pct = _pct(errs, recv)
        add("RX Errors", f"{errs:,}" + (f" ({pct})" if pct else ""))
    add("TX Queue", g("tx_queue_len"))
    return "\n".join(lines) if lines else None


_LPP_UNITS = {"voltage": "V", "temperature": "\u00b0C", "humidity": "%", "pressure": "hPa"}


def _format_lpp_sensors(sensors):
    """LPP Sensors section, matching the browser frontend. Confirmed via
    the OpenAPI schema: each sensor is {channel, type_name, value}, where
    value is either a plain number or (for multi-value sensors like GPS)
    a dict of sub-fields -- shown as indented sub-lines rather than
    guessed-at units, since the schema gives no unit for those."""
    if not sensors:
        return None
    lines = []
    for s in sensors:
        type_name = str(s.get("type_name", "sensor"))
        channel = s.get("channel")
        label = f"{type_name.title()} Ch{channel}" if channel is not None else type_name.title()
        value = s.get("value")
        if isinstance(value, dict):
            lines.append(f"{label}:")
            for k, v in value.items():
                lines.append(f"  {str(k).replace('_', ' ').title()}: {v}")
        else:
            unit = _LPP_UNITS.get(type_name.lower(), "")
            lines.append(f"{label}: {value}{(' ' + unit) if unit else ''}")
    return "\n".join(lines)


def _format_message_meta(m):
    """Small info line shown under each bubble: time, hop count, RSSI, SNR.
    CONFIRMED real fields (captured from a live message object -- not
    guessed): each message carries a "paths" list, one entry per distinct
    route it was heard by, each with path_len (hop count), rssi, and snr.

    Confirmed real bug found on review: this always picked the SHORTEST
    path_len among all entries for every message, outgoing or not. For
    an outgoing message, "paths" accumulates one entry per ack as
    different relays' confirmations come back over time (confirmed via
    the schema: each MessagePath has its own received_at, i.e. these
    aren't simultaneous). Always taking the minimum meant the first,
    closest relay's ack -- often a genuinely trivial 1-hop entry --
    permanently hid every later, more distant relay's ack for the same
    message, no matter how many more came in. That's exactly why
    outgoing messages always showed "1 hop" even when real delivery was
    3+ hops away: the true value was there in the data, just discarded.
    Outgoing messages now show the MOST RECENT path (by received_at)
    instead of the shortest -- the live, current picture, updating each
    time _request_message_reload() re-fetches after a new message_acked
    event, matching what other MeshCore clients show. Incoming messages
    keep the existing shortest-path behavior, which is what you actually
    want there (how directly you heard the sender), a different question
    from "how is delivery of MY message currently going".
    """
    parts = []
    ts = m.get("received_at") or m.get("sender_timestamp")
    if ts:
        try:
            parts.append(datetime.fromtimestamp(ts).strftime("%H:%M"))
        except (ValueError, OSError, OverflowError):
            pass
    paths = m.get("paths") or []
    if paths:
        if m.get("outgoing"):
            if len(paths) > 1:
                xbmc.log(f"[RemoteTerm] outgoing message id={m.get('id')} has {len(paths)} ack "
                          f"paths: {[(p.get('path_len'), p.get('received_at')) for p in paths]}",
                          xbmc.LOGINFO)
            best = max(paths, key=lambda p: p.get("received_at", 0))
        else:
            best = min(paths, key=lambda p: p.get("path_len", 999))
        if best.get("path_len") is not None:
            parts.append(_hops_label(best["path_len"]))
        if best.get("rssi") is not None:
            parts.append(f"RSSI {best['rssi']}dBm")
        if best.get("snr") is not None:
            parts.append(f"SNR {best['snr']}dB")
    return "   ".join(parts)


def _strip_redundant_sender_prefix(text, sender_name):
    """Confirmed from a live message object: channel messages' "text" field
    comes back with the sender's own name baked in as a literal prefix
    (e.g. text = "KR1IS-C Solar :  Yeah, sometimes..." for a message whose
    sender_name is "KR1IS-C Solar "). Since the sender name is already
    shown separately as the bubble's bold header, leaving it in the body
    too wastes real space inside an already-tight fixed bubble -- likely
    part of why some messages needed more lines than expected while
    others didn't, depending on how long that particular sender's name
    happened to be."""
    if not text or not sender_name:
        return text
    prefix = sender_name + ":"
    if text.startswith(prefix):
        return text[len(prefix):].lstrip()
    return text


class KodiExitMonitor(xbmc.Monitor):
    """Kodi calls onAbortRequested() when the whole application is quitting
    -- confirmed in practice: without this, the addon's main() sits blocked
    inside window.doModal() with no way to know Kodi wants it to exit, so
    Kodi's watchdog has to wait out a 5-second grace period and then force-
    kill the script (visible in the log as "script didn't stop in 5
    seconds"). Closing the window here lets doModal() return immediately
    and the normal close()/cleanup path run instead."""

    def __init__(self, window):
        super(KodiExitMonitor, self).__init__()
        self._window = window

    def onAbortRequested(self):
        try:
            self._window.close()
        except Exception:
            pass


class RemoteTermWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super(RemoteTermWindow, self).__init__(*args, **kwargs)
        self.api = RemoteTermAPI()
        self.conversations = []
        self.contacts_all = []
        self.selected = None
        self.contacts_filter = None
        self.contacts_sort = "recent"
        self.repeater_sort = "recent"  # mirrors contacts_sort's values/
                                        # meaning, but scoped separately
                                        # to the Repeater Console's own
                                        # picker list
        self.map_zoom_mode = "regional"  # or "local" -- toggled by the
                                          # Regional/Local View buttons
        self.map_pan_center = None  # (lat, lon) once panned or centered
                                     # on a selected node; None means use
                                     # the real home location (own
                                     # configured/auto-seeded coords, or
                                     # the located-nodes centroid)
        self.packets_my_nodes_only = False  # "My Nodes" toggle on the
                                             # Packets tab, matching the
                                             # same real feature/wording
                                             # confirmed from CoreScope
                                             # (the reference frontend
                                             # this feed was modeled on)
        self.repeater_terminal_lines = []  # accumulated CLI command/
                                            # response scrollback for the
                                            # Repeater Console -- real
                                            # gap fixed: responses used
                                            # to only ever show as a
                                            # transient toast, with the
                                            # actual response text
                                            # discarded entirely
        self.favorites_only = False
        self.show_waterfall = False
        self.selected_repeater = None
        self._last_convo_snapshot = None  # see _convo_snapshot -- lets a WS
                                           # contact/channel event skip a
                                           # disruptive list rebuild when
                                           # nothing visible actually changed
        self._analytics_history = deque()  # (timestamp, total_packets,
                                           # decrypted, packets_recv,
                                           # flood_tx, direct_tx, flood_rx,
                                           # direct_rx, rx_air_secs,
                                           # tx_air_secs) samples
                                           # over the last ~5 minutes, so
                                           # the Decrypt Rate/Packet Activity
                                           # gauges compare against a big
                                           # enough window to be stable
                                           # instead of one noisy poll tick
        self._last_decrypt_pct = 0
        self._unread_counts = {}  # conversation_key -> count. Seeded from
                                   # the server's own GET /api/read-state/
                                   # unreads on startup (confirmed via the
                                   # OpenAPI schema this exists), then kept
                                   # current incrementally as messages
                                   # arrive over the WS -- no longer a
                                   # purely client-side guess that resets
                                   # to zero on every addon restart.
        self._push_conversations = set()  # conversation state keys
                                   # currently opted into push
                                   # notifications, from GET
                                   # /api/push/conversations. Only
                                   # conversations in this set trigger a
                                   # Kodi notification toast on an
                                   # incoming message -- this is what
                                   # stops every single thing heard on
                                   # the mesh from popping a notification.
        self._mentions = set()    # conversation state keys the server
                                   # flagged as having an unread mention,
                                   # from GET /api/read-state/unreads.
        self._cached_messages = []       # full, already-sorted history for
                                          # the open conversation -- "Load
                                          # More" re-slices this locally
                                          # instead of hitting the network
        self._message_display_limit = MESSAGE_DISPLAY_DEFAULT
        self.packet_feed = deque(maxlen=PACKET_FEED_MAXLEN)
        self.packet_feed_lock = threading.Lock()
        self.ws = None
        self._last_message_id = 0
        self._messages_dirty = False
        self._last_reload_time = 0
        self._message_list_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._dashboard_thread = None
        self._analytics_thread = None
        self._message_poll_thread = None
        self._notification_sync_thread = None
        self._exit_monitor = None

    # -- lifecycle ------------------------------------------------------------

    def onInit(self):
        try:
            self._do_init()
        except Exception:
            xbmc.log(f"[RemoteTerm] onInit crashed:\n{traceback.format_exc()}", xbmc.LOGERROR)

    def _do_init(self):
        # Confirmed real bug candidate: a report of the addon silently
        # landing back on the Dashboard tab mid-session, after a
        # multi-minute gap with no logged click, no Back/Backspace press
        # (which is explicitly logged elsewhere), and no error of any
        # kind -- while the user was mid-way through a live repeater
        # query, which is exactly the kind of slow network operation
        # that can trip Kodi's own script-responsiveness handling. This
        # method unconditionally reset the tab to Dashboard and
        # restarted every background refresh timer/thread on every call
        # -- fine if it only ever ran once, but if Kodi ever re-invokes
        # onInit on the same window instance (e.g. after intervening on
        # an unresponsive script), this would both explain the silent
        # jump to Dashboard AND spin up duplicate timer threads running
        # alongside the original ones, a second, worse bug compounding
        # the first. Guarded so real initialization only ever happens
        # once per window instance; logged either way so a recurrence is
        # now provable instead of a mystery.
        if getattr(self, "_initialized", False):
            xbmc.log("[RemoteTerm] onInit called again on an already-initialized window -- "
                      "skipping re-init (this log line, if it ever appears, is itself the "
                      "confirmation that Kodi re-invoked onInit mid-session)", xbmc.LOGWARNING)
            return
        self._initialized = True
        # A checkable build marker: this whole conversation's history has
        # repeatedly hit the same wall diagnosing a report -- a fix gets
        # shipped, the next log shows no trace of it at all, and there's
        # no way to tell "the fix isn't in what's actually running" apart
        # from "it ran and did nothing" without asking the person to dig
        # up their addon.xml. One line here removes the ambiguity for
        # every future report, not just this one.
        try:
            xbmc.log(f"[RemoteTerm] starting addon version {self.api.addon.getAddonInfo('version')}", xbmc.LOGINFO)
        except Exception:
            pass

        self.convo_list = self.getControl(ID_CONVO_LIST)
        self.message_list = self.getControl(ID_MESSAGE_LIST)
        # Confirmed real bug, traced through a log: this list starts with
        # zero items (nothing is populated into it until a conversation
        # is actually opened), and a Kodi list with zero items simply
        # cannot receive focus at all -- it's silently skipped. Every
        # header control that can neighbor it (Search, Notify, the
        # favorite star, the "Favorites Only" toggle) has an explicit
        # ondown/onright pointing here, and when the target can't be
        # focused, Kodi falls back to its own automatic nearest-neighbor
        # navigation for that keypress instead of just failing -- which,
        # in this sparse header-plus-mostly-empty-canvas layout, could
        # land anywhere, including jumping all the way to a nav-rail
        # icon. That's what a real report of getting stranded on the
        # rail with no way back into this tab traced back to: not a bug
        # in the favorites toggle itself, but this list being an
        # unfocusable dead end in the navigation graph whenever no
        # conversation is open. Same fix already proven safe for the
        # conversation list's own empty state (_populate_convo_list adds
        # a placeholder row rather than leaving it at zero items) --
        # applied here too, so this list is never a dead end.
        self.message_list.addItem(xbmcgui.ListItem("Select a contact or channel to view messages"))
        self.convo_title = self.getControl(ID_CONVO_TITLE)
        self.status_dot = self.getControl(ID_STATUS_DOT)
        self.status_text = self.getControl(ID_STATUS_TEXT)
        self.contacts_list = self.getControl(ID_CONTACTS_LIST)
        self.map_label = self.getControl(ID_MAP_LABEL)
        self.map_list = self.getControl(ID_MAP_LIST)
        self.packet_list = self.getControl(ID_PACKET_LIST)
        self.packet_status = self.getControl(ID_PACKET_STATUS)
        self.repeater_picker = self.getControl(ID_REPEATER_PICKER)
        self.repeater_neighbors = self.getControl(ID_REPEATER_NEIGHBORS)
        self.repeater_acl = self.getControl(ID_REPEATER_ACL)
        self.repeater_info = self.getControl(ID_REPEATER_INFO)
        self.repeater_terminal = self.getControl(ID_REPEATER_TERMINAL)
        self.notify_toggle = self.getControl(ID_NOTIFY_TOGGLE)

        self._exit_monitor = KodiExitMonitor(self)
        self.setProperty("tab", TAB_DASHBOARD)
        self.refresh()
        self.setFocusId(ID_NAV_DASHBOARD)
        self._load_dashboard()
        # Confirmed real request: Analytics' own gauges/bars/live feed
        # stayed completely blank until the tab was actually visited even
        # once, since _load_analytics() -- unlike Dashboard's own load
        # just above -- was only ever called from that tab's own nav-icon
        # click handler and its autorefresh loop, and that loop is itself
        # gated on the tab already being on screen (see
        # _start_analytics_autorefresh below). A first-time visit landed
        # on a page with nothing populated yet, and had to wait out a
        # full refresh cycle before showing anything real. Loading it
        # once here mirrors exactly what already happens for Dashboard on
        # the line above -- on a background thread, since this one makes
        # two real network calls (see _load_analytics's own docstring).
        threading.Thread(target=self._load_analytics, daemon=True).start()
        self._start_dashboard_autorefresh()
        self._start_analytics_autorefresh()
        self._start_message_poll()
        self._start_live_updates()
        self._start_notification_sync()
        # Confirmed real report: a user found their map/distance location
        # settings still blank after using the addon normally, with no
        # indication anything was wrong or any action needed on their
        # part. The auto-seed logic in api.py's map_center property is
        # correct and does pull real lat/lon from the radio's own
        # GET /api/radio/config -- but it's a property, only evaluated
        # as a side effect of actually opening the Map tab or sorting
        # Nodes by distance. A user who checks Settings (or simply
        # never visits either of those two tabs) first would never
        # trigger it at all, seeing blank fields with nothing to explain
        # why, regardless of whether their radio actually has real GPS
        # data. Touching the property once here, right at startup,
        # gives every session a chance to auto-fill immediately rather
        # than depending on which tab happens to be opened first -- on
        # a background thread since it's a real network call.
        #
        # This line logs unconditionally, before the thread even starts,
        # specifically so a future log capture can distinguish "this
        # code isn't running yet" from "it ran and something failed" --
        # the previous two attempts to diagnose this were both blocked
        # by not being able to tell those apart from the log alone.
        xbmc.log("[RemoteTerm] _do_init: starting startup map-center seed attempt", xbmc.LOGINFO)
        threading.Thread(target=self._seed_map_center_at_startup, daemon=True).start()
        # Confirmed real report, across three full rounds of fixes that
        # each ruled out the previous theory: the Python side of the
        # waterfall toggle was never the problem -- extensive logging
        # confirmed every single toggle correctly flipped the property,
        # every single render call found packets and colored all 30 bars
        # with zero failures, every time, while the screen kept showing
        # nothing. Removing the XML-side <visible> conditions in favor of
        # Python-only setVisible() calls (the previous attempt) made no
        # difference either. The one thing every failing control had in
        # common: each started as <visible>false</visible> from the very
        # first frame the window ever drew, having never been shown even
        # once. Hiding a control that WAS already showing worked
        # perfectly every time (confirmed via a screenshot: the Live Feed
        # list, its title, and its dot all correctly disappeared) --
        # showing one that had been invisible since window creation
        # never did, suggesting Kodi doesn't fully initialize a control's
        # render resources until it's genuinely been visible at least
        # once. These controls now start visible="true" in the XML so
        # Kodi initializes them properly at parse time, and are hidden
        # here, once, immediately after that initial parse -- so every
        # later setVisible(True) from the toggle is reviving a control
        # that has already been fully rendered before, not asking Kodi to
        # show something for the very first time.
        try:
            for ctrl_id in (ID_WATERFALL_LABEL, ID_WATERFALL_SUBTITLE, ID_WATERFALL_BACKDROP,
                             ID_WATERFALL_ON_INDICATOR, ID_WATERFALL_WAITING_LABEL) + WATERFALL_BAR_IDS:
                self.getControl(ctrl_id).setVisible(False)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] waterfall startup hide pass failed: {e}", xbmc.LOGERROR)
        # Confirmed real request: a skin's Program Addons widget (or a
        # custom shortcut) can only ever launch this addon fresh, always
        # landing on Dashboard -- there was no way for a widget entry, or
        # a shortcut someone builds themselves, to jump straight to e.g.
        # Chats or the Map. main.py already had exactly the right
        # mechanism for this (see its own "mapinfo" argument, used for a
        # completely different purpose): a program addon is re-invoked
        # via RunScript(addon_id, argument), which arrives as sys.argv[1]
        # -- extended here to also recognize a tab name and act on it.
        # Dashboard itself is still fully loaded above regardless of
        # where this sends the user, so backing out to it later shows
        # real data immediately instead of nothing until the next
        # autorefresh tick.
        requested_tab = getattr(self, "initial_tab", None)
        if requested_tab:
            xbmc.log(f"[RemoteTerm] _do_init: launched directly into tab={requested_tab!r} "
                      f"via RunScript argument", xbmc.LOGINFO)
            self._launch_into_tab(requested_tab)

    def _launch_into_tab(self, tab_name):
        """Jumps directly into a specific tab right after the normal
        Dashboard-first startup has already run (see the end of
        _do_init above) -- the actual mechanism behind letting a skin's
        Program Addons widget, or a custom shortcut, deep-link straight
        into e.g. Chats or the Map instead of requiring the addon to be
        opened and the nav rail navigated manually every time.
        Deliberately mirrors each tab's own nav-icon click handler by
        duplicating its exact steps rather than sharing code with it --
        keeping this fully separate means nothing about what a normal
        rail click does can be accidentally changed by this. Silently
        does nothing for "dashboard" itself or any unrecognized name,
        since Dashboard is already the default landing state set up
        above."""
        if tab_name == "chats":
            self._populate_convo_list(self._visible_conversations())
            self._switch_tab(TAB_CHATS, ID_CONVO_LIST)
            threading.Thread(target=self._load_notification_state, daemon=True).start()
        elif tab_name == "nodes":
            self.contacts_filter = None
            self._populate_contacts()
            self._switch_tab(TAB_CONTACTS, ID_CONTACTS_FILTER_ALL)
        elif tab_name == "repeaters":
            threading.Thread(target=self._load_repeater_console, daemon=True).start()
            self._switch_tab(TAB_REPEATERS, ID_REPEATER_PICKER)
        elif tab_name == "map":
            threading.Thread(target=self._load_map, daemon=True).start()
            self._switch_tab(TAB_MAP, ID_MAP_REFRESH)
        elif tab_name == "packets":
            self._render_packet_feed()
            self._switch_tab(TAB_PACKETS, ID_PACKET_LIST)
        elif tab_name == "analytics":
            self._load_analytics()
            self._switch_tab(TAB_ANALYTICS, ID_REFRESH)
            if self.show_waterfall:
                self._generate_waterfall_bars()

    def _seed_map_center_at_startup(self):
        """Just accessing self.api.map_center is enough to trigger its own
        auto-seed side effect (see api.py) -- but confirmed real bug in
        THIS wrapper's first version: it was a bare, unguarded lambda
        passed straight to threading.Thread, unlike every other
        background thread in this file, which all point at a named
        function that does its own try/except internally. map_center's
        own except clause only catches (TypeError, ValueError); any
        other exception (a Kodi Settings-API call behaving unexpectedly
        during early startup is a real, seen-elsewhere possibility, not
        a hypothetical one) would have propagated straight out of that
        bare lambda and killed the thread completely silently -- no
        traceback in kodi.log, nothing. That silence was indistinguishable
        from the feature simply never running, which is exactly what a
        real log capture showed: no request, no success, no failure,
        nothing at all. This wrapper exists solely to guarantee that
        whatever happens here, something ends up in the log."""
        try:
            self.api.map_center
        except Exception as e:
            xbmc.log(f"[RemoteTerm] startup map-center seed attempt failed unexpectedly: {e}", xbmc.LOGINFO)

    def close(self):
        self._stop_event.set()
        if self.ws:
            self.ws.stop()
        super(RemoteTermWindow, self).close()

    def _switch_tab(self, tab_name, focus_id=None):
        """Changing Window.Property(tab) and moving focus into the newly
        visible group in the same instant is unreliable -- Kodi hasn't
        re-evaluated the group's <visible> condition yet, so setFocusId can
        silently no-op and focus is left stranded on the nav rail. A short
        settle delay before the focus call fixes it."""
        self.setProperty("tab", tab_name)
        if focus_id is not None:
            xbmc.sleep(FOCUS_SETTLE_MS)
            try:
                self.setFocusId(focus_id)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] setFocusId({focus_id}) failed: {e}", xbmc.LOGDEBUG)

    def _guard_chat_focus(self, prev_focus=None):
        """Self-healing correction for a now-precisely-confirmed Kodi
        behavior: calling reset() on the conversation list can cause Kodi
        to lose track of whatever control currently has focus and fall
        back to a nav-rail icon -- confirmed via log evidence showing this
        firing synchronously, on the main thread, immediately after a
        plain button click (the favorites-filter toggle), with no
        threading involved at all. Not a race: fully deterministic,
        triggered by the reset() call itself. Restores to prev_focus (the
        control that actually had focus right before the rebuild) when
        that's known and still valid, so e.g. clicking the favorites
        toggle leaves focus back on that same toggle instead of a generic
        fallback -- falls back to the conversation list only if prev_focus
        wasn't captured or isn't one of this tab's own controls.

        Checks focus_id == prev_focus FIRST, before anything else:
        confirmed real bug (log evidence: 8 corrections in under 20
        seconds while a user tried to arrow across the nav rail with
        packets flowing) -- without this check, simply RESTING on any
        control outside the allowed set counts as "drift" regardless of
        whether reset() actually moved anything, which fights a user who
        has legitimately arrow-keyed onto some other nav-rail icon while
        still technically "on" this tab (arrow-key browsing of the rail
        doesn't change the tab property -- only an actual click does).
        Since prev_focus is captured immediately before reset() on this
        same thread with no gap for user input in between, focus_id
        differing from it is the only real evidence the reset() itself
        moved something; if they're equal, nothing happened and the
        user's actual focus -- wherever it is -- must be left alone."""
        if self.getProperty("tab") != TAB_CHATS:
            return
        focus_id = self.getFocusId()
        if focus_id == prev_focus:
            return
        allowed = (ID_CONVO_LIST, ID_MESSAGE_LIST, ID_COMPOSE, ID_FAVORITE_TOGGLE, ID_NOTIFY_TOGGLE, ID_FAVORITES_FILTER, ID_SEARCH_BUTTON)
        if focus_id not in allowed:
            target = prev_focus if prev_focus in allowed else ID_CONVO_LIST
            xbmc.log(f"[RemoteTerm] focus drift detected (focus={focus_id} while tab=chats), "
                      f"restoring to {target}", xbmc.LOGINFO)
            try:
                self.setFocusId(target)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] focus restore failed: {e}", xbmc.LOGDEBUG)

    def _guard_packet_focus(self, prev_focus=None):
        """Same confirmed Kodi behavior as _guard_chat_focus above (a
        list reset() can silently knock focus onto an unrelated nav-rail
        icon), but the trigger here is worse: _render_packet_feed()'s
        reset() of the packet list isn't just a response to a user's own
        click -- it also fires from _handle_raw_packet() on the
        WebSocket background thread, completely unprompted, every single
        time a raw_packet event arrives while this tab is showing. That
        makes this a genuine race rather than a synchronous side effect:
        a packet arriving at exactly the wrong moment (confirmed via a
        real Kodi log capture) silently bounced focus to ID_NAV_DASHBOARD
        while Packets was still the tab actually on screen -- and because
        that happened to be a nav-rail icon, a single Back press then
        exited the whole addon instead of the two presses it should take
        to get from inside this tab back out entirely. ID_NAV_PACKETS is
        deliberately included in `allowed`: sitting focused on this tab's
        own icon (e.g. right after a first Back press) is a legitimate
        resting state that a live packet arriving a moment later
        shouldn't be allowed to undo.

        Checks focus_id == prev_focus FIRST -- see _guard_chat_focus's
        docstring for the full explanation. This matters even more here:
        _handle_raw_packet fires continuously while packets are flowing
        (essentially always, on a live mesh), so without this check every
        single arrival would fight a user who's simply arrow-browsing the
        nav rail without having actually switched tabs yet."""
        if self.getProperty("tab") != TAB_PACKETS:
            return
        focus_id = self.getFocusId()
        if focus_id == prev_focus:
            return
        allowed = (ID_PACKET_LIST, ID_PACKET_MY_NODES_BTN, ID_NAV_PACKETS)
        if focus_id not in allowed:
            target = prev_focus if prev_focus in allowed else ID_PACKET_LIST
            xbmc.log(f"[RemoteTerm] focus drift detected (focus={focus_id} while tab=packets), "
                      f"restoring to {target}", xbmc.LOGINFO)
            try:
                self.setFocusId(target)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] focus restore failed: {e}", xbmc.LOGDEBUG)

    def _guard_analytics_focus(self, prev_focus=None):
        """Analytics' own version of _guard_packet_focus above -- same WS
        background-thread trigger (_handle_raw_packet calls
        _render_analytics_live_feed() on every raw_packet event while
        this tab is showing), same reset()-causes-drift-to-Dashboard
        Kodi behavior, same fix. ID_NAV_ANALYTICS is included in
        `allowed` for the identical reason: focus legitimately resting
        on this tab's own icon after a first Back press shouldn't be
        undone by a live packet arriving moments later.

        Checks focus_id == prev_focus FIRST -- see _guard_chat_focus's
        docstring for the full explanation. Confirmed the actual bug in
        practice via a real log capture: 8 separate "restoring to 103"
        corrections in under 20 seconds while a user tried to arrow
        across the nav rail (9009, 9001, 9005, 9002, 9006, 9007 in turn)
        -- every single attempt got yanked back to the refresh button
        because packets kept arriving and re-triggering this guard's old
        allowed-set-only check, which treated simply resting on any other
        rail icon as drift regardless of whether anything had actually
        moved. That made the rail effectively unusable from this tab
        whenever packets were flowing, which on a live mesh is
        essentially always."""
        if self.getProperty("tab") != TAB_ANALYTICS:
            return
        focus_id = self.getFocusId()
        if focus_id == prev_focus:
            return
        allowed = (ID_REFRESH, ID_ANALYTICS_LIVE_FEED, ID_NAV_ANALYTICS)
        if focus_id not in allowed:
            target = prev_focus if prev_focus in allowed else ID_REFRESH
            xbmc.log(f"[RemoteTerm] focus drift detected (focus={focus_id} while tab=analytics), "
                      f"restoring to {target}", xbmc.LOGINFO)
            try:
                self.setFocusId(target)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] focus restore failed: {e}", xbmc.LOGDEBUG)

    # -- background workers --------------------------------------------------

    def _should_stop(self, timeout):
        """Sleeps up to `timeout` seconds, returning True as soon as either
        this window wants to stop or Kodi itself is shutting down.
        xbmc.Monitor().waitForAbort() is the standard, fast-responding way
        to detect a full application quit -- relying only on this window's
        own close() being called in time was confirmed insufficient: Kodi
        logged "script didn't stop in 5 seconds" and force-killed the
        script more than once during real application shutdown."""
        if self._stop_event.is_set():
            return True
        return self._exit_monitor.waitForAbort(timeout) if self._exit_monitor else self._stop_event.wait(timeout)

    def _start_dashboard_autorefresh(self):
        def loop():
            while not self._should_stop(DASHBOARD_REFRESH_SECS):
                if self.getProperty("tab") == TAB_DASHBOARD:
                    try:
                        self._load_dashboard()
                    except Exception as e:
                        xbmc.log(f"[RemoteTerm] dashboard auto-refresh error: {e}", xbmc.LOGDEBUG)
        self._dashboard_thread = threading.Thread(target=loop, daemon=True)
        self._dashboard_thread.start()

    def _start_analytics_autorefresh(self):
        """Separate, much faster loop than Dashboard's -- confirmed real
        complaint: gauges/bars visibly lagged behind packets that had
        already arrived, because Analytics was sharing Dashboard's 15s
        cadence. This only runs its (more expensive, 2-network-call)
        refresh while the Analytics tab is actually on screen, same
        tab-gating pattern as the dashboard loop."""
        def loop():
            while not self._should_stop(ANALYTICS_REFRESH_SECS):
                if self.getProperty("tab") == TAB_ANALYTICS:
                    try:
                        self._load_analytics()
                    except Exception as e:
                        xbmc.log(f"[RemoteTerm] analytics auto-refresh error: {e}", xbmc.LOGDEBUG)
        self._analytics_thread = threading.Thread(target=loop, daemon=True)
        self._analytics_thread.start()

    def _start_notification_sync(self):
        """Keeps push-enabled conversations and unread counts current
        continuously, not just once at startup or when the Chats tab
        happens to be opened -- confirmed necessary: a conversation
        toggled on the backend while this addon sat on another tab (or
        just hadn't revisited Chats yet) would keep acting on the stale
        list it fetched at launch."""
        def loop():
            while not self._should_stop(NOTIFICATION_SYNC_SECS):
                try:
                    self._load_notification_state()
                except Exception as e:
                    xbmc.log(f"[RemoteTerm] notification sync error: {e}", xbmc.LOGDEBUG)
        self._notification_sync_thread = threading.Thread(target=loop, daemon=True)
        self._notification_sync_thread.start()

    def _start_message_poll(self):
        """Runs frequently but does very little work: a cheap 50-row peek
        (see api.get_latest_message_id) that only flags "something changed"
        rather than fetching anything expensive. The actual expensive full
        reload is centralized in _request_message_reload's debounce, so a
        busy channel pushing many WS events per second still reloads at
        most once every MESSAGE_RELOAD_MIN_INTERVAL seconds -- a real
        deployment log showed a full ~5000-message history walk firing
        every 2-3 seconds without this, which is enough load to make the
        whole addon feel unresponsive."""
        def loop():
            while not self._should_stop(MESSAGE_POLL_SECS):
                if self.selected and self.getProperty("tab") == TAB_CHATS:
                    try:
                        self._poll_new_messages()
                    except Exception as e:
                        xbmc.log(f"[RemoteTerm] message poll error: {e}", xbmc.LOGDEBUG)
                self._flush_message_reload_if_due()
        self._message_poll_thread = threading.Thread(target=loop, daemon=True)
        self._message_poll_thread.start()

    def _request_message_reload(self):
        """Marks the open conversation as needing a refresh without
        necessarily doing one right away -- see _flush_message_reload_if_due."""
        self._messages_dirty = True

    def _flush_message_reload_if_due(self):
        if not self._messages_dirty or not self.selected:
            return
        if self.getProperty("tab") != TAB_CHATS:
            return
        if time.time() - self._last_reload_time < MESSAGE_RELOAD_MIN_INTERVAL:
            return
        self._reload_messages_if_free()

    def _start_live_updates(self):
        if not self.api.live_updates_enabled:
            self.packet_status.setLabel("Live feed disabled in settings")
            return
        self.ws = RemoteTermEventStream(
            host=self.api.host, verify_ssl=self.api.verify_ssl, auth=self.api.auth,
            on_event=self._on_ws_event, on_status_change=self._on_ws_status_change,
        )
        self.ws.start()

    def _on_ws_status_change(self, connected):
        try:
            self.setProperty("live", "true" if connected else "false")
            if connected:
                self.packet_status.setLabel("Live feed connected")
            else:
                self.packet_status.setLabel(
                    "Live feed unreachable -- if this never connects, make sure your "
                    "nginx reverse proxy forwards WebSocket upgrades for /api/ws "
                    "(Upgrade/Connection headers). Messages still update via polling."
                )
        except Exception:
            pass

    def _on_ws_event(self, event):
        etype = event.get("type")
        # Confirmed from a live payload capture: every WS event is wrapped
        # as {"type": ..., "data": {...actual fields...}}. Earlier code read
        # fields straight off the outer envelope, which only has "type" --
        # that's why message events always showed conversation=None and
        # packets never matched any real field.
        payload = event.get("data", event) if isinstance(event.get("data"), dict) else event
        try:
            if etype == "message":
                self._handle_incoming_message(payload)
            elif etype == "message_acked":
                if self.selected:
                    self._request_message_reload()
            elif etype in ("contact", "contact_deleted", "contact_resolved",
                           "channel", "channel_deleted"):
                self._load_conversations()
                if self.getProperty("tab") == TAB_CHATS:
                    # Rebuilding the list (reset() + repopulate) is what
                    # triggers Kodi's focus-loss behavior, confirmed
                    # precisely enough now to know the trigger is the
                    # reset() call itself, not any particular feature.
                    # "contact"/"channel" events fire routinely for
                    # metadata churn (e.g. a contact's last-seen time
                    # updating) that doesn't change what's actually shown
                    # in this list at all -- log evidence showed this
                    # WS-driven path alone firing the rebuild 8 times in
                    # 3 minutes. Comparing against what's already on
                    # screen and only rebuilding when the visible content
                    # would actually differ cuts most of that out instead
                    # of just correcting the disruption after each one.
                    visible = self._visible_conversations()
                    if self._convo_snapshot(visible) != self._last_convo_snapshot:
                        self._populate_convo_list(visible)
                elif self.getProperty("tab") == TAB_CONTACTS:
                    self._populate_contacts()
            elif etype == "health":
                self._render_health(payload)
            elif etype == "raw_packet":
                self._handle_raw_packet(payload)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] ws event dispatch error: {e}", xbmc.LOGDEBUG)

    def _handle_incoming_message(self, message):
        # Confirmed via the OpenAPI Message schema: the field is
        # "conversation_key" -- the other candidates are kept only as a
        # defensive fallback in case a future API version renames it, not
        # because the name was ever actually in doubt.
        conv_key = (message.get("conversation_key") or message.get("channel_key")
                    or message.get("contact_key") or message.get("destination"))
        if self.selected and conv_key and self.selected.get("key") == conv_key:
            self._request_message_reload()
        elif not message.get("outgoing"):
            if conv_key:
                # Seeded from the server's own GET /api/read-state/unreads
                # at startup, then incremented locally as messages arrive
                # -- see _load_notification_state for why this is no
                # longer a purely client-side guess.
                self._unread_counts[conv_key] = self._unread_counts.get(conv_key, 0) + 1
                if self.getProperty("tab") == TAB_CHATS:
                    # Was a full _populate_convo_list() rebuild -- confirmed
                    # by log (a Kodi notification toast opening at the
                    # exact same moment as a focus drift, repeatedly) that
                    # this was now the dominant trigger for the reset()-
                    # causes-focus-loss issue, since messages arrive far
                    # more often than the contact/channel metadata changes
                    # handled elsewhere. Updating the one affected row's
                    # badge property directly, with no reset() at all,
                    # sidesteps the problem instead of working around it.
                    self._update_unread_badge_in_place(conv_key)

            # THE FIX: a notification toast used to fire here for every
            # single non-outgoing message on every conversation, with no
            # check against anything -- so from the moment the addon
            # started, literally everything heard on the mesh (a busy
            # public channel, every repeater chirp routed as a DM, etc.)
            # popped a toast. Confirmed via the OpenAPI schema that the
            # RemoteTerm backend has its own explicit opt-in mechanism for
            # exactly this (GET/POST /api/push/conversations), completely
            # separate from unread tracking -- a conversation not in that
            # list should update its unread badge (above) but never pop a
            # toast. A fresh install's push list is empty by design until
            # the user turns notifications on for a conversation via the
            # Notify button in its header.
            #
            # The push list uses type-prefixed state keys ("channel-...",
            # "contact-..."), not the bare key used everywhere else in
            # this addon. Checking both possible prefixes directly here
            # (rather than first looking up the conversation's type from
            # self.conversations) means this can't go wrong even if that
            # list is momentarily stale or the lookup misses -- it only
            # depends on conv_key itself.
            channel_state_key = f"channel-{conv_key}" if conv_key else None
            contact_state_key = f"contact-{conv_key}" if conv_key else None
            enabled = bool(conv_key) and (
                channel_state_key in self._push_conversations
                or contact_state_key in self._push_conversations
            )
            xbmc.log(f"[RemoteTerm] notify check: conv_key={conv_key!r} "
                     f"channel_key_in_list={channel_state_key in self._push_conversations if channel_state_key else False} "
                     f"contact_key_in_list={contact_state_key in self._push_conversations if contact_state_key else False} "
                     f"-> {'NOTIFY' if enabled else 'suppressed'}", xbmc.LOGINFO)
            if not enabled:
                return

            # Previously used raw text: if a message was entirely emoji,
            # _safe_label_text's emoji-stripping (needed elsewhere to stop
            # a real Kodi label-truncation bug) would leave nothing behind,
            # showing an empty notification body -- exactly what was
            # reported. Dialog().notification() is a plain OS-level toast,
            # not a tag-parsed label, so there's no known reason emoji
            # would break it; _safe_message_text keeps them.
            label = _safe_message_text(message.get("sender_name") or message.get("channel_name")
                                        or message.get("sender") or "RemoteTerm")
            body = _safe_message_text((message.get("text") or message.get("message") or "")[:60])
            xbmcgui.Dialog().notification(label, body, xbmcgui.NOTIFICATION_INFO, 4000)

    def _update_unread_badge_in_place(self, conv_key):
        """Updates one row's unread-count property directly via
        getListItem(), rather than reset()+rebuilding the whole list.
        getListItem() returns a live reference to the actual item already
        on screen -- changing its property updates the badge (Kodi
        re-evaluates the <visible> binding automatically) without ever
        calling reset(), so none of the reset()-triggered focus/selection
        loss can happen here. Relies on the "index" property set during
        the last full _populate_convo_list() still matching
        _visible_conversations()'s current order, which holds as long as
        nothing has re-sorted the list in between -- true here since
        _load_conversations() isn't called on this path."""
        source = self._visible_conversations()
        count = self._unread_counts.get(conv_key, 0)
        # Exact count shown, no "9+" cap -- see _populate_convo_list for
        # why (the requested change is to be able to read 11, 35, etc.
        # rather than a vague "9+"). Only caps at 3 digits, purely so a
        # pathological count (thousands of unread in a very old, very
        # busy channel) doesn't visually overflow the badge.
        display_value = (str(count) if count <= 999 else "999+") if count else ""
        try:
            for i in range(self.convo_list.size()):
                item = self.convo_list.getListItem(i)
                idx_str = item.getProperty("index")
                if idx_str.isdigit() and int(idx_str) < len(source) and source[int(idx_str)]["key"] == conv_key:
                    item.setProperty("unread_count", display_value)
                    return
        except Exception as e:
            xbmc.log(f"[RemoteTerm] in-place badge update failed: {e}", xbmc.LOGDEBUG)

    def _handle_raw_packet(self, packet):
        # Log the full raw payload (just the first few) so the actual field
        # names/shapes are known for certain rather than guessed at again.
        with self.packet_feed_lock:
            first_time = len(self.packet_feed) < 3
            self.packet_feed.appendleft(packet)
        if first_time:
            xbmc.log(f"[RemoteTerm] raw_packet payload: {packet}", xbmc.LOGINFO)
        if self.getProperty("tab") == TAB_PACKETS:
            self._render_packet_feed()
        elif self.getProperty("tab") == TAB_ANALYTICS:
            if self.show_waterfall:
                self._generate_waterfall_bars()
            else:
                self._render_analytics_live_feed()

    def _poll_new_messages(self):
        if not self.selected:
            return
        msg_type = "CHAN" if self.selected["type"] == "channel" else "PRIV"
        latest_id = self.api.get_latest_message_id(self.selected["key"], msg_type)
        if latest_id > self._last_message_id:
            self._request_message_reload()

    # -- top-level refresh ----------------------------------------------------

    def refresh(self):
        # Confirmed real bug: this unconditionally moved keyboard focus to
        # the Dashboard nav icon every time it ran -- fine for the one
        # legitimate case (initial app load, now handled explicitly in
        # onInit instead), but this method is ALSO called by the global
        # header refresh button (ID_REFRESH), which is reachable from
        # every tab. Clicking it while on Nodes (or any other tab) was
        # silently yanking focus back to the nav rail's Dashboard icon
        # even though the tab's own content correctly stayed put --
        # exactly the "refresh kicks me back to the nav rail" report.
        # Refreshing status/conversations in the background should never
        # move focus on its own; removed entirely rather than guarded,
        # since no caller of this method should be deciding where focus
        # belongs.
        self._load_status()
        self._load_conversations()

    def _load_status(self):
        health = self.api.get_health()
        xbmc.log(f"[RemoteTerm] health check response: {health!r}", xbmc.LOGINFO)
        self._render_health(health)

    def _render_health(self, status):
        if not status:
            self.status_dot.setColorDiffuse(RED)
            self.status_text.setLabel("Disconnected -- check RemoteTerm URL in Add-on Settings")
            return
        # Server responded -- it's reachable no matter what shape the
        # payload turns out to be. Render the most informative state we
        # can from whatever fields are actually present, rather than
        # risking a false "Disconnected" from a field-name mismatch.
        radio_connected = status.get("radio_connected")
        if radio_connected:
            info = status.get("connection_info") or "Radio connected"
            self.status_dot.setColorDiffuse(GREEN)
            self.status_text.setLabel(info)
        elif radio_connected is False:
            self.status_dot.setColorDiffuse(AMBER)
            self.status_text.setLabel(f"Server reachable -- radio {status.get('radio_state', 'not connected')}")
        elif status.get("status") in ("ok", "healthy", "up"):
            self.status_dot.setColorDiffuse(AMBER)
            self.status_text.setLabel("Server reachable")
        else:
            # Reachable, but the payload doesn't match any field we
            # recognize -- still better than a blanket "Disconnected".
            self.status_dot.setColorDiffuse(AMBER)
            summary = ", ".join(f"{k}={v}" for k, v in list(status.items())[:4])
            self.status_text.setLabel(f"Server reachable -- {summary}" if summary else "Server reachable")

    def _load_conversations(self):
        self.conversations = self.api.get_conversations()
        self.contacts_all = [c for c in self.conversations if c["type"] == "dm"]

    @staticmethod
    def _to_state_key(conv_type, key):
        """The push/read-state APIs identify a conversation by a
        type-prefixed "state key" -- confirmed live from a real
        GET /api/push/conversations response: entries like
        "channel-828D37872695B8B47E537164FB1570CF" and
        "contact-da2524670a54a3ae...", NOT the bare key used everywhere
        else in this addon (conversation["key"], message conversation_key,
        etc.). Every comparison against push/read-state data has to go
        through this conversion or it silently never matches -- which was
        confirmed as the exact cause of notifications always reading as
        "off" regardless of the backend's real setting, and of the unread
        badge only reflecting a sliver of the server's actual count."""
        prefix = "channel" if conv_type == "channel" else "contact"
        return f"{prefix}-{key}"

    @staticmethod
    def _bare_key_from_state_key(state_key):
        for prefix in ("channel-", "contact-"):
            if state_key.startswith(prefix):
                return state_key[len(prefix):]
        return state_key

    def _load_notification_state(self):
        """Seeds push-enabled conversations and server-truth unread counts
        at startup. Runs on a background thread since both are network
        calls, called once from _do_init before the WS is even likely to
        be delivering messages yet."""
        try:
            push_list = self.api.get_push_conversations()
            self._push_conversations = set(push_list or [])
            xbmc.log(f"[RemoteTerm] push-enabled conversations: {sorted(self._push_conversations)}", xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] get_push_conversations failed: {e}", xbmc.LOGDEBUG)

        try:
            unread = self.api.get_unread_state()
            counts = (unread or {}).get("counts") or {}
            # Server keys are the prefixed state-key format (see
            # _to_state_key) -- de-prefix on the way in so every other
            # part of this addon can keep comparing against the plain
            # conversation key it already uses everywhere.
            self._mentions = set(self._bare_key_from_state_key(k)
                                  for k, v in ((unread or {}).get("mentions") or {}).items() if v)
            for state_key, count in counts.items():
                bare_key = self._bare_key_from_state_key(state_key)
                if count:
                    self._unread_counts[bare_key] = count
                else:
                    # Server says this is fully read -- clear any stale
                    # local count rather than leaving it untouched, or a
                    # conversation read elsewhere (browser, another
                    # device) would keep showing an outdated badge here.
                    self._unread_counts.pop(bare_key, None)
            xbmc.log(f"[RemoteTerm] seeded unread state for {len(counts)} conversation(s) from server: {counts!r}", xbmc.LOGINFO)
            if self.getProperty("tab") == TAB_CHATS:
                # Confirmed real bug, traced through a log: this method's
                # own docstring says it runs "once from _do_init", but
                # it's ALSO kicked off as a background thread from
                # ID_NAV_CHATS's own click handler on every single re-
                # entry into this tab -- meaning every time someone
                # clicks the Chats icon, this fires ~200-1000ms later and
                # unconditionally rebuilt the list a SECOND time, right
                # on top of the main thread's own click handler having
                # already correctly built it and focused it moments
                # earlier. That second, redundant, background-thread
                # reset() is exactly the trigger for Kodi's confirmed
                # focus-eating quirk (see the "contact"/"channel" WS
                # handler above, which hit the identical problem and was
                # fixed the same way) -- and because it lands on a
                # background thread shortly after the user's own next
                # keypress, it can silently steal focus back to the nav
                # rail moments after they thought they'd landed in the
                # list, with nothing left to catch it since the guard
                # only runs inside the rebuild that already fired. Same
                # fix as that WS handler: skip the rebuild entirely when
                # the visible list wouldn't actually change, which is
                # the common case here since this data rarely differs
                # from what a fresh tab-entry just built already.
                visible = self._visible_conversations()
                if self._convo_snapshot(visible) != self._last_convo_snapshot:
                    self._populate_convo_list(visible)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] get_unread_state failed: {e}", xbmc.LOGDEBUG)

    def _visible_conversations(self):
        items = [c for c in self.conversations if c["is_favorite"]] if self.favorites_only else self.conversations
        # Channels first, then direct-message contacts -- requested so the
        # two kinds aren't interleaved in one hard-to-scan list.
        return sorted(items, key=lambda c: 0 if c["type"] == "channel" else 1)

    @staticmethod
    def _convo_snapshot(items):
        """Cheap fingerprint of what the conversation list would actually
        show -- key, display name, favorite flag. Used to skip a
        disruptive rebuild when a WS contact/channel event fires but
        nothing about the visible list would actually change."""
        return tuple((c["key"], c["display"], c.get("is_favorite", False)) for c in items)

    def _populate_convo_list(self, items):
        self._last_convo_snapshot = self._convo_snapshot(items)
        prev_focus = self.getFocusId()
        self.convo_list.reset()
        if not items:
            msg = "No favorites yet -- star a conversation to pin it here" if self.favorites_only \
                else "Nothing here yet"
            self.convo_list.addItem(xbmcgui.ListItem(msg))
            self._guard_chat_focus(prev_focus)
            return
        last_group = None
        for idx, conv in enumerate(items):
            if conv["type"] != last_group:
                header = xbmcgui.ListItem(
                    "[B]CHANNELS[/B]" if conv["type"] == "channel" else "[B]DIRECT MESSAGES[/B]")
                header.setProperty("header", "1")
                self.convo_list.addItem(header)
                last_group = conv["type"]
            li = xbmcgui.ListItem(_safe_label_text(conv["display"]))
            li.setProperty("index", str(idx))
            li.setArt({"icon": _skin_asset("rt5-contacts.png" if conv["type"] == "dm" else "rt5-chats.png")})
            if conv.get("is_favorite"):
                li.setProperty("fav", "1")
            unread = self._unread_counts.get(conv["key"], 0)
            if unread:
                # Exact count, not capped at "9+" -- the badge itself was
                # enlarged in the skin to comfortably fit 2-3 digits.
                li.setProperty("unread_count", str(unread) if unread <= 999 else "999+")
            self.convo_list.addItem(li)
        # Land on the first REAL conversation, not item 0 -- which is
        # always the "CHANNELS"/"DIRECT MESSAGES" section header added
        # just above in this same loop. Kodi has no concept of a
        # non-selectable list row, so without this the list's default
        # selection (item 0) put focus squarely on that bold section
        # label -- visually neither part of the "All Conversations"
        # filter tab above the list nor a real, highlightable row inside
        # it, which read as landing in a dead gap between the two.
        self.convo_list.selectItem(1)
        self._guard_chat_focus(prev_focus)

    # -- Dashboard --------------------------------------------------------------

    def _load_trends(self):
        """Network Trends: uses fields already present in StatisticsResponse
        (packets_per_hour_72h, contacts_heard, repeaters_heard,
        known_channels_active) that were confirmed real via the OpenAPI
        schema but had never actually been wired into any view -- the
        Dashboard and Analytics tabs only ever consumed a subset of what
        this one endpoint already returns."""
        stats = self.api.get_statistics()
        if not stats:
            return

        buckets = stats.get("packets_per_hour_72h") or []
        buckets = sorted(buckets, key=lambda b: b.get("timestamp", 0))
        counts = [b.get("count", 0) for b in buckets]
        # Real data may not be exactly 72 samples (a freshly-started
        # backend won't have 72h of history yet) -- pad on the left with
        # zeros rather than stretching what's there across the full chart,
        # which would misrepresent a short history as a long flat one.
        counts = ([0] * max(0, 72 - len(counts))) + counts
        counts = counts[-72:]
        # Aggregate into 24 three-hour buckets to keep the chart to a
        # manageable, readable number of bars while still covering the
        # full confirmed 72h window the backend provides.
        bucket3h = [sum(counts[i:i+3]) for i in range(0, 72, 3)]
        peak = max(bucket3h) if bucket3h else 0

        CHART_TOP, CHART_HEIGHT, BASELINE = 300, 400, 700
        for i, count in enumerate(bucket3h):
            try:
                bar = self.getControl(ID_TRENDS_BAR_BASE + i)
                height = max(2, int(round((count / peak) * CHART_HEIGHT))) if peak else 2
                bar.setHeight(height)
                bar.setPosition(bar.getPosition()[0], BASELINE - height)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] trends bar {i} update failed: {e}", xbmc.LOGDEBUG)

        try:
            self.getControl(ID_TRENDS_PEAK_LABEL).setLabel(
                f"Peak: {peak:,} packets/3h window" if peak else "No data yet")
        except Exception:
            pass

        def set_activity(base_id, counts_obj):
            counts_obj = counts_obj or {}
            for offset, key in enumerate(("last_hour", "last_24_hours", "last_week")):
                try:
                    self.getControl(base_id + offset).setLabel(str(counts_obj.get(key, "--")))
                except Exception:
                    pass

        set_activity(ID_TRENDS_CONTACTS_1H, stats.get("contacts_heard"))
        set_activity(ID_TRENDS_REPEATERS_1H, stats.get("repeaters_heard"))
        set_activity(ID_TRENDS_CHANNELS_1H, stats.get("known_channels_active"))

    def _load_dashboard(self):
        stats = self.api.get_statistics()
        if not stats:
            for cid in (ID_STAT_CONTACTS, ID_STAT_CHANNELS, ID_STAT_REPEATERS, ID_STAT_PACKETS):
                self.getControl(cid).setLabel("--")
            self.getControl(ID_STAT_DECRYPTED).setLabel("--")
            self.getControl(ID_STAT_OUTGOING).setLabel("--")
            self.getControl(ID_BUSIEST_LIST).reset()
            self.getControl(ID_BUSIEST_LIST).addItem(xbmcgui.ListItem("Statistics unavailable"))
            self._set_bar_fill(ID_DECRYPT_PROGRESS, 0, _bar_tier_color("green"), max_width=260)
            self._set_bar_fill(ID_OUTGOING_PROGRESS, 0, _bar_tier_color("green"), max_width=260)
        else:
            self.getControl(ID_STAT_CONTACTS).setLabel(str(stats.get("contact_count", 0)))
            self.getControl(ID_STAT_CHANNELS).setLabel(str(stats.get("channel_count", 0)))
            self.getControl(ID_STAT_REPEATERS).setLabel(str(stats.get("repeater_count", 0)))
            total_packets = stats.get("total_packets", 0)
            decrypted = stats.get("decrypted_packets", 0)
            total_dms = stats.get("total_dms", 0)
            total_chan = stats.get("total_channel_messages", 0)
            total_outgoing = stats.get("total_outgoing", 0)
            self.getControl(ID_STAT_PACKETS).setLabel(str(total_packets))
            self.getControl(ID_STAT_DECRYPTED).setLabel(f"{decrypted} packets decrypted")
            self.getControl(ID_STAT_DMS).setLabel(str(total_dms))
            self.getControl(ID_STAT_CHANMSG).setLabel(str(total_chan))
            self.getControl(ID_STAT_OUTGOING).setLabel(f"{total_outgoing} sent by you")

            decrypt_pct = int(round((decrypted / total_packets) * 100)) if total_packets else 0
            total_msgs = total_dms + total_chan
            outgoing_pct = int(round((total_outgoing / total_msgs) * 100)) if total_msgs else 0
            # Confirmed real bug, twice over: both bars used a single
            # hardcoded color regardless of the actual percentage, and a
            # width that a screenshot showed visibly overflowing into the
            # next card. First fix attempt (stacked progress-bar-per-tier,
            # switched via a Window property) turned out not to render
            # correctly for these two specifically -- a second screenshot
            # showed the exact same near-full-width fill regardless of
            # the real 16%/6% values, even though the same technique
            # works correctly on Analytics. Rather than keep guessing at
            # why, switched to the same mechanism already confirmed
            # reliable elsewhere in this exact codebase: a plain image
            # resized with setWidth() and recolored with
            # setColorDiffuse() (the battery fill indicator uses this
            # exact approach), which removes any dependency on Kodi
            # re-evaluating a <progress> control's <visible> condition
            # correctly.
            self._set_bar_fill(ID_DECRYPT_PROGRESS, decrypt_pct, _bar_tier_color(_pct_tier(decrypt_pct)), max_width=260)
            try:
                self.getControl(ID_DECRYPT_PCT_LABEL).setLabel(f"{decrypt_pct}%")
            except Exception:
                pass
            self._set_bar_fill(ID_OUTGOING_PROGRESS, outgoing_pct, _bar_tier_color(_pct_tier(outgoing_pct)), max_width=260)
            try:
                self.getControl(ID_OUTGOING_PCT_LABEL).setLabel(f"{outgoing_pct}%")
            except Exception:
                pass

            busiest = self.getControl(ID_BUSIEST_LIST)
            busiest.reset()
            channels = stats.get("busiest_channels_24h") or []
            if not channels:
                busiest.addItem(xbmcgui.ListItem("No channel activity in the last 24h"))
            else:
                for c in channels:
                    busiest.addItem(xbmcgui.ListItem(f"#{_safe_label_text(c.get('channel_name', 'channel'))}   --   {c.get('message_count', 0)} messages"))

        self._load_recent_activity()

    def _load_analytics(self):
        """Analytics tab: everything the API can give beyond what fits on
        the Dashboard. radio_stats fields (battery_mv, uptime_secs,
        noise_floor, last_rssi, last_snr, tx/rx_air_secs, packets_recv/
        sent, flood/direct_tx/rx, errors, queue_len), database_size_mb, and
        fanout_statuses are all CONFIRMED real fields captured from a live
        health check response, not guessed. A "messages/hour" gauge was
        tried here previously but removed: there's no historical/time-
        series endpoint on the API, so it could only ever be a client-side
        approximation that resets to zero every time the addon restarts --
        not something worth a permanent spot next to real backend data."""
        show_gauges = self.api.show_gauges
        self.setProperty("show_gauges", "true" if show_gauges else "false")

        health = self.api.get_health() or {}
        stats = self.api.get_statistics() or {}
        radio_stats = health.get("radio_stats") or {}

        if show_gauges:
            total_packets = stats.get("total_packets", 0)
            decrypted = stats.get("decrypted_packets", 0)
            packets_recv = radio_stats.get("packets_recv", 0)
            flood_tx = radio_stats.get("flood_tx", 0)
            direct_tx = radio_stats.get("direct_tx", 0)
            flood_rx = radio_stats.get("flood_rx", 0)
            direct_rx = radio_stats.get("direct_rx", 0)
            now = time.time()

            # Confirmed by a side-by-side screenshot sequence: computing
            # Decrypt Rate from just the last ~15s poll interval was wildly
            # erratic (33% -> 100% -> 0% -> 100%), because only a handful
            # of packets arrive in that window -- a single packet's decrypt
            # status swings the percentage by 50-100 points on that small a
            # sample. Keeping a short rolling history and comparing against
            # a sample from ~5 minutes ago (or the oldest available) gives
            # a big enough sample to be stable while still being "recent"
            # rather than a near-frozen lifetime ratio. Also used for the
            # Traffic Composition bars below, for the same reason.
            self._analytics_history.append(
                (now, total_packets, decrypted, packets_recv, flood_tx, direct_tx, flood_rx, direct_rx,
                 radio_stats.get("rx_air_secs", 0), radio_stats.get("tx_air_secs", 0)))
            while len(self._analytics_history) > 1 and now - self._analytics_history[0][0] > 300:
                self._analytics_history.popleft()
            oldest = self._analytics_history[0]
            d_packets = total_packets - oldest[1]
            d_decrypted = decrypted - oldest[2]
            d_time = max(1.0, now - oldest[0])

            # Packet Activity/Intensity use a SEPARATE, much shorter ~60s
            # window: confirmed by a real session's screenshots that using
            # the same 300s window as Decrypt Rate meant the reading spent
            # its first five minutes on every fresh session slowly
            # "warming up" (0 -> 3.6 -> 5.2 -> 5.9 -> 8.0 -> 8.6/min over
            # 13 minutes) rather than genuinely fluctuating -- an artifact
            # of the window still filling up, not real traffic changes.
            # Packet count is also a smoother/higher-frequency signal than
            # the binary decrypt-success ratio, so it doesn't need as much
            # averaging to stop being noisy.
            oldest_60s = self._analytics_history[-1]
            for sample in self._analytics_history:
                if now - sample[0] <= 60:
                    oldest_60s = sample
                    break
            d_time_60 = max(1.0, now - oldest_60s[0])
            d_packets_recv = packets_recv - oldest_60s[3]

            if d_packets > 5:
                decrypt_pct = int(round((d_decrypted / d_packets) * 100))
                self._last_decrypt_pct = decrypt_pct
            elif total_packets:
                decrypt_pct = self._last_decrypt_pct or int(round((decrypted / total_packets) * 100))
            else:
                decrypt_pct = 0
            self._set_gauge("gauge_decrypt_frame", ID_ANALYTICS_GAUGE_DECRYPT_LABEL,
                             decrypt_pct, _pct_tier(decrypt_pct), f"{decrypt_pct}%")

            # Second gauge: was Battery, replaced per explicit request --
            # battery_mv is real and correct, but voltage on an
            # externally-powered/solar node barely moves over a session
            # (confirmed unchanged at 4.07V across an entire multi-hour
            # session's worth of screenshots), so the gauge always looked
            # frozen regardless of anything actually happening. Battery
            # is still shown -- just as a footer stat instead of a full
            # gauge -- while this slot uses Last RSSI, which is real,
            # confirmed, and swings by 70+ dB poll to poll on live mesh
            # traffic (also confirmed directly from a screenshot
            # sequence: -20, -63, -94, -90, -63, -96 dBm).
            last_rssi = radio_stats.get("last_rssi")
            if last_rssi is not None:
                # Range corrected again, to -120..-30dBm: confirmed via
                # multiple independent LoRa field-study and IoT gateway
                # sources that this is the conventional practical RSSI
                # span (-30dBm described as "solid"/"screaming loud",
                # -120dBm as "weak"/"a whisper"), not the SX1262 chip's
                # theoretical -148dBm demodulation floor used in a prior
                # revision -- that's the absolute physical limit, not
                # what "RSSI range" conventionally refers to for display.
                # Also switched to a dedicated quality tier (_rssi_tier)
                # instead of the generic intensity-style _pct_tier: RSSI
                # is a signal-QUALITY reading like SNR (less negative is
                # better), so it should read red-to-green in that
                # direction, not treated as a volume/intensity metric.
                rssi_pct = max(0, min(100, int(round((last_rssi + 120) / 90 * 100))))
                self._set_gauge("gauge_rssi_frame", ID_ANALYTICS_GAUGE_BATTERY_LABEL,
                                 rssi_pct, _rssi_tier(last_rssi), f"{last_rssi}dBm")
            else:
                self._set_gauge("gauge_rssi_frame", ID_ANALYTICS_GAUGE_BATTERY_LABEL, 0, "red", "--")

            # Packet Activity replaces Outgoing Share: that gauge only ever
            # reflected messages sent by this radio specifically, so it
            # sat at 0% through an entire passive viewing session with no
            # outgoing chat activity -- correct, but not something worth
            # watching. packets_recv climbs continuously from ambient mesh
            # traffic regardless of what the person using the addon is
            # doing.
            #
            # Rescaled again, from /10 to a log scale (see _log_pct): a
            # real session's screenshots showed rates swinging from 0 to
            # 61.8/min within minutes of each other -- against a /10
            # reference, anything past 6.6/min was already pinned at the
            # top of the red tier. Confirmed a follow-on bug from that
            # same fix, though: feeding this log-scaled arc-position
            # percentage into the generic tier function meant a modest
            # 8.7/min (confirmed from a screenshot) landed at 55%, deep
            # in "red" -- log-scaling deliberately over-expands low
            # values for a visibly-moving needle, but that expansion
            # should never have doubled as the color decision too. Color
            # now comes from _rate_tier using the real packets/min value
            # directly, completely decoupled from how far the needle
            # sweeps.
            packets_per_min = (d_packets_recv / d_time_60) * 60
            activity_pct = _log_pct(packets_per_min, 60)
            self._set_gauge("gauge_outgoing_frame", ID_ANALYTICS_GAUGE_OUTGOING_LABEL,
                             activity_pct, _rate_tier(packets_per_min, 5, 15, 35), f"{packets_per_min:.1f}/min")

            # Signal Quality: last_snr is already a live, instantaneous
            # reading (confirmed fluctuating meaningfully poll to poll in
            # the log: 12.5, 0.0, 11.5, 12.25, 11.75, -0.5dB) -- no
            # smoothing needed, it's real-time by nature.
            #
            # SNR reads as a quality indicator, not an intensity one --
            # confirmed via real LoRa/MeshCore engineering sources (see
            # _snr_tier) that this should use actual dB cutoffs at 0dB
            # and 7dB rather than an arbitrary percentage split, so the
            # color is grounded in documented demodulation/link-quality
            # behavior instead of a guessed linear scale. The arc's fill
            # position (snr_pct) is still just for visual sweep -- -20dB
            # (SF12's demodulation floor) to +20dB spans the range this
            # radio can plausibly report.
            last_snr = radio_stats.get("last_snr")
            if last_snr is not None:
                snr_pct = max(0, min(100, int(round((last_snr + 20) / 40 * 100))))
                self._set_gauge("gauge_snr_frame", ID_ANALYTICS_GAUGE_SNR_LABEL,
                                 snr_pct, _snr_tier(last_snr), f"{last_snr}dB")
            else:
                self._set_gauge("gauge_snr_frame", ID_ANALYTICS_GAUGE_SNR_LABEL, 0, "red", "--")

            # TX Channel Utilization (was "Packet Reception Intensity"):
            # confirmed genuinely redundant with the Packet Activity gauge
            # above and RX Activity below -- all three derived from the
            # exact same received-packet-count delta (RX Activity's
            # flood_rx+direct_rx is mathematically identical to total
            # packets_recv by definition), just displayed three times in
            # slightly different framings. Replaced with tx_air_secs, a
            # real, confirmed backend field that had only ever been shown
            # as a static stat card -- how much of the last window's wall-
            # clock time was spent actively TRANSMITTING, not counting
            # packets at all. Pairs naturally with RX Channel Utilization
            # right next to it for a genuine TX/RX airtime comparison,
            # rather than two widgets measuring the same reception count.
            #
            # Confirmed real gap, reported directly: right after opening
            # the addon/Analytics tab, this local rolling window has no
            # history yet, so it necessarily reads 0% for a while no
            # matter how much real airtime the radio has actually
            # accumulated -- the "stagnant lifetime ratio" problem from
            # earlier revisions and "shows 0 despite lots of real
            # activity" are opposite failure modes of the same root
            # cause: with only one data source, either it's a slow-moving
            # multi-day average, or it's blind until enough local history
            # builds up. Fixed by using BOTH: the real lifetime ratio
            # (tx_air_secs / uptime_secs, confirmed real backend fields)
            # as the value the moment the addon opens, smoothly handing
            # off to the recent 5-minute-window rate once enough local
            # history has actually accumulated (30s+) to make that more
            # responsive figure meaningful. Also switched from the 60s
            # window to 5 minutes for the "recent" side of this handoff --
            # a single short transmission is such a small fraction of 60
            # seconds that it could round away to 0% even though it
            # genuinely happened; 5 minutes is far less likely to dilute
            # a real, recent event into invisibility.
            tx_air_secs = radio_stats.get("tx_air_secs")
            uptime_secs = radio_stats.get("uptime_secs")
            if tx_air_secs is not None:
                if d_time >= 30:
                    d_tx_air = tx_air_secs - oldest[9]
                    tx_util_pct = max(0, min(100, int(round((d_tx_air / d_time) * 100))))
                elif uptime_secs:
                    tx_util_pct = max(0, min(100, int(round((tx_air_secs / uptime_secs) * 100))))
                else:
                    tx_util_pct = 0
                tx_util_tier = _pct_tier(tx_util_pct)
                self._set_bar_fill(ID_ANALYTICS_INTENSITY_BAR, tx_util_pct, _bar_tier_color(tx_util_tier), max_width=776)
                try:
                    self.getControl(ID_ANALYTICS_INTENSITY_LABEL).setLabel(f"{tx_util_pct}% of airtime")
                except Exception:
                    pass

            # RX Channel Utilization: same cold-start-fallback and 5-
            # minute-window reasoning as TX Channel Utilization above,
            # using rx_air_secs (real, confirmed in the health response)
            # instead of TX's field. This is airtime, not event count --
            # a channel moving a few large, slow transmissions and one
            # moving many small, fast ones would show the same packet
            # rate on the Packet Activity gauge but a different
            # utilization here, so the two bars tell separate stories
            # instead of just repeating each other.
            rx_air_secs = radio_stats.get("rx_air_secs")
            if rx_air_secs is not None:
                if d_time >= 30:
                    d_rx_air = rx_air_secs - oldest[8]
                    utilization_pct = max(0, min(100, int(round((d_rx_air / d_time) * 100))))
                elif uptime_secs:
                    utilization_pct = max(0, min(100, int(round((rx_air_secs / uptime_secs) * 100))))
                else:
                    utilization_pct = 0
                utilization_tier = _pct_tier(utilization_pct)
                self._set_bar_fill(ID_ANALYTICS_UTIL_BAR, utilization_pct, _bar_tier_color(utilization_tier), max_width=776)
                try:
                    self.getControl(ID_ANALYTICS_UTIL_LABEL).setLabel(f"{utilization_pct}% of airtime")
                except Exception:
                    pass

            # Region-Scoped Traffic (was "TX Activity"): confirmed
            # genuinely redundant with TX Channel Utilization right above
            # it -- both measured TX volume (airtime% vs packet-rate),
            # and since this node barely transmits, both perpetually sat
            # near 0% and looked identical regardless of which one was
            # "more correct". Replaced with region_scope_24h.scoped_pct,
            # a real StatisticsResponse field (already fetched into
            # `stats` above, no new API call) that had never been shown
            # anywhere: what share of recent messages carry MeshCore's
            # region-scoping metadata, a genuinely different concept
            # (regional message filtering) from anything else on this
            # page. Real literal percentage, no log-scale needed.
            region_scope = stats.get("region_scope_24h") or {}
            scoped_pct = int(round(region_scope.get("scoped_pct", 0) or 0))
            scoped_tier = _pct_tier(scoped_pct)
            self._set_bar_fill(ID_ANALYTICS_BAR_TX, scoped_pct, _bar_tier_color(scoped_tier), max_width=776)
            try:
                self.getControl(ID_ANALYTICS_BAR_TX_LABEL).setLabel(f"{scoped_pct}%")
            except Exception:
                pass
            try:
                self.getControl(ID_ANALYTICS_BAR_TX_COUNTS).setLabel(
                    f"{region_scope.get('scoped_messages', 0)} of {region_scope.get('total_messages', 0)} "
                    f"messages scoped (last 24h)")
            except Exception:
                pass

            # Active Companion Nodes (was "Decrypted Rate"): confirmed
            # genuinely redundant with the Decrypt Rate gauge -- a ratio
            # (%) and a rate (packets/min) are technically different
            # formulas, but both are still just "how much decryption is
            # happening", the same underlying concept shown twice.
            # Replaced with contacts_heard.last_hour (also already in
            # `stats`, also never shown anywhere) -- how many distinct
            # companion nodes have actually been heard recently, a node-
            # diversity reading rather than another decrypt/packet-count
            # metric.
            #
            # Confirmed real bug in the first version of this: dividing
            # by contact_count (this node's LIFETIME total known
            # contacts, 300+ on a mature install) made the percentage
            # inherently tiny and barely distinguishable regardless of
            # whether 2, 4, or 10 companions were actually heard in the
            # last hour -- the wrong denominator for an hourly figure.
            # Log-scaled against a fixed "busy hour" reference instead
            # (20 distinct companions heard in an hour being a lot for a
            # single local mesh), with the real-count-based tiering
            # already used for the packet-rate bars, so small real
            # differences (2 vs 4 vs 10) actually move the bar and change
            # its color instead of all rounding to the same low percent.
            contacts_heard = stats.get("contacts_heard") or {}
            heard_1h = contacts_heard.get("last_hour", 0) or 0
            contact_count = stats.get("contact_count", 0) or 0
            active_pct = _log_pct(heard_1h, 20)
            active_tier = _rate_tier(heard_1h, 2, 5, 10)
            self._set_bar_fill(ID_ANALYTICS_BAR_RX, active_pct, _bar_tier_color(active_tier), max_width=776)
            try:
                self.getControl(ID_ANALYTICS_BAR_RX_LABEL).setLabel(f"{heard_1h}/{contact_count}")
            except Exception:
                pass
            try:
                self.getControl(ID_ANALYTICS_BAR_RX_COUNTS).setLabel(
                    f"{heard_1h} of {contact_count} known contacts heard in the last hour")
            except Exception:
                pass

            self._render_analytics_live_feed()

        def set_stat(control_id, value):
            try:
                self.getControl(control_id).setLabel(value)
            except Exception:
                pass

        set_stat(ID_ANALYTICS_STAT_UPTIME, _format_duration(radio_stats.get("uptime_secs")))
        set_stat(ID_ANALYTICS_STAT_NOISE_FLOOR,
                 f"{radio_stats['noise_floor']} dBm" if radio_stats.get("noise_floor") is not None else "--")
        set_stat(ID_ANALYTICS_STAT_LAST_RSSI,
                 f"{radio_stats['last_rssi']} dBm" if radio_stats.get("last_rssi") is not None else "--")
        set_stat(ID_ANALYTICS_STAT_LAST_SNR,
                 f"{radio_stats['last_snr']} dB" if radio_stats.get("last_snr") is not None else "--")
        set_stat(ID_ANALYTICS_STAT_TX_AIR, _format_duration(radio_stats.get("tx_air_secs")))
        set_stat(ID_ANALYTICS_STAT_RX_AIR, _format_duration(radio_stats.get("rx_air_secs")))
        set_stat(ID_ANALYTICS_STAT_PACKETS_RECV, str(radio_stats.get("packets_recv", "--")))
        set_stat(ID_ANALYTICS_STAT_PACKETS_SENT, str(radio_stats.get("packets_sent", "--")))

        db_size = health.get("database_size_mb")
        set_stat(ID_ANALYTICS_STAT_DB_SIZE, f"Database: {db_size:.1f} MB" if db_size is not None else "Database: --")
        set_stat(ID_ANALYTICS_STAT_ERRORS, f"Errors: {radio_stats.get('errors', '--')}")
        set_stat(ID_ANALYTICS_STAT_QUEUE, f"Queue: {radio_stats.get('queue_len', '--')}")
        battery_mv = radio_stats.get("battery_mv")
        if battery_mv is not None:
            # Same real Li-ion range used elsewhere (~3.3V empty, ~4.2V
            # full) -- this is a genuine percentage of real voltage, not a
            # separate fabricated figure, just expressed two ways (icon
            # fill + text) as requested.
            battery_pct = max(0, min(100, int(round((battery_mv - 3300) / (4200 - 3300) * 100))))
            battery_color = "FF3DDC84" if battery_pct > 50 else ("FFF5A623" if battery_pct > 20 else "FFE74C3C")
            set_stat(ID_ANALYTICS_STAT_BATTERY, f"{battery_pct}%  ({battery_mv / 1000:.2f}V)")
            try:
                fill = self.getControl(ID_ANALYTICS_BATTERY_FILL)
                fill.setColorDiffuse(battery_color)
                fill.setWidth(max(1, int(round(31 * battery_pct / 100))))
            except Exception:
                pass
        else:
            set_stat(ID_ANALYTICS_STAT_BATTERY, "--")

        fanouts = health.get("fanout_statuses") or {}
        if fanouts:
            parts = []
            for f in fanouts.values():
                name = _safe_label_text(f.get("name") or "community bridge")
                status = f.get("status") or "unknown"
                color = "FF3DDC84" if status == "connected" else "FFE74C3C"
                parts.append(f"[COLOR {color}]\u25cf[/COLOR] {name} ({status})")
            set_stat(ID_ANALYTICS_FANOUT_LIST, "Community fanout:   " + "     ".join(parts))
        else:
            set_stat(ID_ANALYTICS_FANOUT_LIST, "Community fanout: none configured")

    def _set_gauge(self, prop_name, label_id, pct, color, value_text):
        bucket = max(0, min(100, int(round(pct / 5.0)) * 5))
        self.setProperty(prop_name, f"{color}-{bucket}")
        try:
            self.getControl(label_id).setLabel(value_text)
        except Exception:
            pass

    def _set_bar_fill(self, image_id, pct, color_hex, max_width):
        """Simple bar driven entirely by resizing/recoloring one plain
        image control -- setWidth() + setColorDiffuse(), the same
        mechanism already confirmed reliable for the battery fill
        indicator. Originally added for the two Dashboard bars after the
        stacked-progress-bar-plus-glow-strip technique (_set_tiered_bar,
        removed) failed for them; now used for every percentage bar in
        the app, including the 4 Analytics ones that technique was
        originally written for, after THAT technique also produced a
        card-overflowing bar there -- twice, even after fixing both the
        XML width and the Python-side max_width default that was
        silently overriding it. Given the same underlying mechanism
        failed in the same way on both pages, it's retired everywhere
        rather than patched a third time: one control per bar, one
        function, nothing left to drift out of sync with anything else."""
        width = max(1, int(round(max_width * pct / 100)))
        try:
            ctrl = self.getControl(image_id)
            ctrl.setColorDiffuse(color_hex)
            ctrl.setWidth(width)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] _set_bar_fill({image_id}) failed: {e}", xbmc.LOGDEBUG)

    def _load_recent_activity(self):
        activity = self.getControl(ID_ACTIVITY_LIST)
        activity.reset()
        recent = self.api.get_recent_activity(limit=14)
        if not recent:
            activity.addItem(xbmcgui.ListItem("No recent activity"))
            return
        for m in recent:
            who = _safe_label_text(m.get("channel_name") or m.get("sender_name") or "You")
            snippet = _safe_message_text((m.get("text") or "")[:70])
            when = _ago(m.get("received_at"))
            li = xbmcgui.ListItem(f"[B]{who}[/B]  {snippet}   [COLOR FF888888]{when}[/COLOR]")
            activity.addItem(li)

    # -- Repeater Console (category 3) -------------------------------------------

    def _load_repeater_console(self):
        repeaters = [c for c in self.contacts_all if c.get("contact_type") == 2]

        # Confirmed real gap: this list never had any sort control at
        # all, always showing repeaters in raw server order. Mirrors
        # _populate_contacts's exact same sort keys/logic for
        # consistency between the two tabs' picker lists.
        center = self.api.map_center
        if self.repeater_sort == "recent":
            repeaters = sorted(repeaters, key=lambda c: c.get("last_seen") or 0, reverse=True)
        elif self.repeater_sort == "distance" and center is not None:
            lat0, lon0 = center
            repeaters = sorted(repeaters, key=lambda c: (self.api.haversine_km(lat0, lon0, c["lat"], c["lon"])
                                                           if c.get("lat") and c.get("lon") else float("inf")))
        elif self.repeater_sort == "hops_near":
            repeaters = sorted(repeaters, key=lambda c: self._hop_sort_key(c.get("last_path_len")))
        elif self.repeater_sort == "hops_far":
            repeaters = sorted(repeaters, key=lambda c: self._hop_sort_key(c.get("last_path_len")), reverse=True)

        self.repeater_picker.reset()
        if not repeaters:
            self.repeater_picker.addItem(xbmcgui.ListItem("No repeaters heard yet"))
            return
        selected_index = None
        for idx, r in enumerate(repeaters):
            if self.repeater_sort == "distance" and center is not None and r.get("lat") and r.get("lon"):
                lat0, lon0 = center
                km = self.api.haversine_km(lat0, lon0, r["lat"], r["lon"])
                extra = f"{self.api.format_distance(km)} away"
            elif self.repeater_sort in ("hops_near", "hops_far"):
                extra = _hops_label(r.get("last_path_len"))
            else:
                extra = f"last heard {_ago(r.get('last_seen'))}"
            li = xbmcgui.ListItem(f"{_safe_label_text(r['display'])}   --   {extra}")
            li.setProperty("key", r["key"])
            li.setProperty("name", r["display"])
            self.repeater_picker.addItem(li)
            if self.selected_repeater and r["key"] == self.selected_repeater["key"]:
                selected_index = idx
        if self.selected_repeater:
            # Confirmed real bug: arriving here from "Open Node Console"
            # on the Nodes tab already fetched this repeater's data
            # correctly in the background, but the picker list itself
            # never visually highlighted which repeater that was, and
            # the info panel kept showing its stale previous text (or
            # the generic "Select a repeater on the left to begin")
            # until the fetch finished -- so even though the right data
            # WAS loading, there was no visible sign of it, and it
            # looked exactly like landing on an empty, unselected page
            # that needed the repeater found and picked again from
            # scratch. Both fixed: the matching item is now focused/
            # highlighted immediately, and the info panel shows a
            # "Querying..." message synchronously before the
            # (multi-second) background fetch even starts.
            if selected_index is not None:
                try:
                    self.repeater_picker.selectItem(selected_index)
                except Exception:
                    pass
            try:
                self.repeater_info.setText(
                    f"Querying {_safe_label_text(self.selected_repeater['name'])} over the mesh -- "
                    f"this can take several seconds...")
            except Exception:
                pass
            # Must be threaded, not called directly: each of the three
            # repeater-console calls is a live mesh round-trip with a
            # 30s timeout, and this method runs inside onClick on the
            # main GUI thread -- calling it synchronously here is exactly
            # what froze the whole app (confirmed via a live traceback:
            # the main thread was caught mid-blocking-read when Kodi tried
            # to force-quit the script).
            threading.Thread(target=self._load_repeater_detail,
                              args=(self.selected_repeater["key"], self.selected_repeater["name"]),
                              daemon=True).start()

    def _select_repeater(self):
        item = self.repeater_picker.getSelectedItem()
        if not item or not item.getProperty("key"):
            return
        key, name = item.getProperty("key"), item.getProperty("name")
        self.selected_repeater = {"key": key, "name": name}
        self.repeater_info.setText(f"Querying {name} over the mesh -- this can take several seconds...")
        self.repeater_neighbors.reset()
        self.repeater_acl.reset()
        threading.Thread(target=self._load_repeater_detail, args=(key, name), daemon=True).start()

    def _load_repeater_detail(self, key, name):
        try:
            self._load_repeater_detail_unsafe(key, name)
        except Exception:
            xbmc.log(f"[RemoteTerm] _load_repeater_detail crashed:\n{traceback.format_exc()}", xbmc.LOGERROR)

    def _load_repeater_detail_unsafe(self, key, name):
        name = _safe_label_text(name)
        # Confirmed real bug (found by checking the OpenAPI spec against
        # what this method actually did): there is a dedicated
        # /repeater/login endpoint, and node-info/neighbors/ACL are
        # exactly the kind of admin-style repeater commands that
        # typically require an authenticated session on real MeshCore
        # firmware -- this method queried them directly, with no login
        # step at all, ever. A guest login (confirmed via the schema to
        # just be an empty password, needing no user interaction) is
        # attempted automatically first here -- it costs nothing extra
        # for a repeater that doesn't require authentication at all,
        # and is likely exactly why a known-good, always-in-range
        # repeater was still returning slow/empty data purely from
        # being queried unauthenticated.
        login_result = self.api.login_repeater(key, "")
        xbmc.log(f"[RemoteTerm] repeater auto guest-login for {key[:12]}: {login_result!r}", xbmc.LOGINFO)
        node_info = self.api.get_repeater_node_info(key)
        xbmc.log(f"[RemoteTerm] repeater node-info for {key[:12]}: {node_info!r}", xbmc.LOGINFO)
        lines = [f"[B]{name}[/B]"]
        if login_result and not login_result.get("authenticated"):
            lines.append("[COLOR FFFFD500](Guest login was not confirmed by the repeater -- "
                          "some data below may be limited. Try Log In as Admin.)[/COLOR]")
        if node_info:
            lat, lon = node_info.get("lat"), node_info.get("lon")
            if lat is not None and lon is not None:
                # Confirmed live: this endpoint returns lat/lon as strings,
                # not numbers -- formatting them with :.5f crashed this
                # entire background thread before neighbors/ACL ever loaded.
                try:
                    lines.append(f"Location: {float(lat):.5f}, {float(lon):.5f}")
                except (TypeError, ValueError):
                    lines.append(f"Location: {lat}, {lon}")
            if node_info.get("clock_utc"):
                lines.append(f"Node clock (UTC): {node_info.get('clock_utc')}")
            if len(lines) == 1:
                # Response came back but none of the fields we expected were
                # present -- show whatever we did get rather than nothing.
                lines.append("[COLOR FF888888]" + ", ".join(f"{k}={v}" for k, v in list(node_info.items())[:8]) + "[/COLOR]")
        else:
            lines.append("[COLOR FF888888]No response -- this RemoteTerm server may not support "
                          "live node-info queries, or the repeater didn't answer in time[/COLOR]")
        self.repeater_info.setText("\n".join(lines))

        # Telemetry (battery, uptime, airtime, packet counts, etc.) --
        # shown right under Node Info to match the browser frontend's
        # layout, fetched and appended as soon as it arrives rather than
        # waiting for neighbors/ACL too.
        status = self.api.query_repeater_status(key)
        xbmc.log(f"[RemoteTerm] repeater telemetry for {key[:12]}: {status!r}", xbmc.LOGINFO)
        telemetry_text = _format_repeater_telemetry(status)
        if telemetry_text:
            lines.append("")
            lines.append("[B]Telemetry[/B]")
            lines.append(telemetry_text)
        else:
            lines.append("")
            lines.append("[COLOR FF888888]Telemetry: no response[/COLOR]")
        self.repeater_info.setText("\n".join(lines))

        neighbors = self.api.get_repeater_neighbors(key)
        xbmc.log(f"[RemoteTerm] repeater neighbors for {key[:12]}: {neighbors!r}", xbmc.LOGINFO)
        self.repeater_neighbors.reset()
        neighbor_list = self._extract_list(neighbors, "neighbors")

        # Distance per neighbor: confirmed via the OpenAPI schema that
        # NeighborInfo has no distance field at all (just pubkey_prefix,
        # name, snr, last_heard_seconds) -- the real web frontend's
        # Distance column must be computed client-side from known contact
        # coordinates, not returned directly. This repeater's own lat/lon
        # came back from node-info just above; matching each neighbor's
        # pubkey_prefix against the local contacts list (which has lat/lon
        # for anyone whose position is known) gives the same computation.
        repeater_lat = repeater_lon = None
        if node_info:
            try:
                repeater_lat = float(node_info.get("lat"))
                repeater_lon = float(node_info.get("lon"))
            except (TypeError, ValueError):
                pass

        if not neighbor_list:
            self.repeater_neighbors.addItem(xbmcgui.ListItem("No neighbor data returned"))
        else:
            for n in neighbor_list:
                snr = n.get("snr")
                heard = n.get("last_heard_seconds")
                bits = [_safe_label_text(n.get("name") or n.get("pubkey_prefix", "?"))]
                if snr is not None:
                    bits.append(f"SNR {snr}dB")
                if heard is not None:
                    bits.append(f"heard {heard}s ago")
                if repeater_lat is not None:
                    prefix = n.get("pubkey_prefix", "")
                    match = next((c for c in self.contacts_all
                                  if prefix and c.get("public_key", "").startswith(prefix)
                                  and c.get("lat") is not None and c.get("lon") is not None), None)
                    if match:
                        dist_km = self.api.haversine_km(repeater_lat, repeater_lon, match["lat"], match["lon"])
                        bits.append(self.api.format_distance(dist_km))
                li = xbmcgui.ListItem("  |  ".join(bits))
                # Full raw fields stashed here (not just the few shown
                # inline) so selecting a row can reveal anything not
                # already surfaced -- confirmed via the OpenAPI schema
                # that NeighborInfo itself has no distance field, so this
                # covers anything else that might turn up unexpectedly.
                li.setProperty("raw_detail", _format_key_value_dict(n))
                self.repeater_neighbors.addItem(li)

        acl = self.api.get_repeater_acl(key)
        xbmc.log(f"[RemoteTerm] repeater acl for {key[:12]}: {acl!r}", xbmc.LOGINFO)
        self.repeater_acl.reset()
        acl_list = self._extract_list(acl, "acl")
        if not acl_list:
            self.repeater_acl.addItem(xbmcgui.ListItem("No ACL data returned"))
        else:
            for entry in acl_list:
                name_ = _safe_label_text(entry.get("name") or entry.get("pubkey_prefix", "?"))
                perm = entry.get("permission_name", "?")
                li = xbmcgui.ListItem(f"{name_}   --   {perm}")
                li.setProperty("raw_detail", _format_key_value_dict(entry))
                self.repeater_acl.addItem(li)

        # LPP Sensors -- appended last since this is the least commonly
        # populated section (only repeaters with attached sensor hardware
        # report anything here), and comes after everything the user is
        # more likely to be waiting on.
        lpp = self.api.get_repeater_lpp_telemetry(key)
        xbmc.log(f"[RemoteTerm] repeater lpp-telemetry for {key[:12]}: {lpp!r}", xbmc.LOGINFO)
        sensors = (lpp or {}).get("sensors") if isinstance(lpp, dict) else None
        lpp_text = _format_lpp_sensors(sensors)
        if lpp_text:
            lines.append("")
            lines.append("[B]LPP Sensors[/B]")
            lines.append(lpp_text)
            self.repeater_info.setText("\n".join(lines))

    @staticmethod
    def _extract_list(response, preferred_key):
        """The confirmed shape for these endpoints' response envelope isn't
        certain, so this accepts either {preferred_key: [...]}, a bare
        list, or the first list-valued field found in the dict."""
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            if isinstance(response.get(preferred_key), list):
                return response[preferred_key]
            for v in response.values():
                if isinstance(v, list):
                    return v
        return None

    def _send_repeater_command(self):
        if not self.selected_repeater:
            xbmcgui.Dialog().notification("Notice", "Select a repeater first.", xbmcgui.NOTIFICATION_WARNING)
            return
        keyboard = xbmc.Keyboard('', f"Command for {self.selected_repeater['name']}")
        keyboard.doModal()
        if not (keyboard.isConfirmed() and keyboard.getText()):
            return
        command_text = keyboard.getText()
        repeater = self.selected_repeater

        # Confirmed real bug: the command was echoed to the terminal
        # TWICE -- once immediately here, then AGAIN inside worker() once
        # the response arrived -- producing garbled, duplicated-looking
        # output that could easily read as nonsensical or "made up" even
        # though the actual response text itself was genuine. Echoed
        # exactly once now, matching how a real terminal (and the
        # browser frontend's own console, confirmed via screenshot: "> gps"
        # then the real reply, nothing else) behaves. The "sending..."
        # status is now a transient toast instead of a permanent terminal
        # line, so the scrollback only ever holds real command/response
        # pairs, not process noise.
        self._append_terminal_line(f"> {command_text}")
        xbmcgui.Dialog().notification("RemoteTerm", "Sending over the mesh...", xbmcgui.NOTIFICATION_INFO, 2000)

        # This is a live mesh round-trip (up to 30s) -- must not run on the
        # main GUI thread, which is exactly what froze the whole app when a
        # similar call was made directly (confirmed via a live traceback).
        def worker():
            result = self.api.send_repeater_command(repeater["key"], command_text)
            # Full raw request/response logged here since a serious
            # concern was raised that the displayed response might not
            # match what the real backend returns -- this is the
            # definitive way to check: the exact command sent and the
            # exact, unmodified JSON body that came back, with nothing
            # in between. Every other endpoint in this addon already
            # logs its raw response for the same reason; this one
            # (confirmed by checking) never did until now.
            xbmc.log(f"[RemoteTerm] repeater command sent to {repeater['key'][:12]}: "
                      f"{command_text!r} -> raw response: {result!r}", xbmc.LOGINFO)
            if result and result.get("response") is not None:
                self._append_terminal_line(result["response"])
            elif result:
                self._append_terminal_line("(command sent -- no response text returned)")
            else:
                self._append_terminal_line("(command failed -- no response from repeater; see kodi.log)")

        threading.Thread(target=worker, daemon=True).start()

    def _append_terminal_line(self, text):
        """Appends one line to the CLI terminal's scrollback. Confirmed
        real bug: a 40-line cap made sense for the panel's old ~3-visible-
        line height, but meant new content routinely landed far below
        what was actually visible, with no reliable way for a Kodi
        textbox to auto-scroll to it -- reported as "can't see the next
        command you enter". A follow-up report showed even the resized
        panel with a 7-line cap still overflowed once wrapped/longer
        response lines were involved. Capped tighter here at 6 lines --
        exactly 3 command/response pairs, matching the "after the 3rd
        command" behavior asked for -- with real margin against
        wrapping, so the newest command and its response should reliably
        stay fully visible without the user needing to scroll."""
        self.repeater_terminal_lines.append(_safe_message_text(str(text)))
        self.repeater_terminal_lines = self.repeater_terminal_lines[-6:]
        try:
            self.repeater_terminal.setText("\n".join(self.repeater_terminal_lines))
        except Exception:
            pass

    def _login_repeater(self):
        if not self.selected_repeater:
            xbmcgui.Dialog().notification("Notice", "Select a repeater first.", xbmcgui.NOTIFICATION_WARNING)
            return
        repeater = self.selected_repeater
        options = ["Log in as Admin", "Log in as Guest"]
        choice = xbmcgui.Dialog().contextmenu(options)
        if choice == -1:
            return
        if choice == 0:
            # Password-masked input for the admin login -- the RemoteTerm
            # API takes a single "password" field either way; a guest
            # login is confirmed via the schema to just be that same
            # field sent as an empty string.
            keyboard = xbmc.Keyboard('', f"Admin password for {repeater['name']}", True)
            keyboard.doModal()
            if not keyboard.isConfirmed():
                return
            password = keyboard.getText()
            role = "Admin"
        else:
            password = ""
            role = "Guest"

        def worker():
            result = self.api.login_repeater(repeater["key"], password)
            if result and result.get("authenticated"):
                xbmcgui.Dialog().notification("RemoteTerm", f"Logged in to {repeater['name']} as {role}",
                                               xbmcgui.NOTIFICATION_INFO)
            else:
                msg = (result or {}).get("message") or "Login failed or no response from repeater"
                xbmcgui.Dialog().notification("RemoteTerm", msg, xbmcgui.NOTIFICATION_ERROR)

        threading.Thread(target=worker, daemon=True).start()
        xbmcgui.Dialog().notification("RemoteTerm", f"Logging in as {role} over the mesh...",
                                       xbmcgui.NOTIFICATION_INFO, 2000)

    # -- Search -----------------------------------------------------------------

    def _do_search(self):
        keyboard = xbmc.Keyboard('', 'Search messages')
        keyboard.doModal()
        if not (keyboard.isConfirmed() and keyboard.getText()):
            return
        query = keyboard.getText()
        xbmc.log(f"[RemoteTerm] searching for: {query!r}", xbmc.LOGINFO)
        results = self.api.search_messages(query)
        xbmc.log(f"[RemoteTerm] search returned {len(results)} result(s)", xbmc.LOGINFO)
        if not results:
            xbmcgui.Dialog().notification("RemoteTerm", f'No results for "{query}"', xbmcgui.NOTIFICATION_INFO)
            return
        # Search moved off its own nav-rail slot and into a dialog reached
        # from the Nodes tab (it searches messages, not nodes -- an odd
        # fit conceptually, but there was nowhere else to put the entry
        # point without a dedicated tab, and the nav rail has no room to
        # spare). A native Kodi select dialog replaces what used to be a
        # full results-list tab -- same query and same "jump straight to
        # that conversation" behavior, just without needing a whole page
        # of its own.
        labels = []
        for m in results:
            label = _safe_label_text(m.get("channel_name") or m.get("sender_name") or (m.get("conversation_key") or "")[:12])
            snippet = _safe_message_text((m.get("text") or "")[:80])
            labels.append(f"{label}: {snippet}")
        choice = xbmcgui.Dialog().select(f'Results for "{query}"', labels)
        if choice == -1:
            return
        m = results[choice]
        key = m.get("conversation_key", "")
        if not key:
            return
        msg_type = m.get("type", "CHAN")
        match = next((c for c in self.conversations if c["key"] == key), None)
        if not match:
            match = {"key": key, "type": "dm" if msg_type == "PRIV" else "channel", "display": key[:12]}
        self._open_conversation(match)
        self._switch_tab(TAB_CHATS, ID_COMPOSE)
        self._populate_convo_list(self._visible_conversations())

    # -- Contacts (clients / repeaters / room servers / sensors) -----------------

    def _populate_contacts(self):
        items = self.contacts_all
        if self.contacts_filter is not None:
            items = [c for c in items if c.get("contact_type") == self.contacts_filter]

        center = self.api.map_center
        if self.contacts_sort == "recent":
            items = sorted(items, key=lambda c: c.get("last_seen") or 0, reverse=True)
        elif self.contacts_sort == "distance":
            if center is not None:
                lat0, lon0 = center
                items = sorted(items, key=lambda c: (self.api.haversine_km(lat0, lon0, c["lat"], c["lon"])
                                                      if c.get("lat") and c.get("lon") else float("inf")))
            # else: no configured location to sort by -- fall through and
            # leave items in server order rather than sorting against a
            # fabricated origin point. The per-row label below already
            # tells the user why nothing is sorted, instead of silently
            # showing a "distance" that was never actually measured from
            # anywhere real.
        elif self.contacts_sort == "hops_near":
            items = sorted(items, key=lambda c: self._hop_sort_key(c.get("last_path_len")))
        elif self.contacts_sort == "hops_far":
            items = sorted(items, key=lambda c: self._hop_sort_key(c.get("last_path_len")), reverse=True)

        self.contacts_list.reset()
        if not items:
            self.contacts_list.addItem(xbmcgui.ListItem("No contacts in this category"))
            return
        for c in items:
            type_name = CONTACT_TYPE_NAMES.get(c.get("contact_type", 0), "Unknown")
            extra = _ago(c.get("last_seen"))
            if self.contacts_sort == "distance":
                if center is not None and c.get("lat") and c.get("lon"):
                    lat0, lon0 = center
                    km = self.api.haversine_km(lat0, lon0, c["lat"], c["lon"])
                    extra = f"{self.api.format_distance(km)} away"
                elif center is None:
                    extra = "set your location in Settings"
            elif self.contacts_sort in ("hops_near", "hops_far"):
                extra = _hops_label(c.get("last_path_len"))
            li = xbmcgui.ListItem(f"{_safe_label_text(c['display'])}   [{type_name}]   -- {extra}")
            li.setProperty("key", c["key"])
            li.setProperty("contact_type", str(c.get("contact_type", 0)))
            self.contacts_list.addItem(li)

    @staticmethod
    def _hop_sort_key(n):
        if n is None:
            return 999
        if n < 0:  # flood -- treat as "many hops, unknown"
            return 998
        return n

    def _show_contact_context(self):
        item = self.contacts_list.getSelectedItem()
        if not item or not item.getProperty("key"):
            return
        key = item.getProperty("key")
        contact_type = item.getProperty("contact_type")
        name = item.getLabel().split("   [")[0]
        options = ["View details"]
        if contact_type == "2":
            options.append("Query live status (repeater)")
            options.append("Open Node Console")
        options.append("Message this contact")
        choice = xbmcgui.Dialog().contextmenu(options)
        if choice == -1:
            return
        if options[choice] == "View details":
            self._show_contact_detail(key, name)
        elif options[choice] == "Query live status (repeater)":
            self._query_repeater_live(key, name)
        elif options[choice] == "Open Node Console":
            # Repeaters is now a first-class nav tab (see ID_NAV_REPEATERS)
            # rather than a destination reachable only from here -- this
            # remains as a convenient shortcut straight to a specific
            # repeater's console, but it's no longer the ONLY way in, and
            # it now leads to the same consistently-behaved tab (same
            # Back behavior, same everything) as the nav icon does.
            self.selected_repeater = {"key": key, "name": name}
            self._load_repeater_console()
            self._switch_tab(TAB_REPEATERS, ID_REPEATER_PICKER)
        elif options[choice] == "Message this contact":
            match = next((c for c in self.conversations if c["key"] == key), None)
            if match:
                self._open_conversation(match)
                self._switch_tab(TAB_CHATS, ID_COMPOSE)
                self._populate_convo_list(self._visible_conversations())

    def _show_contact_detail(self, key, name):
        detail = self.api.get_contact_detail(key)
        # Confirmed real bug: "if not detail" treats a genuinely empty
        # dict ({}) the same as a failed call (None) -- but an empty
        # dict with no keys at all is a different, valid situation
        # (the endpoint successfully returned, it just has nothing to
        # report), while a dict WITH keys that all happen to be zero
        # (e.g. a repeater you've never directly messaged: dm_message_
        # count=0, no active rooms) is neither of those and shouldn't
        # be told apart as "no detail" either. Logging the raw response
        # here since this hadn't been confirmed live before.
        xbmc.log(f"[RemoteTerm] contact detail for {key[:12]}: {detail!r}", xbmc.LOGINFO)
        if detail is None:
            xbmcgui.Dialog().notification("RemoteTerm", "Could not reach the server for details",
                                           xbmcgui.NOTIFICATION_WARNING)
            return
        dm_count = detail.get('dm_message_count', 0)
        chan_count = detail.get('channel_message_count', 0)
        rooms = detail.get("most_active_rooms") or []
        nearest = detail.get("nearest_repeaters") or []
        if not dm_count and not chan_count and not rooms and not nearest:
            xbmcgui.Dialog().notification(
                "RemoteTerm", "No message history or activity with this contact yet",
                xbmcgui.NOTIFICATION_INFO)
            return
        lines = [
            f"Direct messages: {dm_count}",
            f"Channel messages seen from this sender: {chan_count}",
        ]
        if rooms:
            lines.append("Most active rooms: " + ", ".join(r.get("channel_name", "?") for r in rooms[:5]))
        if nearest:
            lines.append("Nearest repeaters: " + ", ".join(r.get("name", "?") for r in nearest[:5]))
        xbmcgui.Dialog().textviewer(name, "\n".join(lines))

    def _query_repeater_live(self, public_key, display_name):
        dialog = xbmcgui.DialogProgress()
        dialog.create("RemoteTerm", f"Querying {display_name} over the mesh...")
        result_holder = {}

        def worker():
            result_holder["status"] = self.api.query_repeater_status(public_key)

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        waited = 0
        while t.is_alive() and waited < 32 and not dialog.iscanceled():
            xbmc.sleep(200)
            waited += 0.2
        dialog.close()

        status = result_holder.get("status")
        if not status:
            xbmcgui.Dialog().notification("RemoteTerm", "Repeater did not respond in time",
                                           xbmcgui.NOTIFICATION_WARNING)
            return
        # Full raw response logged once here: a side-by-side comparison
        # against the real web frontend showed its "Telemetry" panel has
        # far more fields (uptime, TX/RX airtime %, RSSI, SNR, packet
        # rates, flood/direct breakdown, duplicates, RX errors, TX queue,
        # debug flags) than the 3 this addon was extracting (battery,
        # airtime, packets_received). Rather than guess the extra field
        # names, this logs the complete response for confirmation, and
        # the display below now shows EVERY field the API actually
        # returns instead of a fixed, likely-incomplete subset.
        xbmc.log(f"[RemoteTerm] repeater status (full) for {public_key[:12]}: {status!r}", xbmc.LOGINFO)
        xbmcgui.Dialog().textviewer(f"{display_name} -- Live Status", _format_key_value_dict(status) or "No data returned")

    def _show_repeater_more_info(self, public_key, display_name):
        """Radio Settings, Owner Info, and Regions -- confirmed via the
        RemoteTerm OpenAPI schema (radio-settings, owner-info, regions
        endpoints), not guessed. Runs on a background thread since each
        is its own live mesh round-trip; called from a button press, so
        this mirrors the existing threaded pattern used for refresh."""
        dialog = xbmcgui.DialogProgress()
        dialog.create("RemoteTerm", f"Querying {display_name} over the mesh...")
        sections = []

        def fetch(label, func):
            if dialog.iscanceled():
                return
            try:
                result = func(public_key)
                xbmc.log(f"[RemoteTerm] repeater {label.lower()} for {public_key[:12]}: {result!r}", xbmc.LOGINFO)
                if result:
                    sections.append(f"[B]{label}[/B]\n" + _format_key_value_dict(result))
            except Exception as e:
                xbmc.log(f"[RemoteTerm] repeater {label.lower()} query failed: {e}", xbmc.LOGDEBUG)

        fetch("Radio Settings", self.api.get_repeater_radio_settings)
        fetch("Owner Info", self.api.get_repeater_owner_info)
        fetch("Regions", self.api.get_repeater_regions)
        fetch("Advert Intervals", self.api.get_repeater_advert_intervals)
        dialog.close()

        text = "\n\n".join(sections) if sections else "No data returned"
        xbmcgui.Dialog().textviewer(f"{display_name} -- More Info", text)

    # -- Map (distance list -- no dynamic controls, nothing to get stuck
    #    in; a scatter-plot canvas built from many runtime-added controls
    #    turned out fragile in practice) -----------------------------

    def _map_center_point(self):
        """Real, non-fabricated center point for the map: the user's own
        configured location if set (Add-on Settings), otherwise the
        centroid of every currently-located node -- never a hardcoded
        city or region. This addon's deployment happens to be LA-based,
        but nothing here assumes that; a different install with nodes
        clustered elsewhere centers correctly on its own real data."""
        center = self.api.map_center
        if center is not None:
            return center
        pts = [c for c in self.contacts_all if c.get("lat") and c.get("lon")]
        if not pts:
            return None
        return (sum(c["lat"] for c in pts) / len(pts), sum(c["lon"] for c in pts) / len(pts))

    def _render_map_tiles(self, center_lat, center_lon, zoom):
        """Sets each of the grid's tile image controls to its correct real
        map tile (fetched/cached via the API client) and returns the
        pixel origin (top-left corner, in the same global Web Mercator
        pixel space used for markers) of the grid at this zoom -- needed
        afterward to place markers at the right on-screen position.
        Snapped to whole-tile boundaries (Kodi can't crop a sub-region of
        an image without PIL, which isn't available in Kodi's bundled
        Python), so the displayed center is accurate to within roughly
        half a tile's width of the true center rather than pixel-exact --
        a reasonable trade-off, not a fabrication of position.

        Confirmed real centering bug (now fixed): the origin used to be
        computed by FLOORING the center pixel to its containing tile,
        then shifting left by half the grid width -- for a 4-tile-wide
        grid, that's always 2 tiles before the center's own tile and only
        1 after, a systematic ~half-tile leftward bias every time,
        regardless of the true fractional position within that tile.
        ROUNDING to the nearest tile boundary instead removes that
        one-directional bias and halves the worst-case error (256px ->
        128px) -- a small, safe fix that doesn't require changing the
        grid's tile count or its layout (5 columns would be properly
        symmetric, but collides with the side list at this canvas width).

        Fetches all tiles in PARALLEL rather than one after another --
        confirmed real bug: 12 tiles fetched sequentially at an 8s
        timeout each meant a genuinely slow/unreachable tile server made
        the whole view take up to 96 seconds, which is what actually
        produced the reported "freeze" (confirmed by the FPS counter
        collapsing to ~15 during it). Worst case is now bounded by the
        slowest SINGLE tile (a few seconds), not the sum of all twelve."""
        cx, cy = self.api.lonlat_to_pixel(center_lon, center_lat, zoom)
        tile = self.api.TILE_SIZE
        origin_tile_x = round(cx / tile) - ID_MAP_GRID_COLS // 2
        origin_tile_y = round(cy / tile) - ID_MAP_GRID_ROWS // 2

        coords = [(origin_tile_x + col, origin_tile_y + row)
                  for row in range(ID_MAP_GRID_ROWS) for col in range(ID_MAP_GRID_COLS)]
        results = [None] * len(coords)

        def fetch_one(i, tx, ty):
            # Confirmed real bug: get_tile_path itself used to have an
            # unguarded call before its own try/except started, so an
            # exception there silently killed this thread with nothing
            # in the log at all (Python's default behavior for an
            # uncaught exception inside a thread target is to print to
            # stderr, which Kodi's log never sees). That's fixed at the
            # source now, but this wrapper stays as a permanent backstop
            # so the exact same failure mode -- a silent, invisible dead
            # thread -- can never happen again for a different reason.
            try:
                results[i] = self.api.get_tile_path(zoom, tx, ty)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] map tile thread {i} ({tx},{ty}) crashed: {type(e).__name__}: {e}", xbmc.LOGINFO)

        threads = [threading.Thread(target=fetch_one, args=(i, tx, ty), daemon=True)
                   for i, (tx, ty) in enumerate(coords)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6)

        tid = ID_MAP_TILE_BASE
        for path in results:
            try:
                if path:
                    self.getControl(tid).setImage(path)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] map tile control {tid} failed: {e}", xbmc.LOGINFO)
            tid += 1
        failed = sum(1 for p in results if not p)
        if failed:
            xbmc.log(f"[RemoteTerm] map: {failed} of {len(results)} tiles failed to load "
                      f"(zoom={zoom}, network issue or tile server unreachable)", xbmc.LOGINFO)
        try:
            using_carto = bool((self.api.addon.getSetting("carto_api_key") or "").strip())
            self.getControl(1014).setLabel(
                "(c) OpenStreetMap contributors (c) CARTO" if using_carto else "(c) OpenStreetMap contributors")
        except Exception:
            pass
        return origin_tile_x * tile, origin_tile_y * tile

    def _place_map_markers(self, nodes, zoom, origin_px_x, origin_px_y, highlight_key=None):
        """Positions real marker dots over the tile grid using pure Web
        Mercator projection math (no image compositing) -- blue for
        repeaters, green for every other node type, per explicit
        request. Nodes that fall outside the currently-displayed tile
        grid are simply skipped (like any real map, markers off-screen
        aren't shown), and any marker slots beyond how many real located
        nodes there are get hidden rather than left showing stale
        positions from a previous render. If highlight_key is given,
        that one node's marker renders larger and in a distinct color so
        selecting a node from the list actually shows where it is on the
        map, not just facts about it in a popup.

        Confirmed real bug: this used to take the first N in-bounds nodes
        in whatever order `nodes` was already sorted (nearest-to-home or
        most-recent), breaking as soon as the cap was reached. Since this
        deployment has hundreds of nodes packed densely around LA and
        comparatively few further out, "first N by distance" meant the
        cap was reached almost entirely from that one dense cluster --
        confirmed by a screenshot showing the Regional view (which should
        span Central California to Mexico) with every marker bunched
        into a single blob near LA, none of the real, further-out nodes
        that were still within the visible area ever getting a turn.
        Fixed by collecting every in-bounds candidate FIRST, then, only
        if there are more than the cap allows, taking an evenly-spaced
        sample across that full list rather than just the front of it --
        so a zoomed-out view actually shows the real geographic spread of
        what's on screen instead of one lopsided cluster."""
        grid_w = ID_MAP_GRID_COLS * self.api.TILE_SIZE
        grid_h = ID_MAP_GRID_ROWS * self.api.TILE_SIZE
        candidates = []
        for c in nodes:
            px, py = self.api.lonlat_to_pixel(c["lon"], c["lat"], zoom)
            rel_x, rel_y = px - origin_px_x, py - origin_px_y
            if 0 <= rel_x <= grid_w and 0 <= rel_y <= grid_h:
                candidates.append((c, rel_x, rel_y))

        if len(candidates) > ID_MAP_MARKER_COUNT:
            step = len(candidates) / ID_MAP_MARKER_COUNT
            candidates = [candidates[int(i * step)] for i in range(ID_MAP_MARKER_COUNT)]

        mid = ID_MAP_MARKER_BASE
        shown = 0
        for c, rel_x, rel_y in candidates:
            try:
                dot = self.getControl(mid)
                is_highlighted = highlight_key is not None and c.get("key") == highlight_key
                size = 28 if is_highlighted else 14
                dot.setWidth(size)
                dot.setHeight(size)
                dot.setPosition(int(ID_MAP_GRID_LEFT + rel_x - size / 2), int(ID_MAP_GRID_TOP + rel_y - size / 2))
                if is_highlighted:
                    dot.setColorDiffuse("FFFFFFFF")
                else:
                    dot.setColorDiffuse("FF2A6DF4" if c.get("contact_type") == 2 else "FF00FF66")
                dot.setVisible(True)
            except Exception as e:
                # This whole code path was completely unreachable-in-
                # practice until a separate, now-fixed bug (a hardcoded
                # <visible>false</visible> on every marker control, which
                # permanently overrides any setVisible(True) call from
                # Python since Kodi's skin engine re-asserts XML-defined
                # visibility conditions every frame) meant markers never
                # rendered regardless of what this function did. Logging
                # here for real now, in case anything else turns out to
                # be wrong with positioning/coloring now that it can
                # actually be observed.
                xbmc.log(f"[RemoteTerm] map marker {mid} failed: {type(e).__name__}: {e}", xbmc.LOGINFO)
            mid += 1
            shown += 1
        while mid < ID_MAP_MARKER_BASE + ID_MAP_MARKER_COUNT:
            try:
                self.getControl(mid).setVisible(False)
            except Exception:
                pass
            mid += 1
        xbmc.log(f"[RemoteTerm] map: placed {shown} marker(s) out of {len(nodes)} located node(s) "
                  f"(grid covers {grid_w}x{grid_h}px at zoom {zoom})", xbmc.LOGINFO)
        return shown

    def _load_map(self):
        pts = [c for c in self.contacts_all if c.get("lat") and c.get("lon")]
        self.map_list.reset()
        if not pts:
            for mid in range(ID_MAP_MARKER_BASE, ID_MAP_MARKER_BASE + ID_MAP_MARKER_COUNT):
                try:
                    self.getControl(mid).setVisible(False)
                except Exception:
                    pass
            self.map_list.addItem(xbmcgui.ListItem("No contacts have reported GPS location yet"))
            self.map_label.setLabel("No located nodes yet")
            return

        center = self.map_pan_center or self._map_center_point()
        lat0, lon0 = center
        zoom = 11 if self.map_zoom_mode == "local" else 7
        # Immediate feedback before the (up to several seconds, even
        # parallelized) tile fetch -- otherwise the page gives no visual
        # sign anything is happening, which is exactly what read as a
        # "freeze" before.
        try:
            self.map_label.setLabel(f"Loading {'local' if self.map_zoom_mode == 'local' else 'regional'} map tiles...")
        except Exception:
            pass
        origin_x, origin_y = self._render_map_tiles(lat0, lon0, zoom)

        # Sorted by last heard (most recent first), per explicit request --
        # this ordering only affects the side list now; which markers
        # actually get drawn on the map is decided separately (see
        # _place_map_markers' even-sampling fix), so this no longer needs
        # to double as "pick which nodes are worth showing" the way it
        # did before that fix.
        rows = sorted(pts, key=lambda c: c.get("last_seen") or 0, reverse=True)
        user_center = self.api.map_center

        shown = self._place_map_markers(rows, zoom, origin_x, origin_y)

        for c in rows:
            type_name = CONTACT_TYPE_NAMES.get(c.get("contact_type", 0), "Unknown")
            li = xbmcgui.ListItem(f"{_safe_label_text(c['display'])}   [{type_name}]   --   heard {_ago(c.get('last_seen'))}")
            li.setProperty("map_key", c["key"])
            self.map_list.addItem(li)

        view_name = "Local" if self.map_zoom_mode == "local" else "Regional"
        centered_on = "your configured location" if user_center is not None else "the centroid of located nodes"
        # shown vs len(rows) is not a fair comparison on its own -- rows
        # is every located node anywhere, most of which are outside the
        # current view's bounds regardless of the marker cap. Only worth
        # flagging when the cap (not geography) is the reason something's
        # missing, i.e. shown == the cap itself.
        if shown >= ID_MAP_MARKER_COUNT:
            self.map_label.setLabel(f"Showing {shown} node(s) spread across the visible area (more are hidden) -- "
                                     f"{view_name} view, centered on {centered_on}")
        else:
            self.map_label.setLabel(f"{len(rows)} located node(s) -- {view_name} view, centered on {centered_on}")

    def _show_map_node_info(self):
        item = self.map_list.getSelectedItem()
        if not item:
            return
        key = item.getProperty("map_key")
        if not key:
            return
        match = next((c for c in self.contacts_all if c["key"] == key), None)
        if not match:
            return
        # Re-center the map on this node and highlight its marker BEFORE
        # the popup blocks on user input, so the map behind it is already
        # showing the real location by the time they dismiss the dialog
        # -- requested explicitly: selecting a node should show WHERE it
        # is, not just describe it in a popup.
        threading.Thread(target=self._center_map_on_node, args=(match,), daemon=True).start()
        type_name = CONTACT_TYPE_NAMES.get(match.get("contact_type", 0), "Unknown")
        lines = [
            f"Type: {type_name}",
            f"Last heard: {_ago(match.get('last_seen'))}",
            f"Coordinates: {match['lat']:.5f}, {match['lon']:.5f}",
        ]
        xbmcgui.Dialog().ok(_safe_label_text(match["display"]), "\n".join(lines))

    def _center_map_on_node(self, node):
        self.map_pan_center = (node["lat"], node["lon"])
        zoom = 11 if self.map_zoom_mode == "local" else 7
        origin_x, origin_y = self._render_map_tiles(node["lat"], node["lon"], zoom)
        pts = [c for c in self.contacts_all if c.get("lat") and c.get("lon")]
        self._place_map_markers(pts, zoom, origin_x, origin_y, highlight_key=node["key"])
        try:
            self.map_label.setLabel(f"Centered on {_safe_label_text(node['display'])} "
                                     f"-- press Home to return to your actual location")
        except Exception:
            pass

    def _map_home(self):
        self.map_pan_center = None
        self._load_map()

    def _pan_map(self, direction):
        zoom = 11 if self.map_zoom_mode == "local" else 7
        lat0, lon0 = self.map_pan_center or self._map_center_point() or (0.0, 0.0)
        cx, cy = self.api.lonlat_to_pixel(lon0, lat0, zoom)
        grid_w = ID_MAP_GRID_COLS * self.api.TILE_SIZE
        grid_h = ID_MAP_GRID_ROWS * self.api.TILE_SIZE
        # Shifts by 60% of the visible grid each press -- enough to
        # reveal new area while keeping meaningful overlap with what was
        # already on screen, rather than jumping to a totally
        # disconnected view.
        if direction == "north":
            cy -= grid_h * 0.6
        elif direction == "south":
            cy += grid_h * 0.6
        elif direction == "east":
            cx += grid_w * 0.6
        elif direction == "west":
            cx -= grid_w * 0.6
        new_lon, new_lat = self.api.pixel_to_lonlat(cx, cy, zoom)
        self.map_pan_center = (new_lat, new_lon)
        self._load_map()

    # -- Conversations / messages -------------------------------------------------

    def _open_conversation(self, conversation):
        self.selected = conversation
        self.convo_title.setLabel(conversation["display"])
        self._update_favorite_toggle()
        self._update_notify_toggle()
        self._last_message_id = 0
        self._message_display_limit = MESSAGE_DISPLAY_DEFAULT
        self._cached_messages = []
        if self._unread_counts.pop(conversation.get("key"), None):
            self._update_unread_badge_in_place(conversation.get("key"))
        # Tell the server this conversation was actually read -- confirmed
        # via the OpenAPI schema (per-type mark-read endpoints exist for
        # both contacts and channels). A prior version of this client only
        # ever cleared its own local counter above, so the server's own
        # unread/mention state (GET /api/read-state/unreads) never
        # reflected anything being read from this client at all.
        key, conv_type = conversation.get("key"), conversation.get("type")

        def mark_read_worker():
            try:
                if conv_type == "channel":
                    self.api.mark_channel_read(key)
                else:
                    self.api.mark_contact_read(key)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] mark-read failed for {key}: {e}", xbmc.LOGDEBUG)

        threading.Thread(target=mark_read_worker, daemon=True).start()
        # Show a placeholder immediately, before the network fetch even
        # starts, instead of leaving the PREVIOUS conversation's messages
        # on screen until the new ones abruptly replace them -- that
        # abrupt swap is what read as a "flash" when switching between
        # busy channels. This makes the transition look intentional.
        # Guarded by the same lock as a real reload so this can't race
        # with one already in flight for whatever was open before.
        with self._message_list_lock:
            self.message_list.reset()
            loading = xbmcgui.ListItem(f"Loading messages for {conversation['display']}...")
            loading.setProperty("align", "left")
            # "00000000" (fully zero alpha) was used here for "no visible
            # bubble" -- confirmed by screenshot to render as a solid
            # WHITE box instead of transparent, matching the same Kodi
            # quirk already fixed for button textures: some builds don't
            # honour all-zero colordiffuse and fall back to the texture's
            # native colour. White text on that white box was invisible,
            # which is exactly the "white box, no words" symptom reported.
            # A near-zero but non-zero alpha avoids the same trap.
            loading.setProperty("bubble_color", "01000000")
            self.message_list.addItem(loading)
        self._load_messages(force_scroll_bottom=True)

    def _update_favorite_toggle(self):
        if not self.selected:
            return
        # "favorite" lives directly on the Contact/Channel object now (see
        # api.get_conversations), not in a separate settings list -- so
        # the currently-selected conversation's own is_favorite flag is
        # already the answer, no lookup needed.
        is_fav = bool(self.selected.get("is_favorite"))
        self.setProperty("selected_favorite", "true" if is_fav else "false")

    def _toggle_favorite(self):
        if not self.selected:
            return
        fav_type = "channel" if self.selected["type"] == "channel" else "contact"
        result = self.api.toggle_favorite(fav_type, self.selected["key"])
        if result is not None:
            # Trust the server's resulting state rather than re-fetching
            # everything over the network just to learn one boolean --
            # apply it to both the selected conversation and its entry in
            # the cached list so the star and the list row agree
            # immediately.
            new_fav = bool(result.get("favorite"))
            self.selected["is_favorite"] = new_fav
            for conv in self.conversations:
                if conv["type"] == self.selected["type"] and conv["key"] == self.selected["key"]:
                    conv["is_favorite"] = new_fav
                    break
            self._update_favorite_toggle()
            self._populate_convo_list(self._visible_conversations())
        else:
            xbmcgui.Dialog().notification("RemoteTerm", "Could not update favorites",
                                           xbmcgui.NOTIFICATION_ERROR)

    def _update_notify_toggle(self):
        if not self.selected:
            return
        state_key = self._to_state_key(self.selected["type"], self.selected["key"])
        enabled = state_key in self._push_conversations
        self.notify_toggle.setLabel("Notify: On" if enabled else "Notify: Off")

    def _toggle_notify(self):
        if not self.selected:
            return
        state_key = self._to_state_key(self.selected["type"], self.selected["key"])

        def worker():
            result = self.api.toggle_push_conversation(state_key)
            if result is not None:
                if state_key in self._push_conversations:
                    self._push_conversations.discard(state_key)
                else:
                    self._push_conversations.add(state_key)
                self._update_notify_toggle()
            else:
                xbmcgui.Dialog().notification("RemoteTerm", "Could not update notification setting",
                                               xbmcgui.NOTIFICATION_ERROR)

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_favorites_filter(self):
        self.favorites_only = not self.favorites_only
        self.setProperty("favorites_only", "true" if self.favorites_only else "false")
        if self.favorites_only:
            # Explicitly re-fetch rather than trusting whatever was cached
            # from the last general refresh -- favorites can be changed
            # from the real web UI or another client while this addon is
            # open, and switching into this view is exactly the moment
            # the person wants to see the current, real list.
            self._load_conversations()
        self._populate_convo_list(self._visible_conversations())
        # Confirmed real bug, traced through exact keypress timing in a
        # log: the previous fix here kept focus ON this button (id 340)
        # after the click, on the theory that "stay where you were" was
        # the safe behavior -- and it did technically work, the log
        # showed the drift-and-restore succeeding every time. But from
        # the user's side, landing back on the SAME toggle button they
        # just pressed, with the flash-to-Dashboard-and-back happening
        # too fast to clearly perceive, read as "nothing happened" --
        # so the very next thing they did was press Enter again, which
        # doesn't "confirm" or "enter" anything on a toggle button, it
        # just flips the filter straight back off. That's the actual
        # loop that was reported as being "kicked out and needing to
        # re-enter": not a focus failure, a focus target that didn't
        # match what pressing Enter on it would visibly, unambiguously
        # confirm. Landing directly in the (now-filtered) list instead
        # -- the same place clicking the Chats nav icon itself lands --
        # shows a real highlighted row immediately, so there's nothing
        # left to be unsure about, and an extra Enter press just opens
        # that conversation instead of undoing the toggle.
        try:
            self.setFocusId(ID_CONVO_LIST)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] setFocusId({ID_CONVO_LIST}) failed: {e}", xbmc.LOGDEBUG)

    def _load_messages(self, force_scroll_bottom=False):
        """Guaranteed reload for explicit user actions (opening a
        conversation, a successful send) -- blocks briefly on the lock if
        a background reload happens to be in flight, which is an
        acceptable short wait for a deliberate action, unlike the
        background poll path below which must never block the main thread."""
        with self._message_list_lock:
            self._load_messages_unsafe(force_scroll_bottom)

    def _reload_messages_if_free(self):
        """Used only by the debounced background poll. See _load_messages
        for why concurrent callers must be serialized: without this,
        screenshots showed some message rows rendering correctly while
        others in the very same list showed raw, unparsed "[COLOR ...][B]"
        tag text with the name or message cut off -- the signature of an
        interleaved reset()/addItem() write from two threads at once, not
        a formatting bug (a real formatting bug would break every row
        identically). This uses a non-blocking acquire rather than a plain
        lock: if a reload is already in flight (a real network fetch that
        can itself take a few seconds), this just skips rather than
        blocking the main GUI thread -- that would reproduce the exact
        class of freeze already fixed for repeater queries. A skipped
        reload isn't lost; the in-progress one covers it, or the next
        debounce tick will."""
        if not self._message_list_lock.acquire(blocking=False):
            xbmc.log("[RemoteTerm] message reload already in progress, skipping", xbmc.LOGDEBUG)
            return
        try:
            self._load_messages_unsafe(force_scroll_bottom=False)
        finally:
            self._message_list_lock.release()

    def _load_messages_unsafe(self, force_scroll_bottom=False):
        if not self.selected:
            return
        self._last_reload_time = time.time()
        self._messages_dirty = False

        # "Smart scroll": a background reload used to jump the view to the
        # newest message every time, no matter where the user had scrolled
        # -- on a busy channel refreshing every few seconds, that reads as
        # the whole screen constantly jerking around. Only force the jump
        # for an explicit action (opening the conversation, just sending a
        # message) or when the user was already reading near the bottom;
        # otherwise leave their scroll position alone.
        old_size = self.message_list.size()
        try:
            old_pos = self.message_list.getSelectedPosition()
        except Exception:
            old_pos = old_size - 1
        should_scroll_bottom = force_scroll_bottom or old_size == 0 or old_pos >= old_size - 3

        msg_type = "CHAN" if self.selected["type"] == "channel" else "PRIV"
        messages = self.api.get_messages(self.selected["key"], msg_type)
        xbmc.log(f"[RemoteTerm] loaded {len(messages)} message(s) for {self.selected['key'][:12]} ({msg_type})",
                  xbmc.LOGINFO)
        self._cached_messages = messages
        self._render_cached_messages(should_scroll_bottom)

    def _render_cached_messages(self, should_scroll_bottom):
        """Renders from self._cached_messages, which already holds the full,
        correctly-ordered history for the open conversation -- "Load More"
        just raises self._message_display_limit and calls this again, with
        no network round-trip at all, since the data is already in memory."""
        prev_focus = self.getFocusId()
        messages = self._cached_messages
        total = len(messages)
        limit = self._message_display_limit
        truncated = total > limit
        if truncated:
            messages = messages[-limit:]
        self.message_list.reset()
        if not messages:
            li = xbmcgui.ListItem("No messages in this conversation yet.")
            li.setProperty("align", "left")
            li.setProperty("bubble_color", "01000000")
            self.message_list.addItem(li)
            self._last_message_id = 0
            self._guard_chat_focus(prev_focus)
            return
        if truncated:
            note = xbmcgui.ListItem(
                f"[COLOR FF6D9DF5][B]Load {min(MESSAGE_DISPLAY_STEP, total - len(messages))} more "
                f"older message(s)[/B][/COLOR]  ({total - len(messages)} not shown)")
            note.setProperty("align", "left")
            note.setProperty("bubble_color", "331B2130")
            note.setProperty("load_more", "1")
            self.message_list.addItem(note)
        for m in messages:
            outgoing = bool(m.get("outgoing"))
            raw_sender_name = "You" if outgoing else (m.get("sender_name") or "Node")
            sender = _safe_label_text(raw_sender_name)
            raw_text = _strip_redundant_sender_prefix(m.get("text") or "", raw_sender_name)
            text = _wrap_for_bubble(_safe_message_text(raw_text))
            accent = GREEN if outgoing else _sender_color(sender)
            acked = m.get("acked", 0)
            # Plain ASCII rather than checkmark glyphs (\u2713) -- an
            # earlier screenshot showed those rendering as missing-glyph
            # boxes in this skin's font, the same class of issue as the
            # bracket lookalikes above.
            ack_marker = "  (delivered)" if (outgoing and acked) else ("  (sent)" if outgoing else "")
            label = f"[COLOR {accent}][B]{sender}[/B][/COLOR]{ack_marker}[CR]{text}"
            li = xbmcgui.ListItem(label)
            li.setProperty("align", "right" if outgoing else "left")
            li.setProperty("bubble_color", OUTGOING_BUBBLE if outgoing else INCOMING_BUBBLE)
            li.setProperty("meta_text", _format_message_meta(m))
            self.message_list.addItem(li)
        self._last_message_id = max((m.get("id") or 0) for m in messages)
        if should_scroll_bottom:
            try:
                self.message_list.selectItem(self.message_list.size() - 1)
            except Exception:
                pass
        self._guard_chat_focus(prev_focus)

    def _send_compose(self):
        if not self.selected:
            xbmcgui.Dialog().notification("Notice", "Select a contact or channel first.", xbmcgui.NOTIFICATION_WARNING)
            return
        keyboard = xbmc.Keyboard('', f"Message {self.selected['display']}")
        keyboard.doModal()
        if not (keyboard.isConfirmed() and keyboard.getText()):
            return
        text = keyboard.getText()
        conversation = self.selected
        xbmc.log(f"[RemoteTerm] sending to {conversation['key'][:12]} ({conversation['type']}): {text!r}",
                  xbmc.LOGINFO)

        # Confirmed real bug: this used to run send_message() directly on
        # the main GUI thread with a 6s timeout, both wrong for a live
        # mesh send (a multi-hop transmission can legitimately take
        # close to the 30s used everywhere else in this addon for the
        # same class of operation) -- freezing the whole UI for the
        # duration, and risking a false "failed" for a message that was
        # actually still in flight. Moved to a background thread with
        # the correct timeout, and the three real outcomes (confirmed
        # sent / timed out with no confirmation / genuinely failed) are
        # now reported honestly rather than collapsed into one
        # sent-or-failed toast -- because with no idempotency key
        # anywhere in this API (confirmed against the schema), a
        # confidently-wrong "failed" is what could actually put a
        # duplicate out over the mesh, if it prompts a resend.
        def worker():
            status, _ = self.api.send_message(conversation, text)
            if status == "ok":
                xbmcgui.Dialog().notification("RemoteTerm", "Message sent", xbmcgui.NOTIFICATION_INFO, 2000)
                self._load_messages(force_scroll_bottom=True)
            elif status == "timeout":
                xbmcgui.Dialog().notification(
                    "RemoteTerm",
                    "No confirmation in time -- it may still have gone through. "
                    "Check the conversation before resending.",
                    xbmcgui.NOTIFICATION_WARNING, 6000)
                self._load_messages(force_scroll_bottom=True)
            else:
                xbmcgui.Dialog().notification("RemoteTerm", "Failed to send -- check host/URL in Settings",
                                               xbmcgui.NOTIFICATION_ERROR)

        threading.Thread(target=worker, daemon=True).start()

    # -- Event handling -----------------------------------------------------------

    def onClick(self, control_id):
        xbmc.log(f"[RemoteTerm] onClick control_id={control_id} tab={self.getProperty('tab')}", xbmc.LOGINFO)
        try:
            self._dispatch_click(control_id)
        except Exception:
            xbmc.log(f"[RemoteTerm] onClick handler crashed:\n{traceback.format_exc()}", xbmc.LOGERROR)
            xbmcgui.Dialog().notification("RemoteTerm", "Something went wrong -- check kodi.log",
                                           xbmcgui.NOTIFICATION_ERROR)

    def _dispatch_click(self, control_id):
        if control_id == ID_REFRESH:
            self.refresh()
            if self.getProperty("tab") == TAB_DASHBOARD:
                self._load_dashboard()
            elif self.getProperty("tab") == TAB_ANALYTICS:
                self._load_analytics()

        elif control_id == ID_NAV_DASHBOARD:
            # Confirmed real bug: this used to be a deliberate no-op, on
            # the reasoning that Dashboard was always reachable via Back
            # from any tab, so clicking its own icon had nothing to do.
            # That reasoning went stale when Back navigation was changed
            # (see _dispatch_action) to stay on whichever tab you're
            # already on instead of always jumping to Dashboard -- once
            # that changed, this no-op meant clicking this icon from any
            # OTHER tab did genuinely nothing at all: the tab property
            # never changed, so Dashboard's own content group (gated on
            # Window.Property(tab)==dashboard) never became visible,
            # regardless of what the nav rail itself showed as focused.
            # A real report confirmed exactly this: selecting Dashboard
            # after backing out of a different tab left that other tab's
            # content on screen with no way to actually reach Dashboard
            # from the rail. Now matches every other nav icon's own
            # handler: unconditionally reload and switch.
            self._load_dashboard()
            self._switch_tab(TAB_DASHBOARD, ID_NAV_DASHBOARD)

        elif control_id == ID_NAV_CHATS:
            self._populate_convo_list(self._visible_conversations())
            self._switch_tab(TAB_CHATS, ID_CONVO_LIST)
            # Re-sync with the backend every time the Chats tab is opened,
            # not just once at addon startup -- unread/notification state
            # can change from other clients (the browser frontend, another
            # device) at any time, and this addon has no other way to
            # find out except asking again.
            threading.Thread(target=self._load_notification_state, daemon=True).start()

        elif control_id == ID_SEARCH_BUTTON:
            self._do_search()

        elif control_id == ID_NAV_CONTACTS:
            self.contacts_filter = None
            self._populate_contacts()
            self._switch_tab(TAB_CONTACTS, ID_CONTACTS_FILTER_ALL)

        elif control_id == ID_CONTACTS_FILTER_ALL:
            self.contacts_filter = None
            self._populate_contacts()
        elif control_id == ID_CONTACTS_FILTER_CLIENTS:
            self.contacts_filter = 1
            self._populate_contacts()
        elif control_id == ID_CONTACTS_FILTER_REPEATERS:
            self.contacts_filter = 2
            self._populate_contacts()
        elif control_id == ID_CONTACTS_FILTER_ROOMS:
            self.contacts_filter = 3
            self._populate_contacts()
        elif control_id == ID_CONTACTS_FILTER_SENSORS:
            self.contacts_filter = 4
            self._populate_contacts()

        elif control_id == ID_SORT_RECENT:
            self.contacts_sort = "recent"
            self._populate_contacts()
        elif control_id == ID_SORT_DISTANCE:
            self.contacts_sort = "distance"
            self._populate_contacts()
        elif control_id == ID_SORT_HOPS_NEAR:
            self.contacts_sort = "hops_near"
            self._populate_contacts()
        elif control_id == ID_SORT_HOPS_FAR:
            self.contacts_sort = "hops_far"
            self._populate_contacts()

        elif control_id == ID_CONTACTS_LIST:
            self._show_contact_context()

        elif control_id == ID_NAV_REPEATERS:
            # Confirmed real complaint (multiple reports of getting
            # "lost"): this used to be reachable only as a drill-down
            # from a repeater's context menu inside Nodes, with no nav
            # icon of its own and Back not returning anywhere
            # predictable. Now a first-class tab like every other --
            # self.selected_repeater is intentionally NOT cleared here,
            # so arriving from a repeater's own context menu (which
            # already sets it) still shows that repeater pre-loaded,
            # while arriving directly from the nav rail with nothing
            # selected yet just shows the plain picker list.
            threading.Thread(target=self._load_repeater_console, daemon=True).start()
            self._switch_tab(TAB_REPEATERS, ID_REPEATER_PICKER)

        elif control_id == ID_REPEATER_SORT_RECENT:
            self.repeater_sort = "recent"
            self._load_repeater_console()
        elif control_id == ID_REPEATER_SORT_DISTANCE:
            self.repeater_sort = "distance"
            self._load_repeater_console()
        elif control_id == ID_REPEATER_SORT_HOPS_NEAR:
            self.repeater_sort = "hops_near"
            self._load_repeater_console()
        elif control_id == ID_REPEATER_SORT_HOPS_FAR:
            self.repeater_sort = "hops_far"
            self._load_repeater_console()

        elif control_id == ID_NAV_MAP:
            threading.Thread(target=self._load_map, daemon=True).start()
            self._switch_tab(TAB_MAP, ID_MAP_REFRESH)
        elif control_id == ID_MAP_REFRESH:
            self._load_conversations()
            threading.Thread(target=self._load_map, daemon=True).start()
        elif control_id == ID_MAP_REGIONAL_BTN:
            self.map_zoom_mode = "regional"
            threading.Thread(target=self._load_map, daemon=True).start()
        elif control_id == ID_MAP_LOCAL_BTN:
            self.map_zoom_mode = "local"
            threading.Thread(target=self._load_map, daemon=True).start()
        elif control_id == ID_MAP_HOME:
            threading.Thread(target=self._map_home, daemon=True).start()
        elif control_id == ID_MAP_PAN_NORTH:
            threading.Thread(target=self._pan_map, args=("north",), daemon=True).start()
        elif control_id == ID_MAP_PAN_SOUTH:
            threading.Thread(target=self._pan_map, args=("south",), daemon=True).start()
        elif control_id == ID_MAP_PAN_EAST:
            threading.Thread(target=self._pan_map, args=("east",), daemon=True).start()
        elif control_id == ID_MAP_PAN_WEST:
            threading.Thread(target=self._pan_map, args=("west",), daemon=True).start()
        elif control_id == ID_MAP_LIST:
            self._show_map_node_info()

        elif control_id == ID_NAV_PACKETS:
            self._render_packet_feed()
            self._switch_tab(TAB_PACKETS, ID_PACKET_LIST)
        elif control_id == ID_PACKET_MY_NODES_BTN:
            self.packets_my_nodes_only = not self.packets_my_nodes_only
            try:
                self.getControl(ID_PACKET_MY_NODES_BTN).setLabel(
                    f"My Nodes: {'On' if self.packets_my_nodes_only else 'Off'}")
            except Exception:
                pass
            self._render_packet_feed()
        elif control_id == ID_PACKET_LIST:
            self._show_packet_detail()

        elif control_id == ID_NAV_ANALYTICS:
            self._load_analytics()
            self._switch_tab(TAB_ANALYTICS, ID_REFRESH)
            if self.show_waterfall:
                self._generate_waterfall_bars()

        elif control_id == ID_WATERFALL_TOGGLE:
            self._toggle_waterfall()

        elif control_id == ID_NAV_TRENDS_BTN:
            self._load_trends()
            self._switch_tab(TAB_TRENDS, ID_TRENDS_BACK)

        elif control_id == ID_TRENDS_BACK:
            self._switch_tab(TAB_DASHBOARD, ID_NAV_TRENDS_BTN)

        elif control_id == ID_CONVO_LIST:
            item = self.convo_list.getSelectedItem()
            idx_str = item.getProperty("index") if item else ""
            source = self._visible_conversations()
            if idx_str.isdigit() and int(idx_str) < len(source):
                conv = source[int(idx_str)]
                if conv.get("contact_type") == 2:
                    # Repeaters aren't chat partners -- they don't accept
                    # DMs the way a client contact does, so opening a
                    # normal conversation against one always loaded an
                    # empty, dead-end chat box (confirmed live: "loaded 0
                    # message(s)" for a repeater's key). Route into the
                    # Repeater Console instead, which is what a repeater
                    # actually supports: live node info, telemetry,
                    # neighbors/ACL, and admin/guest login.
                    self.selected_repeater = {"key": conv["key"], "name": conv["display"]}
                    self._load_repeater_console()
                    self._switch_tab(TAB_REPEATERS, ID_REPEATER_PICKER)
                else:
                    self._open_conversation(conv)
                    self.setFocusId(ID_COMPOSE)

        elif control_id == ID_MESSAGE_LIST:
            item = self.message_list.getSelectedItem()
            if item and item.getProperty("load_more"):
                self._message_display_limit += MESSAGE_DISPLAY_STEP
                # Already in memory -- no network call, so this is instant.
                with self._message_list_lock:
                    self._render_cached_messages(should_scroll_bottom=False)

        elif control_id == ID_FAVORITE_TOGGLE:
            self._toggle_favorite()

        elif control_id == ID_NOTIFY_TOGGLE:
            self._toggle_notify()

        elif control_id == ID_FAVORITES_FILTER:
            self._toggle_favorites_filter()

        elif control_id == ID_REPEATER_PICKER:
            self._select_repeater()
        elif control_id in (ID_REPEATER_NEIGHBORS, ID_REPEATER_ACL):
            item = self.getControl(control_id).getSelectedItem()
            detail = item.getProperty("raw_detail") if item else ""
            if detail:
                xbmcgui.Dialog().textviewer("Full Details", detail)
        elif control_id == ID_REPEATER_COMMAND:
            self._send_repeater_command()
        elif control_id == ID_REPEATER_REFRESH:
            if self.selected_repeater:
                threading.Thread(target=self._load_repeater_detail,
                                  args=(self.selected_repeater["key"], self.selected_repeater["name"]),
                                  daemon=True).start()
        elif control_id == ID_REPEATER_MORE_INFO:
            if self.selected_repeater:
                threading.Thread(target=self._show_repeater_more_info,
                                  args=(self.selected_repeater["key"], self.selected_repeater["name"]),
                                  daemon=True).start()
        elif control_id == ID_REPEATER_LOGIN:
            self._login_repeater()

        elif control_id == ID_COMPOSE:
            self._send_compose()

    def _format_packet(self, p):
        """Confirmed shape (captured live from a real deployment):
        {payload_type, snr, rssi, decrypted, transport_code, region,
         decrypted_info: {channel_name, sender, channel_key, contact_key,
                           sender_timestamp, message}}
        decrypted_info is only present when decrypted=True; an encrypted/
        unrecognized packet just won't have it, which is expected."""
        ptype = p.get("payload_type") or "Packet"
        parts = [str(ptype)]
        if p.get("rssi") is not None:
            parts.append(f"RSSI {p['rssi']}dBm")
        if p.get("snr") is not None:
            parts.append(f"SNR {p['snr']}dB")

        info = p.get("decrypted_info") or {}
        if info.get("sender"):
            parts.append(f"from {_safe_label_text(info['sender'])}")
        if info.get("channel_name"):
            parts.append(f"in #{_safe_label_text(info['channel_name'])}")
        if p.get("decrypted"):
            parts.append("decrypted")
        text = _safe_message_text((info.get("message") or "")[:60])
        if text:
            parts.append(f'"{text}"')

        return "  |  ".join(parts)

    def _format_packet_compact(self, p):
        """One-line format for the compact Analytics mini feed. Deliberately
        drops sender/channel/message text -- unlike _format_packet on the
        full-width Packets tab, those are free-text, mesh-provided fields
        of unbounded length and script, and were overflowing this panel's
        much narrower fixed-height rows (confirmed live: long sender names
        wrapped into the next row and an unrenderable glyph in one name
        broke the layout entirely). Type + RSSI + SNR is real, always
        short, and still changes with every packet."""
        ptype = p.get("payload_type") or "Packet"
        bits = [str(ptype)]
        if p.get("rssi") is not None:
            bits.append(f"{p['rssi']}dBm")
        if p.get("snr") is not None:
            bits.append(f"{p['snr']}dB")
        return "   ".join(bits)

    def _packet_columns(self, p):
        """Splits a packet into the fixed set of columns the redesigned
        feed displays, matching CoreScope's real "Excel-like columns"
        packet feed (confirmed via its own README/screenshots) as
        closely as Kodi's list control allows -- genuinely separate,
        aligned fields instead of one long pipe-delimited string. Same
        real fields as the original _format_packet, just split apart
        rather than concatenated."""
        info = p.get("decrypted_info") or {}
        return {
            "col_type": str(p.get("payload_type") or "Packet"),
            "col_rssi": f"{p['rssi']}dBm" if p.get("rssi") is not None else "--",
            "col_snr": f"{p['snr']}dB" if p.get("snr") is not None else "--",
            "col_from": _safe_label_text(info.get("sender") or ("(encrypted)" if not p.get("decrypted") else "--")),
            "col_channel": f"#{_safe_label_text(info['channel_name'])}" if info.get("channel_name") else "--",
            "col_message": _safe_message_text((info.get("message") or "")[:110]),
        }

    def _render_packet_feed(self):
        prev_focus = self.getFocusId()
        with self.packet_feed_lock:
            packets = list(self.packet_feed)
        # Live decrypt-rate context, shown alongside the connection
        # status so the "why is My Nodes empty" answer is visible even
        # when the feed isn't empty -- a confirmed real WebSocket capture
        # showed a whole 20-second stretch with 0 of many packets
        # decrypted, which is expected on a busy shared mesh fanout, not
        # a fault, but looked like one without this context.
        if packets and self.getProperty("live") == "true":
            decrypted_total = sum(1 for p in packets if p.get("decrypted"))
            try:
                self.packet_status.setLabel(
                    f"Live feed connected -- {decrypted_total} of {len(packets)} recent packets "
                    f"decrypted (only your own channels/DMs can decrypt)")
            except Exception:
                pass
        if self.packets_my_nodes_only:
            known_keys = {c["key"] for c in self.contacts_all}
            decrypted_count = sum(1 for p in packets if p.get("decrypted"))
            packets = [p for p in packets
                       if (p.get("decrypted_info") or {}).get("contact_key") in known_keys]
        self.packet_list.reset()
        if not packets:
            if self.packets_my_nodes_only:
                # Distinguishes two genuinely different situations, since
                # confirmed real WebSocket payloads showed EVERY packet
                # in a whole 20-second capture as decrypted:False --
                # "empty because nothing decrypted at all" is a very
                # different, less alarming fact than "things decrypted
                # but none were from a known contact." A shared mesh
                # fanout carries mostly other people's channel traffic
                # your radio has no key for; only your own joined
                # channels or DMs addressed to you ever decrypt, so long
                # encrypted-only stretches are expected, not a fault.
                if decrypted_count == 0:
                    msg = ("Nothing in the current feed has decrypted yet -- this is normal on a "
                           "shared mesh; only your own channels or messages sent directly to you "
                           "can decrypt")
                else:
                    msg = (f"{decrypted_count} packet(s) decrypted, but none from a contact you "
                           f"know")
            else:
                msg = "Waiting for packets..."
            self.packet_list.addItem(xbmcgui.ListItem(msg))
            self._guard_packet_focus(prev_focus)
            return
        for p in packets:
            li = xbmcgui.ListItem(self._format_packet(p))
            for key, value in self._packet_columns(p).items():
                li.setProperty(key, value)
            li.setProperty("packet_detail", self._format_packet_detail(p))
            self.packet_list.addItem(li)
        self._guard_packet_focus(prev_focus)

    def _format_packet_detail(self, p):
        """Full, untruncated detail text for the popup shown when a
        packet row is selected -- the "detail pane" from the reference
        design (CoreScope shows byte-level breakdown in a side panel;
        this addon's API doesn't expose raw bytes, so this surfaces
        every real decoded field it does have instead, in full rather
        than the row's truncated/column-width-limited version)."""
        info = p.get("decrypted_info") or {}
        lines = [f"Type: {p.get('payload_type') or 'Packet'}"]
        if p.get("rssi") is not None:
            lines.append(f"RSSI: {p['rssi']}dBm")
        if p.get("snr") is not None:
            lines.append(f"SNR: {p['snr']}dB")
        lines.append(f"Decrypted: {'Yes' if p.get('decrypted') else 'No'}")
        if p.get("transport_code"):
            lines.append(f"Transport: {p['transport_code']}")
        if p.get("region"):
            lines.append(f"Region: {p['region']}")
        if info.get("sender"):
            lines.append(f"From: {_safe_label_text(info['sender'])}")
        if info.get("channel_name"):
            lines.append(f"Channel: #{_safe_label_text(info['channel_name'])}")
        if info.get("message"):
            lines.append(f"Message: {_safe_message_text(info['message'])}")
        return "\n".join(lines)

    def _show_packet_detail(self):
        item = self.packet_list.getSelectedItem()
        if not item:
            return
        detail = item.getProperty("packet_detail")
        if not detail:
            return
        xbmcgui.Dialog().ok("Packet Detail", detail)

    def _render_analytics_live_feed(self):
        """Compact live packet feed shown in the space to the right of the
        four Analytics gauges -- reuses the exact same real, already-
        flowing packet_feed data as the full Packets tab (no separate or
        fabricated data source), just a smaller/more frequent view of it
        so the Analytics page has something visibly moving in real time
        beyond the periodic gauge refresh."""
        try:
            feed = self.getControl(ID_ANALYTICS_LIVE_FEED)
        except Exception:
            return
        prev_focus = self.getFocusId()
        with self.packet_feed_lock:
            packets = list(self.packet_feed)[:12]
        feed.reset()
        if not packets:
            feed.addItem(xbmcgui.ListItem("Waiting for packets..."))
            self._guard_analytics_focus(prev_focus)
            return
        for p in packets:
            feed.addItem(xbmcgui.ListItem(self._format_packet_compact(p)))
        self._guard_analytics_focus(prev_focus)

    def _generate_waterfall_bars(self):
        """Colors each of the 30 waterfall row controls (ids in
        WATERFALL_BAR_IDS) from the most recent packets in packet_feed --
        the same real, already-flowing data as the Live Feed list this
        panel swaps with, not a separate or fabricated source. Newest
        packet at the top (row 0), each older one a row further down,
        matching how a real waterfall display actually reads: new data
        enters at the top and history is pushed downward, not sideways.
        This addon has no per-frequency signal data to show (this radio
        has no spectrum-analyzer hardware -- see the class-level notes on
        the WATERFALL_BAR_IDS constant), so unlike a true SDR waterfall
        each row is a single flat color rather than a horizontal
        spectrum slice; RSSI over time is the closest honest equivalent
        available from what this radio actually exposes. Packets with no
        rssi reading (rare, but seen in a real capture) are skipped
        rather than drawn as a misleading color -- an absent row reads
        honestly as "no data here", a colored one wouldn't. Any row
        beyond however many real packets currently exist is set fully
        transparent instead of carrying over a stale color from a
        previous render, so a freshly-opened waterfall with few packets
        so far shows exactly that -- a partly-filled strip, not a full
        one lying about how much real data backs it.

        Confirmed real report: toggling this on/off (16 clicks in one
        real session, no visible change reported any of those times, no
        exception surfaced either) left no way to tell WHERE it was
        failing -- every per-row getControl() failure here was being
        silently swallowed and skipped, individually, with nothing to
        show for it afterward. This function running to completion
        without error says nothing about whether any row was actually
        found and colored; logging the real counts is the only way to
        tell those two apart from a log capture.

        Confirmed by that same logging afterward: every single toggle
        correctly flipped the property, and every single render call
        found packets and successfully colored all 30 rows -- 0
        failures, every time -- while a screenshot taken during an "ON"
        moment still showed the old Live Feed list on screen. The Python
        side was never the problem: see _do_init's own notes on why
        these controls now start visible="true" and get hidden once at
        startup instead, which is what actually fixed that."""
        try:
            packets_with_rssi = [p for p in list(self.packet_feed) if p.get("rssi") is not None]
        except Exception:
            packets_with_rssi = []
        newest_first = packets_with_rssi[:len(WATERFALL_BAR_IDS)]
        colored = 0
        failed = 0
        first_error = None
        for i, bar_id in enumerate(WATERFALL_BAR_IDS):
            try:
                ctrl = self.getControl(bar_id)
            except Exception as e:
                failed += 1
                if first_error is None:
                    first_error = str(e)
                continue
            if i < len(newest_first):
                packet = newest_first[i]
                ctrl.setColorDiffuse(_rssi_to_waterfall_color(packet["rssi"]))
                colored += 1
            else:
                ctrl.setColorDiffuse("00000000")
        xbmc.log(f"[RemoteTerm] waterfall render: {len(packets_with_rssi)} packets with rssi in "
                  f"packet_feed, {colored} rows actually colored, {failed} rows failed to resolve"
                  f"{f' (first error: {first_error})' if first_error else ''}", xbmc.LOGINFO)
        ready = bool(newest_first)
        self.setProperty("waterfall_ready", "true" if ready else "")
        try:
            self.getControl(ID_WATERFALL_WAITING_LABEL).setVisible(not ready)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] waterfall waiting-label setVisible failed: {e}", xbmc.LOGINFO)

    def _toggle_waterfall(self):
        self.show_waterfall = not self.show_waterfall
        self.setProperty("show_waterfall", "true" if self.show_waterfall else "false")
        xbmc.log(f"[RemoteTerm] waterfall toggled: now {'ON' if self.show_waterfall else 'OFF'} "
                  f"(show_waterfall property set to {self.getProperty('show_waterfall')!r})", xbmc.LOGINFO)
        try:
            self.getControl(ID_WATERFALL_LIVE_LABEL).setVisible(not self.show_waterfall)
            self.getControl(ID_WATERFALL_LABEL).setVisible(self.show_waterfall)
            self.getControl(ID_WATERFALL_SUBTITLE).setVisible(self.show_waterfall)
            self.getControl(ID_WATERFALL_DOT).setVisible(not self.show_waterfall)
            self.getControl(ID_WATERFALL_ON_INDICATOR).setVisible(self.show_waterfall)
            self.getControl(ID_ANALYTICS_LIVE_FEED).setVisible(not self.show_waterfall)
            self.getControl(ID_WATERFALL_BACKDROP).setVisible(self.show_waterfall)
            for bar_id in WATERFALL_BAR_IDS:
                self.getControl(bar_id).setVisible(self.show_waterfall)
            if not self.show_waterfall:
                self.getControl(ID_WATERFALL_WAITING_LABEL).setVisible(False)
        except Exception as e:
            xbmc.log(f"[RemoteTerm] waterfall setVisible pass failed: {e}", xbmc.LOGERROR)
        if self.show_waterfall:
            # Paint immediately from whatever's already in packet_feed,
            # rather than leaving 30 blank bars until the next raw_packet
            # event happens to arrive -- which, on a quiet mesh, could be
            # a genuinely long wait.
            self._generate_waterfall_bars()

    def onAction(self, action):
        try:
            self._dispatch_action(action)
        except Exception:
            xbmc.log(f"[RemoteTerm] onAction handler crashed:\n{traceback.format_exc()}", xbmc.LOGERROR)

    def _dispatch_action(self, action):
        action_id = action.getId()

        # REMOVED: this used to preview a conversation's messages just by
        # scrolling to it (Up/Down highlighting ID_CONVO_LIST), debounced
        # to avoid firing on every keypress. Two separate log captures
        # confirmed it as the trigger for a real focus-corruption bug:
        # loading a conversation from a background thread rebuilds the
        # message list control, and if that happens while Kodi's engine is
        # concurrently processing keyboard input for the (different,
        # still-focused) conversation list, focus ends up somewhere wrong
        # -- observed landing on an unrelated nav-rail icon with zero
        # intervening keypresses. A reactive "detect and restore" guard
        # (_guard_chat_focus) caught and fixed it within about a second
        # both times, but a visible flicker back to the nav rail and back
        # is still a real disruption, and this race can't be fully closed
        # from the addon side -- it's background-thread GUI mutation
        # racing the engine's own input processing. Removing the feature
        # removes the race entirely. Opening a conversation now requires
        # pressing Select/Enter again, same as before this was added.

        # Every content control's onleft/onup/ondown that used to be able
        # to escape to the nav rail (id 9000) now points back at itself
        # instead -- confirmed report: arrowing Left out of a category
        # landed on the rail's default (Dashboard) icon while the
        # category's own content stayed on screen underneath, a mismatch
        # between what looked selected and what was showing. Rather than
        # try to keep that in sync, arrow keys simply can't leave a
        # category's content anymore. Select/Enter on a nav icon is the
        # only way in (already handled by onClick), and Back/Delete
        # (below) is the only way out, back to that same tab's own nav
        # icon, from anywhere inside a category.
        if action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            # Logged explicitly (not just implied by the tab switching)
            # because a report of "randomly kicked to Dashboard while
            # using Chats" needs to distinguish a real Back/Backspace
            # keypress firing from anything else that might cause it --
            # this line is the definitive answer next time it happens.
            xbmc.log(f"[RemoteTerm] Back/Backspace action id={action_id} fired from tab={self.getProperty('tab')} focus={self.getFocusId()}",
                      xbmc.LOGINFO)
            current_tab = self.getProperty("tab")
            current_nav_id = TAB_NAV_ID.get(current_tab)
            if current_tab == TAB_TRENDS:
                # Trends isn't a nav-rail tab of its own -- it's a
                # Dashboard drill-down reached via ID_NAV_TRENDS_BTN, so
                # Back from it always lands on Dashboard, same as its own
                # explicit Back button (ID_TRENDS_BACK).
                self._load_dashboard()
                self._switch_tab(TAB_DASHBOARD, ID_NAV_DASHBOARD)
            elif self.getFocusId() != current_nav_id:
                # THE FIX: confirmed report of getting "stuck" on Dashboard
                # needing a full addon exit to escape -- this branch used
                # to be unconditional self.close() the moment Back was
                # pressed while already on the dashboard tab, regardless
                # of what actually had focus. Since arrow keys can't leave
                # a tab's own content (see the comment above), landing on
                # some Dashboard control (e.g. after using the Trends
                # button) with no nav-rail highlight and Back exiting the
                # whole addon instead of just backing up one step left no
                # graceful way back to another tab. Back now returns focus
                # to the nav rail first; a second Back press from there
                # (where focus genuinely is the rail) exits, matching the
                # comment's original intent of "Back is the only way out"
                # without skipping the actual rail on the way there.
                #
                # Confirmed second real complaint, fixed here: this used
                # to unconditionally re-target ID_NAV_DASHBOARD regardless
                # of which tab the user was actually backing out of --
                # e.g. backing out of Contacts landed you on Dashboard
                # with its icon highlighted, discarding the tab you came
                # from and forcing a second click to get back to it. Now
                # focus returns to that SAME tab's own nav icon (via
                # TAB_NAV_ID), and the tab's content stays exactly as it
                # was -- no reload, no _switch_tab, nothing visibly
                # changes except which rail icon is highlighted.
                #
                # Deliberately compares against THIS tab's specific icon
                # (current_nav_id) rather than "is focus on any nav rail
                # icon at all": confirmed via a real log capture that a
                # background WS event (a live raw_packet arriving while
                # Packets or Analytics was showing -- see
                # _guard_packet_focus/_guard_analytics_focus) can knock
                # focus onto the WRONG icon, e.g. ID_NAV_DASHBOARD, while
                # a completely different tab is still the one actually on
                # screen. Treating that as "already on the rail" made a
                # single Back press exit the whole addon instead of the
                # two it should take. Comparing against the specific
                # expected icon self-corrects that drift back to the
                # right one instead, exactly like a first Back press.
                self.setFocusId(current_nav_id if current_nav_id is not None else ID_NAV_DASHBOARD)
            else:
                # Focus is already on this tab's own rail icon (a second
                # Back press) -- exit the addon, the same "Back is the
                # only way out" behavior that previously applied to
                # Dashboard alone, now uniform across every tab.
                self.close()
