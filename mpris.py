"""
MPRIS D-Bus service for the Audiobook Player.

Exposes org.mpris.MediaPlayer2 and org.mpris.MediaPlayer2.Player so that
mpris-proxy (BlueZ) can forward Bluetooth media-button events (play/pause,
next, previous) to the player.

System requirement on Raspberry Pi:
    sudo apt install python3-dbus python3-gi gir1.2-glib-2.0

mpris-proxy is part of bluez-utils:
    sudo apt install bluez
    mpris-proxy &       # or enable via systemd
"""

import threading
import logging

log = logging.getLogger(__name__)

try:
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib
    DBUS_OK = True
except ImportError:
    DBUS_OK = False
    log.warning("dbus / gi not available – MPRIS disabled")

BUS_NAME      = "org.mpris.MediaPlayer2.audiobookplayer"
OBJECT_PATH   = "/org/mpris/MediaPlayer2"
IFACE_ROOT    = "org.mpris.MediaPlayer2"
IFACE_PLAYER  = "org.mpris.MediaPlayer2.Player"
IFACE_PROPS   = "org.freedesktop.DBus.Properties"


class MprisService(dbus.service.Object if DBUS_OK else object):
    """
    Minimal MPRIS2 service.  Create once, then call:
        service.update_metadata(title, author)   – when a book is loaded
        service.update_status(playing, paused)   – called automatically via poll
    The player callbacks (play/pause/next/prev) are supplied as callables.
    """

    def __init__(self, on_play_pause, on_next, on_previous, on_stop):
        if not DBUS_OK:
            return

        self._on_play_pause = on_play_pause
        self._on_next       = on_next
        self._on_previous   = on_previous
        self._on_stop       = on_stop

        self._playing  = False
        self._paused   = False
        self._title    = ""
        self._artist   = ""
        self._position = 0   # microseconds

        # GLib main loop runs in its own daemon thread
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        try:
            bus      = dbus.SessionBus()
            bus_name = dbus.service.BusName(BUS_NAME, bus)
            super().__init__(bus_name, OBJECT_PATH)
            self._loop   = GLib.MainLoop()
            self._thread = threading.Thread(
                target=self._loop.run, daemon=True, name="mpris-glib"
            )
            self._thread.start()
            log.info("MPRIS service started as %s", BUS_NAME)
        except Exception as exc:
            log.warning("Could not start MPRIS service: %s", exc)

    # ── Public update API ──────────────────────────────────────────────────────

    def update_metadata(self, title: str, artist: str = ""):
        self._title  = title
        self._artist = artist
        self._emit_props_changed(IFACE_PLAYER, ["Metadata"])

    def update_status(self, playing: bool, paused: bool, position_sec: float = 0.0):
        changed = (playing != self._playing) or (paused != self._paused)
        self._playing  = playing
        self._paused   = paused
        self._position = int(position_sec * 1_000_000)
        if changed:
            self._emit_props_changed(IFACE_PLAYER, ["PlaybackStatus", "Position"])

    def _emit_props_changed(self, iface: str, props: list):
        if not DBUS_OK:
            return
        try:
            changed = dbus.Dictionary(
                {p: self._player_props()[p] for p in props if p in self._player_props()},
                signature="sv",
            )
            self.PropertiesChanged(iface, changed, dbus.Array([], signature="s"))
        except Exception:
            pass

    # ── MPRIS root interface ───────────────────────────────────────────────────

    @dbus.service.method(IFACE_ROOT)
    def Raise(self): pass

    @dbus.service.method(IFACE_ROOT)
    def Quit(self): pass

    # ── MPRIS player interface ─────────────────────────────────────────────────

    @dbus.service.method(IFACE_PLAYER)
    def PlayPause(self):
        self._on_play_pause()

    @dbus.service.method(IFACE_PLAYER)
    def Play(self):
        if not self._playing or self._paused:
            self._on_play_pause()

    @dbus.service.method(IFACE_PLAYER)
    def Pause(self):
        if self._playing and not self._paused:
            self._on_play_pause()

    @dbus.service.method(IFACE_PLAYER)
    def Stop(self):
        self._on_stop()

    @dbus.service.method(IFACE_PLAYER)
    def Next(self):
        self._on_next()

    @dbus.service.method(IFACE_PLAYER)
    def Previous(self):
        self._on_previous()

    @dbus.service.method(IFACE_PLAYER, in_signature="x")
    def Seek(self, offset_us: int): pass

    @dbus.service.method(IFACE_PLAYER, in_signature="ox")
    def SetPosition(self, track_id, position_us: int): pass

    @dbus.service.method(IFACE_PLAYER, in_signature="s")
    def OpenUri(self, uri: str): pass

    # ── D-Bus Properties ───────────────────────────────────────────────────────

    @dbus.service.method(IFACE_PROPS, in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        return self._all_props(interface).get(prop, "")

    @dbus.service.method(IFACE_PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self._all_props(interface)

    @dbus.service.method(IFACE_PROPS, in_signature="ssv")
    def Set(self, interface, prop, value): pass

    @dbus.service.signal(IFACE_PROPS, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated): pass

    # ── Property helpers ───────────────────────────────────────────────────────

    def _playback_status(self) -> str:
        if self._playing and not self._paused:
            return "Playing"
        if self._paused:
            return "Paused"
        return "Stopped"

    def _player_props(self) -> dict:
        return {
            "PlaybackStatus": dbus.String(self._playback_status()),
            "LoopStatus":     dbus.String("None"),
            "Rate":           dbus.Double(1.0),
            "Shuffle":        dbus.Boolean(False),
            "Metadata": dbus.Dictionary({
                "mpris:trackid": dbus.ObjectPath(
                    "/org/mpris/MediaPlayer2/CurrentTrack"
                ),
                "xesam:title":  dbus.String(self._title),
                "xesam:artist": dbus.Array([self._artist], signature="s"),
            }, signature="sv"),
            "Volume":        dbus.Double(1.0),
            "Position":      dbus.Int64(self._position),
            "MinimumRate":   dbus.Double(1.0),
            "MaximumRate":   dbus.Double(1.0),
            "CanGoNext":     dbus.Boolean(True),
            "CanGoPrevious": dbus.Boolean(True),
            "CanPlay":       dbus.Boolean(True),
            "CanPause":      dbus.Boolean(True),
            "CanSeek":       dbus.Boolean(False),
            "CanControl":    dbus.Boolean(True),
        }

    def _all_props(self, interface: str) -> dict:
        if interface == IFACE_ROOT:
            return {
                "CanQuit":           dbus.Boolean(False),
                "CanRaise":          dbus.Boolean(False),
                "HasTrackList":      dbus.Boolean(False),
                "Identity":          dbus.String("Audiobook Player"),
                "SupportedUriSchemes": dbus.Array([], signature="s"),
                "SupportedMimeTypes":  dbus.Array([], signature="s"),
            }
        if interface == IFACE_PLAYER:
            return self._player_props()
        return {}


# ── Null object when D-Bus is unavailable ──────────────────────────────────────

class _NullMpris:
    def update_metadata(self, *a, **kw): pass
    def update_status(self, *a, **kw):   pass


def create_service(on_play_pause, on_next, on_previous, on_stop):
    """Return a live MprisService or a silent no-op if D-Bus is unavailable."""
    if DBUS_OK:
        return MprisService(on_play_pause, on_next, on_previous, on_stop)
    return _NullMpris()
