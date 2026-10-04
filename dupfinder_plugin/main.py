"""Duplicate Finder: lists the files under the chosen folders that share size and
MEGA's content checksum, grouped, in a window of its own, and shows a chosen copy
in the app. Read-only. The grouping is in duplicates.py.
"""

import ctypes
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from duplicates import DuplicateFinder, format_size, parent_path
from megaexplorer_plugin import Plugin, RpcError

plugin = Plugin()

FIELDS = ["name", "size", "path", "crc"]


def make_dpi_aware():
    # Without this Windows bitmap-stretches the window on a scaled display, and
    # the text comes out blurred.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


class Window:
    def __init__(self, ctx):
        self.ctx = ctx
        self.folders = list(ctx.items)
        self.closing = threading.Event()
        self.updates = queue.Queue()
        self.files_by_row = {}

        make_dpi_aware()
        self.root = tk.Tk()
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.root.title(f"Duplicate Finder - {self.scope()}")
        self.root.geometry(f"{self.px(900)}x{self.px(600)}")
        self.root.minsize(self.px(560), self.px(360))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.style_widgets()

        frame = ttk.Frame(self.root, padding=self.px(12))
        frame.pack(fill="both", expand=True)
        self.build_summary(frame)
        self.build_buttons(frame)
        self.build_table(frame)

        threading.Thread(target=self.scan, daemon=True).start()
        self.root.after(100, self.poll)

    def px(self, n):
        return round(n * self.scale)

    def scope(self):
        if len(self.folders) == 1:
            return self.folders[0].path
        return f"{len(self.folders)} folders"

    def style_widgets(self):
        base = tkfont.nametofont("TkDefaultFont")
        self.bold = base.copy()
        self.bold.configure(weight="bold")
        self.headline = base.copy()
        self.headline.configure(size=round(base.cget("size") * 1.6), weight="bold")
        style = ttk.Style(self.root)
        # ttk's row height is fixed in pixels and does not follow the font on a scaled display.
        style.configure("Treeview", rowheight=base.metrics("linespace") + self.px(6))

    # --- layout -----------------------------------------------------------------------

    def build_summary(self, parent):
        summary = ttk.Frame(parent)
        summary.pack(fill="x")
        self.total = ttk.Label(summary, text="Looking for duplicates...", font=self.headline)
        self.total.pack(anchor="w")
        self.detail = ttk.Label(summary, text=f"Listing the files in {self.scope()}")
        self.detail.pack(anchor="w", pady=(self.px(2), 0))
        self.note = ttk.Label(summary, text="", foreground="gray40")
        self.progress = ttk.Progressbar(summary, mode="indeterminate")
        self.progress.pack(fill="x", pady=(self.px(8), 0))
        self.progress.start(15)

    def build_buttons(self, parent):
        # Packed before the table so the table, not the buttons, gives way when the window shrinks.
        bar = ttk.Frame(parent)
        bar.pack(side="bottom", fill="x", pady=(self.px(10), 0))
        self.go_button = ttk.Button(bar, text="Go to file", command=self.go_to_file, state="disabled")
        self.go_button.pack(side="right")
        ttk.Label(bar, text="Shows the selected copy in MEGA Explorer", foreground="gray40").pack(
            side="right", padx=(0, self.px(10)))
        self.expand_button = ttk.Button(bar, text="Expand all", command=lambda: self.set_open(True),
                                        state="disabled")
        self.expand_button.pack(side="left")
        self.collapse_button = ttk.Button(bar, text="Collapse all", command=lambda: self.set_open(False),
                                          state="disabled")
        self.collapse_button.pack(side="left", padx=(self.px(6), 0))

    def build_table(self, parent):
        table = ttk.Frame(parent)
        table.pack(fill="both", expand=True, pady=(self.px(12), 0))
        self.tree = ttk.Treeview(table, columns=("folder", "size", "wasted"), selectmode="browse")
        for column, text, width, anchor, stretch in (
            ("#0", "Name", 300, "w", True),
            ("folder", "Folder", 360, "w", True),
            ("size", "Size", 90, "e", False),
            ("wasted", "Wasted", 90, "e", False),
        ):
            self.tree.heading(column, text=text, anchor=anchor)
            self.tree.column(column, width=self.px(width), minwidth=self.px(60), anchor=anchor, stretch=stretch)
        self.tree.tag_configure("group", font=self.bold)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-Button-1>", self.on_double_click)
        self.tree.bind("<Return>", lambda e: self.go_to_file())

    # --- listing, off the UI thread ---------------------------------------------------

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
                    self.detail.config(text=f"Listing the files in {self.scope()}... {value:,}")
                elif kind == "done":
                    self.show(value)
                else:
                    self.stop_progress()
                    self.total.config(text="Could not list the files")
                    self.detail.config(text=value)
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(100, self.poll)

    def stop_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

    # --- results ----------------------------------------------------------------------

    def show(self, finder):
        self.stop_progress()
        groups = finder.groups()
        for group in groups:
            row = self.tree.insert(
                "", "end", open=True, tags=("group",), text=group.title,
                values=(f"{len(group.files)} copies", format_size(group.size), format_size(group.wasted)))
            for item in group.files:
                child = self.tree.insert(row, "end", text=item.name,
                                         values=(parent_path(item.path), format_size(item.size), ""))
                self.files_by_row[child] = item

        copies = sum(len(g.files) for g in groups)
        if groups:
            self.total.config(text=f"{format_size(sum(g.wasted for g in groups))} wasted")
            self.detail.config(
                text=f"{len(groups):,} sets of duplicates ({copies:,} files). Keeping one copy of each "
                     f"would free this much. {finder.files:,} files checked in {self.scope()}.")
            self.expand_button.config(state="normal")
            self.collapse_button.config(state="normal")
        else:
            self.total.config(text="No duplicates")
            self.detail.config(text=f"{finder.files:,} files checked in {self.scope()}.")

        skipped = []
        if finder.no_crc:
            skipped.append(f"{finder.no_crc:,} uploaded without a checksum")
        if finder.empty:
            skipped.append(f"{finder.empty:,} empty")
        if skipped:
            self.show_note(f"Not compared: {', '.join(skipped)}.")

    def show_note(self, text):
        self.note.config(text=text)
        self.note.pack(anchor="w", pady=(self.px(2), 0))

    def set_open(self, is_open):
        for row in self.tree.get_children(""):
            self.tree.item(row, open=is_open)

    # --- showing a copy in the app ----------------------------------------------------

    def selected_file(self):
        selected = self.tree.selection()
        return self.files_by_row.get(selected[0]) if selected else None

    def on_select(self, _event):
        self.go_button.config(state="normal" if self.selected_file() else "disabled")

    def on_double_click(self, event):
        # A group row's double-click is Treeview's own expand/collapse.
        if self.tree.identify_row(event.y) in self.files_by_row:
            self.go_to_file()

    def go_to_file(self):
        item = self.selected_file()
        if item is None:
            return
        try:
            self.ctx.reveal(item)
        except RpcError as e:
            self.show_note(f"Could not show {item.path}: {e.message}")

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
