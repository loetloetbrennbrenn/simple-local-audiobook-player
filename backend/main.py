import os
import io
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import init_db, get_db, Progress
from library import scan_library, extract_cover_bytes, get_audio_files
from player import AudiobookPlayer

LIBRARY_PATH = os.environ.get("LIBRARY_PATH", os.path.expanduser("~/Audiobooks"))
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

app = FastAPI(title="Raspi Audiobook Player")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_library_cache: list = []


def save_progress_callback(book_id: Optional[str], file_index: int, position: float):
    if not book_id:
        return
    from database import SessionLocal
    db = SessionLocal()
    try:
        prog = db.query(Progress).filter(Progress.book_id == book_id).first()
        if prog:
            prog.position = position
            prog.file_index = file_index
            prog.updated_at = datetime.utcnow()
        else:
            prog = Progress(book_id=book_id, position=position, file_index=file_index)
            db.add(prog)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


player = AudiobookPlayer(on_progress=save_progress_callback)


@app.on_event("startup")
async def startup_event():
    init_db()
    global _library_cache
    _library_cache = scan_library(LIBRARY_PATH)


# ── Library ──────────────────────────────────────────────────────────────────

@app.get("/api/library")
def get_library():
    return {"books": _library_cache, "library_path": LIBRARY_PATH}


@app.post("/api/library/scan")
def rescan_library():
    global _library_cache
    _library_cache = scan_library(LIBRARY_PATH)
    return {"books": _library_cache, "count": len(_library_cache)}


@app.get("/api/library/path")
def get_library_path():
    return {"library_path": LIBRARY_PATH}


@app.post("/api/library/path")
def set_library_path(body: dict):
    global LIBRARY_PATH, _library_cache
    new_path = body.get("path", "")
    expanded = os.path.expanduser(new_path)
    if not os.path.isdir(expanded):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    LIBRARY_PATH = expanded
    _library_cache = scan_library(LIBRARY_PATH)
    return {"library_path": LIBRARY_PATH, "books": _library_cache}


@app.get("/api/books/{book_id}")
def get_book(book_id: str):
    book = next((b for b in _library_cache if b["id"] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.get("/api/books/{book_id}/cover")
def get_cover(book_id: str):
    book = next((b for b in _library_cache if b["id"] == book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    cover_bytes = extract_cover_bytes(book["path"])
    if not cover_bytes:
        raise HTTPException(status_code=404, detail="No cover found")

    content_type = "image/jpeg"
    if cover_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        content_type = "image/png"

    return Response(content=cover_bytes, media_type=content_type)


# ── Progress ──────────────────────────────────────────────────────────────────

@app.get("/api/progress/{book_id}")
def get_progress(book_id: str, db: Session = Depends(get_db)):
    prog = db.query(Progress).filter(Progress.book_id == book_id).first()
    if not prog:
        return {"book_id": book_id, "position": 0.0, "file_index": 0}
    return {"book_id": book_id, "position": prog.position, "file_index": prog.file_index}


@app.post("/api/progress/{book_id}")
def save_progress(book_id: str, body: dict, db: Session = Depends(get_db)):
    position = float(body.get("position", 0.0))
    file_index = int(body.get("file_index", 0))
    prog = db.query(Progress).filter(Progress.book_id == book_id).first()
    if prog:
        prog.position = position
        prog.file_index = file_index
        prog.updated_at = datetime.utcnow()
    else:
        prog = Progress(book_id=book_id, position=position, file_index=file_index)
        db.add(prog)
    db.commit()
    return {"ok": True}


# ── Player ────────────────────────────────────────────────────────────────────

class PlayRequest(BaseModel):
    book_id: str
    file_index: Optional[int] = None
    position: Optional[float] = None


class SeekRequest(BaseModel):
    seconds: float
    mode: str = "absolute"


class VolumeRequest(BaseModel):
    volume: int


@app.post("/api/player/play")
def play(req: PlayRequest, db: Session = Depends(get_db)):
    book = next((b for b in _library_cache if b["id"] == req.book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    prog = db.query(Progress).filter(Progress.book_id == req.book_id).first()
    file_index = req.file_index if req.file_index is not None else (prog.file_index if prog else 0)
    position = req.position if req.position is not None else (prog.position if prog else 0.0)

    files = book["files"]
    if file_index >= len(files):
        file_index = 0
        position = 0.0

    player.play(req.book_id, files, file_index, position)
    return {"ok": True, "book_id": req.book_id, "file_index": file_index, "position": position}


@app.post("/api/player/pause")
def pause():
    player.pause()
    return {"ok": True}


@app.post("/api/player/stop")
def stop():
    player.stop()
    return {"ok": True}


@app.post("/api/player/seek")
def seek(req: SeekRequest):
    player.seek(req.seconds, req.mode)
    return {"ok": True}


@app.post("/api/player/skip_forward")
def skip_forward(body: dict = {}):
    seconds = float(body.get("seconds", 30.0)) if body else 30.0
    player.skip_forward(seconds)
    return {"ok": True}


@app.post("/api/player/skip_backward")
def skip_backward(body: dict = {}):
    seconds = float(body.get("seconds", 15.0)) if body else 15.0
    player.skip_backward(seconds)
    return {"ok": True}


@app.post("/api/player/seek_to_file")
def seek_to_file(body: dict):
    file_index = int(body.get("file_index", 0))
    position = float(body.get("position", 0.0))
    player.seek_to_file(file_index, position)
    return {"ok": True}


@app.get("/api/player/status")
def get_status():
    return player.status


@app.post("/api/player/volume")
def set_volume(req: VolumeRequest):
    player.set_volume(req.volume)
    return {"ok": True, "volume": req.volume}


@app.get("/api/player/volume")
def get_volume():
    return {"volume": player.get_volume()}


# ── Serve Frontend ─────────────────────────────────────────────────────────────

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        return FileResponse(index)
