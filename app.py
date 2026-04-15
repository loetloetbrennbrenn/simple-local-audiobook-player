#!/usr/bin/env python3
"""Raspi Audiobook Player – local Tkinter app."""

import json
import os
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

# make backend utilities importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from library import scan_library, extract_cover_bytes
from player import AudiobookPlayer
from progress import ProgressStore
import mpris as mpris_mod

import tkinter as tk
from tkinter import ttk, filedialog

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ── Config ─────────────────────────────────────────────────────────────────────
_CFG_DIR = Path.home() / ".audiobook_player"
_CFG_FILE = _CFG_DIR / "config.json"

def load_config() -> dict:
    if _CFG_FILE.exists():
        try:
            return json.loads(_CFG_FILE.read_text())
        except Exception:
            pass
    return {"library_path": str(Path.home() / "Audiobooks")}

def save_config(cfg: dict):
    _CFG_DIR.mkdir(parents=True, exist_ok=True)
    _CFG_FILE.write_text(json.dumps(cfg, indent=2))

# ── Palette ────────────────────────────────────────────────────────────────────
BG       = "#0f0f14"
BG2      = "#1a1a26"
BG3      = "#222236"
ACCENT   = "#7c3aed"
ACC2     = "#6d28d9"
TEXT     = "#f0eeff"
TEXT2    = "#9ca3af"
TEXT3    = "#6b7280"
BORDER   = "#2d2d42"

COVER_SZ = 155   # px – cover thumbnail size
CARD_W   = COVER_SZ + 20
CARD_H   = COVER_SZ + 60
PAD      = 10

# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_time(s: float) -> str:
    if not s or s < 0:
        return "0:00"
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

def fmt_dur(s: float) -> str:
    if not s:
        return ""
    h, rem = divmod(int(s), 3600)
    m = rem // 60
    return f"{h}h {m}m" if h else f"{m}m"

def _mk_placeholder(size: int):
    img = Image.new("RGB", (size, size), BG2)
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    d.ellipse([cx-28, cy-28, cx+28, cy+28], outline="#4c1d95", width=3)
    d.ellipse([cx-18, cy-18, cx+18, cy+18], outline="#4c1d95", width=2)
    for dx in (-14, 14):
        d.rectangle([cx+dx-5, cy-12, cx+dx+5, cy+12], fill="#4c1d95")
    return img

def load_cover(folder: str, size: int):
    """Return PIL Image for a book folder (or placeholder)."""
    raw = extract_cover_bytes(folder)
    if raw and PIL_OK:
        try:
            img = Image.open(BytesIO(raw)).convert("RGB")
            img.thumbnail((size, size), Image.LANCZOS)
            bg = Image.new("RGB", (size, size), BG2)
            ox = (size - img.width) // 2
            oy = (size - img.height) // 2
            bg.paste(img, (ox, oy))
            return bg
        except Exception:
            pass
    return _mk_placeholder(size) if PIL_OK else None

# ── Seek canvas ────────────────────────────────────────────────────────────────
class SeekBar(tk.Canvas):
    """Thin horizontal seek bar. Click or drag to seek."""
    def __init__(self, parent, on_seek, height=6, **kw):
        super().__init__(parent, height=height, bg=BG3,
                         highlightthickness=0, cursor="hand2", **kw)
        self._on_seek = on_seek
        self._pct = 0.0
        self._track = self.create_rectangle(0, 0, 0, 0, fill=BORDER, width=0)
        self._fill  = self.create_rectangle(0, 0, 0, 0, fill=ACCENT, width=0)
        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._click)
        self.bind("<B1-Motion>", self._click)

    def set_percent(self, pct: float):
        self._pct = max(0.0, min(1.0, pct))
        self._redraw()

    def _redraw(self, *_):
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 2:
            return
        self.coords(self._track, 0, 0, w, h)
        fill_w = int(w * self._pct) if self._pct > 0 else 0
        self.coords(self._fill, 0, 0, fill_w, h)

    def _click(self, e):
        w = self.winfo_width()
        if w < 1:
            return
        pct = max(0.0, min(1.0, e.x / w))
        self._on_seek(pct)

