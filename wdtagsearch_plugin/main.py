"""WD Tag Search: search the files by WD Tagger's tags and show the matches as a
grid of thumbnails. The tags of the whole drive, or of the folders settings.json
names (scope.py), are listed once, at start, and a search runs over that list in
memory, with suggestions drawn from the tags already on the files and a live count. The query can also be run in the app's current tab.
The index and the query rules are in tagquery.py.
"""

import ctypes
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

import scope
from megaexplorer_plugin import NoThumbnail, Plugin, RpcError
from tagquery import RATING_PREFIX, RATINGS, File, TagIndex, query_text

plugin = Plugin()

FIELDS = ["name", "tags", "mtime", "hasThumbnail"]
PAGE = 40
TILE = 160          # target tile size in px at 100% scaling; MEGA's thumbnails are 200 px squares
POPUP_ROWS = 10
TOOLTIP_DELAY = 400  # ms
RESIZE_DELAY = 150   # ms of no resizing before the thumbnails are scaled again
PLACEHOLDER = "#d9d9d9"
SELECTED = "#0078d4"
# The app's thumbnail service runs 4 fetches at once; more workers only queue there,
# past the point where a stale request could still be skipped.
THUMB_WORKERS = 4
NAVIGATION_KEYS = ("Up", "Down", "Return", "Tab", "Escape", "Shift_L", "Shift_R")


def make_dpi_aware():
    # Without this Windows bitmap-stretches the window on a scaled display, and
    # the text comes out blurred.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def find_root(ctx):
    item = ctx.items[0]
    while item.parent is not None:
        item = ctx.get(item.parent, fields=["parent"])
    return item


def parent_path(path):
    head = path.rsplit("/", 1)[0]
    return head or "/"


class Tooltip:
    """A borderless label that follows the pointer."""

    def __init__(self, root):
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.withdraw()
        self.label = tk.Label(self.window, justify="left", background="#ffffe1", relief="solid",
                              borderwidth=1, padx=6, pady=4)
        self.label.pack()

    def show(self, text, x, y):
        self.label.config(text=text)
        self.window.geometry(f"+{x + 16}+{y + 16}")
        self.window.deiconify()
        self.window.lift()

    def hide(self):
        self.window.withdraw()


