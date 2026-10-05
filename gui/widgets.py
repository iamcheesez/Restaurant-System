"""Reusable building blocks shared by every page. No database access here."""
import math
import tkinter as tk
from tkinter import ttk

from gui.formatting import long_date
from gui.theme import BADGES, COLORS, FONTS


class AutoScrollbar(ttk.Scrollbar):
    """A grid-managed scrollbar that hides itself when everything fits."""

    def set(self, first, last):
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.grid_remove()
        else:
            self.grid()
        super().set(first, last)


# ------------------------------------------------------------------ window chrome

class StatusBar(ttk.Frame):
    """Bottom bar for short messages. Errors stay until the next message; others fade after a few seconds."""

    MARKERS = {"info": "subtle", "success": "primary", "error": "chili"}

    def __init__(self, parent):
        super().__init__(parent, style="StatusBar.TFrame")
        ttk.Separator(self).pack(side="top", fill="x")
        inner = ttk.Frame(self, style="StatusBar.TFrame", padding=(16, 6))
        inner.pack(fill="x")
        self.marker = tk.Frame(inner, width=8, height=8, background=COLORS["surface"])
        self.marker.pack(side="left", padx=(0, 8))
        self.message = ttk.Label(inner, style="Status.TLabel")
        self.message.pack(side="left")
        self.location = ttk.Label(inner, style="StatusMuted.TLabel")
        self.location.pack(side="right")
        self.kind, self.text, self._timer = None, "", None

    def show(self, text, kind="info", timeout=8000):
        self._cancel_timer()
        self.kind, self.text = kind, text
        self.marker.configure(background=COLORS[self.MARKERS[kind]])
        self.message.configure(text=text, style="StatusError.TLabel" if kind == "error" else "Status.TLabel")
        if timeout and kind != "error":
            self._timer = self.after(timeout, self.clear)

    def info(self, text, timeout=8000):
        self.show(text, "info", timeout)

    def success(self, text, timeout=6000):
        self.show(text, "success", timeout)

    def error(self, text):
        self.show(text, "error")

    def clear(self):
        self._cancel_timer()
        self.kind, self.text = None, ""
        self.marker.configure(background=COLORS["surface"])
        self.message.configure(text="", style="Status.TLabel")

    def set_location(self, text):
        self.location.configure(text=text)

    def _cancel_timer(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def destroy(self):
        self._cancel_timer()
        super().destroy()


class Sidebar(ttk.Frame):
    """Left navigation. The current page gets a saffron bar, a lighter background and bold text."""

    def __init__(self, parent, items, on_select):
        super().__init__(parent, style="Sidebar.TFrame", width=228)
        self.pack_propagate(False)
        brand = ttk.Frame(self, style="Sidebar.TFrame", padding=(22, 24, 20, 22))
        brand.pack(fill="x")
        ttk.Label(brand, text="Restaurant System", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Tables, orders and receipts", style="BrandSub.TLabel").pack(anchor="w", pady=(2, 0))
        self.buttons, self.bars, self.active = {}, {}, None
        for key, label in items:
            row = tk.Frame(self, background=COLORS["sidebar"])
            row.pack(fill="x", pady=1)
            bar = tk.Frame(row, width=4, background=COLORS["sidebar"])
            bar.pack(side="left", fill="y")
            button = ttk.Button(row, text=label, style="Nav.TButton", command=lambda k=key: on_select(k))
            button.pack(side="left", fill="x", expand=True)
            self.buttons[key], self.bars[key] = button, bar

    def set_active(self, key):
        self.active = key
        for k, button in self.buttons.items():
            current = k == key
            button.configure(style="NavActive.TButton" if current else "Nav.TButton")
            self.bars[k].configure(background=COLORS["saffron"] if current else COLORS["sidebar"])


class TopBar(ttk.Frame):
    """Today's date on the left; the signed-in employee and Log out on the right."""

    def __init__(self, parent, on_logout):
        super().__init__(parent, style="TopBar.TFrame")
        inner = ttk.Frame(self, style="TopBar.TFrame", padding=(28, 10, 20, 10))
        inner.pack(fill="x")
        self.date = ttk.Label(inner, style="TopBar.TLabel")
        self.date.pack(side="left")
        self.logout = ttk.Button(inner, text="Log out", style="Logout.TButton", command=on_logout)
        self.logout.pack(side="right")
        self.name = ttk.Label(inner, style="TopBarName.TLabel")
        self.name.pack(side="right", padx=(4, 16))
        ttk.Label(inner, text="Signed in as", style="TopBar.TLabel").pack(side="right")
        ttk.Separator(self).pack(side="bottom", fill="x")
        self._timer = None
        self._tick()

    def set_employee(self, name):
        self.name.configure(text=name)

    def _tick(self):
        self.date.configure(text=long_date())
        self._timer = self.after(60_000, self._tick)

    def destroy(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
        super().destroy()


class PageHeader(ttk.Frame):
    """Page title, a one-line summary, an optional back link, and the page's main actions on the right."""

    def __init__(self, parent, title, subtitle="", back=None):
        super().__init__(parent, style="Page.TFrame")
        left = ttk.Frame(self, style="Page.TFrame")
        left.pack(side="left", fill="x", expand=True)
        if back:
            ttk.Button(left, text=back[0], style="Link.TButton", command=back[1]).pack(anchor="w", pady=(0, 4))
        self.title = ttk.Label(left, text=title, style="Title.TLabel")
        self.title.pack(anchor="w")
        self.subtitle = ttk.Label(left, text=subtitle, style="Subtitle.TLabel")
        self.subtitle.pack(anchor="w", pady=(2, 0))
        self.actions = ttk.Frame(self, style="Page.TFrame")
        self.actions.pack(side="right", anchor="s")

    def set(self, title=None, subtitle=None):
        if title is not None:
            self.title.configure(text=title)
        if subtitle is not None:
            self.subtitle.configure(text=subtitle)

    def add_action(self, text, command, style="TButton"):
        button = ttk.Button(self.actions, text=text, style=style, command=command)
        button.pack(side="left", padx=(8, 0))
        return button


# ------------------------------------------------------------------ content blocks

class Card(tk.Frame):
    """A white panel with a thin border, an optional title row (with room for actions) and a body."""

    def __init__(self, parent, title=None, subtitle=None, padding=16):
        super().__init__(parent, background=COLORS["surface"], highlightthickness=1,
                         highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])
        inner = ttk.Frame(self, style="Surface.TFrame", padding=padding)
        inner.pack(fill="both", expand=True)
        self.actions = None
        if title:
            head = ttk.Frame(inner, style="Surface.TFrame")
            head.pack(fill="x", pady=(0, 10))
            text = ttk.Frame(head, style="Surface.TFrame")
            text.pack(side="left", fill="x", expand=True)
            self.title = ttk.Label(text, text=title, style="Section.TLabel")
            self.title.pack(anchor="w")
            if subtitle:
                ttk.Label(text, text=subtitle, style="SurfaceSmall.TLabel").pack(anchor="w")
            self.actions = ttk.Frame(head, style="Surface.TFrame")
            self.actions.pack(side="right")
        self.body = ttk.Frame(inner, style="Surface.TFrame")
        self.body.pack(fill="both", expand=True)


class StatStrip(tk.Frame):
    """Key figures in one panel, separated by thin dividers (not one card per number)."""

    def __init__(self, parent, stats):
        super().__init__(parent, background=COLORS["surface"], highlightthickness=1,
                         highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])
        self.values, self.notes = {}, {}
        for i, (key, caption) in enumerate(stats):
            if i:
                ttk.Separator(self, orient="vertical").pack(side="left", fill="y", pady=14)
            cell = ttk.Frame(self, style="Surface.TFrame", padding=(22, 14))
            cell.pack(side="left", fill="both", expand=True)
            ttk.Label(cell, text=caption, style="SurfaceMuted.TLabel").pack(anchor="w")
            self.values[key] = ttk.Label(cell, text="-", style="Stat.TLabel")
            self.values[key].pack(anchor="w", pady=(2, 0))
            self.notes[key] = ttk.Label(cell, text="", style="SurfaceSmall.TLabel")
            self.notes[key].pack(anchor="w")

    def set(self, key, value, note=""):
        self.values[key].configure(text=str(value))
        self.notes[key].configure(text=note)


class Badge(ttk.Label):
    """Status label that says the status in words ('Occupied', 'Paid'), with its own color."""

    def __init__(self, parent, kind="free", text=None):
        super().__init__(parent)
        self.set(kind, text)

    def set(self, kind, text=None):
        self.kind = kind
        self.configure(text=text or BADGES[kind][0], style=f"{kind}.Badge.TLabel")


class Notice(ttk.Label):
    """A full-width message strip, for example to explain why a paid order can't be changed."""

    def __init__(self, parent, text="", error=False):
        super().__init__(parent, text=text, style="NoticeError.TLabel" if error else "Notice.TLabel",
                         wraplength=900, justify="left")


class EmptyState(ttk.Frame):
    """What to show instead of a blank area: what happened and what to do next."""

    def __init__(self, parent, title, message, action=None, surface=True):
        bg = "Surface" if surface else "Page"
        super().__init__(parent, style=f"{bg}.TFrame", padding=24)
        ttk.Label(self, text=title, style="Section.TLabel" if surface else "Title.TLabel").pack(anchor="w")
        self.message = ttk.Label(self, text=message, style=f"{bg}Muted.TLabel" if surface else "Muted.TLabel",
                                 wraplength=460, justify="left")
        self.message.pack(anchor="w", pady=(4, 12))
        if action:
            ttk.Button(self, text=action[0], command=action[1]).pack(anchor="w")


class LabeledEntry(ttk.Frame):
    """A small label above an entry. Use show='*' for passwords."""

    def __init__(self, parent, label, width=18, show=None, surface=False):
        bg = "Surface" if surface else "Page"
        super().__init__(parent, style=f"{bg}.TFrame")
        ttk.Label(self, text=label, style=f"{bg}Small.TLabel" if surface else "Small.TLabel").pack(anchor="w")
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width, show=show or "")
        self.entry.pack(anchor="w", fill="x", pady=(3, 0))

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)


