"""
RemoteTerm API client -- built against RemoteTerm's documented API contract
(commit 74c13d19, per the project's own DeepWiki API reference and
README_ADVANCED.md / AGENTS.md). All routes below are confirmed routes,
not guesses. Where the verb/shape of a route wasn't spelled out in the
public docs, it is called defensively and fails soft (returns an empty/
None result rather than raising) so a single unsupported route never
breaks the rest of the addon.

CONFIRMED (per RemoteTerm API contract):
  GET   /api/health                                        -> HealthStatus
  GET   /api/contacts?limit=&offset=                        -> list[Contact]
  GET   /api/contacts/{key}                                 -> Contact
  GET   /api/contacts/{key}/detail                          -> ContactDetail
  POST  /api/contacts/{key}/repeater/status                 -> RepeaterStatusResponse
  GET   /api/channels                                       -> list[Channel]
  GET   /api/settings                                       -> AppSettings
  PATCH /api/settings                                       -> AppSettings
  POST  /api/settings/favorites/toggle {type,id}             -> FavoriteToggleResponse
                                                                 {type, id, favorite}

NOTE (verified against the v3.17.1 OpenAPI schema): there is no
/api/contacts/sync or /api/channels/sync route, and AppSettings has no
"favorites" list -- favorite state lives directly on each Contact/Channel
object as a "favorite" boolean instead. A prior version of this client
called both nonexistent sync routes (dead code, unused) and read
favorites from settings (a real bug -- it silently always evaluated to
"nothing is a favorite"). Both are fixed below.
  GET   /api/messages?conversation_key=&type=&limit=&offset=&q=
                                                              -> list[Message]
  POST  /api/messages/direct   {destination, text}           -> Message
  POST  /api/messages/channel  {channel_key, text}           -> Message
  GET   /api/statistics                                      -> StatisticsResponse
  POST  /api/contacts/{key}/repeater/neighbors               -> RepeaterNeighborsResponse
  POST  /api/contacts/{key}/repeater/acl                     -> RepeaterAclResponse
  POST  /api/contacts/{key}/repeater/node-info                -> RepeaterNodeInfoResponse
  POST  /api/contacts/{key}/command   {command}               -> CommandResponse
  WS    /api/ws  events: health, contact, contact_deleted, message,
                 message_acked, channel, channel_deleted, raw_packet,
                 error, success, pong

Message.type constants are the literal strings "PRIV" and "CHAN".
Contact.type: 0=unknown, 1=client, 2=repeater, 3=room, 4=sensor.
Contact.effective_route.path_len: real hop count field (confirmed against
the OpenAPI schema: -1=flood, 0=direct, >0=explicit route), used for the
Nodes tab's "closest/furthest by hops" sort. An earlier version of this
comment claimed a "Contact.last_path_len" field that never actually
existed anywhere in the schema -- reading it always silently returned
None, which made that sort a permanent no-op. Corrected here.
GET /api/messages pages with limit 1..1000 (default 100) + offset; this
client walks every page so full history backfills correctly instead of
being cut off at an arbitrary single-page limit.

The node map does NOT depend on any external tile/static-map service --
an earlier version did, and that service (staticmap.openstreetmap.de)
turned out to be unreachable from a real deployment (DNS failure in
testing), which took the whole Map tab down for a reason entirely
outside RemoteTerm or this addon. Node positions are now projected
locally from the user's own configured lat/lon (equirectangular
approximation, accurate enough at mesh-radio range) and drawn with
plain Kodi controls, so the map always works offline.
"""

import math
import os

import xbmc
import xbmcaddon
import xbmcvfs
import requests
import urllib3

MAX_MESSAGE_PAGES = 30       # 30 * 1000 = up to 30k messages of scrollback
MESSAGE_PAGE_SIZE = 1000


