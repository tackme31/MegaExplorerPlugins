"""The part of ZIP Search that needs no window: reading a ZIP's index and one of its
entries through byte-range reads, entry-name decoding, the name filter, naming
the saved file, and the cache of indexes read before. main.py holds the window.
"""

import json
import os
import re
import struct
import zipfile
from dataclasses import dataclass

READ_LIMIT = 1 << 20      # items.readRange answers at most 1 MiB
BLOCK = 64 << 10          # smallest read: a local header and a small entry in one call
TAIL = 128 << 10          # the end record, the comment and usually the whole central directory
FETCH_ABOVE = 1 << 20     # entry data bigger than this comes through items.fetchFile
FETCH_CHUNK = 8 << 20     # one items.fetchFile at most, so a large entry can report progress


class _Bytes:
    def __init__(self, start, data):
        self.start, self.end, self.data = start, start + len(data), data

    def read(self, pos, n):
        return self.data[pos - self.start:pos - self.start + n]

    def close(self):
        pass


class _LocalFile:
    def __init__(self, start, length, path):
        self.start, self.end = start, start + length
        self.file = open(path, "rb")

    def read(self, pos, n):
        self.file.seek(pos - self.start)
        return self.file.read(n)

    def close(self):
        self.file.close()


class RemoteFile:
    """A read-only, seekable file over a file in MEGA, for zipfile to read.

    read_range(offset, length) -> bytes is items.readRange; fetch_range(offset,
    length) -> path is items.fetchFile with a range. Everything read is kept, so
    zipfile's many small reads near the end of the file cost one call."""

    def __init__(self, size, read_range, fetch_range=None):
        self.size = size
        self._read_range = read_range
        self._fetch_range = fetch_range
        self._segments = []
        self._pos = 0
        self.calls = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, offset, whence=0):
        if whence == 0:
            pos = offset
        elif whence == 1:
            pos = self._pos + offset
        else:
            pos = self.size + offset
        if pos < 0:
            raise OSError("negative seek position")
        self._pos = pos
        return pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self._pos
        out = bytearray()
        while n > 0 and self._pos < self.size:
            segment = self._find(self._pos) or self._load(self._pos, n)
            chunk = segment.read(self._pos, min(n, segment.end - self._pos))
            if not chunk:
                break
            out += chunk
            self._pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def covered(self, start, end):
        pos = start
        while pos < end:
            segment = self._find(pos)
            if segment is None:
                return False
            pos = segment.end
        return True

    def prefetch(self, start, length, cancelled=lambda: False, progress=None):
        """Brings start..start+length in as local files, FETCH_CHUNK per fetch_range,
        calling progress(done, length) after each. False if cancelled() turned true."""
        if self._fetch_range is None:
            return True
        done = 0
        while done < length:
            if cancelled():
                return False
            n = min(FETCH_CHUNK, length - done)
            if not self.covered(start + done, start + done + n):
                self.calls += 1
                path = self._fetch_range(start + done, n)
                self._segments.append(_LocalFile(start + done, os.path.getsize(path), path))
            done += n
            if progress is not None:
                progress(done, length)
        return True

    def close(self):
        for segment in self._segments:
            segment.close()
        self._segments = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _find(self, pos):
        for segment in self._segments:
            if segment.start <= pos < segment.end:
                return segment
        return None

    def _load(self, pos, want):
        if self.size - pos <= TAIL:
            start, end = max(0, self.size - TAIL), self.size
        else:
            start = pos
            end = min(self.size, max(pos + want, start + BLOCK), start + READ_LIMIT)
        self.calls += 1
        data = self._read_range(start, end - start)
        if not data:
            raise OSError(f"no data at offset {start}")
        segment = _Bytes(start, data)
        self._segments.append(segment)
        return segment


@dataclass
class Entry:
    path: str        # folder inside the ZIP, "" at its top, no trailing "/"
    name: str
    size: int
    offset: int      # its local header's offset, which identifies it even among duplicate names


def display_name(info):
    """The entry's name as its creator meant it. Without the UTF-8 flag zipfile
    reads names as CP437; Japanese tools write CP932 there, and some write UTF-8
    without setting the flag."""
    if info.flag_bits & 0x800:
        name = info.orig_filename
    else:
        try:
            raw = info.orig_filename.encode("cp437")
        except UnicodeEncodeError:
            raw = None
        name = info.orig_filename
        if raw is not None:
            for encoding in ("utf-8", "cp932"):
                try:
                    name = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    pass
    return name.replace("\\", "/")


def list_entries(remote):
    """The files in the ZIP read through remote, in the order of its index."""
    with zipfile.ZipFile(remote) as archive:
        entries = []
        for info in archive.infolist():
            if info.is_dir():
                continue
            full = display_name(info).strip("/")
            if not full or full.endswith("/"):
                continue
            folder, _, name = full.rpartition("/")
            entries.append(Entry(folder, name, info.file_size, info.header_offset))
        return entries


