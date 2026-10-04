"""Grouping files into sets with the same content, by (size, crc).

crc is the CRC part of the fingerprint MEGA keeps with each file. Above 8 KB it
covers a spread-out 8 KB sample, so a shared (size, crc) is near-certain rather
than proof that two files are identical.
"""

from dataclasses import dataclass


@dataclass
class Group:
    size: int
    files: list

    @property
    def wasted(self):
        """Bytes that would be freed by keeping only one copy."""
        return self.size * (len(self.files) - 1)

    @property
    def title(self):
        """The first copy's name, and how many other names the copies go by."""
        first = self.files[0].name
        others = len({f.name for f in self.files} - {first})
        return first if not others else f"{first} (+{others} other name{'s' if others > 1 else ''})"


class DuplicateFinder:
    def __init__(self):
        self.files = 0
        self.empty = 0
        self.no_crc = 0
        self._seen = set()
        self._buckets = {}

    def add(self, item):
        # Overlapping selections (a folder and one inside it) list a file twice.
        if item.handle in self._seen:
            return
        self._seen.add(item.handle)
        self.files += 1
        # Every empty file has the same "content"; listing them would be noise.
        if item.size == 0:
            self.empty += 1
        elif item.crc is None:
            self.no_crc += 1
        else:
            self._buckets.setdefault((item.size, item.crc), []).append(item)

    def groups(self):
        """The sets of two or more, largest waste first; files in each by path."""
        groups = [
            Group(size, sorted(items, key=lambda i: i.path.lower()))
            for (size, _crc), items in self._buckets.items()
            if len(items) > 1
        ]
        groups.sort(key=lambda g: (-g.wasted, g.files[0].path.lower()))
        return groups


def parent_path(path):
    """The folder part of an item's path: "/Photos" for "/Photos/a.jpg", "/" at the top."""
    head = path.rsplit("/", 1)[0]
    return head or "/"


def format_size(size):
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