# ── Settings dialog ─────────────────────────────────────────────────────────────
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_path: str, on_save):
        super().__init__(parent)
        self.title("Einstellungen")
        self.configure(bg=BG2)
        self.resizable(False, False)
        self._on_save = on_save

        tk.Label(self, text="Bibliothekspfad", bg=BG2, fg=TEXT2,
                 font=("sans-serif", 11)).pack(padx=20, pady=(16, 4), anchor="w")

        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x", padx=20)

        self._entry = tk.Entry(row, bg=BG3, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=("sans-serif", 11),
                               highlightthickness=1, highlightbackground=BORDER,
                               highlightcolor=ACCENT)
        self._entry.insert(0, current_path)
        self._entry.pack(side="left", fill="x", expand=True, ipady=6)

        tk.Button(row, text="…", bg=BG3, fg=TEXT, relief="flat",
                  activebackground=ACCENT, activeforeground=TEXT,
                  command=self._browse, padx=8).pack(side="left", padx=(6, 0))

        self._err = tk.Label(self, text="", bg=BG2, fg="#f87171",
                             font=("sans-serif", 10))
        self._err.pack(padx=20, anchor="w")

        btn_row = tk.Frame(self, bg=BG2)
        btn_row.pack(fill="x", padx=20, pady=(8, 16))

        tk.Button(btn_row, text="Abbrechen", bg=BG3, fg=TEXT2, relief="flat",
                  activebackground=BG3, command=self.destroy,
                  padx=12, pady=6).pack(side="right", padx=(8, 0))
        tk.Button(btn_row, text="Speichern & Scannen", bg=ACCENT, fg=TEXT,
                  relief="flat", activebackground=ACC2,
                  command=self._save, padx=12, pady=6).pack(side="right")

        self.transient(parent)
        self.grab_set()
        self.geometry(f"480x150+{parent.winfo_rootx()+60}+{parent.winfo_rooty()+80}")

    def _browse(self):
        path = filedialog.askdirectory(title="Bibliotheksordner wählen",
                                       initialdir=self._entry.get())
        if path:
            self._entry.delete(0, "end")
            self._entry.insert(0, path)

    def _save(self):
        path = self._entry.get().strip()
        if not os.path.isdir(os.path.expanduser(path)):
            self._err.config(text="Ordner nicht gefunden.")
            return
        self._on_save(path)
        self.destroy()

# ── Book card widget ────────────────────────────────────────────────────────────
class BookCard(tk.Frame):
    def __init__(self, parent, book: dict, progress: dict, is_active: bool, on_click):
        super().__init__(parent, bg=BG3 if is_active else BG2,
                         padx=PAD, pady=PAD, cursor="hand2",
                         highlightthickness=2,
                         highlightbackground=ACCENT if is_active else BG2)
        self._book = book
        self._on_click = on_click
        self._cover_photo = None

        # Cover area
        self._cover_label = tk.Label(self, bg=BG2, width=COVER_SZ, height=COVER_SZ)
        self._cover_label.pack()
        self._bind_click(self._cover_label)

        # Title
        title = book["title"]
        if len(title) > 28:
            title = title[:26] + "…"
        tk.Label(self, text=title, bg=BG3 if is_active else BG2,
                 fg=TEXT, font=("sans-serif", 10, "bold"),
                 wraplength=COVER_SZ, justify="left").pack(anchor="w")

        # Author
        if book.get("author"):
            author = book["author"]
            if len(author) > 30:
                author = author[:28] + "…"
            tk.Label(self, text=author, bg=BG3 if is_active else BG2,
                     fg=TEXT2, font=("sans-serif", 9)).pack(anchor="w")

        # Duration + files
        info = f"{book['file_count']} {'Datei' if book['file_count']==1 else 'Dateien'}"
        dur = fmt_dur(book.get("total_duration", 0))
        if dur:
            info += f"  ·  {dur}"
        tk.Label(self, text=info, bg=BG3 if is_active else BG2,
                 fg=TEXT3, font=("sans-serif", 8)).pack(anchor="w")

        # Progress bar
        prog = progress.get(book["id"])
        total = book.get("total_duration", 0)
        if prog and total:
            pct = min(1.0, prog["position"] / total)
            bar_outer = tk.Frame(self, bg=BORDER, height=3)
            bar_outer.pack(fill="x", pady=(4, 0))
            bar_inner = tk.Frame(bar_outer, bg=ACCENT, height=3)
            bar_inner.place(relwidth=pct, relheight=1.0)

        self._bind_click(self)

    def _bind_click(self, w):
        w.bind("<Button-1>", lambda _: self._on_click(self._book))
        for child in w.winfo_children():
            child.bind("<Button-1>", lambda _: self._on_click(self._book))

    def set_cover(self, photo):
        self._cover_photo = photo
        if photo:
            self._cover_label.config(image=photo, width=COVER_SZ, height=COVER_SZ)
        self._cover_label.image = photo

