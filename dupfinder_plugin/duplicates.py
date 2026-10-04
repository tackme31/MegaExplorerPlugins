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
