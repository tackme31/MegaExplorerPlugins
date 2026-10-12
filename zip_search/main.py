"""ZIP Search: lists the files inside every ZIP under the chosen folders, in a window
of its own, one ZIP at a time as each index is read, and saves a chosen file out of
its ZIP without downloading the rest. The ZIP reading is in zipindex.py.
"""

import ctypes
import os
import queue
import sys
import threading
import tkinter as tk
from ctypes import wintypes
from tkinter import font as tkfont
from tkinter import ttk

from megaexplorer_plugin import Cancelled, Plugin, RpcError
from zipindex import (RemoteFile, extract, filter_terms, format_size, list_entries, matches,
                      safe_file_name, unique_path)

plugin = Plugin()

ZIP_FIELDS = ["name", "size", "path"]
FILTER_DELAY_MS = 250


def make_dpi_aware():
    # Without this Windows bitmap-stretches the window on a scaled display, and
    # the text comes out blurred.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]


def downloads_folder():
    # FOLDERID_Downloads: the user may have moved it, so ~/Downloads is only the fallback.
    guid = _GUID(0x374DE290, 0x123F, 0x4565, (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
    path = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path)) == 0:
            try:
                return path.value
            finally:
                ctypes.windll.ole32.CoTaskMemFree(path)
    except (AttributeError, OSError):
        pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


