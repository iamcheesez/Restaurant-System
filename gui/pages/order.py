"""Order details: header facts, the dishes at their price at order, the total, and the order actions.
A paid order is shown read-only: its change buttons are disabled and a notice explains why."""
from tkinter import ttk

import restaurant_system as rs
from gui import actions
from gui.formatting import day_and_time, elapsed, money, plural
from gui.pages.base import Page
from gui.widgets import Badge, Card, Column, DataTable, EmptyState, Notice


class OrderPage(Page):
    key = "order"
    title = "Order"
    nav_key = "tables"

    def back_link(self):
        return ("Back to tables", lambda: self.app.show_page("tables", table_id=self._table_id()))

    def build(self):
        self.order, self.order_id = None, None
        self.content = ttk.Frame(self.body, style="Page.TFrame")
        self.missing = EmptyState(self.body, "Order not found",
                                  "This order no longer exists. It may have been cancelled. Pick a table to "
                                  "see its current order.", action=("Go to tables", lambda: self.app.show_page("tables")),
                                  surface=False)

        self.notice_row = ttk.Frame(self.content, style="Page.TFrame")
        self.notice = Notice(self.notice_row)
        self.notice.pack(side="left", fill="x", expand=True)
        self.receipt_button = ttk.Button(self.notice_row, text="View receipt", command=self._view_receipt)
        self.receipt_button.pack(side="left", padx=(8, 0))

        facts = self.facts_card = Card(self.content, padding=(20, 14))
        facts.pack(fill="x")
        self.facts = {}
        for i, (key, caption) in enumerate((("table", "Table"), ("taken_by", "Taken by"), ("opened", "Opened"),
                                            ("status", "Status"))):
            cell = ttk.Frame(facts.body, style="Surface.TFrame")
            cell.grid(row=0, column=i, sticky="w", padx=(0, 48))
            ttk.Label(cell, text=caption, style="SurfaceSmall.TLabel").pack(anchor="w")
            if key == "status":
                self.badge = Badge(cell, "open")
                self.badge.pack(anchor="w", pady=(4, 0))
            else:
                self.facts[key] = ttk.Label(cell, style="SurfaceBold.TLabel")
                self.facts[key].pack(anchor="w", pady=(2, 0))

        toolbar = ttk.Frame(self.content, style="Page.TFrame")
        toolbar.pack(fill="x", pady=(16, 10))
        self.buttons = {}
        for name, text, command, style, side in (
                ("add", "Add item", self.add_items, "Primary.TButton", "left"),
                ("remove", "Remove item", self.remove_item, "TButton", "left"),
                ("pay", "Pay", self.pay, "Primary.TButton", "right"),
                ("cancel", "Cancel order", self.cancel, "Danger.TButton", "right"),
                ("transfer", "Transfer", self.transfer, "TButton", "right"),
                ("bill", "Show bill", self.show_bill, "TButton", "right")):
            self.buttons[name] = ttk.Button(toolbar, text=text, command=command, style=style)
            self.buttons[name].pack(side=side, padx=(0, 8) if side == "left" else (8, 0))

        items = Card(self.content, title="Items")
        items.pack(fill="both", expand=True)
        self.items = DataTable(items.body, [
            Column("name", "Dish", 260, stretch=True),
            Column("quantity", "Quantity", 90, anchor="e"),
            Column("price_at_order", "Price at order", 130, anchor="e", fmt=money),
            Column("subtotal", "Subtotal", 120, anchor="e", fmt=money),
        ], empty_message="No dishes yet. Use Add item to start the order.", on_select=lambda r: self._update_buttons())
        self.items.pack(fill="both", expand=True)
        total = ttk.Frame(items.body, style="Surface.TFrame")
        total.pack(fill="x", pady=(12, 0))
        self.total = ttk.Label(total, style="Total.TLabel")
        self.total.pack(side="right")
        ttk.Label(total, text="Total", style="SurfaceMuted.TLabel").pack(side="right", padx=(0, 12))
        self.count = ttk.Label(total, style="SurfaceMuted.TLabel")
        self.count.pack(side="left")

    def on_show(self, order_id=None, **kwargs):
        if order_id is not None:
            self.order_id = order_id
        self.refresh()

    def refresh(self):
        if self.order_id is None:
            return self._show_missing()
        ok, order = self.app.call(rs.get_order, self.order_id, report=False)
        if not ok:
            return self._show_missing()
        bill = self.load(rs.get_bill, self.order_id)
        if bill is None:
            return
        self.order = order
        self.missing.pack_forget()
        self.content.pack(fill="both", expand=True)
        paid = order["status"] == "paid"
        self.header.set(title=f"Order #{order['order_id']}",
                        subtitle=(f"Paid. Receipt #{order['receipt_id']}." if paid
                                  else f"Open for {elapsed(order['order_time'])}."))
        self.facts["table"].configure(text=f"Table {order['table_id']}")
        self.facts["taken_by"].configure(text=order["taken_by"])
        self.facts["opened"].configure(text=day_and_time(order["order_time"]))
        self.badge.set("paid" if paid else "open")
        if paid:
            self.notice.configure(text=f"This order was paid on receipt #{order['receipt_id']}. "
                                       "Paid orders can't be changed, cancelled or moved.")
            self.notice_row.pack(fill="x", pady=(0, 14), before=self.facts_card)
        else:
            self.notice_row.pack_forget()
        self.items.set_rows(bill["lines"], key="item_id")
        self.total.configure(text=money(bill["total"]))
        self.count.configure(text=plural(len(bill["lines"]), "dish", "dishes"))
        self._update_buttons()

    def _update_buttons(self):
        open_order = self.order is not None and self.order["status"] == "open"
        for name in ("add", "transfer", "cancel", "pay"):
            self.buttons[name].state(["!disabled"] if open_order else ["disabled"])
        self.buttons["remove"].state(["!disabled"] if open_order and self.items.selected() else ["disabled"])
        self.buttons["bill"].state(["!disabled"] if self.order is not None else ["disabled"])

    def _show_missing(self):
        self.order = None
        self.content.pack_forget()
        self.header.set(title=f"Order #{self.order_id}" if self.order_id else "Order", subtitle="")
        self.missing.pack(fill="x", anchor="nw")

    # ---------------------------------------------------------------- actions (all through gui.actions)
    # The buttons are disabled for paid orders, but each action still asks the service layer first,
    # so a stale screen can never change a paid order. The page refreshes after every action.

    def add_items(self):
        if self.order_id is not None:
            actions.add_items(self.app, self.order_id, on_added=self.refresh)
            self.refresh()

    def remove_item(self):
        line = self.items.selected()
        if self.order_id is not None and line is not None:
            actions.remove_item(self.app, self.order_id, line)
            self.refresh()

    def show_bill(self):
        if self.order_id is not None:
            actions.show_bill(self.app, self.order_id)

    def transfer(self):
        if self.order_id is not None:
            actions.transfer(self.app, self.order_id)
            self.refresh()

    def cancel(self):
        if self.order_id is None:
            return
        result = actions.cancel(self.app, self.order_id)
        if result is not None:  # the order no longer exists: show the freed table on the floor
            self.app.show_page("tables", table_id=result["table_id"])
        else:
            self.refresh()

    def pay(self):
        if self.order_id is not None:
            actions.pay(self.app, self.order_id)
            self.refresh()  # a paid order now shows read-only, with its receipt

    def _table_id(self):
        return self.order["table_id"] if self.order else None

    def _view_receipt(self):
        if self.order and self.order["receipt_id"]:
            self.app.show_page("receipts", receipt_id=self.order["receipt_id"])
