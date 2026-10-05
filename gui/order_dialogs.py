"""Dialogs for working with an order: add items, show the bill, transfer, pay.

Transfer and Pay are confirmation dialogs (ConfirmDialog) with a choice inside, so choosing and
confirming is one step and the confirm button always names what will happen.
"""
import tkinter as tk
from tkinter import ttk

import restaurant_system as rs
from gui.dialogs import ConfirmDialog, Dialog
from gui.formatting import bill_text, money, plural
from gui.theme import COLORS, FONTS
from gui.widgets import Column, DataTable, LabeledCombo, LabeledEntry

ALL = "All categories"


class AddItemDialog(Dialog):
    """Pick dishes and add them to an open order. Stays open so several dishes can be added.
    Every add goes through add_order_item; if it refuses, its own message is shown here."""

    def __init__(self, app, order_id, on_added):
        super().__init__(app, f"Add items to order #{order_id}", width=580)
        self.app, self.order_id, self.on_added, self.added = app, order_id, on_added, []
        ttk.Label(self.body, text=f"Add items to order #{order_id}", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.body, text="Pick a dish, set the quantity and choose Add to order. You can add several "
                                  "dishes before closing.", style="SurfaceMuted.TLabel", wraplength=520,
                  justify="left").pack(anchor="w", pady=(4, 12))
        filters = ttk.Frame(self.body, style="Surface.TFrame")
        filters.pack(fill="x")
        self.search = LabeledEntry(filters, "Search", width=26, surface=True)
        self.search.pack(side="left")
        self.search.var.trace_add("write", lambda *a: self.load_menu())
        self.category = LabeledCombo(filters, "Category", [ALL], width=18, surface=True)
        self.category.var.set(ALL)
        self.category.pack(side="left", padx=(12, 0))
        self.category.combo.bind("<<ComboboxSelected>>", lambda e: self.load_menu())
        self.menu = DataTable(self.body, [
            Column("name", "Dish", 240, stretch=True),
            Column("category", "Category", 120),
            Column("price", "Price", 90, anchor="e", fmt=money),
        ], empty_message="No dishes match. Sold-out dishes are not listed.", height=9,
            on_activate=lambda row: self.add())
        self.menu.pack(fill="both", expand=True, pady=(12, 0))
        row = ttk.Frame(self.body, style="Surface.TFrame")
        row.pack(fill="x", pady=(12, 0))
        ttk.Label(row, text="Quantity", style="Surface.TLabel").pack(side="left")
        self.quantity = tk.StringVar(value="1")
        self.quantity_box = ttk.Spinbox(row, from_=1, to=99, width=6, textvariable=self.quantity)
        self.quantity_box.pack(side="left", padx=(10, 0))
        self.message = ttk.Label(self.body, style="SurfaceMuted.TLabel", wraplength=520, justify="left")
        self.message.pack(anchor="w", pady=(10, 0))
        self.close_button, self.add_button = self.add_buttons([("Close", self.cancel, "TButton"),
                                                               ("Add to order", self.add, "Primary.TButton")])
        self.load_menu()

    def load_menu(self):
        ok, categories = self.app.call(rs.list_categories, dialog=False)
        if ok:
            self.category.set_values([ALL] + categories)
        category = self.category.get()
        ok, dishes = self.app.call(rs.list_menu, self.search.get(), None if category == ALL else category,
                                   dialog=False)
        if ok:
            self.menu.set_rows(dishes, key="item_id")

    def add(self):
        dish = self.menu.selected()
        if dish is None:
            self._say("Select a dish first.", error=True)
            return
        text = self.quantity.get().strip()
        try:
            quantity = int(text)
        except ValueError:
            quantity = text  # not a whole number: add_order_item rejects it with its own message
        ok, result = self.app.call(rs.add_order_item, self.order_id, dish["item_id"], quantity, dialog=False)
        if not ok:
            self._say(result, error=True)
            self.load_menu()  # for example, a dish that was just sold out leaves the list
            return
        self.added.append((dish["name"], quantity))
        self.quantity.set("1")
        self._say(f"Added {quantity} x {dish['name']} to order #{self.order_id}.")
        self.app.status.success(f"Added {quantity} x {dish['name']} to order #{self.order_id}.")
        self.on_added()

    def _say(self, text, error=False):
        self.message.configure(text=text, style="SurfaceError.TLabel" if error else "SurfaceSuccess.TLabel")


