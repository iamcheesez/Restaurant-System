"""Reports: daily sales, best sellers and busiest hours, for all time or a chosen date range."""
from datetime import date
from tkinter import ttk

import restaurant_system as rs
from gui.formatting import money, plural
from gui.pages.base import Page
from gui.widgets import BarList, Card, Column, DataTable, LabeledEntry


class ReportsPage(Page):
    key = "reports"
    title = "Reports"
    subtitle = "All time."

    REPORTS = [
        ("daily", "Daily sales", "Receipts and sales per day, by payment date.",
         [Column("day", "Day", 120, stretch=True), Column("receipts", "Receipts", 90, anchor="e"),
          Column("total", "Sales", 110, anchor="e", fmt=money)]),
        ("best", "Best sellers", "The five dishes sold most on paid orders, by payment date.",
         [Column("rank", "Rank", 60), Column("name", "Dish", 200, stretch=True),
          Column("sold", "Sold", 80, anchor="e")]),
        ("hours", "Busiest hours", "The five hours of the day when most orders were taken (open and paid).",
         [Column("label", "Hour", 100, stretch=True), Column("orders", "Orders", 90, anchor="e")]),
    ]

    CHART_TITLES = {"daily": "Sales per day", "best": "Quantity sold", "hours": "Orders per hour"}

    def build(self):
        bar = ttk.Frame(self.body, style="Page.TFrame")
        bar.pack(fill="x")
        self.start = LabeledEntry(bar, "From (YYYY-MM-DD)", width=16)
        self.start.pack(side="left")
        self.end = LabeledEntry(bar, "To (YYYY-MM-DD)", width=16)
        self.end.pack(side="left", padx=(12, 0))
        for field in (self.start, self.end):
            field.entry.bind("<Return>", lambda e: self.refresh())
        ttk.Button(bar, text="Show report", style="Primary.TButton", command=self.refresh).pack(
            side="left", anchor="s", padx=(12, 0))
        ttk.Button(bar, text="Today", command=self.today).pack(side="left", anchor="s", padx=(8, 0))
        ttk.Button(bar, text="All time", command=self.all_time).pack(side="left", anchor="s", padx=(8, 0))
        self.error = ttk.Label(self.body, style="Error.TLabel")
        self.error.pack(anchor="w", pady=(6, 8))

        self.tabs = ttk.Notebook(self.body)
        self.tabs.pack(fill="both", expand=True)
        self.tables, self.bars = {}, {}
        for key, label, note, columns in self.REPORTS:
            tab = ttk.Frame(self.tabs, style="Page.TFrame", padding=(0, 14, 0, 0))
            self.tabs.add(tab, text=label)
            tab.columnconfigure(0, weight=2, uniform="report")
            tab.columnconfigure(1, weight=3, uniform="report")
            tab.rowconfigure(0, weight=1)
            table_card = Card(tab, title=label, subtitle=note)
            table_card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
            self.tables[key] = DataTable(table_card.body, columns, empty_message="No data for this period.", height=12)
            self.tables[key].pack(fill="both", expand=True)
            chart_card = Card(tab, title=self.CHART_TITLES[key])
            chart_card.grid(row=0, column=1, sticky="nsew")
            self.bars[key] = BarList(chart_card.body, label_width=170 if key == "best" else 110)
            self.bars[key].pack(fill="x", anchor="n")

    def today(self):
        self.start.set(date.today().isoformat())
        self.end.set(date.today().isoformat())
        self.refresh()

    def all_time(self):
        self.start.set("")
        self.end.set("")
        self.refresh()

    def refresh(self):
        start, end = self.start.get().strip() or None, self.end.get().strip() or None
        results = {}
        for key, service in (("daily", rs.daily_sales_report), ("best", rs.best_sellers_report),
                             ("hours", rs.busiest_hours_report)):
            ok, rows = self.app.call(service, start, end, dialog=False)
            if not ok:
                self.error.configure(text=rows)  # for example an invalid date; the reports keep their last data
                return
            results[key] = rows
        self.error.configure(text="")
        self.header.set(subtitle=self._period(start, end))

        daily = results["daily"]
        self.tables["daily"].set_rows(daily, key="day")
        self.bars["daily"].set_rows([(r["day"], r["total"], money(r["total"])) for r in reversed(daily)])

        best = [dict(r, rank=i + 1) for i, r in enumerate(results["best"])]
        self.tables["best"].set_rows(best, key="rank")
        self.bars["best"].set_rows([(r["name"], r["sold"], str(r["sold"])) for r in best])

        hours = [dict(r, label=f"{r['hour']}:00") for r in results["hours"]]
        self.tables["hours"].set_rows(hours, key="hour")
        self.bars["hours"].set_rows([(r["label"], r["orders"], plural(r["orders"], "order")) for r in hours])

    @staticmethod
    def _period(start, end):
        if start and end:
            return "Only " + start + "." if start == end else f"From {start} to {end}."
        if start:
            return f"From {start} onwards."
        if end:
            return f"Up to {end}."
        return "All time."
