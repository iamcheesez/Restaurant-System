"""Receipts: find receipts by date, receipt, order or table, and preview one as it would print."""
import tkinter as tk
from tkinter import ttk

import restaurant_system as rs
from gui.formatting import day_and_time, money, parse_whole_number, plural, receipt_text
from gui.pages.base import Page
from gui.theme import COLORS, FONTS
from gui.widgets import Card, Column, DataTable, LabeledEntry


class ReceiptsPage(Page):
    key = "receipts"
    title = "Receipts"

    def build(self):
        filters = ttk.Frame(self.body, style="Page.TFrame")
        filters.pack(fill="x")
        self.fields = {}
        for key, label, width in (("start", "Paid from (YYYY-MM-DD)", 16), ("end", "Paid to", 14),
                                  ("receipt_id", "Receipt #", 9), ("order_id", "Order #", 9), ("table_id", "Table", 7)):
            field = LabeledEntry(filters, label, width=width)
            field.pack(side="left", padx=(0, 12))
            field.entry.bind("<Return>", lambda e: self.refresh())
            self.fields[key] = field
        ttk.Button(filters, text="Search", style="Primary.TButton", command=self.refresh).pack(
            side="left", anchor="s")
        ttk.Button(filters, text="Clear", command=self.clear).pack(side="left", anchor="s", padx=(8, 0))
        self.error = ttk.Label(self.body, style="Error.TLabel")
        self.error.pack(anchor="w", pady=(6, 8))

        split = ttk.Frame(self.body, style="Page.TFrame")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=1)  # the list takes the spare width
        split.columnconfigure(1, weight=0)  # the receipt keeps the width of the paper
        split.rowconfigure(0, weight=1)

        listing = Card(split)
        listing.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self.table = DataTable(listing.body, [
            Column("receipt_id", "Receipt", 82, fmt=lambda v: f"#{v}"),
            Column("paid_time", "Paid", 140, fmt=day_and_time),
            Column("table_id", "Table", 64),
            Column("issued_by", "Issued by", 150, stretch=True),
            Column("amount", "Total", 90, anchor="e", fmt=money),
        ], empty_message="No receipts match these filters. Clear them to see every receipt.",
            on_select=self._show_receipt, height=16)
        self.table.pack(fill="both", expand=True)

        preview = Card(split, title="Receipt")
        preview.grid(row=0, column=1, sticky="nsew")
        paper = tk.Frame(preview.body, background=COLORS["page"], padx=14, pady=14)
        paper.pack(fill="both", expand=True)
        self.paper = tk.Text(paper, width=42, height=20, font=FONTS["mono"], background=COLORS["surface"],
                             foreground=COLORS["ink"], relief="flat", padx=16, pady=14, wrap="none",
                             highlightthickness=1, highlightbackground=COLORS["border"],
                             highlightcolor=COLORS["primary"])
        self.paper.pack(fill="both", expand=True)
        self.paper.configure(state="disabled")
        actions = ttk.Frame(preview.body, style="Surface.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        self.print_button = ttk.Button(actions, text="Print receipt", style="Primary.TButton",
                                       command=self.later("Printing receipts"))
        self.print_button.pack(side="right")
        self.save_button = ttk.Button(actions, text="Save as text", command=self.later("Saving receipts"))
        self.save_button.pack(side="right", padx=(0, 8))
        self._set_paper("Select a receipt to see it here.")

    def on_show(self, receipt_id=None, **kwargs):
        self.refresh()
        if receipt_id is not None and not self.table.select(receipt_id):
            self.clear()
            self.table.select(receipt_id)

    def clear(self):
        for field in self.fields.values():
            field.set("")
        self.refresh()

    def refresh(self):
        numbers = {}
        for key, label in (("receipt_id", "Receipt #"), ("order_id", "Order #"), ("table_id", "Table")):
            numbers[key], problem = parse_whole_number(self.fields[key].get(), label)
            if problem:
                self.error.configure(text=problem)
                return
        ok, receipts = self.app.call(rs.list_receipts, self.fields["start"].get(), self.fields["end"].get(),
                                     dialog=False, **numbers)
        if not ok:
            self.error.configure(text=receipts)
            return
        self.error.configure(text="")
        self.table.set_rows(receipts, key="receipt_id")
        total = sum(r["amount"] for r in receipts)
        self.header.set(subtitle=f"{plural(len(receipts), 'receipt')} shown, {money(total)} in total.")
        if self.table.selected() is None:
            self._set_paper("Select a receipt to see it here.")

    def _show_receipt(self, row):
        state = ["!disabled"] if row else ["disabled"]
        self.print_button.state(state)
        self.save_button.state(state)
        if row is None:
            self._set_paper("Select a receipt to see it here.")
            return
        receipt = self.load(rs.get_receipt, row["receipt_id"])
        if receipt is not None:
            self._set_paper(receipt_text(receipt))

    def _set_paper(self, text):
        self.paper.configure(state="normal")
        self.paper.delete("1.0", "end")
        self.paper.insert("1.0", text)
        self.paper.configure(state="disabled")
