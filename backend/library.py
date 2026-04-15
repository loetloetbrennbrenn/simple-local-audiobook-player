import os
import hashlib
import json
from pathlib import Path
from typing import List, Optional
from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".m4b", ".flac", ".ogg", ".aac", ".wav", ".opus"}
COVER_NAMES = {"cover.jpg", "cover.jpeg", "cover.png", "folder.jpg", "folder.jpeg", "folder.png", "albumart.jpg"}


def book_id_from_path(path: str) -> str:
    return hashlib.md5(path.encode()).hexdigest()


def get_audio_files(folder: str) -> List[str]:
    files = []
    for f in sorted(Path(folder).iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            files.append(str(f))
    return files


def get_duration(filepath: str) -> float:
    try:
        audio = MutagenFile(filepath)
        if audio and audio.info:
            return audio.info.length
    except Exception:
        pass
    return 0.0


def extract_cover_bytes(folder: str) -> Optional[bytes]:
    folder_path = Path(folder)

    for name in COVER_NAMES:
        candidate = folder_path / name
        if candidate.exists():
            return candidate.read_bytes()

    for f in sorted(folder_path.iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            try:
                audio = MutagenFile(str(f))
                if audio is None:
                    continue
                if hasattr(audio, "tags") and audio.tags:
                    for key in audio.tags.keys():
                        if key.startswith("APIC"):
                            return audio.tags[key].data
                if isinstance(audio, MP4):
                    covr = audio.tags.get("covr")
                    if covr:
                        return bytes(covr[0])
                if isinstance(audio, FLAC):
                    if audio.pictures:
                        return audio.pictures[0].data
            except Exception:
                pass
            break

    return None


def get_title_from_folder(folder: str) -> str:
    return Path(folder).name


def get_author_from_files(folder: str) -> Optional[str]:
    for f in sorted(Path(folder).iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS:
            try:
                audio = MutagenFile(str(f))
                if audio is None:
                    continue
                tags = audio.tags
                if tags is None:
                    continue
                for key in ("TPE1", "TPE2", "\xa9ART", "artist", "ARTIST"):
                    val = tags.get(key)
                    if val:
                        return str(val[0]) if hasattr(val, "__iter__") and not isinstance(val, str) else str(val)
            except Exception:
                pass
            break
    return None


def scan_library(library_path: str) -> List[dict]:
    library_path = os.path.expanduser(library_path)
    if not os.path.isdir(library_path):
        return []

    books = []
    for item in sorted(Path(library_path).iterdir()):
        if not item.is_dir():
            continue
        audio_files = get_audio_files(str(item))
        if not audio_files:
            continue

        total_duration = sum(get_duration(f) for f in audio_files)
        book = {
            "id": book_id_from_path(str(item)),
            "title": get_title_from_folder(str(item)),
            "author": get_author_from_files(str(item)),
            "path": str(item),
            "files": audio_files,
            "file_count": len(audio_files),
            "total_duration": total_duration,
            "has_cover": extract_cover_bytes(str(item)) is not None,
        }
        books.append(book)

    return books