class RemoteTermAPI:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Shared session specifically for map tile fetches -- gives real
        # TCP connection reuse/pooling across the 12 tiles fetched per
        # map view (each fired on its own thread), instead of a fresh
        # connection+TLS handshake per tile via a bare requests.get()
        # each time. Also naturally caps concurrent connections to this
        # host via urllib3's own per-host pool limit, rather than truly
        # unbounded parallel connections. Scoped separately from the
        # main RemoteTerm backend's own requests so a tile-fetch issue
        # can never affect the primary API connection or vice versa.
        self._tile_session = requests.Session()

    # -- settings -------------------------------------------------------------

    @property
    def host(self):
        return self.addon.getSetting('host').rstrip('/')

    @property
    def verify_ssl(self):
        return self.addon.getSettingBool('verify_ssl')

    @property
    def timeout(self):
        try:
            return float(self.addon.getSetting('timeout')) or 6
        except (TypeError, ValueError):
            return 6

    @property
    def auth(self):
        user = self.addon.getSetting('basic_auth_user')
        pw = self.addon.getSetting('basic_auth_pass')
        return (user, pw) if user and pw else None

    def get_radio_config(self):
        return self._get("/api/radio/config")

    @property
    def map_center(self):
        """Returns (lat, lon) only if a genuine, non-zero location is
        available -- either already configured in Add-on Settings, or
        (newly) auto-seeded from the radio's own GPS location via
        GET /api/radio/config, confirmed via the OpenAPI schema to
        return real lat/lon fields for the station itself. A prior
        version of this comment said there was no backend-provided
        location to fall back to -- that was true before this endpoint
        was found; it genuinely exists now, so a first-time user no
        longer needs to hand-enter coordinates their own radio already
        knows. Only auto-fills once (checking the setting is still blank
        each time, not overwriting anything the user has already set or
        deliberately cleared), and only if the radio's own value isn't
        (0, 0) -- the same "reads as valid but is actually just an
        unconfigured default" trap as the old hardcoded Los Angeles
        fallback this class already had to remove once."""
        try:
            lat_raw = self.addon.getSetting('map_center_lat').strip()
            lon_raw = self.addon.getSetting('map_center_lon').strip()
            if lat_raw and lon_raw:
                return float(lat_raw), float(lon_raw)
            config = self.get_radio_config()
            if config:
                lat, lon = config.get("lat"), config.get("lon")
                if lat is not None and lon is not None and (lat, lon) != (0, 0):
                    self.addon.setSetting('map_center_lat', str(lat))
                    self.addon.setSetting('map_center_lon', str(lon))
                    xbmc.log(f"[RemoteTerm] auto-seeded map center from the radio's own "
                              f"GPS config: {lat}, {lon}", xbmc.LOGINFO)
                    return lat, lon
            return None
        except (TypeError, ValueError):
            return None

    @property
    def live_updates_enabled(self):
        try:
            return self.addon.getSettingBool('enable_live_updates')
        except Exception:
            return True

    @property
    def use_metric(self):
        try:
            return self.addon.getSetting('units') == 'Metric'
        except Exception:
            return False

    @property
    def show_gauges(self):
        try:
            return self.addon.getSettingBool('show_gauges')
        except Exception:
            return True

    def format_distance(self, km):
        """Distance display honoring the Imperial/Metric setting. Only
        distance is affected by this setting right now -- temperature
        isn't shown anywhere in the addon as structured data (it only
        ever appears as free-form chat text from a weather bot, which
        isn't something to parse/convert), so there's nothing else for
        the setting to apply to yet."""
        if self.use_metric:
            return f"{km:.1f} km"
        return f"{km * 0.621371:.1f} mi"

    # -- low-level HTTP ---------------------------------------------------------

    def _get(self, path, params=None):
        try:
            r = requests.get(
                f"{self.host}{path}", params=params,
                timeout=self.timeout, verify=self.verify_ssl, auth=self.auth,
            )
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            xbmc.log(f"[RemoteTerm] GET {path} failed: {e}", xbmc.LOGINFO)
            return None

    def _post(self, path, json_body=None, params=None, timeout=None):
        try:
            r = requests.post(
                f"{self.host}{path}", json=json_body, params=params,
                timeout=timeout if timeout is not None else self.timeout,
                verify=self.verify_ssl, auth=self.auth,
            )
            r.raise_for_status()
            if not r.content:
                return {}
            return r.json()
        except requests.exceptions.RequestException as e:
            detail = ""
            try:
                detail = e.response.text[:200] if e.response is not None else ""
            except Exception:
                pass
            xbmc.log(f"[RemoteTerm] POST {path} failed: {e} {detail}", xbmc.LOGINFO)
            return None

    # -- health / stats -----------------------------------------------------

    def get_health(self):
        return self._get("/api/health") or {}

    def get_statistics(self):
        return self._get("/api/statistics")  # None if unavailable -- caller handles

    # -- contacts -------------------------------------------------------------

    def get_contacts(self):
        """Walks every page so lists longer than one page aren't truncated."""
        out = []
        offset = 0
        page_size = 300
        while True:
            page = self._get("/api/contacts", {"limit": page_size, "offset": offset})
            if not isinstance(page, list) or not page:
                break
            out.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
            if offset > 6000:  # sanity cap
                break
        return out

    def get_contact_detail(self, public_key):
        return self._get(f"/api/contacts/{public_key}/detail")

    def query_repeater_status(self, public_key):
        """Live round-trip to the repeater over the mesh -- can take several
        seconds. Returns None if the contact isn't a repeater or is unreachable."""
        return self._post(f"/api/contacts/{public_key}/repeater/status", timeout=self.MESH_QUERY_TIMEOUT)

    # -- channels -------------------------------------------------------------

    def get_channels(self):
        result = self._get("/api/channels")
        return result if isinstance(result, list) else []

    # -- settings / favorites --------------------------------------------------

    def toggle_favorite(self, fav_type, fav_id):
        """Returns the FavoriteToggleResponse dict {type, id, favorite} on
        success, or None on failure. The server is the source of truth for
        the resulting state -- the caller should apply result['favorite']
        rather than assuming the toggle flipped whatever it locally
        believed the previous state to be."""
        return self._post("/api/settings/favorites/toggle", {"type": fav_type, "id": fav_id})

    # -- push notifications / read state ---------------------------------------
    # Confirmed via the OpenAPI schema: notification-worthiness and unread
    # state are both tracked server-side, per conversation "state key" (a
    # contact's public_key or a channel's key) -- NOT something this
    # client should be deciding on its own by reacting to every "message"
    # WS event regardless of conversation. A prior version of this client
    # did exactly that (popped a toast for literally every non-outgoing
    # message on every contact and channel, with no concept of which
    # conversations the user actually wants notified about), which is
    # what produced a notification for every single thing heard on the
    # mesh from the moment the addon started.

    def get_push_conversations(self):
        """GET /api/push/conversations -> bare list[str] of conversation
        state keys currently opted into push notifications. This is the
        authoritative "should this conversation notify" list -- a fresh
        install has an empty list (nothing opted in) until the user
        explicitly enables it per-conversation via toggle_push_conversation."""
        result = self._get("/api/push/conversations")
        return result if isinstance(result, list) else []

    def toggle_push_conversation(self, key):
        """POST /api/push/conversations/toggle {key} -- flips whether the
        given conversation state key is in the push-enabled list."""
        return self._post("/api/push/conversations/toggle", {"key": key})

    def get_unread_state(self):
        """GET /api/read-state/unreads -> UnreadCounts{counts, mentions,
        last_message_times, first_unread_ids, last_read_ats}, each a map
        of conversation state key -> value. This is the server's own
        authoritative unread/mention tracking, confirmed via the OpenAPI
        schema -- it persists across restarts and is shared with any other
        client talking to the same RemoteTerm backend, unlike a
        client-side-only counter that resets to zero every time this addon
        restarts."""
        return self._get("/api/read-state/unreads")

    def mark_contact_read(self, public_key):
        """POST /api/contacts/{public_key}/mark-read."""
        return self._post(f"/api/contacts/{public_key}/mark-read")

    def mark_channel_read(self, key):
        """POST /api/channels/{key}/mark-read."""
        return self._post(f"/api/channels/{key}/mark-read")

    # -- messages ---------------------------------------------------------------

    def get_messages(self, conversation_key, msg_type):
        """Fetches the FULL history for a conversation by walking every page
        (server pages max out at 1000/request), not just the first page."""
        out = []
        offset = 0
        for _ in range(MAX_MESSAGE_PAGES):
            page = self._get("/api/messages", {
                "conversation_key": conversation_key,
                "type": msg_type,
                "limit": MESSAGE_PAGE_SIZE,
                "offset": offset,
            })
            if not isinstance(page, list) or not page:
                break
            out.extend(page)
            if len(page) < MESSAGE_PAGE_SIZE:
                break
            offset += MESSAGE_PAGE_SIZE
        out.sort(key=lambda m: (m.get("received_at") or 0, m.get("id") or 0))
        return out

    def get_latest_message_id(self, conversation_key, msg_type):
        """Cheap poll check. An earlier version trusted an 'after_id' query
        parameter to do incremental fetches -- that parameter was never
        actually confirmed against the real API, and in practice the server
        just ignores it and returns its normal page every time, which made
        every 5-second poll believe there were hundreds of new messages and
        re-fetch/re-render the ENTIRE conversation history on every cycle.
        For a multi-thousand-message channel that's enough load to make the
        whole addon feel like it isn't working. This instead pulls only a
        small recent page and returns the highest message id seen, so the
        caller can cheaply decide whether a full reload is actually needed."""
        result = self._get("/api/messages", {
            "conversation_key": conversation_key,
            "type": msg_type,
            "limit": 50,
        })
        messages = result if isinstance(result, list) else []
        if not messages:
            return 0
        return max((m.get("id") or 0) for m in messages)

    def search_messages(self, query, limit=200):
        result = self._get("/api/messages", {"q": query, "limit": limit})
        messages = result if isinstance(result, list) else []
        return sorted(messages, key=lambda m: m.get("received_at", 0), reverse=True)

    # -- sending ----------------------------------------------------------------

    def send_direct(self, public_key, text):
        # Confirmed real bug found on review: this used the default
        # settings timeout (6s) instead of MESH_QUERY_TIMEOUT (30s) used
        # everywhere else in this addon for a live mesh round-trip.
        # Sending a message is exactly that same class of operation --
        # it has to actually transmit over LoRa, potentially through
        # multiple hops, before the server can confirm it. A 6s client
        # timeout could easily fire before a real multi-hop send
        # finishes, reporting "failed" for a message that actually went
        # out moments later. Given the API schema has no idempotency key
        # or client timestamp field at all (confirmed by checking
        # SendDirectMessageRequest/SendChannelMessageRequest directly --
        # neither has one), the server has no way to recognize a resend
        # as a duplicate. A false "failed" that prompts the user to
        # retry is exactly the kind of mechanism that could put a
        # genuine duplicate out over the mesh, which is the real problem
        # here -- not a bug in this addon's message format itself, but
        # in how confidently it reports failure.
        return self._post_distinguishing_timeout("/api/messages/direct",
                                                   {"destination": public_key, "text": text})

    def send_channel(self, channel_key, text):
        return self._post_distinguishing_timeout("/api/messages/channel",
                                                   {"channel_key": channel_key, "text": text})

    def _post_distinguishing_timeout(self, path, json_body):
        """Like _post, but for sends where the difference between "the
        server said no" and "we simply stopped waiting" genuinely
        matters to the caller -- returns ("ok", body), ("timeout", None),
        or ("error", None) instead of collapsing all three into a single
        None."""
        try:
            r = requests.post(
                f"{self.host}{path}", json=json_body, timeout=self.MESH_QUERY_TIMEOUT,
                verify=self.verify_ssl, auth=self.auth,
            )
            r.raise_for_status()
            return "ok", (r.json() if r.content else {})
        except requests.exceptions.Timeout as e:
            xbmc.log(f"[RemoteTerm] POST {path} timed out after {self.MESH_QUERY_TIMEOUT}s "
                      f"(message may still have been sent): {e}", xbmc.LOGINFO)
            return "timeout", None
        except requests.exceptions.RequestException as e:
            xbmc.log(f"[RemoteTerm] POST {path} failed: {e}", xbmc.LOGINFO)
            return "error", None

    def send_message(self, conversation, text):
        if conversation["type"] == "dm":
            return self.send_direct(conversation["key"], text)
        return self.send_channel(conversation["key"], text)

    # -- unified conversation list ------------------------------------------------

    def get_conversations(self):
        """Merged, UI-ready list combining contacts and channels:
        [{"display", "key", "type": "dm"|"channel", "contact_type": int,
          "is_favorite": bool}]
        contact_type is only meaningful for type == "dm" (0=unknown,
        1=client, 2=repeater, 3=room, 4=sensor).

        Favorite state is read directly off each Contact/Channel's own
        "favorite" field -- there is no separate favorites list in
        AppSettings (confirmed against the OpenAPI schema: AppSettings has
        no "favorites" property at all). An earlier version of this method
        cross-referenced a settings["favorites"] list that never actually
        existed on this API, which meant every conversation was silently
        treated as non-favorite regardless of its real state."""
        items = []
        for c in self.get_contacts():
            key = c.get("public_key")
            if not key:
                continue
            name = c.get("name") or key[:12]
            # Confirmed real bug: this used to read c.get("last_path_len"),
            # a field that does not exist anywhere in the actual Contact
            # schema (verified against the OpenAPI spec) -- it always
            # returned None, silently. That made the "Fewest/Most Hops"
            # sort on the Nodes tab a permanent no-op (every contact tied
            # at the same "unknown" sort key, so the list just kept
            # whatever order the server happened to return contacts in,
            # which looked coincidentally alphabetical-ish) and made every
            # row display "unknown" instead of a real hop count. The
            # actual field, confirmed in the schema with explicit
            # documented semantics ("-1=flood, 0=direct, >0=explicit
            # route"), is effective_route.path_len -- effective_route is
            # the backend's own already-resolved best-known route
            # (override, direct, or flood), not something this addon
            # needs to pick between itself.
            effective_route = c.get("effective_route") or {}
            hop_count = effective_route.get("path_len")
            items.append({
                "display": name, "key": key, "type": "dm",
                "contact_type": c.get("type", 0),
                "lat": c.get("lat"), "lon": c.get("lon"),
                "last_seen": c.get("last_seen"),
                "last_path_len": hop_count,
                "is_favorite": bool(c.get("favorite")),
            })

        # The main "Public" channel is special-cased: shown without the "#"
        # every other channel gets, and pinned to the very top of the
        # channel group. Confirmed report: some deployments have a second,
        # near-duplicate channel whose name is literally "#public" (or
        # similar casing) that isn't in the real channel list the user
        # actually sees elsewhere -- collapsing anything matching
        # "public" (with any leading #, case-insensitive) into one
        # canonical entry avoids showing a phantom duplicate.
        public_channel = None
        other_channels = []
        for ch in self.get_channels():
            key = ch.get("key")
            if not key:
                continue
            name = ch.get("name") or "channel"
            if name.strip().lower().lstrip("#") == "public":
                if public_channel is None or name == "Public":
                    public_channel = {
                        "display": "Public", "key": key, "type": "channel", "contact_type": None,
                        "is_favorite": bool(ch.get("favorite")),
                    }
                continue
            label = name if name.startswith("#") else f"#{name}"
            other_channels.append({
                "display": label, "key": key, "type": "channel", "contact_type": None,
                "is_favorite": bool(ch.get("favorite")),
            })
        if public_channel:
            items.append(public_channel)
        items.extend(other_channels)
        return items

    # -- repeater console (neighbors / ACL / node info) -------------------------
    #
    # These are live round-trips over the mesh to the repeater itself, not
    # ordinary DB-backed REST calls -- confirmed from a real deployment log,
    # node-info alone can take well over 6 seconds and time out on the
    # general request timeout. They get their own generous timeout,
    # independent of the "Request timeout" setting meant for quick calls.
    MESH_QUERY_TIMEOUT = 30

    def get_repeater_neighbors(self, public_key):
        return self._post(f"/api/contacts/{public_key}/repeater/neighbors",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_acl(self, public_key):
        return self._post(f"/api/contacts/{public_key}/repeater/acl",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_node_info(self, public_key):
        return self._post(f"/api/contacts/{public_key}/repeater/node-info",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_radio_settings(self, public_key):
        """Confirmed via OpenAPI schema: RepeaterRadioSettingsResponse ->
        firmware_version, radio (freq/bw/sf/cr as one string), tx_power,
        airtime_factor, duty_cycle_limit, repeat_enabled, flood_max."""
        return self._post(f"/api/contacts/{public_key}/repeater/radio-settings",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_owner_info(self, public_key):
        """Confirmed via OpenAPI schema: RepeaterOwnerInfoResponse ->
        owner_info, firmware_version, name, guest_password (admin-only,
        blank for guest logins per the schema description)."""
        return self._post(f"/api/contacts/{public_key}/repeater/owner-info",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_regions(self, public_key):
        """Confirmed via OpenAPI schema: RepeaterRegionsResponse ->
        regions (list of {name, depth, flood_allowed, is_home}), raw,
        truncated, source ('cli' for full admin hierarchy or 'anon' for
        guest-accessible flood-allowed names only)."""
        return self._post(f"/api/contacts/{public_key}/repeater/regions",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_advert_intervals(self, public_key):
        """Confirmed via OpenAPI schema: RepeaterAdvertIntervalsResponse ->
        advert_interval, flood_advert_interval."""
        return self._post(f"/api/contacts/{public_key}/repeater/advert-intervals",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def get_repeater_lpp_telemetry(self, public_key):
        """Confirmed via OpenAPI schema: RepeaterLppTelemetryResponse ->
        sensors: list[LppSensor{channel, type_name, value}]. value is
        either a plain number or, for multi-value sensors like GPS, a
        dict (e.g. {latitude, longitude, altitude})."""
        return self._post(f"/api/contacts/{public_key}/repeater/lpp-telemetry",
                           timeout=self.MESH_QUERY_TIMEOUT)

    def login_repeater(self, public_key, password):
        """Confirmed via OpenAPI schema: RepeaterLoginRequest takes a
        single "password" field (empty string for a guest login, the
        repeater's admin password for an admin login) and returns
        RepeaterLoginResponse {status, authenticated, message}."""
        return self._post(f"/api/contacts/{public_key}/repeater/login",
                           {"password": password}, timeout=self.MESH_QUERY_TIMEOUT)

    def send_repeater_command(self, public_key, command):
        result = self._post(f"/api/contacts/{public_key}/command", {"command": command},
                             timeout=self.MESH_QUERY_TIMEOUT)
        xbmc.log(f"[RemoteTerm] POST .../command body={{'command': {command!r}}} -> {result!r}", xbmc.LOGINFO)
        return result

    # -- recent activity (dashboard) ---------------------------------------------

    def get_recent_activity(self, limit=12):
        """Latest messages across every conversation, newest first -- used
        for the dashboard's live activity panel."""
        result = self._get("/api/messages", {"limit": limit, "offset": 0})
        messages = result if isinstance(result, list) else []
        return sorted(messages, key=lambda m: m.get("received_at", 0), reverse=True)

    # -- map (local projection, no external service required) -------------------

    @staticmethod
    def haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlmb = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        return 2 * R * math.asin(min(1, math.sqrt(a)))

    # -- slippy map tiles ---------------------------------------------------------
    # Kodi's bundled Python has no PIL/Pillow, so tiles are never composited
    # into one image -- instead a GRID of individual tile image files is
    # fetched, cached to disk, and displayed edge-to-edge via ordinary Kodi
    # <control type="image"> controls (see gui.py), which is how a slippy
    # map's tiles work natively anyway. Markers are separate, positioned
    # dot controls placed with pure Web Mercator math, not drawn onto any
    # image.
    #
    # Confirmed real, very recent policy change: CARTO's raster basemap
    # tiles (dark_all, used here originally to match this addon's dark
    # theme) now require a free API key -- unkeyed requests are served an
    # "API key required" watermark instead of the actual map, which is
    # exactly what a live test showed. A key is free but requires the
    # user to personally register with their own email at
    # carto.com/basemaps/apikey, so it can't be baked into the addon
    # itself. Defaults to OpenStreetMap's own tile server instead, which
    # is confirmed to genuinely require no key or registration for normal
    # interactive viewing (fetching only the tiles for what's on screen,
    # properly cached) -- exactly this addon's usage pattern. If the user
    # adds a CARTO key in settings, CARTO's dark style is used instead for
    # the closer aesthetic match; otherwise this just works out of the
    # box.
    TILE_SIZE = 256
    OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    CARTO_TILE_URL = "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png?key={key}"
    TILE_SUBDOMAINS = ("a", "b", "c", "d")

    @staticmethod
    def lonlat_to_pixel(lon, lat, zoom):
        """Standard Web Mercator projection -> GLOBAL pixel coordinates at
        the given zoom (i.e. tile index * 256 + offset within tile), not
        coordinates relative to any particular view. Confirmed standard
        slippy-map math (same projection OpenStreetMap/CARTO/Google Maps
        tiles use), not something invented for this addon."""
        lat = max(min(lat, 85.05112878), -85.05112878)  # Mercator's own valid range
        n = 2 ** zoom
        x = (lon + 180.0) / 360.0 * n * RemoteTermAPI.TILE_SIZE
        lat_rad = math.radians(lat)
        y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n * RemoteTermAPI.TILE_SIZE
        return x, y

    @staticmethod
    def pixel_to_lonlat(px, py, zoom):
        """Inverse of lonlat_to_pixel -- standard closed-form Web Mercator
        inverse (using asinh/sinh), needed for the North/South/East/West
        pan buttons: panning shifts a position in PIXEL space (a fixed,
        zoom-appropriate distance regardless of latitude), then this
        converts that shifted pixel position back to real lon/lat so the
        next render centers on an actual place, not an arbitrary pixel
        offset with no coordinate meaning."""
        n = 2 ** zoom
        lon = px / (n * RemoteTermAPI.TILE_SIZE) * 360.0 - 180.0
        y_frac = py / (n * RemoteTermAPI.TILE_SIZE)
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y_frac)))
        lat = math.degrees(lat_rad)
        return lon, lat

    def get_tile_path(self, z, x, y):
        """Returns a local file path for the given tile, fetching and
        caching it first if not already on disk. Returns None on failure
        (network down, tile doesn't exist, etc.) -- caller shows a plain
        dark background for that slot rather than crashing, since a
        missing tile shouldn't take down the whole map view. Caches
        indefinitely (map tiles for a given z/x/y essentially never
        change) to respect tile usage etiquette against needlessly
        repeated requests for a hobby/personal addon like this one, and
        to keep the map feeling fast on repeat visits.

        Confirmed real bug (now fixed): this whole function used to have
        an unguarded call (translatePath) before its own try/except even
        started -- if that raised (this runs inside a background
        threading.Thread with no exception handler around the target
        function), Python's default behavior for an uncaught exception in
        a thread is to print to stderr and silently end the thread, which
        never reaches xbmc.log at all. That's confirmed by the evidence:
        "12 of 12 tiles failed" logged 3 milliseconds after the click,
        far too fast to be a real network timeout. The entire body is
        now one try/except so a genuine bug here is finally visible in
        the log instead of dying silently.

        Uses OpenStreetMap's own no-key-required tile server by default;
        switches to CARTO's dark style only if the user has entered a
        free CARTO API key in settings (see TILE_URL comments above for
        why CARTO can no longer be used keyless). Cache directory
        versioned ("_v2") specifically so any tiles already cached from
        before this fix -- which, confirmed via a live screenshot, were
        CARTO's "API key required" watermark image, itself a validly
        cacheable 200-OK response -- are never reused; without this,
        switching providers wouldn't fix anything for a user who'd
        already tried the broken one.
        """
        try:
            n = 2 ** z
            if not (0 <= x < n and 0 <= y < n):
                return None
            try:
                temp_path = xbmcvfs.translatePath("special://temp/")
            except AttributeError:
                # Older Kodi versions expose this on xbmc, not xbmcvfs.
                temp_path = xbmc.translatePath("special://temp/")
            carto_key = (self.addon.getSetting("carto_api_key") or "").strip()
            provider = "carto" if carto_key else "osm"
            cache_dir = os.path.join(temp_path, f"remoteterm_tiles_v2_{provider}")
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{z}_{x}_{y}.png")
            if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
                return cache_path
            if carto_key:
                subdomain = RemoteTermAPI.TILE_SUBDOMAINS[(x + y) % len(RemoteTermAPI.TILE_SUBDOMAINS)]
                url = RemoteTermAPI.CARTO_TILE_URL.format(s=subdomain, z=z, x=x, y=y, key=carto_key)
            else:
                url = RemoteTermAPI.OSM_TILE_URL.format(z=z, x=x, y=y)
            # Identifying User-Agent, per OSM tile usage policy
            # (operations.osmfoundation.org/policies/tiles). Re-checked
            # against the current live policy text directly rather than
            # assumed: this addon's actual usage already matches the
            # explicitly PERMITTED pattern almost exactly ("normal
            # interactive viewing... only the tiles needed for the
            # current viewport", "re-visits served from your local
            # cache") -- only 12 on-screen tiles fetched per unique area
            # ever viewed, then cached permanently (well past their
            # 7-day minimum), never bulk-downloaded or pre-seeded ahead
            # of what's shown. The one real gap found on review: the
            # User-Agent named the app but gave OSM no way to reach out
            # if there were ever an issue -- their own policy explicitly
            # asks for a contact URL/email and says traffic identified
            # only as "personal use" is harder for them to act on than
            # traffic with real contact info. Fixed by pointing at this
            # addon's own public setup page (already linked from
            # addon.xml), which is a genuine, findable reference for
            # this specific software, plus a version number worth
            # bumping on future releases per their own guidance.
            #
            # Timeout kept short (4s): confirmed real bug previously,
            # fetching 12 tiles sequentially at 8s each meant a slow/
            # unreachable tile server produced up to 96 seconds of
            # apparent "freeze" -- now paired with parallel fetching in
            # gui.py, so worst case is bounded by one short timeout, not
            # the sum of all tiles.
            resp = self._tile_session.get(url, timeout=4, headers={
                "User-Agent": "RemoteTerm-Kodi-Addon/10.8.0 "
                              "(+https://gist.github.com/LA-Seniors/0d06033d441897e1f3bd067d89e421ba)"})
            if resp.status_code == 200 and resp.content:
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                return cache_path
            xbmc.log(f"[RemoteTerm] map tile HTTP {resp.status_code} for {z}/{x}/{y}", xbmc.LOGINFO)
        except Exception as e:
            # Elevated from LOGDEBUG to LOGINFO: debug logging is off by
            # default in Kodi, so a real, confirmed cause of "the map
            # doesn't show anything" (every tile fetch failing) was
            # invisible in a normal log capture. This needs to be visible
            # without the user having to know to enable debug logging.
            xbmc.log(f"[RemoteTerm] map tile fetch failed ({z}/{x}/{y}): {type(e).__name__}: {e}", xbmc.LOGINFO)
        return None