class Window:
    def __init__(self, ctx):
        self.ctx = ctx
        self.folders = list(ctx.items)
        self.closing = threading.Event()
        self.updates = queue.Queue()
        self.rows = []             # (zip Item, Entry), the row's iid is its index
        self.terms = []
        self.filter_job = None
        self.zips_done = 0
        self.zips_total = None
        self.failed = []
        self.downloads = queue.Queue()
        self.downloading = threading.Event()

        make_dpi_aware()
        self.root = tk.Tk()
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.root.title(f"ZIP Search - {self.scope()}")
        self.root.geometry(f"{self.px(1000)}x{self.px(640)}")
        self.root.minsize(self.px(600), self.px(360))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.style_widgets()

        frame = ttk.Frame(self.root, padding=self.px(12))
        frame.pack(fill="both", expand=True)
        self.build_summary(frame)
        self.build_status(frame)
        self.build_table(frame)
        self.build_menu()

        threading.Thread(target=self.scan, daemon=True).start()
        self.saver = threading.Thread(target=self.download_worker, daemon=True)
        self.saver.start()
        self.root.after(100, self.poll)

    def px(self, n):
        return round(n * self.scale)

    def scope(self):
        if len(self.folders) == 1:
            return self.folders[0].path
        return f"{len(self.folders)} folders"

    def style_widgets(self):
        base = tkfont.nametofont("TkDefaultFont")
        self.headline = base.copy()
        self.headline.configure(size=round(base.cget("size") * 1.6), weight="bold")
        style = ttk.Style(self.root)
        # ttk's row height is fixed in pixels and does not follow the font on a scaled display.
        style.configure("Treeview", rowheight=base.metrics("linespace") + self.px(6))

    # --- layout -----------------------------------------------------------------------

    def build_summary(self, parent):
        summary = ttk.Frame(parent)
        summary.pack(fill="x")
        self.total = ttk.Label(summary, text="Looking for ZIP files...", font=self.headline)
        self.total.pack(anchor="w")
        self.detail = ttk.Label(summary, text=f"Listing the files in {self.scope()}")
        self.detail.pack(anchor="w", pady=(self.px(2), 0))
        self.note = ttk.Label(summary, text="", foreground="gray40")
        self.progress = ttk.Progressbar(summary, mode="indeterminate")
        self.progress.pack(fill="x", pady=(self.px(8), 0))
        self.progress.start(15)

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(self.px(10), 0))
        ttk.Label(bar, text="Filter by file name:").pack(side="left")
        self.filter_text = tk.StringVar()
        self.filter_text.trace_add("write", lambda *_: self.schedule_filter())
        entry = ttk.Entry(bar, textvariable=self.filter_text)
        entry.pack(side="left", fill="x", expand=True, padx=(self.px(6), 0))
        entry.bind("<Escape>", lambda e: self.filter_text.set(""))
        entry.focus_set()
        self.shown = ttk.Label(bar, text="", foreground="gray40")
        self.shown.pack(side="left", padx=(self.px(10), 0))

    def build_status(self, parent):
        # Packed before the table so the table, not the status line, gives way when the window shrinks.
        bar = ttk.Frame(parent)
        bar.pack(side="bottom", fill="x", pady=(self.px(8), 0))
        self.status = ttk.Label(bar, text="Right-click a file to save it to your Downloads folder.",
                                foreground="gray40")
        self.status.pack(side="left", fill="x", expand=True)

    def build_table(self, parent):
        table = ttk.Frame(parent)
        table.pack(fill="both", expand=True, pady=(self.px(10), 0))
        self.tree = ttk.Treeview(table, columns=("zip", "path", "name", "size"), show="headings",
                                 selectmode="extended")
        for column, text, width, anchor, stretch in (
            ("zip", "ZIP file", 220, "w", True),
            ("path", "Path in ZIP", 300, "w", True),
            ("name", "File name", 280, "w", True),
            ("size", "Size", 90, "e", False),
        ):
            self.tree.heading(column, text=text, anchor=anchor)
            self.tree.column(column, width=self.px(width), minwidth=self.px(60), anchor=anchor, stretch=stretch)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<App>", lambda e: self.open_menu_at_selection())
        self.tree.bind("<Shift-F10>", lambda e: self.open_menu_at_selection())

    def build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Download", command=self.download_selected)
        self.menu.add_command(label="Show ZIP in MEGA Explorer", command=self.reveal_selected)

    # --- reading the ZIPs, off the UI thread ------------------------------------------

    def scan(self):
        try:
            zips, seen = [], set()
            for folder in self.folders:
                for item in self.ctx.descendants(folder, type="file", fields=ZIP_FIELDS):
                    if self.closing.is_set():
                        return
                    if item.name.lower().endswith(".zip") and item.handle not in seen:
                        seen.add(item.handle)
                        zips.append(item)
            zips.sort(key=lambda z: z.path.casefold())
            self.updates.put(("zips", len(zips)))
            for item in zips:
                if self.closing.is_set():
                    return
                self.updates.put(("reading", item))
                try:
                    with self.remote(item) as remote:
                        entries = list_entries(remote)
                except Cancelled:
                    return
                except RpcError as e:
                    if e.code == 0:      # the app closed the connection
                        return
                    self.updates.put(("failed", (item, e.message)))
                    continue
                except Exception as e:  # a damaged or unsupported ZIP must not end the scan
                    self.updates.put(("failed", (item, f"{type(e).__name__}: {e}")))
                    continue
                self.updates.put(("zip", (item, entries)))
            self.updates.put(("done", None))
        except RpcError as e:
            self.updates.put(("error", e.message))

    def remote(self, item):
        return RemoteFile(item.size,
                          lambda offset, length: self.ctx.read_range(item, offset, length),
                          lambda offset, length: self.ctx.fetch_file(item, offset=offset, length=length))

    def poll(self):
        try:
            for _ in range(200):
                kind, value = self.updates.get_nowait()
                if kind == "zips":
                    self.start_reading(value)
                elif kind == "reading":
                    self.detail.config(text=f"Reading {value.path}")
                elif kind == "zip":
                    self.add_zip(*value)
                elif kind == "failed":
                    item, reason = value
                    print(f"could not read {item.path}: {reason}", file=sys.stderr)
                    self.failed.append(item)
                    self.zips_done += 1
                    self.update_counts()
                elif kind == "done":
                    self.finish()
                elif kind == "error":
                    self.stop_progress()
                    self.total.config(text="Could not list the files")
                    self.detail.config(text=value)
                elif kind == "status":
                    self.status.config(text=value)
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(100, self.poll)

    def start_reading(self, count):
        self.zips_total = count
        self.progress.stop()
        self.progress.config(mode="determinate", maximum=max(count, 1), value=0)
        if count == 0:
            self.finish()
        else:
            self.update_counts()

    def add_zip(self, item, entries):
        start = len(self.rows)
        self.rows.extend((item, entry) for entry in entries)
        for index in range(start, len(self.rows)):
            self.insert_if_shown(index)
        self.zips_done += 1
        self.update_counts()

    def update_counts(self):
        self.progress.config(value=self.zips_done)
        self.total.config(text=f"{len(self.rows):,} files in {self.zips_done:,} of {self.zips_total:,} ZIPs")
        self.update_shown()
        if self.failed:
            names = ", ".join(z.name for z in self.failed[:3])
            more = f" and {len(self.failed) - 3:,} more" if len(self.failed) > 3 else ""
            self.note.config(text=f"Could not read {len(self.failed):,} ZIP(s): {names}{more}")
            self.note.pack(anchor="w", pady=(self.px(2), 0), before=self.progress)

    def finish(self):
        self.stop_progress()
        if not self.zips_total:
            self.total.config(text="No ZIP files")
            self.detail.config(text=f"No ZIP file in {self.scope()}.")
        else:
            self.total.config(text=f"{len(self.rows):,} files in {self.zips_total:,} ZIPs")
            self.detail.config(text=f"Every ZIP in {self.scope()} has been read.")

    def stop_progress(self):
        self.progress.stop()
        self.progress.pack_forget()

    # --- the filter -------------------------------------------------------------------

    def schedule_filter(self):
        if self.filter_job is not None:
            self.root.after_cancel(self.filter_job)
        self.filter_job = self.root.after(FILTER_DELAY_MS, self.apply_filter)

    def apply_filter(self):
        self.filter_job = None
        terms = filter_terms(self.filter_text.get())
        if terms == self.terms:
            return
        self.terms = terms
        self.tree.delete(*self.tree.get_children(""))
        for index in range(len(self.rows)):
            self.insert_if_shown(index)
        self.update_shown()

    def insert_if_shown(self, index):
        item, entry = self.rows[index]
        if self.terms and not matches(entry.name, self.terms):
            return
        self.tree.insert("", "end", iid=str(index),
                         values=(item.name, entry.path, entry.name, format_size(entry.size)))

    def update_shown(self):
        if self.terms:
            self.shown.config(text=f"{len(self.tree.get_children('')):,} shown")
        else:
            self.shown.config(text="")

    # --- the menu ---------------------------------------------------------------------

    def selected_rows(self):
        return [self.rows[int(iid)] for iid in self.tree.selection()]

    def on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        self.tree.focus(row)
        self.popup(event.x_root, event.y_root)

    def open_menu_at_selection(self):
        selection = self.tree.selection()
        if not selection:
            return
        box = self.tree.bbox(selection[0])
        x, y = (box[0], box[1] + box[3]) if box else (0, 0)
        self.popup(self.tree.winfo_rootx() + x + self.px(20), self.tree.winfo_rooty() + y)

    def popup(self, x, y):
        rows = self.selected_rows()
        self.menu.entryconfig(0, label=f"Download {len(rows):,} files" if len(rows) > 1 else "Download")
        zips = {item.handle for item, _ in rows}
        self.menu.entryconfig(1, state="normal" if len(zips) == 1 else "disabled")
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def reveal_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        try:
            self.ctx.reveal(rows[0][0])
        except RpcError as e:
            self.status.config(text=f"Could not show {rows[0][0].path}: {e.message}")

    # --- saving a file out of its ZIP -------------------------------------------------

    def download_selected(self):
        rows = self.selected_rows()
        for row in rows:
            self.downloads.put(row)
        if rows and not self.downloading.is_set():
            self.status.config(text=f"Downloading {rows[0][1].name}...")

    def download_worker(self):
        while True:
            item, entry = self.downloads.get()
            if self.closing.is_set():
                return
            self.downloading.set()
            self.updates.put(("status", f"Downloading {entry.name} ({format_size(entry.size)}) from {item.name}..."))
            try:
                path = self.save(item, entry)
                if path is not None:
                    self.updates.put(("status", f"Saved {path}"))
            except Cancelled:
                return
            except RpcError as e:
                self.updates.put(("status", f"Could not download {entry.name}: {e.message}"))
            except Exception as e:  # an encrypted or unsupported entry must not stop the worker
                print(f"could not extract {entry.name} from {item.path}: {e!r}", file=sys.stderr)
                self.updates.put(("status", f"Could not download {entry.name}: {e}"))
            finally:
                if self.downloads.empty():
                    self.downloading.clear()

    def save(self, item, entry):
        folder = downloads_folder()
        os.makedirs(folder, exist_ok=True)
        part = None
        try:
            with self.remote(item) as remote:
                target = unique_path(folder, safe_file_name(entry.name))
                part = target + ".part"
                with open(part, "wb") as out:
                    done = extract(remote, entry.info, out, self.closing.is_set)
                if not done:
                    return None
                # Another save may have taken the name while this one ran.
                target = unique_path(folder, os.path.basename(target))
                os.replace(part, target)
                part = None
                return target
        finally:
            if part is not None and os.path.exists(part):
                os.remove(part)

    def close(self):
        self.closing.set()
        self.downloads.put((None, None))
        self.root.destroy()

    def run(self):
        self.root.mainloop()


@plugin.command("search")
def search(ctx):
    window = Window(ctx)
    window.run()
    # A download writing its file stops at the next chunk and removes its .part; one
    # still waiting on MEGA has written nothing yet and is left to die with the process.
    window.saver.join(timeout=5)
    return None


if __name__ == "__main__":
    plugin.run()