class LabeledCombo(ttk.Frame):
    """A small label above a read-only drop-down list."""

    def __init__(self, parent, label, values=(), width=18, surface=False):
        bg = "Surface" if surface else "Page"
        super().__init__(parent, style=f"{bg}.TFrame")
        ttk.Label(self, text=label, style=f"{bg}Small.TLabel" if surface else "Small.TLabel").pack(anchor="w")
        self.var = tk.StringVar()
        self.combo = ttk.Combobox(self, textvariable=self.var, values=list(values), width=width, state="readonly")
        self.combo.pack(anchor="w", fill="x", pady=(3, 0))

    def get(self):
        return self.var.get()

    def set_values(self, values, keep=True):
        current = self.var.get()
        self.combo.configure(values=list(values))
        if not keep or current not in values:
            self.var.set(values[0] if values else "")


# ------------------------------------------------------------------ data table

class Column:
    def __init__(self, key, heading, width=120, anchor="w", stretch=False, fmt=None):
        self.key, self.heading, self.width, self.anchor, self.stretch = key, heading, width, anchor, stretch
        self.fmt = fmt or (lambda v: "" if v is None else str(v))


class DataTable(ttk.Frame):
    """A scrollable table of dict rows with an empty-state message.
    on_select(row or None) runs when the selection changes; on_activate(row) on double-click or Enter."""

    def __init__(self, parent, columns, empty_message="Nothing to show.", height=10, on_select=None,
                 on_activate=None):
        super().__init__(parent, style="Surface.TFrame")
        self.columns = columns
        self.on_select, self.on_activate = on_select, on_activate
        self.rows, self.key = {}, None
        self.tree = ttk.Treeview(self, columns=[c.key for c in columns], show="headings", height=height,
                                 selectmode="browse")
        for c in columns:
            self.tree.heading(c.key, text=c.heading, anchor=c.anchor)
            self.tree.column(c.key, width=c.width, minwidth=40, anchor=c.anchor, stretch=c.stretch)
        scroll = AutoScrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree.tag_configure("odd", background=COLORS["row_alt"])
        self.empty = ttk.Label(self.tree, text=empty_message, style="SurfaceMuted.TLabel", wraplength=360,
                               justify="center")
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.tree.bind("<Double-1>", self._double_click)
        self.tree.bind("<Return>", lambda e: self._activate())

    def set_rows(self, rows, key):
        """Show rows (dicts). key names the field that identifies a row; the selection survives a refresh."""
        previous = self.tree.selection()
        self.key = key
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        for i, row in enumerate(rows):
            iid = str(row[key])
            self.rows[iid] = row
            values = [c.fmt(row.get(c.key)) for c in self.columns]
            self.tree.insert("", "end", iid=iid, values=values, tags=("odd",) if i % 2 else ())
        if rows:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        still_there = [iid for iid in previous if iid in self.rows]
        if still_there:
            self.tree.selection_set(still_there)
        elif previous and self.on_select:
            self.on_select(None)

    def selected(self):
        selection = self.tree.selection()
        return self.rows.get(selection[0]) if selection else None

    def select(self, key_value):
        iid = str(key_value)
        if iid in self.rows:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            return True
        return False

    def set_empty_message(self, text):
        self.empty.configure(text=text)

    def count(self):
        # (not __len__: an empty table would then count as False, and Python 3.9's tkinter
        #  treats a False parent as "no parent")
        return len(self.rows)

    def _selected(self, _event):
        if self.on_select:
            self.on_select(self.selected())

    def _double_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell":
            self._activate()

    def _activate(self):
        row = self.selected()
        if row is not None and self.on_activate:
            self.on_activate(row)


