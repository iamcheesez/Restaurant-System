"""Dashboard: today's key figures, a compact floor view and the open orders."""
import tkinter as tk
from datetime import date
from tkinter import ttk

import restaurant_system as rs
from gui.formatting import elapsed, money, plural
from gui.pages.base import Page
from gui.theme import COLORS, FONTS
from gui.widgets import Card, Column, DataTable, StatStrip


class DashboardPage(Page):
    key = "dashboard"
    title = "Dashboard"
    subtitle = "What is happening on the floor right now."

    def build(self):
        self.header.add_action("Find a receipt", lambda: self.app.show_page("receipts"))
        self.header.add_action("Seat customers", lambda: self.app.show_page("tables"), style="Primary.TButton")

        self.stats = StatStrip(self.body, [("free", "Free tables"), ("occupied", "Occupied tables"),
                                           ("open", "Open orders"), ("sales", "Today's sales")])
        self.stats.pack(fill="x")

        row = ttk.Frame(self.body, style="Page.TFrame")
        row.pack(fill="both", expand=True, pady=(16, 0))
        row.columnconfigure(0, weight=0)  # the floor keeps its natural width
        row.columnconfigure(1, weight=1)  # the open orders get the rest
        row.rowconfigure(0, weight=1)

        floor = Card(row, title="Floor", subtitle="Click a table to manage it.")
        floor.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.floor = ttk.Frame(floor.body, style="Surface.TFrame")
        self.floor.pack(fill="both", expand=True)

        orders = Card(row, title="Open orders", subtitle="Double-click an order to open it.")
        orders.grid(row=0, column=1, sticky="nsew")
        self.orders = DataTable(orders.body, [
            Column("order_id", "Order", 70, fmt=lambda v: f"#{v}"),
            Column("table_id", "Table", 66),
            Column("taken_by", "Taken by", 150, stretch=True),
            Column("waiting", "Open for", 90),
            Column("item_count", "Dishes", 74, anchor="e"),
            Column("total", "Total", 88, anchor="e", fmt=money),
        ], empty_message="No open orders. Seat customers from the Tables page to start one.",
            on_activate=lambda r: self.app.show_page("order", order_id=r["order_id"]))
        self.orders.pack(fill="both", expand=True)

    def refresh(self):
        tables = self.load(rs.table_overview)
        if tables is None:
            return
        today = date.today()
        sales = self.load(rs.daily_sales_report, today, today) or []
        occupied = [t for t in tables if t["status"] == "occupied"]
        open_orders = sorted((dict(t, waiting=elapsed(t["order_time"])) for t in tables if t["order_id"]),
                             key=lambda o: o["order_time"])
        self.stats.set("free", len(tables) - len(occupied), f"of {plural(len(tables), 'table')}")
        self.stats.set("occupied", len(occupied), "")
        self.stats.set("open", len(open_orders), money(sum(o["total"] for o in open_orders)) + " not yet paid")
        self.stats.set("sales", money(sales[0]["total"] if sales else 0),
                       plural(sales[0]["receipts"] if sales else 0, "receipt"))
        self.header.set(subtitle=f"{len(occupied)} of {plural(len(tables), 'table')} occupied, "
                                 f"{plural(len(open_orders), 'open order')}.")
        self._draw_floor(tables)
        self.orders.set_rows(open_orders, key="order_id")

    def _draw_floor(self, tables):
        for child in self.floor.winfo_children():
            child.destroy()
        per_row = 4
        for i, t in enumerate(tables):
            occupied = t["status"] == "occupied"
            bg = COLORS["saffron_tint"] if occupied else COLORS["primary_tint"]
            chip = tk.Frame(self.floor, background=bg, cursor="hand2", highlightthickness=1,
                            highlightbackground=COLORS["saffron"] if occupied else COLORS["border"],
                            highlightcolor=COLORS["saffron"] if occupied else COLORS["border"])
            chip.grid(row=i // per_row, column=i % per_row, padx=(0, 8), pady=(0, 8), sticky="nsew")
            number = tk.Label(chip, text=str(t["table_id"]), font=FONTS["section"], background=bg,
                              foreground=COLORS["ink"])
            number.pack(anchor="w", padx=10, pady=(6, 0))
            state = tk.Label(chip, text=f"Order #{t['order_id']}" if occupied else "Free",
                             font=FONTS["small"], background=bg,
                             foreground=COLORS["saffron_ink"] if occupied else COLORS["primary"])
            state.pack(anchor="w", padx=10, pady=(0, 6))
            for widget in (chip, number, state):
                widget.bind("<Button-1>", lambda e, tid=t["table_id"]: self.app.show_page("tables", table_id=tid))
        for c in range(per_row):
            self.floor.columnconfigure(c, weight=1, uniform="chip", minsize=88)
