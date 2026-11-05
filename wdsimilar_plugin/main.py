"""WD Similar: shows the files whose WD Tagger tags are most like a chosen file's,
as a grid of thumbnails, in a window that stays open: the tags of the whole drive,
or of the folders settings.json names (scope.py), are listed once, and any file
selected in the app can then be searched from the window. Read-only. The ranking
is in similar.py.
"""

import ctypes
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk

import scope
from megaexplorer_plugin import CommandError, NoThumbnail, Plugin, RpcError
from similar import SimilarityIndex, fingerprint, terms_of

plugin = Plugin()

FIELDS = ["name", "path", "tags", "size", "crc", "hasThumbnail"]
PAGE = 20
TILE = 160          # target tile size in px at 100% scaling; MEGA's thumbnails are 200 px squares
TOOLTIP_DELAY = 400  # ms
RESIZE_DELAY = 150   # ms of no resizing before the thumbnails are scaled again
PLACEHOLDER = "#d9d9d9"
SELECTED = "#0078d4"
# The app's thumbnail service runs 4 fetches at once; more workers only queue there,
# past the point where a stale request could still be skipped.
THUMB_WORKERS = 4


def make_dpi_aware():
    # Without this Windows bitmap-stretches the window on a scaled display, and
    # the text comes out blurred.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def find_root(ctx, item):
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
    def __init__(self, ctx, item):
        self.ctx = ctx
        self.closing = threading.Event()
        self.updates = queue.Queue()
        self.thumb_requests = queue.Queue()
        self.root_item = find_root(ctx, item)
        self.index = None
        self.ranking = None      # every match of the current query
        self.visible = None      # the ranking as shown: copies left out or not
        self.timing = ""
        self.scope_note = ""     # scope.describe() of the folders the index was listed from
        self.generation = 0      # bumped whenever the tiles are replaced
        self.tiles = []          # the Matches shown, in rank order
        self.images = {}         # tile number or "query" -> PhotoImage, kept referenced
        self.originals = {}      # tile number -> the thumbnail as fetched, to scale on resize
        self.resize_job = None
        self.selected = None     # tile number
        self.hovered = None
        self.hover_job = None
        self.pointer = (0, 0)
        self.busy = True
        self.columns = 1
        self.query = None        # (item, terms, fingerprint)

        make_dpi_aware()
        self.root = tk.Tk()
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.base = self.px(TILE)
        self.tile = self.base
        self.root.title("WD Similar")
        self.root.geometry(f"{self.px(960)}x{self.px(760)}")
        self.root.minsize(self.px(480), self.px(420))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.root, padding=self.px(12))
        frame.pack(fill="both", expand=True)
        self.build_query(frame)
        self.build_toolbar(frame)
        self.build_footer(frame)
        self.build_grid(frame)
        self.tooltip = Tooltip(self.root)

        for _ in range(THUMB_WORKERS):
            threading.Thread(target=self.fetch_thumbnails, daemon=True).start()
        self.set_query(item)
        self.start_listing()
        self.root.after(100, self.poll)

    def px(self, n):
        return round(n * self.scale)

    # --- layout -----------------------------------------------------------------------

    def build_query(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x")
        self.query_image = ttk.Label(top)
        self.query_image.pack(side="left", padx=(0, self.px(10)))
        text = ttk.Frame(top)
        text.pack(side="left", fill="x", expand=True)
        self.query_name = ttk.Label(text, font=("TkDefaultFont", 11, "bold"))
        self.query_name.pack(anchor="w")
        self.query_path = ttk.Label(text, foreground="gray40")
        self.query_path.pack(anchor="w")
        self.query_words = ttk.Label(text, foreground="gray40", wraplength=self.px(760))
        self.query_words.pack(anchor="w", pady=(self.px(2), 0))

    def build_toolbar(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(self.px(10), 0))
        self.search_button = ttk.Button(bar, text="Search selected", command=self.search_selected,
                                        state="disabled")
        self.search_button.pack(side="left")
        self.rebuild_button = ttk.Button(bar, text="Rebuild index", command=self.start_listing,
                                         state="disabled")
        self.rebuild_button.pack(side="left", padx=(self.px(6), 0))
        self.hide_copies = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Hide copies of this file", variable=self.hide_copies,
                        command=self.show_ranking).pack(side="left", padx=(self.px(14), 0))
        self.status = ttk.Label(parent, text="")
        self.status.pack(anchor="w", pady=(self.px(8), 0))

    def build_footer(self, parent):
        # Packed before the grid so the grid, not the footer, gives way when the window shrinks.
        bar = ttk.Frame(parent)
        bar.pack(side="bottom", fill="x", pady=(self.px(8), 0))
        self.more_button = ttk.Button(bar, text="Load more", command=self.load_more, state="disabled")
        self.more_button.pack(side="left")
        self.count = ttk.Label(bar, text="", foreground="gray40")
        self.count.pack(side="left", padx=(self.px(10), 0))
        ttk.Label(bar, text="Double-click to open a file in MEGA Explorer; right-click to search from it",
                  foreground="gray40").pack(side="right")

    def build_grid(self, parent):
        holder = ttk.Frame(parent)
        holder.pack(fill="both", expand=True, pady=(self.px(8), 0))
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
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Return>", lambda e: self.reveal(self.selected))
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Find similar images", command=lambda: self.search_tile(self.selected))
        self.menu.add_command(label="Show in MEGA Explorer", command=lambda: self.reveal(self.selected))

    # --- the query ------------------------------------------------------------------

    def set_query(self, item):
        terms = terms_of(item.tags)
        self.query = (item, terms, fingerprint(item.size, item.crc))
        self.query_name.config(text=item.name)
        self.query_path.config(text=item.path)
        self.query_words.config(text=f"{len(terms)} words: {' '.join(terms)}")
        self.query_image.config(image="")
        self.images.pop("query", None)
        if item.has_thumbnail:
            self.thumb_requests.put((self.generation, "query", item.handle))

    def search_selected(self):
        try:
            selected = self.ctx.selection(fields=FIELDS + ["type"])
        except RpcError as e:
            self.status.config(text=f"Could not read the selection: {e.message}")
            return
        item = next((i for i in selected if i.is_file and terms_of(i.tags)), None)
        if item is None:
            self.status.config(text="Select an image or video tagged by WD Tagger in MEGA Explorer, "
                                    "then press Search selected.")
            return
        self.set_query(item)
        self.start_ranking()

    def search_tile(self, number):
        if number is None or self.busy:
            return
        match = self.tiles[number]
        try:
            # The tile holds what the listing saw; the query needs the tags as they are now.
            item = self.ctx.get(match.handle, fields=FIELDS + ["type"])
        except RpcError as e:
            self.status.config(text=f"Could not read {match.name}: {e.message}")
            return
        if not terms_of(item.tags):
            self.status.config(text=f"{item.name} no longer has WD Tagger tags.")
            return
        self.set_query(item)
        self.start_ranking()

    # --- listing and ranking, off the UI thread -------------------------------------

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.menu.entryconfigure("Find similar images", state=state)
        self.search_button.config(state=state)
        self.rebuild_button.config(state=state)

    def start_listing(self):
        self.set_busy(True)
        self.status.config(text="Listing the files...")
        threading.Thread(target=self.list_and_rank, args=(self.query,), daemon=True).start()

    def start_ranking(self):
        self.set_busy(True)
        self.status.config(text=f"Ranking {len(self.index):,} tagged files...")
        threading.Thread(target=self.rank, args=(self.index, self.query, 0.0), daemon=True).start()

    def list_and_rank(self, query):
        try:
            started = time.perf_counter()
            paths = scope.load_folders()
            folders, missing = scope.folders_to_list(self.ctx, self.root_item, paths)
            if not folders:
                self.updates.put(("error", f"None of the folders in settings.json was found: "
                                           f"{', '.join(missing)}"))
                return
            self.updates.put(("scope", scope.describe(paths, missing)))
            index = SimilarityIndex()
            listed = 0
            for folder in folders:
                for item in self.ctx.descendants(folder, type="file", fields=FIELDS):
                    if self.closing.is_set():
                        return
                    index.add(item.handle, item.name, item.path, item.tags, item.size, item.crc,
                              item.has_thumbnail)
                    listed += 1
                    if listed % 1000 == 0:
                        self.updates.put(("status", f"Listing the files... {listed:,}"))
            self.rank(index, query, time.perf_counter() - started)
        except scope.SettingsError as e:
            self.updates.put(("error", str(e)))
        except RpcError as e:
            self.updates.put(("error", f"Could not list the files: {e.message}"))

    def rank(self, index, query, list_seconds):
        item, terms, _fp = query
        started = time.perf_counter()
        ranking = index.rank(terms, exclude=item.handle)
        self.updates.put(("ranked", (index, query, ranking, list_seconds, time.perf_counter() - started)))

    def poll(self):
        try:
            while True:
                kind, value = self.updates.get_nowait()
                if kind == "status":
                    self.status.config(text=value)
                elif kind == "scope":
                    self.scope_note = value
                elif kind == "ranked":
                    self.on_ranked(*value)
                elif kind == "thumb":
                    self.on_thumbnail(*value)
                else:
                    self.status.config(text=value)
                    self.set_busy(False)
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(100, self.poll)

    def on_ranked(self, index, query, ranking, list_seconds, rank_seconds):
        self.index = index
        self.set_busy(False)
        if query is not self.query:
            # A stale result must never be shown under a new header.
            self.start_ranking()
            return
        self.ranking = ranking
        timing = f"Listed in {list_seconds:.1f} s, ranked in {rank_seconds:.1f} s." if list_seconds \
            else f"Ranked in {rank_seconds:.1f} s."
        self.timing = f"{len(index):,} tagged files. {timing}{self.scope_note}"
        self.show_ranking()

    # --- results --------------------------------------------------------------------

    def show_ranking(self):
        if self.ranking is None:
            return
        fp = self.query[2] if self.hide_copies.get() else None
        self.visible = self.ranking.without_copies(fp)
        hidden = len(self.ranking) - len(self.visible)
        note = f" {hidden:,} copies of this file hidden." if hidden else ""
        self.status.config(text=f"{len(self.visible):,} similar files.{note} {self.timing}")
        self.generation += 1
        self.tiles = []
        self.images = {k: v for k, v in self.images.items() if k == "query"}
        self.originals = {}
        self.selected = None
        self.set_hovered(None)
        self.canvas.yview_moveto(0)
        self.load_more()

    def load_more(self):
        start = len(self.tiles)
        matches = self.visible.page(start, PAGE)
        self.tiles.extend(matches)
        for number, match in enumerate(matches, start):
            if match.has_thumbnail:
                self.thumb_requests.put((self.generation, number, match.handle))
        self.redraw()
        self.more_button.config(state="normal" if len(self.tiles) < len(self.visible) else "disabled")
        self.count.config(text=f"Showing {len(self.tiles):,} of {len(self.visible):,}")

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

    def on_double_click(self, event):
        self.open(self.tile_at(event))

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

    def show_tooltip(self):
        self.hover_job = None
        if self.hovered is None or self.hovered >= len(self.tiles):
            return
        match = self.tiles[self.hovered]
        text = (f"{match.name}\n{parent_path(match.path)}\n"
                f"#{self.hovered + 1}   score {match.score:.3f}   "
                f"{len(match.shared)}/{match.terms} words shared")
        self.tooltip.show(text, *self.pointer)

    # --- thumbnails, THUMB_WORKERS at a time off the UI thread ----------------------------------

    def fetch_thumbnails(self):
        while not self.closing.is_set():
            generation, key, handle = self.thumb_requests.get()
            # Tiles replaced since the request was queued are not worth a download.
            if generation != self.generation and key != "query":
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
            self.updates.put(("thumb", (generation, key, picture)))

    def on_thumbnail(self, generation, key, picture):
        if key == "query":
            photo = ImageTk.PhotoImage(picture.resize((self.base, self.base), Image.LANCZOS))
            self.images["query"] = photo
            self.query_image.config(image=photo)
        elif generation == self.generation and key < len(self.tiles):
            self.originals[key] = picture
            self.images[key] = self.photo(picture)
            self.draw_tile(key)
            self.canvas.tag_raise("selection")

    # --- showing a file in the app ----------------------------------------------------

    def open(self, number):
        if number is None:
            return
        match = self.tiles[number]
        try:
            self.ctx.open(match.handle)
        except RpcError as e:
            self.status.config(text=f"Could not open {match.path}: {e.message}")

    def reveal(self, number):
        if number is None:
            return
        match = self.tiles[number]
        try:
            self.ctx.reveal(match.handle)
        except RpcError as e:
            self.status.config(text=f"Could not show {match.path}: {e.message}")

    def close(self):
        self.closing.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


@plugin.command("find")
def find(ctx):
    if len(ctx.items) != 1 or not ctx.items[0].is_file:
        raise CommandError("Select one image or video")
    item = ctx.items[0]
    if not terms_of(item.tags):
        raise CommandError(f"{item.name} has no WD Tagger tags. Tag it with WD Tagger first.")
    Window(ctx, item).run()
    return None


if __name__ == "__main__":
    plugin.run()