class BillDialog(Dialog):
    """The bill of an order, laid out like a printed bill. The total is the one get_bill returns."""

    def __init__(self, app, order, bill):
        super().__init__(app, f"Bill for order #{order['order_id']}", width=420)
        self.text_content = bill_text(order, bill)
        ttk.Label(self.body, text=f"Bill for order #{order['order_id']}", style="Section.TLabel").pack(anchor="w")
        paper = tk.Text(self.body, width=42, height=min(26, self.text_content.count("\n") + 2), font=FONTS["mono"],
                        background=COLORS["surface"], foreground=COLORS["ink"], relief="flat", padx=14, pady=12,
                        wrap="none", highlightthickness=1, highlightbackground=COLORS["border"],
                        highlightcolor=COLORS["border"])
        paper.insert("1.0", self.text_content)
        paper.configure(state="disabled")
        paper.pack(fill="both", expand=True, pady=(12, 0))
        self.add_buttons([("Close", lambda: self.close(True), "Primary.TButton")])


class TransferDialog(ConfirmDialog):
    """Choose a free table for an open order and confirm the move. Returns the chosen table id."""

    def __init__(self, app, order, free_tables):
        source = order["table_id"]
        super().__init__(app, f"Transfer order #{order['order_id']}",
                         f"Move order #{order['order_id']} from table {source} to a free table. The order keeps its "
                         f"number, dishes and prices, and table {source} becomes free.",
                         "Transfer order", danger=False, cancel_text="Keep it here", width=460)
        self.choice = DataTable(self.body, [
            Column("table_id", "Free table", 140, stretch=True, fmt=lambda v: f"Table {v}"),
            Column("seats", "Seats", 90, anchor="e"),
        ], empty_message="No free tables right now. Free a table first, then try again.",
            height=min(8, max(3, len(free_tables))), on_select=lambda row: self._update(),
            on_activate=lambda row: self.confirm())
        self.choice.pack(fill="x", pady=(14, 0))
        self.choice.set_rows(free_tables, key="table_id")
        self._update()

    def _update(self):
        row = self.choice.selected()
        self.confirm_button.configure(text=f"Transfer to table {row['table_id']}" if row else "Transfer order")
        self.confirm_button.state(["!disabled"] if row else ["disabled"])

    def confirm(self):
        row = self.choice.selected()
        if row is not None:
            self.close(row["table_id"])


class PayDialog(ConfirmDialog):
    """Confirm payment of an order's total (from get_bill) and choose cash or card. Returns the method."""

    METHODS = (("cash", "Cash"), ("card", "Card"))

    def __init__(self, app, order, bill):
        total = money(bill["total"])
        super().__init__(app, f"Pay order #{order['order_id']}",
                         f"Take payment of {total} for order #{order['order_id']} on table {order['table_id']} "
                         f"({plural(len(bill['lines']), 'dish', 'dishes')}). This issues the receipt and frees the "
                         "table. A paid order can't be changed afterwards.",
                         f"Pay {total}", danger=False, cancel_text="Not yet")
        self.method = tk.StringVar(value="cash")
        box = ttk.Frame(self.body, style="Surface.TFrame")
        box.pack(anchor="w", pady=(14, 0))
        ttk.Label(box, text="Payment method", style="SurfaceSmall.TLabel").pack(anchor="w")
        self.method_buttons = {}
        for value, label in self.METHODS:
            self.method_buttons[value] = ttk.Radiobutton(box, text=label, value=value, variable=self.method,
                                                         style="Surface.TRadiobutton")
            self.method_buttons[value].pack(anchor="w")

    def confirm(self):
        self.close(self.method.get())