class Window:
    def __init__(self, ctx):
        self.ctx = ctx
        self.index = TagIndex()
        self.terms = []
        self.loaded = False
        self.closing = threading.Event()
        self.updates = queue.Queue()
        self.thumb_requests = queue.Queue()
        self.drive_root = find_root(ctx)
        self.results = []        # every File the last search found, newest first
        self.generation = 0      # bumped whenever the tiles are replaced
        self.tiles = []          # the Files shown
        self.images = {}         # tile number -> PhotoImage, kept referenced
        self.originals = {}      # tile number -> the thumbnail as fetched, to scale on resize
        self.paths = {}          # handle -> path, read when a tooltip first needs it
        self.resize_job = None
        self.selected = None     # tile number
        self.hovered = None
        self.hover_job = None
        self.pointer = (0, 0)
        self.columns = 1
        self.suggestion_keys = []

        make_dpi_aware()
        self.root = tk.Tk()
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.base = self.px(TILE)
        self.tile = self.base
        self.root.title("WD Tag Search")
        self.root.geometry(f"{self.px(960)}x{self.px(760)}")
        self.root.minsize(self.px(480), self.px(420))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.root, padding=self.px(12))
        frame.pack(fill="both", expand=True)
        self.build_query(frame)
        self.build_footer(frame)
        self.build_grid(frame)
        self.build_popup()
        self.tooltip = Tooltip(self.root)
        self.root.bind("<Configure>", lambda e: self.place_popup())

        self.refresh()
        for _ in range(THUMB_WORKERS):
            threading.Thread(target=self.fetch_thumbnails, daemon=True).start()
        threading.Thread(target=self.load, daemon=True).start()
        self.root.after(100, self.poll)

    def px(self, n):
        return round(n * self.scale)

    # --- layout -----------------------------------------------------------------------

    def build_query(self, parent):
        self.status = ttk.Label(parent, text="Counting tags...")
        self.status.pack(anchor="w")

        rating_row = ttk.Frame(parent)
        rating_row.pack(fill="x", pady=(self.px(8), 0))
        ttk.Label(rating_row, text="Rating:").pack(side="left", padx=(0, self.px(6)))
        self.rating = ttk.Combobox(rating_row, state="readonly", width=24)
        self.rating.pack(side="left")
        self.rating.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.label_ratings()

        self.chips = ttk.Frame(parent)
        self.chips.pack(fill="x", pady=(self.px(8), self.px(4)))

        entry_row = ttk.Frame(parent)
        entry_row.pack(fill="x")
        self.entry = ttk.Entry(entry_row)
        self.entry.pack(side="left", fill="x", expand=True)
        self.search_button = ttk.Button(entry_row, text="Search", command=self.search)
        self.search_button.pack(side="left", padx=(self.px(6), 0))
        self.hits = ttk.Label(entry_row, text="", width=24, font=("Segoe UI", 10, "bold"))
        self.hits.pack(side="left", padx=(self.px(10), 0))
        self.entry.bind("<KeyRelease>", self.on_key)
        self.entry.bind("<Return>", self.on_return)
        self.entry.bind("<Shift-Return>", self.accept_typed)
        self.entry.bind("<Tab>", self.on_tab)
        self.entry.bind("<Down>", lambda e: self.move_selection(1))
        self.entry.bind("<Up>", lambda e: self.move_selection(-1))
        self.entry.bind("<Escape>", self.on_escape)
        self.entry.bind("<BackSpace>", self.on_backspace)
        self.entry.bind("<FocusOut>", lambda e: self.root.after(200, self.hide_popup_unless_focused))
        self.entry.focus_set()

        query_row = ttk.Frame(parent)
        query_row.pack(fill="x", pady=(self.px(6), 0))
        ttk.Label(query_row, text="Query:", foreground="gray40").pack(side="left", padx=(0, self.px(6)))
        self.query = ttk.Entry(query_row)
        self.query.pack(side="left", fill="x", expand=True)
        ttk.Button(query_row, text="Search in MEGA Explorer", command=self.search_in_app).pack(
            side="left", padx=(self.px(6), 0))
        ttk.Button(query_row, text="Clear", command=self.clear).pack(side="left", padx=(self.px(6), 0))

    def build_footer(self, parent):
        # Packed before the grid so the grid, not the footer, gives way when the window shrinks.
        bar = ttk.Frame(parent)
        bar.pack(side="bottom", fill="x", pady=(self.px(8), 0))
        self.more_button = ttk.Button(bar, text="Load more", command=self.load_more, state="disabled")
        self.more_button.pack(side="left")
        self.count = ttk.Label(bar, text="", foreground="gray40")
        self.count.pack(side="left", padx=(self.px(10), 0))
        ttk.Label(bar, text="Double-click to open a file in MEGA Explorer; right-click for more",
                  foreground="gray40").pack(side="right")

    def build_grid(self, parent):
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, pady=(self.px(10), 0))
        self.canvas = tk.Canvas(holder, highlightthickness=0, borderwidth=0, background="white",
                                takefocus=True, yscrollincrement=self.tile // 2)
        scroll = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda e: self.set_hovered(None))
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Double-Button-1>", lambda e: self.open(self.tile_at(e)))
        self.canvas.bind("<Return>", lambda e: self.open(self.selected))
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Open", command=lambda: self.open(self.selected))
        self.menu.add_command(label="Show in MEGA Explorer", command=lambda: self.reveal(self.selected))

    def build_popup(self):
        self.popup = tk.Toplevel(self.root)
        self.popup.overrideredirect(True)
        self.popup.withdraw()
        self.suggestions = tk.Listbox(self.popup, height=POPUP_ROWS, activestyle="none",
                                      exportselection=False, relief="solid", borderwidth=1)
        self.suggestions.pack(fill="both", expand=True)
        # A press on the list would take the focus from the entry, and the class
        # binding selects only on release; accept straight away instead.
        self.suggestions.bind("<Button-1>", self.on_popup_click)
        self.suggestions.bind("<Motion>", self.on_popup_motion)

    # --- counting, off the UI thread ----------------------------------------------

    def load(self):
        try:
            paths = scope.load_folders()
            folders, missing = scope.folders_to_list(self.ctx, self.drive_root, paths)
            if not folders:
                self.updates.put(("error", f"none of the folders in settings.json was found: "
                                           f"{', '.join(missing)}"))
                return
            index = TagIndex()
            n = 0
            for folder in folders:
                for item in self.ctx.descendants(folder, type="file", fields=FIELDS):
                    if self.closing.is_set():
                        return
                    index.add(item.tags, File(item.handle, item.name, item.mtime, bool(item.has_thumbnail)))
                    n += 1
                    if n % 1000 == 0:
                        self.updates.put(("progress", n))
            self.updates.put(("done", (index, scope.describe(paths, missing))))
        except scope.SettingsError as e:
            self.updates.put(("error", str(e)))
        except RpcError as e:
            self.updates.put(("error", e.message))

    def poll(self):
        try:
            while True:
                kind, value = self.updates.get_nowait()
                if kind == "progress":
                    self.status.config(text=f"Counting tags... {value:,} files")
                elif kind == "done":
                    self.index, note = value
                    self.loaded = True
                    self.status.config(text=f"{self.index.files:,} files, {len(self.index.files_by_word):,} "
                                            f"distinct tags (counted at start).{note}")
                    self.label_ratings()
                    self.refresh()
                elif kind == "thumb":
                    self.on_thumbnail(*value)
                else:
                    self.status.config(text=f"Could not count tags: {value}")
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(100, self.poll)

    # --- editing ------------------------------------------------------------------

    def on_key(self, event):
        if event.keysym not in NAVIGATION_KEYS:
            self.refresh_suggestions()

    def popup_shown(self):
        return self.popup.winfo_viewable()

    def move_selection(self, step):
        if not self.popup_shown():
            self.refresh_suggestions(force=True)
            return "break"
        size = self.suggestions.size()
        current = self.suggestions.curselection()
        index = (current[0] + step) % size if current else 0
        self.select_suggestion(index)
        return "break"

    def select_suggestion(self, index):
        self.suggestions.selection_clear(0, "end")
        self.suggestions.selection_set(index)
        self.suggestions.see(index)

    def on_return(self, _event):
        if self.popup_shown() and self.suggestions.curselection():
            return self.accept()
        if self.entry.get().strip():
            return self.accept_typed()
        self.search()
        return "break"

    def on_tab(self, _event):
        if self.popup_shown() and self.suggestions.curselection():
            return self.accept()
        return None

    def on_escape(self, _event):
        if self.popup_shown():
            self.hide_popup()
            return "break"
        return None

    def on_popup_click(self, event):
        index = self.suggestions.nearest(event.y)
        if 0 <= index < len(self.suggestion_keys):
            self.select_suggestion(index)
            self.accept()
        self.entry.focus_set()
        return "break"

    def on_popup_motion(self, event):
        index = self.suggestions.nearest(event.y)
        if 0 <= index < len(self.suggestion_keys):
            self.select_suggestion(index)

    def accept_typed(self, _event=None):
        self.suggestions.selection_clear(0, "end")
        return self.accept()

    def accept(self, _event=None):
        current = self.suggestions.curselection()
        if current and self.popup_shown():
            term = self.index.name(self.suggestion_keys[current[0]])
        else:
            term = self.entry.get().strip().replace('"', "")
        if term and term.lower() not in (t.lower() for t in self.terms):
            self.terms.append(term)
        self.entry.delete(0, "end")
        self.refresh()
        return "break"

    def on_backspace(self, _event):
        if not self.entry.get() and self.terms:
            self.terms.pop()
            self.refresh()
            return "break"
        return None

    def remove(self, term):
        self.terms.remove(term)
        self.refresh()
        self.entry.focus_set()

    def clear(self):
        self.terms.clear()
        self.rating.current(0)
        self.entry.delete(0, "end")
        self.refresh()
        self.entry.focus_set()

    def label_ratings(self):
        """Each rating with its file count, once counted."""
        selected = max(self.rating.current(), 0)
        labels = ["All"] + [
            f"{r} ({self.index.matches([RATING_PREFIX + r]):,})" if self.loaded else r for r in RATINGS]
        self.rating.config(values=labels)
        self.rating.current(selected)

    def query_terms(self):
        index = self.rating.current()
        rating = [RATING_PREFIX + RATINGS[index - 1]] if index > 0 else []
        return self.terms + rating

    def refresh(self):
        for chip in self.chips.winfo_children():
            chip.destroy()
        for term in self.terms:
            ttk.Button(self.chips, text=f"{term}  ×", command=lambda t=term: self.remove(t)).pack(
                side="left", padx=(0, self.px(4)))

        terms = self.query_terms()
        self.query.delete(0, "end")
        self.query.insert(0, query_text(terms))
        if not terms:
            self.hits.config(text="")
        elif self.loaded:
            self.hits.config(text=f"→ {self.index.matches(terms):,} files")
        else:
            self.hits.config(text="→ (counting...)")
        self.refresh_suggestions()

    # --- the suggestion popup -----------------------------------------------------

    def refresh_suggestions(self, force=False):
        text = self.entry.get().strip()
        if not text and not force:
            self.hide_popup()
            return
        exclude = {t.lower() for t in self.terms}
        self.suggestion_keys = self.index.suggest(text, exclude)
        self.suggestions.delete(0, "end")
        for key in self.suggestion_keys:
            self.suggestions.insert("end", f"{self.index.label(key)}   ({self.index.count(key):,})")
        if not self.suggestion_keys:
            self.hide_popup()
            return
        self.suggestions.config(height=min(POPUP_ROWS, len(self.suggestion_keys)))
        self.select_suggestion(0)
        self.show_popup()

    def show_popup(self):
        self.popup.deiconify()
        self.place_popup()
        self.popup.lift()

    def place_popup(self):
        if not self.popup_shown():
            return
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        self.popup.geometry(f"{self.entry.winfo_width()}x{self.suggestions.winfo_reqheight()}+{x}+{y}")

    def hide_popup(self):
        self.popup.withdraw()

    def hide_popup_unless_focused(self):
        if self.closing.is_set():
            return
        if self.root.focus_get() is not self.entry:
            self.hide_popup()

    # --- searching ------------------------------------------------------------------

    def search(self):
        self.hide_popup()
        if not self.loaded:
            self.status.config(text="Still counting tags; search again in a moment.")
            return
        terms = self.query_terms()
        if not terms:
            self.status.config(text="Add a tag or pick a rating first.")
            return
        self.results = self.index.search(terms)
        self.status.config(text=f"{len(self.results):,} files match {query_text(terms)}, newest first.")
        self.generation += 1
        self.tiles = []
        self.images = {}
        self.originals = {}
        self.selected = None
        self.set_hovered(None)
        self.canvas.yview_moveto(0)
        self.load_more()

    def search_in_app(self):
        self.hide_popup()
        try:
            self.ctx.search(self.query.get().strip())
        except RpcError as e:
            self.status.config(text=f"Could not search: {e.message}")
            return
        self.status.config(text="Searched in MEGA Explorer's current tab")

    def load_more(self):
        start = len(self.tiles)
        files = self.results[start:start + PAGE]
        self.tiles.extend(files)
        for number, file in enumerate(files, start):
            if file.has_thumbnail:
                self.thumb_requests.put((self.generation, number, file.handle))
        self.redraw()
        self.more_button.config(state="normal" if len(self.tiles) < len(self.results) else "disabled")
        self.count.config(text=f"Showing {len(self.tiles):,} of {len(self.results):,}")

    # --- the grid -------------------------------------------------------------------

    def on_resize(self, event):
        # As many columns as fit tiles near the target size, then stretched to fill the width.
        columns = max(1, round(event.width / self.base))
        tile = max(1, event.width // columns)
        if (columns, tile) == (self.columns, self.tile):
            return
        self.columns, self.tile = columns, tile
        self.canvas.configure(yscrollincrement=tile // 2)
        self.redraw()
        if self.resize_job is not None:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(RESIZE_DELAY, self.rescale)

    def rescale(self):
        self.resize_job = None
        for number, picture in self.originals.items():
            self.images[number] = self.photo(picture)
        self.redraw()

    def photo(self, picture):
        return ImageTk.PhotoImage(picture.resize((self.tile, self.tile), Image.LANCZOS))

    def tile_box(self, number):
        row, column = divmod(number, self.columns)
        x, y = column * self.tile, row * self.tile
        return x, y, x + self.tile, y + self.tile

    def redraw(self):
        self.canvas.delete("all")
        for number in range(len(self.tiles)):
            self.draw_tile(number)
        rows = -(-len(self.tiles) // self.columns)
        self.canvas.configure(scrollregion=(0, 0, self.columns * self.tile, rows * self.tile))
        self.draw_selection()

    def draw_tile(self, number):
        x0, y0, x1, y1 = self.tile_box(number)
        tag = f"tile{number}"
        self.canvas.delete(tag)
        photo = self.images.get(number)
        # Until rescale() runs after a resize, the old-size image is drawn rather than none.
        if photo is not None:
            self.canvas.create_image(x0, y0, image=photo, anchor="nw", tags=tag)
        else:
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=PLACEHOLDER, outline="#c4c4c4", tags=tag)
            self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=self.tiles[number].name,
                                    width=self.tile - self.px(8), fill="gray30", tags=tag)

    def draw_selection(self):
        self.canvas.delete("selection")
        if self.selected is None:
            return
        x0, y0, x1, y1 = self.tile_box(self.selected)
        width = self.px(3)
        # Drawn inside the tile, so it covers no neighbour and needs no gap between tiles.
        inset = width / 2
        self.canvas.create_rectangle(x0 + inset, y0 + inset, x1 - inset, y1 - inset,
                                     outline=SELECTED, width=width, tags="selection")

    def tile_at(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        column = int(x // self.tile)
        if column >= self.columns or x < 0 or y < 0:
            return None
        number = int(y // self.tile) * self.columns + column
        return number if number < len(self.tiles) else None

    def on_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        self.set_hovered(None)

    def on_click(self, event):
        self.canvas.focus_set()
        self.selected = self.tile_at(event)
        self.draw_selection()

    def on_right_click(self, event):
        number = self.tile_at(event)
        if number is None:
            return
        self.canvas.focus_set()
        self.selected = number
        self.draw_selection()
        self.set_hovered(None)
        self.menu.tk_popup(event.x_root, event.y_root)

    # --- tooltip ----------------------------------------------------------------------

    def on_motion(self, event):
        number = self.tile_at(event)
        if number != self.hovered:
            self.set_hovered(number)
        if number is not None:
            self.pointer = (event.x_root, event.y_root)

    def set_hovered(self, number):
        self.hovered = number
        self.tooltip.hide()
        if self.hover_job is not None:
            self.root.after_cancel(self.hover_job)
            self.hover_job = None
        if number is not None:
            self.hover_job = self.root.after(TOOLTIP_DELAY, self.show_tooltip)

    def path_of(self, file):
        # Listing the path for every file is what makes a listing slow; one at a time is not.
        if file.handle not in self.paths:
            try:
                self.paths[file.handle] = self.ctx.get(file.handle, fields=["path"]).path
            except RpcError:
                return ""
        return self.paths[file.handle]

    def show_tooltip(self):
        self.hover_job = None
        if self.hovered is None or self.hovered >= len(self.tiles):
            return
        file = self.tiles[self.hovered]
        lines = [file.name]
        path = self.path_of(file)
        if path:
            lines.append(parent_path(path))
        if file.mtime:
            lines.append(datetime.fromtimestamp(file.mtime).strftime("%Y-%m-%d %H:%M"))
        self.tooltip.show("\n".join(lines), *self.pointer)

    # --- thumbnails, THUMB_WORKERS at a time off the UI thread ----------------------------------

    def fetch_thumbnails(self):
        while not self.closing.is_set():
            generation, number, handle = self.thumb_requests.get()
            # Tiles replaced since the request was queued are not worth a download.
            if generation != self.generation:
                continue
            try:
                path = self.ctx.fetch_thumbnail(handle)
            except (NoThumbnail, RpcError):
                continue
            try:
                with Image.open(path) as image:
                    side = min(image.size)
                    picture = ImageOps.fit(image.convert("RGB"), (side, side))
                path.unlink(missing_ok=True)
            except OSError:
                continue
            self.updates.put(("thumb", (generation, number, picture)))

    def on_thumbnail(self, generation, number, picture):
        if generation == self.generation and number < len(self.tiles):
            self.originals[number] = picture
            self.images[number] = self.photo(picture)
            self.draw_tile(number)
            self.canvas.tag_raise("selection")

    # --- showing a file in the app ----------------------------------------------------

    def open(self, number):
        if number is None:
            return
        file = self.tiles[number]
        try:
            self.ctx.open(file.handle)
        except RpcError as e:
            self.status.config(text=f"Could not open {file.name}: {e.message}")

    def reveal(self, number):
        if number is None:
            return
        file = self.tiles[number]
        try:
            self.ctx.reveal(file.handle)
        except RpcError as e:
            self.status.config(text=f"Could not show {file.name}: {e.message}")

    def close(self):
        self.closing.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


@plugin.command("open")
def open_window(ctx):
    Window(ctx).run()
    return None


if __name__ == "__main__":
    plugin.run()
