"""Looking INSIDE archives that Kaggle mounted without extracting (and, only on explicit request, extracting the useful members).

Listing and sniffing never write anything. Extraction is a deliberate, opt-in COPY inside Kaggle's own working disk (``/kaggle/working``,
never a laptop, never git): it is allowlisted by file type (images, annotations, class-name files; videos only when asked), refuses unsafe
member paths (absolute paths, ``..``, links), stops before the disk would fill, and its output is never bundled.

Supported: zip, and tar (plain / gzip / bzip2 / xz). 7z, rar and single-file gzip are detected and reported as unsupported.
"""
from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from .errors import DataSourceError

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ANNOTATION_SUFFIXES = {".xml", ".txt", ".json", ".yaml", ".yml", ".names", ".csv"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".mpg", ".mpeg", ".wmv"}
SUPPORTED = ("zip", "tar", "tar.gz", "tar.bz2", "tar.xz")
_MAGIC = ((b"PK\x03\x04", "zip"), (b"PK\x05\x06", "zip"), (b"\x1f\x8b", "gzip"), (b"BZh", "bzip2"), (b"\xfd7zXZ\x00", "xz"), (b"7z\xbc\xaf\x27\x1c", "7z"),
          (b"Rar!\x1a\x07", "rar"), (b"\xff\xd8\xff", "jpeg"), (b"\x89PNG\r\n\x1a\n", "png"), (b"%PDF", "pdf"), (b"SQLite format 3", "sqlite"))
ARCHIVE_KINDS = {"zip", "tar", "gzip", "bzip2", "xz", "7z", "rar"}


class ArchiveError(DataSourceError):
    """The archive cannot be read/extracted safely."""


def sniff_kind(path: Path) -> str | None:
    """File type from its first bytes (extension ignored): zip/tar/gzip/…/jpeg/png/text, or None if unknown. Reads <= 512 bytes."""
    try:
        with open(path, "rb") as f:
            head = f.read(512)
    except OSError:
        return None
    for magic, name in _MAGIC:
        if head.startswith(magic):
            return name
    if len(head) >= 262 and head[257:262] == b"ustar":
        return "tar"
    if head and all(b in b"\t\n\r" or 32 <= b < 127 or b >= 128 for b in head[:200]):
        try:
            text = head.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return None
        low = text.lstrip().lower()
        if low.startswith(("<!doctype html", "<html")) or "<html" in low[:300]:
            return "html"
        if low.startswith(("{", "[")):
            return "json"
        if low.startswith("<?xml"):
            return "xml"
        return "text"
    return None


def text_preview(path: Path, limit: int = 160) -> dict:
    """First characters of a small text-like file (whitespace collapsed) and, for HTML, its <title>. Used to say what an opaque file IS."""
    import re
    try:
        raw = Path(path).read_bytes()[:200_000].decode("utf-8", errors="ignore")
    except OSError:
        return {}
    out = {"preview": " ".join(raw.split())[:limit]}
    m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    if m:
        out["html_title"] = " ".join(m.group(1).split())[:160]
    return out


class ArchiveReader:
    """Read-only view of a zip/tar: member listing and in-memory reads of single members (nothing is extracted)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.kind = sniff_kind(self.path)
        if self.kind == "zip":
            try:
                self._zip = zipfile.ZipFile(self.path)
            except zipfile.BadZipFile as e:
                raise ArchiveError(f"{self.path.name}: starts like a zip but cannot be read ({e}): truncated or corrupt upload") from e
            self._tar = None
        elif self.kind in ("tar", "gzip", "bzip2", "xz"):
            try:
                self._tar = tarfile.open(self.path, "r:*")
            except tarfile.TarError as e:
                raise ArchiveError(f"{self.path.name}: detected as {self.kind} but it is not a tar archive ({e}); single compressed files are not supported") from e
            self._zip = None
        else:
            raise ArchiveError(f"{self.path.name}: {self.kind or 'unknown'} is not a supported archive type (supported: {SUPPORTED})")

    def entries(self) -> list[tuple[str, int]]:
        """(member path, uncompressed bytes) for regular files only."""
        if self._zip is not None:
            return [(i.filename, i.file_size) for i in self._zip.infolist() if not i.is_dir()]
        assert self._tar is not None
        return [(m.name, m.size) for m in self._tar.getmembers() if m.isfile()]

    def read(self, name: str, limit: int = 2_000_000) -> bytes:
        if self._zip is not None:
            with self._zip.open(name) as f:
                return f.read(limit)
        assert self._tar is not None
        f = self._tar.extractfile(name)
        return f.read(limit) if f else b""

    def close(self) -> None:
        (self._zip or self._tar).close()   # type: ignore[union-attr]


def _safe_target(dest: Path, member: str) -> Path | None:
    p = PurePosixPath(member.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or not p.parts:
        return None
    target = (dest / Path(*p.parts)).resolve()
    try:
        target.relative_to(dest.resolve())
    except ValueError:
        return None
    return target


def extract_useful(archive: Path, dest: Path, *, include_videos: bool = False, max_bytes: int = 15_000_000_000, free_margin_bytes: int = 2_000_000_000) -> dict:
    """Extract ONLY images + annotation/class files (videos on request) into ``dest``. Returns a summary; raises ArchiveError before writing if the
    selected members would not fit (``max_bytes`` or free disk minus a margin). Unsafe member paths are skipped and counted."""
    reader = ArchiveReader(archive)
    try:
        allowed = IMAGE_SUFFIXES | ANNOTATION_SUFFIXES | (VIDEO_SUFFIXES if include_videos else set())
        picked, skipped_type, unsafe, total = [], 0, 0, 0
        for name, size in reader.entries():
            if PurePosixPath(name).suffix.lower() not in allowed:
                skipped_type += 1
                continue
            if _safe_target(dest, name) is None:
                unsafe += 1
                continue
            picked.append((name, size))
            total += size
        dest.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(dest).free
        if total > max_bytes:
            raise ArchiveError(f"extraction would write {total / 1e9:.1f} GB (> max_bytes {max_bytes / 1e9:.1f} GB): nothing was extracted")
        if total + free_margin_bytes > free:
            raise ArchiveError(f"extraction needs {total / 1e9:.1f} GB but only {free / 1e9:.1f} GB is free on {dest} (margin {free_margin_bytes / 1e9:.1f} GB): nothing was extracted")
        written = 0
        for name, _size in picked:
            target = _safe_target(dest, name)
            assert target is not None
            target.parent.mkdir(parents=True, exist_ok=True)
            if reader._zip is not None:
                with reader._zip.open(name) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
            else:
                src = reader._tar.extractfile(name)       # type: ignore[union-attr]
                if src is None:
                    continue
                with src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1 << 20)
            written += 1
        return {"archive": archive.name, "kind": reader.kind, "files_extracted": written, "bytes_selected": total, "skipped_other_types": skipped_type,
                "skipped_unsafe_paths": unsafe, "videos_included": include_videos, "destination": str(dest)}
    finally:
        reader.close()


def memory_reader(path: Path):
    """(entries, read) pair over an archive, for profilers that must work on a listing instead of a directory."""
    r = ArchiveReader(path)
    return r, r.entries(), (lambda name, n=200_000: r.read(name, n))

