"""Tables: the floor as cards (number, seats, status, open order) and the actions for the selected table."""
from tkinter import ttk

import restaurant_system as rs
from gui import actions
from gui.formatting import elapsed, money, plural
from gui.pages.base import Page
from gui.theme import SPACE
from gui.widgets import Badge, Card, ScrollFrame, TableCard


class TablesPage(Page):
    key = "tables"
    title = "Tables"
    subtitle = ""

    def build(self):
        self.header.add_action("Refresh", self.refresh)
        self.tables, self.cards, self.selected_id, self._columns = [], {}, None, 0

        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        self.floor = ScrollFrame(self.body, on_resize=lambda width: self._layout(width))
        self.floor.grid(row=0, column=0, sticky="nsew")

        panel = Card(self.body, padding=20)
        panel.grid(row=0, column=1, sticky="ns", padx=(SPACE["l"], 0))
        self.detail = panel.body
        self.detail_title = ttk.Label(self.detail, style="Section.TLabel")
        self.detail_title.pack(anchor="w")
        self.detail_seats = ttk.Label(self.detail, style="SurfaceMuted.TLabel")
        self.detail_seats.pack(anchor="w")
        self.detail_badge = Badge(self.detail, "free")
        self.detail_badge.pack(anchor="w", pady=(8, 10))
        self.detail_lines = ttk.Label(self.detail, style="Surface.TLabel", justify="left", wraplength=250)
        self.detail_lines.pack(anchor="w")
        self.hint = ttk.Label(self.detail, style="SurfaceMuted.TLabel", wraplength=250, justify="left",
                              text="Select a table to see its order and what you can do next.")
        self.hint.pack(anchor="w")
        self.actions = ttk.Frame(self.detail, style="Surface.TFrame")
        self.actions.pack(fill="x", pady=(16, 0))
        self.buttons = {
            "seat": ttk.Button(self.actions, text="Seat customers", style="Primary.TButton", command=self.seat),
            "open": ttk.Button(self.actions, text="Open order", style="Primary.TButton", command=self._open_order),
            "transfer": ttk.Button(self.actions, text="Transfer to another table", command=self.transfer),
            "pay": ttk.Button(self.actions, text="Pay", command=self.pay),
            "cancel": ttk.Button(self.actions, text="Cancel order", style="Danger.TButton", command=self.cancel),
        }
        self._show_detail(None)

    def on_show(self, table_id=None, **kwargs):
        self.refresh()
        if table_id is not None:
            self.select(table_id)

    def refresh(self):
        tables = self.load(rs.table_overview)
        if tables is None:
            return
        self.tables = tables
        occupied = sum(1 for t in tables if t["status"] == "occupied")
        self.header.set(subtitle=f"{occupied} of {plural(len(tables), 'table')} occupied. Click a table to select it; "
                                 "double-click an occupied table to open its order.")
        for card in self.cards.values():
            card.destroy()
        self.cards = {}
        for t in tables:
            details = ()
            if t["order_id"]:
                details = ((f"Order #{t['order_id']}", True), (t["taken_by"], False),
                           (f"Open {elapsed(t['order_time'])}, {money(t['total'])}", False))
            self.cards[t["table_id"]] = TableCard(self.floor.inner, t, self.select, details, on_open=self.open_table)
        self._columns = 0
        self._layout(self.floor.width())
        self.select(self.selected_id)

    def _layout(self, width):
        columns = max(1, (width + SPACE["m"]) // (TableCard.WIDTH + SPACE["m"]))
        if columns == self._columns or not self.cards:
            return
        self._columns = columns
        for i, card in enumerate(self.cards.values()):
            card.grid(row=i // columns, column=i % columns, padx=(0, SPACE["m"]), pady=(0, SPACE["m"]), sticky="nw")

    def select(self, table_id):
        self.selected_id = table_id if table_id in self.cards else None
        for tid, card in self.cards.items():
            card.set_selected(tid == self.selected_id)
        table = next((t for t in self.tables if t["table_id"] == self.selected_id), None)
        self._show_detail(table)

    def _show_detail(self, table):
        for button in self.buttons.values():
            button.pack_forget()
        if table is None:
            self.detail_title.configure(text="No table selected")
            self.detail_seats.configure(text="")
            self.detail_badge.pack_forget()
            self.detail_lines.configure(text="")
            self.hint.pack(anchor="w")
            return
        self.hint.pack_forget()
        self.detail_title.configure(text=f"Table {table['table_id']}")
        self.detail_seats.configure(text=f"{table['seats']} seats")
        self.detail_badge.pack(anchor="w", pady=(8, 10), before=self.detail_lines)
        if table["order_id"]:
            self.detail_badge.set("occupied")
            self.detail_lines.configure(text=f"Order #{table['order_id']}\nTaken by {table['taken_by']}\n"
                                             f"Open for {elapsed(table['order_time'])}\n"
                                             f"{plural(table['item_count'], 'dish', 'dishes')}, "
                                             f"total {money(table['total'])}")
            order = ("open", "transfer", "pay", "cancel")
        else:
            self.detail_badge.set("free")
            self.detail_lines.configure(text="No open order.")
            order = ("seat",)
        for name in order:
            self.buttons[name].pack(fill="x", pady=(0, 8))

    # ---------------------------------------------------------------- actions (all through gui.actions)

    def selected_table(self):
        return next((t for t in self.tables if t["table_id"] == self.selected_id), None)

    def open_table(self, table_id):
        """Double-click: open the table's order (a free table is only selected)."""
        self.select(table_id)
        self._open_order()

    def seat(self):
        table = self.selected_table()
        if table is not None:
            actions.seat_customers(self.app, table["table_id"])
            self.refresh()

    def transfer(self):
        table = self.selected_table()
        if table is not None and table["order_id"]:
            destination = actions.transfer(self.app, table["order_id"])
            if destination is not None:
                self.selected_id = destination  # keep the moved order selected
            self.refresh()

    def pay(self):
        table = self.selected_table()
        if table is not None and table["order_id"]:
            actions.pay(self.app, table["order_id"])
            self.refresh()

    def cancel(self):
        table = self.selected_table()
        if table is not None and table["order_id"]:
            actions.cancel(self.app, table["order_id"])
            self.refresh()

    def _open_order(self):
        table = self.selected_table()
        if table and table["order_id"]:
            self.app.show_page("order", order_id=table["order_id"])