# ------------------------------------------------------------------ floor (tables)

class SeatMarkers(tk.Canvas):
    """One dot per seat, up to four per row. Filled saffron when the table is occupied."""

    SIZE, GAP, PER_ROW = 10, 6, 4

    def __init__(self, parent, seats, occupied, background):
        rows = max(1, math.ceil(seats / self.PER_ROW))
        columns = min(seats, self.PER_ROW) or 1
        width = columns * self.SIZE + (columns - 1) * self.GAP
        height = rows * self.SIZE + (rows - 1) * self.GAP
        super().__init__(parent, width=width, height=height, background=background, highlightthickness=0, bd=0)
        for i in range(seats):
            r, c = divmod(i, self.PER_ROW)
            x, y = c * (self.SIZE + self.GAP), r * (self.SIZE + self.GAP)
            if occupied:
                self.create_oval(x, y, x + self.SIZE, y + self.SIZE, fill=COLORS["saffron"], outline=COLORS["saffron"])
            else:
                self.create_oval(x + 1, y + 1, x + self.SIZE - 1, y + self.SIZE - 1, outline=COLORS["primary"], width=2)


class TableCard(tk.Frame):
    """One table on the floor: number, seats, status and (when occupied) its open order.
    Click to select; double-click runs on_open (the Tables page opens the order)."""

    WIDTH, HEIGHT = 184, 184

    def __init__(self, parent, table, on_click, details=(), on_open=None):
        self.table = table
        occupied = table["status"] == "occupied"
        bg = COLORS["saffron_tint"] if occupied else COLORS["surface"]
        super().__init__(parent, background=bg, width=self.WIDTH, height=self.HEIGHT, highlightthickness=2,
                         highlightbackground=COLORS["border"], highlightcolor=COLORS["border"], cursor="hand2",
                         takefocus=True)
        self.grid_propagate(False)
        self.columnconfigure(0, weight=1)
        pad = {"padx": 14}
        tk.Label(self, text=str(table["table_id"]), font=FONTS["table_number"], background=bg,
                 foreground=COLORS["ink"]).grid(row=0, column=0, sticky="w", pady=(8, 0), **pad)
        tk.Label(self, text=f"{table['seats']} seats", font=FONTS["small"], background=bg,
                 foreground=COLORS["muted"]).grid(row=0, column=1, sticky="ne", pady=(14, 0), padx=(0, 14))
        SeatMarkers(self, table["seats"], occupied, bg).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 8), **pad)
        text, bg_key, fg_key = BADGES["occupied" if occupied else "free"]
        tk.Label(self, text=text, font=FONTS["small_bold"], background=COLORS[bg_key], foreground=COLORS[fg_key],
                 padx=8, pady=2).grid(row=2, column=0, columnspan=2, sticky="w", **pad)
        for i, (line, bold) in enumerate(details):
            tk.Label(self, text=line, font=FONTS["body_bold" if bold else "small"], background=bg,
                     foreground=COLORS["ink" if bold else "muted"], anchor="w").grid(
                row=3 + i, column=0, columnspan=2, sticky="w", pady=(6 if i == 0 else 0, 0), **pad)
        for widget in [self] + self._descendants(self):
            widget.bind("<Button-1>", lambda e: on_click(table["table_id"]))
            if on_open:
                widget.bind("<Double-Button-1>", lambda e: on_open(table["table_id"]))
        self.bind("<Return>", lambda e: on_click(table["table_id"]))
        self.bind("<space>", lambda e: on_click(table["table_id"]))

    def set_selected(self, selected):
        color = COLORS["primary"] if selected else COLORS["border"]
        self.configure(highlightbackground=color, highlightcolor=color)

    @staticmethod
    def _descendants(widget):
        found = []
        for child in widget.winfo_children():
            found.append(child)
            found.extend(TableCard._descendants(child))
        return found


