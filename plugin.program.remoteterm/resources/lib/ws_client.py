"""
Minimal WebSocket client (stdlib only -- socket/ssl/base64/hashlib/struct)
for RemoteTerm's real-time event feed at /api/ws.

RemoteTerm has no REST endpoint for historical raw packets or for pushing
new messages to an already-open conversation -- both are WebSocket-only
(events: health, contact, contact_deleted, message, message_acked,
channel, channel_deleted, raw_packet, error, success, pong). Without this
client the Packet Feed tab has nothing to show and open conversations
would never learn about replies without a manual refresh.

This client is intentionally defensive: any failure just triggers a
backoff-and-reconnect rather than crashing the addon, and the GUI treats
"no live connection yet" as a normal, recoverable state.
"""

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import threading
import time
from urllib.parse import urlparse

import xbmc

_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class SimpleWebSocket:
    """Just enough RFC6455 client to read a JSON event stream and keep it
    alive with pings. Not a general-purpose WS implementation."""

    def __init__(self, url, verify_ssl=True, auth=None, timeout=10, read_timeout=None):
        self.url = url
        self.verify_ssl = verify_ssl
        self.auth = auth
        self.timeout = timeout
        # Deliberately separate from `timeout` (which governs the initial
        # TCP connect + HTTP handshake, where a generous value is what you
        # want on a slower network): this one bounds how long recv_events()
        # can sit blocked in a single recv() once the connection is live,
        # so that RemoteTermEventStream.stop()'s force-close (see close()
        # below) is never more than one read_timeout away from actually
        # unblocking the thread. Defaults to `timeout` if not given.
        self.read_timeout = read_timeout if read_timeout is not None else timeout
        self.sock = None
        self._buffer = b""

    def connect(self):
        parsed = urlparse(self.url)
        is_tls = parsed.scheme == "wss"
        host = parsed.hostname
        port = parsed.port or (443 if is_tls else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        raw_sock = socket.create_connection((host, port), timeout=self.timeout)
        if is_tls:
            ctx = ssl.create_default_context()
            if not self.verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=host)
        else:
            self.sock = raw_sock

        key = base64.b64encode(os.urandom(16)).decode()
        headers = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}:{port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        if self.auth:
            token = base64.b64encode(f"{self.auth[0]}:{self.auth[1]}".encode()).decode()
            headers.append(f"Authorization: Basic {token}")
        headers.append("\r\n")
        self.sock.sendall("\r\n".join(headers).encode())

        response = self._recv_handshake_response()
        if " 101 " not in response.split("\r\n", 1)[0]:
            raise ConnectionError(f"WebSocket handshake failed: {response.splitlines()[:1]}")

        expected_accept = base64.b64encode(
            hashlib.sha1((key + _MAGIC).encode()).digest()
        ).decode()
        if expected_accept not in response:
            raise ConnectionError("WebSocket handshake accept key mismatch")

        self.sock.settimeout(self.read_timeout)

    def _recv_handshake_response(self):
        data = b""
        self.sock.settimeout(self.timeout)
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", errors="replace")

    def send_text(self, text):
        payload = text.encode("utf-8")
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        length = len(payload)
        header = bytearray()
        header.append(0x80 | 0x1)  # FIN + text opcode
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        self.sock.sendall(bytes(header) + mask + masked)

    def _send_pong(self, payload=b""):
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        header = bytearray([0x80 | 0xA, 0x80 | len(payload)])
        self.sock.sendall(bytes(header) + mask + masked)

    def recv_events(self):
        """Generator yielding decoded JSON payloads (dicts) as text frames
        arrive. Handles ping/pong and close frames transparently.

        A read timeout here means "nothing arrived in time", not "the
        connection is dead" -- a quiet mesh network can easily go tens of
        seconds between events. Only a real socket error/close ends the
        generator; a plain timeout just loops back and waits again, and
        yields None once per timeout so the caller can use the moment to
        send a keepalive ping without believing the stream ended."""
        self.sock.settimeout(self.read_timeout)
        while True:
            frame, timed_out = self._read_frame()
            if timed_out:
                yield None
                continue
            if frame is None:
                return
            opcode, payload = frame
            if opcode == 0x8:  # close
                return
            if opcode == 0x9:  # ping
                self._send_pong(payload)
                continue
            if opcode == 0xA:  # pong
                continue
            if opcode in (0x1, 0x0):  # text / continuation
                try:
                    text = payload.decode("utf-8", errors="replace")
                    if text:
                        yield json.loads(text)
                except (ValueError, json.JSONDecodeError):
                    continue

    def _read_exact(self, n):
        chunks = []
        remaining = n
        while remaining > 0:
            chunk = self.sock.recv(remaining)
            if not chunk:
                raise ConnectionError("socket closed")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _read_frame(self):
        """Returns (frame_or_None, timed_out). timed_out=True means "try
        again later", distinct from frame=None which means the connection
        actually ended (socket closed / reset)."""
        try:
            head = self._read_exact(2)
        except socket.timeout:
            return None, True
        except (ConnectionError, OSError):
            return None, False
        b0, b1 = head[0], head[1]
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        length = b1 & 0x7F
        if length == 126:
            length = struct.unpack(">H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", self._read_exact(8))[0]
        mask_key = self._read_exact(4) if masked else None
        payload = self._read_exact(length) if length else b""
        if masked and mask_key:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return (opcode, payload), False

    def close(self):
        """Force-closes the underlying socket so a thread blocked in
        recv() wakes up promptly instead of waiting out its full read
        timeout -- this is what lets stop() (below) actually interrupt a
        live read.

        Plain sock.close() is NOT sufficient for this on every platform:
        closing a socket from a different thread than the one blocked in
        recv() on it is only reliably interruptive on Linux. On macOS/BSD
        (confirmed via a real shutdown-hang in this addon's own Kodi log,
        where the read-thread's recv() didn't notice the close() at all
        and the script had to be force-killed after Kodi's 5-second grace
        period), a bare close() from another thread can leave that recv()
        blocked indefinitely -- the fd doesn't actually get torn down
        until the blocked call returns on its own. shutdown(SHUT_RDWR)
        first is the actual cross-platform-correct way to unblock a
        concurrent recv(): it tells the kernel to fail the in-progress
        read immediately, on every platform, independent of when close()
        gets around to freeing the fd."""
        try:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.sock.close()
        except OSError:
            pass


class RemoteTermEventStream:
    """Background-thread wrapper: connects, reconnects with backoff, and
    calls on_event(dict) for every decoded WS event. Also sends a "ping"
    text frame periodically to keep the connection alive through nginx."""

    def __init__(self, host, verify_ssl, auth, on_event, on_status_change=None):
        self.host = host
        self.verify_ssl = verify_ssl
        self.auth = auth
        self.on_event = on_event
        self.on_status_change = on_status_change
        self._stop = threading.Event()
        self._thread = None
        self._current_ws = None
        self.connected = False

    def _ws_url(self):
        if self.host.startswith("https://"):
            return "wss://" + self.host[len("https://"):] + "/api/ws"
        if self.host.startswith("http://"):
            return "ws://" + self.host[len("http://"):] + "/api/ws"
        return "ws://" + self.host + "/api/ws"

    def start(self):
        self._stop.clear()
        self._current_ws = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Sets the stop flag AND force-closes whatever socket is currently
        open. Without the forced close, a thread blocked inside a socket
        read can take up to its full read timeout to notice the flag --
        confirmed in practice: Kodi gave the script 5 seconds to exit and
        had to kill it because this thread was still blocked reading."""
        self._stop.set()
        ws = self._current_ws
        if ws is not None:
            ws.close()

    def _set_connected(self, value):
        if value != self.connected:
            self.connected = value
            if self.on_status_change:
                try:
                    self.on_status_change(value)
                except Exception as e:
                    xbmc.log(f"[RemoteTerm] ws status callback error: {e}", xbmc.LOGDEBUG)

    def _run(self):
        backoff = 3
        attempt = 0
        while not self._stop.is_set():
            attempt += 1
            url = self._ws_url()
            xbmc.log(f"[RemoteTerm] ws attempt #{attempt}: connecting to {url}", xbmc.LOGINFO)
            # timeout=15 for the connect+handshake (unchanged -- a slower
            # network shouldn't spuriously fail the connection attempt).
            # read_timeout=3 is the new, separate backstop for the
            # steady-state read loop -- see SimpleWebSocket.__init__ and
            # .close() for why: it bounds how long a stop() force-close
            # can possibly take to unblock this thread, comfortably under
            # Kodi's 5-second shutdown grace period, regardless of
            # whether shutdown()+close() interrupt a pending recv()
            # instantly on a given platform.
            ws = SimpleWebSocket(url, verify_ssl=self.verify_ssl, auth=self.auth,
                                  timeout=15, read_timeout=3)
            self._current_ws = ws
            try:
                ws.connect()
                xbmc.log("[RemoteTerm] ws handshake OK, live feed connected", xbmc.LOGINFO)
                self._set_connected(True)
                backoff = 3
                last_ping = time.time()
                event_count = 0
                for event in ws.recv_events():
                    if self._stop.is_set():
                        break
                    if event is None:
                        # plain read timeout -- normal on a quiet mesh,
                        # NOT a disconnect. Just fall through to the
                        # keepalive-ping check below and keep waiting.
                        pass
                    else:
                        event_count += 1
                        if event_count <= 3 or event_count % 50 == 0:
                            xbmc.log(f"[RemoteTerm] ws event #{event_count}: type={event.get('type')}", xbmc.LOGINFO)
                        try:
                            self.on_event(event)
                        except Exception as e:
                            xbmc.log(f"[RemoteTerm] ws event handler error: {e}", xbmc.LOGDEBUG)
                    if time.time() - last_ping > 20:
                        try:
                            ws.send_text("ping")
                        except OSError as e:
                            xbmc.log(f"[RemoteTerm] ws ping failed, reconnecting: {e}", xbmc.LOGINFO)
                            break
                        last_ping = time.time()
                xbmc.log(f"[RemoteTerm] ws stream ended after {event_count} event(s)", xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f"[RemoteTerm] ws connect/read failed ({type(e).__name__}): {e}", xbmc.LOGINFO)
            finally:
                ws.close()
                self._set_connected(False)
            if self._stop.is_set():
                return
            xbmc.log(f"[RemoteTerm] ws retrying in {backoff}s", xbmc.LOGINFO)
            self._stop.wait(backoff)
            backoff = min(backoff * 2, 30)