def extract(remote, offset, out, cancelled=lambda: False, progress=None):
    """Writes the entry whose local header is at offset in the ZIP read through remote
    to the binary file out. Returns False if cancelled() turned true part-way.
    progress(done, total) follows the download of a large entry's data."""
    with zipfile.ZipFile(remote) as archive:
        info = next((i for i in archive.infolist() if i.header_offset == offset), None)
        if info is None:
            raise zipfile.BadZipFile("the file is no longer in the ZIP")
        remote.seek(info.header_offset)
        header = remote.read(30)
        if len(header) != 30 or header[:4] != b"PK\x03\x04":
            raise zipfile.BadZipFile("bad local file header")
        name_length, extra_length = struct.unpack("<HH", header[26:30])
        data_start = info.header_offset + 30 + name_length + extra_length
        if info.compress_size > FETCH_ABOVE:
            if not remote.prefetch(data_start, info.compress_size, cancelled, progress):
                return False
        with archive.open(info) as source:
            while True:
                if cancelled():
                    return False
                chunk = source.read(READ_LIMIT)
                if not chunk:
                    return True
                out.write(chunk)


def matches(name, terms):
    """True when every term occurs in name, ignoring case."""
    folded = name.casefold()
    return all(term in folded for term in terms)


def filter_terms(text):
    return [term.casefold() for term in text.split()]


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_file_name(name):
    name = _INVALID.sub("_", name).rstrip(" .")
    if not name:
        name = "file"
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name


def unique_path(folder, name, exists=os.path.exists):
    """folder/name, or folder/'stem (n).ext' for the first n not taken."""
    stem, ext = os.path.splitext(name)
    candidate = os.path.join(folder, name)
    n = 1
    while exists(candidate):
        candidate = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    return candidate


def format_size(size):
    if size < 1024:
        return f"{size:,} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:,.1f} {unit}"


MAX_TAGS = 10
MAX_TAG_BYTES = 3000


def tag_filter_terms(text):
    """The ZIP-tag filter: tags separated by commas, each matched as part of a tag."""
    return [term.strip().casefold() for term in text.split(",") if term.strip()]


def tags_match(tags, terms):
    """True when every term occurs in at least one of tags, ignoring case."""
    folded = [tag.casefold() for tag in tags]
    return all(any(term in tag for tag in folded) for term in terms)


def clean_tags(values):
    """The tags typed into the editor, trimmed, without blanks or repeats (MEGA
    compares tags ignoring case). Raises ValueError for what MEGA would refuse."""
    tags, seen = [], set()
    for value in values:
        tag = value.strip()
        if not tag or tag.casefold() in seen:
            continue
        if "," in tag:
            raise ValueError(f"A tag cannot contain a comma: {tag}")
        seen.add(tag.casefold())
        tags.append(tag)
    if len(tags) > MAX_TAGS:
        raise ValueError(f"At most {MAX_TAGS} tags")
    if len(",".join(tags).encode("utf-8")) > MAX_TAG_BYTES:
        raise ValueError(f"All tags together must fit in {MAX_TAG_BYTES} bytes")
    return tags


def tag_changes(old, new):
    """(add, remove) that turn old into new. A change of case only is no change,
    as MEGA matches tags ignoring case."""
    old_folded = {tag.casefold() for tag in old}
    new_folded = {tag.casefold() for tag in new}
    return ([tag for tag in new if tag.casefold() not in old_folded],
            [tag for tag in old if tag.casefold() not in new_folded])


def parse_extensions(text):
    """The extensions box, "zip, .cbz, *.EPUB", as [".zip", ".cbz", ".epub"]."""
    extensions = []
    for part in text.split(","):
        ext = part.strip().lstrip("*").lstrip(".").strip().casefold()
        if ext and f".{ext}" not in extensions:
            extensions.append(f".{ext}")
    if not extensions:
        raise ValueError("Enter at least one extension")
    return extensions


def has_extension(name, extensions):
    return name.casefold().endswith(tuple(extensions))


class IndexCache:
    """ZIP indexes read before, by MEGA handle, in one JSON file. An index is used only
    while the ZIP's mtime and size are still the ones it was read at."""

    VERSION = 1

    def __init__(self, path):
        self.path = path
        self.zips = self._read()
        self.added = {}

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") == self.VERSION and isinstance(data.get("zips"), dict):
                return data["zips"]
        except (OSError, ValueError, AttributeError):
            pass
        return {}

    def get(self, handle, mtime, size):
        record = self.zips.get(handle)
        if not record or mtime is None or record.get("mtime") != mtime or record.get("size") != size:
            return None
        try:
            return [Entry(*fields) for fields in record["entries"]]
        except (KeyError, TypeError):
            return None

    def put(self, handle, mtime, size, entries):
        if mtime is None:
            return
        record = {"mtime": mtime, "size": size,
                  "entries": [[e.path, e.name, e.size, e.offset] for e in entries]}
        self.zips[handle] = record
        self.added[handle] = record

    def save(self):
        """Writes what was added since the last save, over what is on disk now, so two
        windows searching at once do not drop each other's indexes."""
        if not self.added:
            return
        zips = self._read()
        zips.update(self.added)
        part = self.path + ".tmp"
        with open(part, "w", encoding="utf-8") as f:
            json.dump({"version": self.VERSION, "zips": zips}, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(part, self.path)
        self.zips = zips
        self.added = {}

    def clear(self):
        """Forgets every index. Returns how many ZIPs were in the cache."""
        count = len(self._read().keys() | self.zips.keys())
        self.zips, self.added = {}, {}
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
        return count
