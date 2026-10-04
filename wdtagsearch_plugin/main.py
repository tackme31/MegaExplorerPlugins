"""WD Tag Search: build a `tag:` query over WD Tagger's tags, with suggestions
drawn from the tags already on the account's files and a live count of what it
would match, and run it in the app's current tab. The window; the index and the
query rules are in tagquery.py.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk

from megaexplorer_plugin import Plugin, RpcError
from tagquery import RATING_PREFIX, RATINGS, TagIndex, query_text

plugin = Plugin()


def find_root(ctx):
    item = ctx.items[0]
    while item.parent is not None:
        item = ctx.get(item.parent, fields=["parent"])
    return item


class Builder:
    def __init__(self, ctx):
        self.ctx = ctx
        self.index = TagIndex()
        self.terms = []
        self.loaded = False
        self.closing = threading.Event()
        self.updates = queue.Queue()
        self.drive_root = find_root(ctx)

        self.root = tk.Tk()
        self.root.title("WD Tag Search")
        self.root.geometry("560x620")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        self.status = ttk.Label(frame, text="Counting tags...")
        self.status.pack(anchor="w")

        rating_row = ttk.Frame(frame)
        rating_row.pack(fill="x", pady=(8, 0))
        ttk.Label(rating_row, text="Rating:").pack(side="left", padx=(0, 6))
        self.rating = ttk.Combobox(rating_row, state="readonly", width=24)
        self.rating.pack(side="left")
        self.rating.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.label_ratings()

        self.chips = ttk.Frame(frame)
        self.chips.pack(fill="x", pady=(8, 4))

        self.entry = ttk.Entry(frame)
        self.entry.pack(fill="x")
        self.entry.bind("<KeyRelease>", self.on_key)
        self.entry.bind("<Return>", self.accept)
        self.entry.bind("<Shift-Return>", self.accept_typed)
        self.entry.bind("<Tab>", self.accept)
        self.entry.bind("<Down>", lambda e: self.move_selection(1))
        self.entry.bind("<Up>", lambda e: self.move_selection(-1))
        self.entry.bind("<BackSpace>", self.on_backspace)
        self.entry.focus_set()

        self.suggestions = tk.Listbox(frame, height=14, activestyle="none", exportselection=False)
        self.suggestions.pack(fill="both", expand=True, pady=(4, 8))
        self.suggestions.bind("<Double-Button-1>", self.accept)
        self.suggestion_keys = []

        self.hits = ttk.Label(frame, text="", font=("Segoe UI", 11, "bold"))
        self.hits.pack(anchor="w")

        self.query = ttk.Entry(frame)
        self.query.pack(fill="x", pady=(4, 8))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Search", command=self.search).pack(side="right")
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left")

        self.refresh()
        threading.Thread(target=self.load, daemon=True).start()
        self.root.after(100, self.poll)

    # --- counting, off the UI thread ----------------------------------------------

    def load(self):
        try:
            index = TagIndex()
            files = self.ctx.descendants(self.drive_root, type="file", fields=["tags"])
            for n, item in enumerate(files, 1):
                if self.closing.is_set():
                    return
                index.add(item.tags)
                if n % 1000 == 0:
                    self.updates.put(("progress", n))
            self.updates.put(("done", index))
        except RpcError as e:
            self.updates.put(("error", e.message))

    def poll(self):
        try:
            while True:
                kind, value = self.updates.get_nowait()
                if kind == "progress":
                    self.status.config(text=f"Counting tags... {value:,} files")
                elif kind == "done":
                    self.index = value
                    self.loaded = True
                    self.status.config(
                        text=f"{value.files:,} files, {len(value.files_by_word):,} distinct tags (counted at start)")
                    self.label_ratings()
                    self.refresh()
                else:
                    self.status.config(text=f"Could not count tags: {value}")
        except queue.Empty:
            pass
        if not self.closing.is_set():
            self.root.after(100, self.poll)

    # --- editing ------------------------------------------------------------------

    def on_key(self, event):
        if event.keysym not in ("Up", "Down", "Return", "Tab", "Shift_L", "Shift_R"):
            self.refresh_suggestions()

    def move_selection(self, step):
        size = self.suggestions.size()
        if not size:
            return "break"
        current = self.suggestions.curselection()
        index = (current[0] + step) % size if current else 0
        self.suggestions.selection_clear(0, "end")
        self.suggestions.selection_set(index)
        self.suggestions.see(index)
        return "break"

    def accept_typed(self, _event=None):
        self.suggestions.selection_clear(0, "end")
        return self.accept()

    def accept(self, _event=None):
        current = self.suggestions.curselection()
        if current:
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

    def label_ratings(self):
        """Each rating with its file count, once counted."""
        selected = max(self.rating.current(), 0)
        labels = ["All"] + [
            f"{r} ({self.index.matches([RATING_PREFIX + r]):,})" if self.loaded else r for r in RATINGS]
        self.rating.config(values=labels)
        self.rating.current(selected)

    def selected_rating(self):
        """None for All."""
        index = self.rating.current()
        return RATINGS[index - 1] if index > 0 else None

    def refresh(self):
        for chip in self.chips.winfo_children():
            chip.destroy()
        for term in self.terms:
            ttk.Button(self.chips, text=f"{term}  ×", command=lambda t=term: self.remove(t)).pack(
                side="left", padx=(0, 4))

        rating = self.selected_rating()
        query_terms = list(self.terms)
        if rating is not None:
            query_terms.append(RATING_PREFIX + rating)

        self.query.delete(0, "end")
        self.query.insert(0, query_text(query_terms))
        if not query_terms:
            self.hits.config(text="")
        elif self.loaded:
            self.hits.config(text=f"→ {self.index.matches(query_terms):,} files match in the Cloud Drive")
        else:
            self.hits.config(text="→ (counting...)")
        self.refresh_suggestions()

    def refresh_suggestions(self):
        exclude = {t.lower() for t in self.terms}
        self.suggestion_keys = self.index.suggest(self.entry.get().strip(), exclude)
        self.suggestions.delete(0, "end")
        for key in self.suggestion_keys:
            self.suggestions.insert("end", f"{self.index.label(key)}   ({self.index.count(key):,})")
        if self.suggestion_keys and self.entry.get().strip():
            self.suggestions.selection_set(0)

    # --- running the query in the app ------------------------------------------

    def search(self):
        try:
            self.ctx.search(self.query.get().strip())
        except RpcError as e:
            self.status.config(text=f"Could not search: {e.message}")
            return
        self.status.config(text="Searched in MEGA Explorer's current tab")

    def close(self):
        self.closing.set()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


@plugin.command("open")
def open_builder(ctx):
    Builder(ctx).run()
    return None


if __name__ == "__main__":
    plugin.run()