# ── Main application ────────────────────────────────────────────────────────────
class AudiobookApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audiobook Player")
        self.configure(bg=BG)
        self.geometry("1024x700")
        self.minsize(640, 480)

        self._cfg = load_config()
        self._store = ProgressStore()
        self._player = AudiobookPlayer(on_progress=self._on_progress_cb)
        self._mpris = mpris_mod.create_service(
            on_play_pause=self._toggle_pause,
            on_next=self._next_file,
            on_previous=self._prev_file,
            on_stop=self._player.stop,
        )
        self._library: list = []
        self._progress: dict = {}
        self._current_book: dict | None = None
        self._cover_cache: dict = {}
        self._seek_dragging = False
        self._status_pos = 0.0
        self._status_dur = 0.0
        self._status_paused = True
        self._resize_job = None

        self._build_ui()
        self._load_library()
        self._schedule_poll()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<space>", lambda _: self._toggle_pause())
        self.bind("<Left>", lambda _: self._player.skip_backward(15))
        self.bind("<Right>", lambda _: self._player.skip_forward(30))
        self.bind("<Configure>", self._on_resize)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=BG2, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="🎧  Audiobooks", bg=BG2, fg=TEXT,
                 font=("sans-serif", 16, "bold")).pack(side="left", padx=16)
        btn_row = tk.Frame(header, bg=BG2)
        btn_row.pack(side="right", padx=12)
        tk.Button(btn_row, text="⟳ Scannen", bg=BG3, fg=TEXT2, relief="flat",
                  activebackground=ACCENT, activeforeground=TEXT,
                  command=self._rescan, padx=10, pady=4,
                  font=("sans-serif", 10)).pack(side="left", padx=4)
        tk.Button(btn_row, text="⚙", bg=BG3, fg=TEXT2, relief="flat",
                  activebackground=ACCENT, activeforeground=TEXT,
                  command=self._open_settings, padx=10, pady=4,
                  font=("sans-serif", 12)).pack(side="left")

        # Scrollable cover grid
        grid_area = tk.Frame(self, bg=BG)
        grid_area.pack(fill="both", expand=True)

        self._canvas = tk.Canvas(grid_area, bg=BG, highlightthickness=0,
                                 yscrollcommand=lambda *a: self._scrollbar.set(*a))
        self._scrollbar = ttk.Scrollbar(grid_area, orient="vertical",
                                        command=self._canvas.yview)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.bind("<MouseWheel>", self._on_scroll)
        self._canvas.bind("<Button-4>", self._on_scroll)
        self._canvas.bind("<Button-5>", self._on_scroll)

        self._grid_frame = tk.Frame(self._canvas, bg=BG)
        self._grid_win = self._canvas.create_window((0, 0), window=self._grid_frame,
                                                    anchor="nw")
        self._grid_frame.bind("<Configure>", self._on_grid_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Player bar (bottom)
        self._player_bar = tk.Frame(self, bg=BG2, pady=8)
        self._player_bar.pack(fill="x")
        self._build_player_bar(self._player_bar)

    def _build_player_bar(self, bar):
        # Seek bar full width
        self._seekbar = SeekBar(bar, on_seek=self._on_seek_click)
        self._seekbar.pack(fill="x", padx=0, pady=(0, 6))

        content = tk.Frame(bar, bg=BG2)
        content.pack(fill="x", padx=12)

        # Cover thumbnail
        self._pb_cover = tk.Label(content, bg=BG2, width=44, height=44)
        self._pb_cover.pack(side="left", padx=(0, 10))
        self._pb_cover_photo = None

        # Title + time
        info = tk.Frame(content, bg=BG2)
        info.pack(side="left", fill="x", expand=True)
        self._pb_title = tk.Label(info, text="Kein Buch ausgewählt", bg=BG2, fg=TEXT,
                                  font=("sans-serif", 11, "bold"), anchor="w")
        self._pb_title.pack(anchor="w")
        self._pb_time = tk.Label(info, text="", bg=BG2, fg=TEXT2,
                                 font=("sans-serif", 10), anchor="w")
        self._pb_time.pack(anchor="w")

        # Controls
        ctrl = tk.Frame(content, bg=BG2)
        ctrl.pack(side="right")

        def btn(parent, text, cmd, big=False):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=BG2, fg=TEXT, relief="flat",
                          activebackground=ACCENT, activeforeground=TEXT,
                          font=("sans-serif", 13 if big else 11),
                          padx=6, pady=4)
            b.pack(side="left", padx=2)
            return b

        btn(ctrl, "⏮", self._prev_file)
        btn(ctrl, "↩ 15s", lambda: self._player.skip_backward(15))
        self._play_btn = btn(ctrl, "▶", self._toggle_pause, big=True)
        btn(ctrl, "30s ↪", lambda: self._player.skip_forward(30))
        btn(ctrl, "⏭", self._next_file)

        # Volume
        vol_frame = tk.Frame(content, bg=BG2)
        vol_frame.pack(side="right", padx=(0, 16))
        tk.Label(vol_frame, text="🔊", bg=BG2, fg=TEXT2,
                 font=("sans-serif", 11)).pack(side="left")
        self._vol_slider = ttk.Scale(vol_frame, from_=0, to=100,
                                     orient="horizontal", length=80,
                                     command=self._on_volume)
        self._vol_slider.set(80)
        self._vol_slider.pack(side="left")

    # ── Grid ───────────────────────────────────────────────────────────────────

    def _on_grid_configure(self, e):
        canvas_w = getattr(self, "_canvas_w", self._canvas.winfo_width()) or 1
        self._canvas.configure(scrollregion=(0, 0, canvas_w, e.height))

    def _on_canvas_configure(self, e):
        self._canvas_w = e.width
        self._canvas.itemconfig(self._grid_win, width=e.width)
        self._on_resize()

    def _on_scroll(self, e):
        if e.num == 4 or e.delta > 0:
            self._canvas.yview_scroll(-2, "units")
        else:
            self._canvas.yview_scroll(2, "units")

    def _on_resize(self, _=None):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(350, self._populate_grid)

    def _populate_grid(self):
        grid_w = getattr(self, "_canvas_w", self._canvas.winfo_width())
        if grid_w < 100:
            grid_w = self.winfo_width() - 24
        if grid_w < 100:
            grid_w = 900
        cols = max(1, grid_w // (CARD_W + PAD * 2))

        if not self._library:
            for w in self._grid_frame.winfo_children():
                w.destroy()
            lbl = tk.Label(self._grid_frame,
                           text="Keine Bücher gefunden.\nBibliothekspfad prüfen oder Scannen klicken.",
                           bg=BG, fg=TEXT3, font=("sans-serif", 13),
                           justify="center")
            lbl.pack(expand=True, pady=60)
            return

        if cols == getattr(self, "_last_cols", -1):
            return
        self._last_cols = cols

        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._cover_cache.clear()

        self._progress = self._store.get_all()

        cards = []
        for i, book in enumerate(self._library):
            r, c = divmod(i, cols)
            is_active = self._current_book and book["id"] == self._current_book["id"]
            card = BookCard(self._grid_frame, book, self._progress,
                            bool(is_active), self._on_book_click)
            card.grid(row=r, column=c, padx=PAD, pady=PAD, sticky="nw")
            cards.append((book, card))

        # Load covers in background
        for book, card in cards:
            threading.Thread(target=self._load_cover_bg, args=(book, card),
                             daemon=True).start()

    def _load_cover_bg(self, book: dict, card: BookCard):
        pil_img = load_cover(book["path"], COVER_SZ)
        if pil_img and PIL_OK:
            photo = ImageTk.PhotoImage(pil_img)
            self.after(0, lambda p=photo, c=card: c.set_cover(p))

    # ── Library loading ─────────────────────────────────────────────────────────

    def _load_library(self):
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        path = self._cfg.get("library_path", str(Path.home() / "Audiobooks"))
        books = scan_library(path)
        self.after(0, lambda: self._on_scan_done(books))

    def _on_scan_done(self, books: list):
        self._library = books
        self._last_cols = -1  # force full rebuild with correct canvas size
        self.after(80, self._populate_grid)
        self._restore_last_book()

    def _rescan(self):
        self._library = []
        self._populate_grid()
        self._load_library()

    def _restore_last_book(self):
        last_id = self._cfg.get("last_book_id")
        if not last_id:
            return
        book = next((b for b in self._library if b["id"] == last_id), None)
        if book:
            self._current_book = book
            self._update_player_bar_book(book)

    # ── Playback ────────────────────────────────────────────────────────────────

    def _on_book_click(self, book: dict):
        self._current_book = book
        self._cfg["last_book_id"] = book["id"]
        save_config(self._cfg)
        prog = self._store.get(book["id"])
        self._player.play(book["id"], book["files"],
                          prog["file_idx"], prog["position"])
        self._update_player_bar_book(book)
        self._populate_grid()

    def _toggle_pause(self):
        if self._current_book:
            self._player.pause()

    def _prev_file(self):
        if not self._current_book:
            return
        idx = max(0, self._player.status["file_index"] - 1)
        self._player.seek_to_file(idx)

    def _next_file(self):
        if not self._current_book:
            return
        files = self._current_book.get("files", [])
        idx = min(len(files) - 1, self._player.status["file_index"] + 1)
        self._player.seek_to_file(idx)

    def _on_seek_click(self, pct: float):
        if self._status_dur:
            self._player.seek(pct * self._status_dur)

    def _on_volume(self, val):
        self._player.set_volume(int(float(val)))

    # ── Progress callback (from MPV thread) ─────────────────────────────────────

    def _on_progress_cb(self, book_id, file_idx, position):
        if book_id:
            self._store.save(book_id, file_idx, position)

    # ── Status polling ──────────────────────────────────────────────────────────

    def _schedule_poll(self):
        self._poll_status()
        self.after(500, self._schedule_poll)

    def _poll_status(self):
        s = self._player.status
        self._status_pos = s.get("position", 0.0)
        self._status_dur = s.get("duration", 0.0)
        self._status_paused = s.get("paused", True)
        playing = s.get("playing", False)

        if self._status_dur:
            self._seekbar.set_percent(self._status_pos / self._status_dur)
        else:
            self._seekbar.set_percent(0)

        self._pb_time.config(
            text=f"{fmt_time(self._status_pos)}  /  {fmt_time(self._status_dur)}"
            if playing else ""
        )
        self._play_btn.config(text="⏸" if playing and not self._status_paused else "▶")
        self._mpris.update_status(playing, self._status_paused, self._status_pos)

    def _update_player_bar_book(self, book: dict):
        self._pb_title.config(text=book["title"])
        self._mpris.update_metadata(book["title"], book.get("author", ""))
        threading.Thread(target=self._load_pb_cover, args=(book,), daemon=True).start()

    def _load_pb_cover(self, book: dict):
        pil_img = load_cover(book["path"], 44)
        if pil_img and PIL_OK:
            photo = ImageTk.PhotoImage(pil_img)
            self.after(0, lambda p=photo: self._set_pb_cover(p))

    def _set_pb_cover(self, photo):
        self._pb_cover_photo = photo
        self._pb_cover.config(image=photo)

    # ── Settings ────────────────────────────────────────────────────────────────

    def _open_settings(self):
        def on_save(path):
            self._cfg["library_path"] = path
            save_config(self._cfg)
            self._rescan()

        SettingsDialog(self, self._cfg.get("library_path", ""), on_save)

    # ── Close ───────────────────────────────────────────────────────────────────

    def _on_close(self):
        self._player.stop()
        self.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AudiobookApp()
    app.mainloop()