class ScrollFrame(ttk.Frame):
    """A vertically scrollable area. Put content in .inner; on_resize(width) runs when the width changes."""

    def __init__(self, parent, on_resize=None, background=None):
        super().__init__(parent, style="Page.TFrame")
        bg = background or COLORS["page"]
        self.canvas = tk.Canvas(self, background=bg, highlightthickness=0, bd=0)
        self.scroll = AutoScrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.inner = tk.Frame(self.canvas, background=bg)
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.on_resize, self._width = on_resize, None
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._canvas_resized)
        self.canvas.bind("<Enter>", lambda e: self._wheel(True))
        self.canvas.bind("<Leave>", lambda e: self._wheel(False))

    def _canvas_resized(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)
        if event.width != self._width:
            self._width = event.width
            if self.on_resize:
                self.on_resize(event.width)

    def _wheel(self, on):
        if on:
            self.canvas.bind_all("<MouseWheel>", self._on_wheel)
            self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
            self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        else:
            for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                self.canvas.unbind_all(sequence)

    def destroy(self):
        self._wheel(False)  # don't leave the mouse wheel bound to a destroyed canvas
        super().destroy()

    def _on_wheel(self, event):
        step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step * max(1, abs(event.delta) // 120), "units")

    def width(self):
        return self._width or self.canvas.winfo_width()


# ------------------------------------------------------------------ reports

class BarList(tk.Canvas):
    """Horizontal bars for one measure: label, bar, value. One color, labels in text color, no legend."""

    ROW, BAR = 30, 12

    def __init__(self, parent, label_width=150, empty_message="No data for this period."):
        super().__init__(parent, background=COLORS["surface"], highlightthickness=0, bd=0, height=60)
        self.label_width, self.empty_message, self.rows = label_width, empty_message, []
        self.bind("<Configure>", lambda e: self.redraw())

    def set_rows(self, rows):
        """rows: list of (label, value, value_text)."""
        self.rows = list(rows)
        self.configure(height=max(60, len(self.rows) * self.ROW + 8))
        self.redraw()

    def redraw(self):
        self.delete("all")
        width = max(self.winfo_width(), 200)
        if not self.rows:
            self.create_text(width / 2, 30, text=self.empty_message, fill=COLORS["muted"], font=FONTS["body"])
            return
        top = max(value for _, value, _ in self.rows) or 1
        bar_room = max(40, width - self.label_width - 90)
        for i, (label, value, value_text) in enumerate(self.rows):
            mid = 4 + i * self.ROW + self.ROW / 2
            self.create_text(0, mid, text=label, anchor="w", fill=COLORS["ink"], font=FONTS["body"])
            end = self.label_width + max(2, bar_room * value / top)
            self.create_rectangle(self.label_width, mid - self.BAR / 2, end, mid + self.BAR / 2,
                                  fill=COLORS["primary"], width=0)
            self.create_text(end + 8, mid, text=value_text, anchor="w", fill=COLORS["ink"], font=FONTS["small_bold"])
