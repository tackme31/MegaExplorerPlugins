"""Duplicate Finder: lists the files under the chosen folders that share size and
MEGA's content checksum, grouped, in a window of its own. Double-click a file to
show it in the app. Read-only. The grouping is in duplicates.py.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk

from duplicates import DuplicateFinder
from megaexplorer_plugin import Plugin, RpcError

plugin = Plugin()

FIELDS = ["name", "size", "path", "crc"]


def human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class Window:
    def __init__(self, ctx):
        self.ctx = ctx
        self.folders = list(ctx.items)
        self.closing = threading.Event()
        self.updates = queue.Queue()
        self.handles = {}

        self.root = tk.Tk()
        where = self.folders[0].path if len(self.folders) == 1 else f"{len(self.folders)} folders"
        self.root.title(f"Duplicate Finder - {where}")
        self.root.geometry("820x560")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        self.status = ttk.Label(frame, text="Listing files...")
        self.status.pack(anchor="w", pady=(0, 8))

        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("size", "wasted"), selectmode="browse")
        self.tree.heading("#0", text="File")
        self.tree.heading("size", text="Size")
        self.tree.heading("wasted", text="Wasted")
        self.tree.column("#0", width=560)
        self.tree.column("size", width=100, anchor="e", stretch=False)
        self.tree.column("wasted", width=100, anchor="e", stretch=False)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-Button-1>", self.reveal)

        ttk.Label(frame, text="Double-click a file to show it in MEGA Explorer.").pack(anchor="w", pady=(8, 0))

        threading.Thread(target=self.scan, daemon=True).start()
        self.root.after(100, self.poll)

    # --- listing, off the UI thread -----------------------------------------------

    def scan(self):
        try:
            finder = DuplicateFinder()
            for folder in self.folders:
                for item in self.ctx.descendants(folder, type="file", fields=FIELDS):
                    if self.closing.is_set():
                        return
                    finder.add(item)
                    if finder.files % 1000 == 0:
                        self.updates.put(("progress", finder.files))
            self.updates.put(("done", finder))
        except RpcError as e:
            self.updates.put(("error", e.message))

    def poll(self):
        try:
            while True:
                kind, value = self.updates.get_nowait()
                if kind == "progress":
                    self.status.config(text=f"Listing files... {value:,}")
                elif kind == "done":
                    self.show(value)
                else:
                    self.status.config(text=f"Could not list the files: {value}")
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(100, self.poll)

    def show(self, finder):
        groups = finder.groups()
        for n, group in enumerate(groups):
            parent = self.tree.insert(
                "", "end", open=True,
                text=f"{len(group.files)} copies of {group.files[0].name}",
                values=(human_size(group.size), human_size(group.wasted)))
            for item in group.files:
                row = self.tree.insert(parent, "end", text=item.path, values=(human_size(item.size), ""))
                self.handles[row] = item.handle
        wasted = sum(g.wasted for g in groups)
        text = (f"{finder.files:,} files, {len(groups):,} sets of duplicates, "
                f"{human_size(wasted)} could be freed")
        skipped = []
        if finder.no_crc:
            skipped.append(f"{finder.no_crc:,} without a checksum")
        if finder.empty:
            skipped.append(f"{finder.empty:,} empty")
        if skipped:
            text += f" (not compared: {', '.join(skipped)})"
        self.status.config(text=text)

    # --- showing a file in the app ---------------------------------------------------

    def reveal(self, _event):
        selected = self.tree.selection()
        handle = self.handles.get(selected[0]) if selected else None
        if handle is None:
            return
        try:
            self.ctx.reveal(handle)
        except RpcError as e:
            self.status.config(text=f"Could not show the file: {e.message}")

    def close(self):
        self.closing.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


@plugin.command("find")
def find(ctx):
    Window(ctx).run()
    return None


if __name__ == "__main__":
    plugin.run()
