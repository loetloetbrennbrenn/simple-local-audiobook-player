import threading
import time
from typing import Optional, Callable

try:
    import mpv
    MPV_AVAILABLE = True
except ImportError:
    MPV_AVAILABLE = False


class AudiobookPlayer:
    def __init__(self, on_progress: Optional[Callable] = None):
        self._lock = threading.Lock()
        self._player = None
        self._current_book_id: Optional[str] = None
        self._current_files: list = []
        self._current_file_index: int = 0
        self._on_progress = on_progress
        self._progress_thread: Optional[threading.Thread] = None
        self._running = False

        if MPV_AVAILABLE:
            self._init_mpv()

    def _init_mpv(self):
        self._player = mpv.MPV(
            audio_display=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
        )
        self._player.observe_property("time-pos", self._on_time_pos)
        self._player.observe_property("eof-reached", self._on_eof)

    def _on_time_pos(self, name, value):
        if value is not None and self._on_progress:
            self._on_progress(self._current_book_id, self._current_file_index, float(value))

    def _on_eof(self, name, value):
        if value:
            self._next_file()

    def _next_file(self):
        with self._lock:
            next_index = self._current_file_index + 1
            if next_index < len(self._current_files):
                self._current_file_index = next_index
                self._player.play(self._current_files[next_index])

    def play(self, book_id: str, files: list, file_index: int = 0, position: float = 0.0):
        with self._lock:
            self._current_book_id = book_id
            self._current_files = files
            self._current_file_index = file_index

        if not MPV_AVAILABLE:
            return

        self._player.play(files[file_index])
        if position > 0:
            time.sleep(0.3)
            try:
                self._player.seek(position, "absolute")
            except Exception:
                pass

    def pause(self):
        if self._player:
            self._player.pause = not self._player.pause

    def seek(self, seconds: float, mode: str = "absolute"):
        if self._player:
            try:
                self._player.seek(seconds, mode)
            except Exception:
                pass

    def seek_to_file(self, file_index: int, position: float = 0.0):
        with self._lock:
            if file_index < 0 or file_index >= len(self._current_files):
                return
            self._current_file_index = file_index

        if self._player:
            self._player.play(self._current_files[file_index])
            if position > 0:
                time.sleep(0.3)
                try:
                    self._player.seek(position, "absolute")
                except Exception:
                    pass

    def stop(self):
        if self._player:
            self._player.stop()

    @property
    def status(self) -> dict:
        paused = False
        position = 0.0
        duration = 0.0

        if self._player and MPV_AVAILABLE:
            try:
                paused = bool(self._player.pause)
                pos = self._player.time_pos
                dur = self._player.duration
                position = float(pos) if pos is not None else 0.0
                duration = float(dur) if dur is not None else 0.0
            except Exception:
                pass

        return {
            "book_id": self._current_book_id,
            "file_index": self._current_file_index,
            "position": position,
            "duration": duration,
            "paused": paused,
            "playing": self._current_book_id is not None,
            "mpv_available": MPV_AVAILABLE,
        }

    def set_volume(self, volume: int):
        if self._player:
            self._player.volume = max(0, min(100, volume))

    def get_volume(self) -> int:
        if self._player:
            try:
                return int(self._player.volume or 100)
            except Exception:
                pass
        return 100

    def skip_forward(self, seconds: float = 30.0):
        self.seek(seconds, "relative")

    def skip_backward(self, seconds: float = 15.0):
        self.seek(-seconds, "relative")
