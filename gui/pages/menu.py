"""Menu: search and filter dishes; add, edit, delete and sold-out actions arrive in Phase 4."""
from tkinter import ttk

import restaurant_system as rs
from gui.formatting import money, plural
from gui.pages.base import Page
from gui.theme import BADGES
from gui.widgets import Card, Column, DataTable, LabeledCombo, LabeledEntry

ALL = "All categories"


class MenuPage(Page):
    key = "menu"
    title = "Menu"

    def build(self):
        self.header.add_action("Add dish", self.later("Adding dishes"), style="Primary.TButton")
        self._timer = None

        filters = ttk.Frame(self.body, style="Page.TFrame")
        filters.pack(fill="x", pady=(0, 14))
        self.search = LabeledEntry(filters, "Search by name or category", width=30)
        self.search.pack(side="left")
        self.search.var.trace_add("write", lambda *a: self._refresh_soon())
        self.category = LabeledCombo(filters, "Category", [ALL], width=20)
        self.category.pack(side="left", padx=(16, 0))
        self.category.var.set(ALL)
        self.category.combo.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.show_sold_out = ttk.Checkbutton(filters, text="Show sold-out dishes", command=self.refresh)
        self.show_sold_out.state(["!alternate", "selected"])
        self.show_sold_out.pack(side="left", padx=(16, 0), anchor="s", pady=(0, 4))

        card = Card(self.body)
        card.pack(fill="both", expand=True)
        self.table = DataTable(card.body, [
            Column("name", "Dish", 240, stretch=True),
            Column("category", "Category", 140),
            Column("price", "Price", 100, anchor="e", fmt=money),
            Column("available", "Status", 130, fmt=lambda v: BADGES["available" if v else "sold_out"][0]),
            Column("order_count", "On orders", 100, anchor="e"),
        ], empty_message="No dishes match. Clear the search or choose another category.",
            on_select=lambda r: self._update_buttons(), height=14)
        self.table.pack(fill="both", expand=True)

        actions = ttk.Frame(card.body, style="Surface.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        self.edit = ttk.Button(actions, text="Edit dish", command=self.later("Editing dishes"))
        self.edit.pack(side="left")
        self.availability = ttk.Button(actions, text="Mark sold out", command=self.later("Changing availability"))
        self.availability.pack(side="left", padx=(8, 0))
        self.delete = ttk.Button(actions, text="Delete dish", style="Danger.TButton",
                                 command=self.later("Deleting dishes"))
        self.delete.pack(side="right")
        self._update_buttons()

    def refresh(self):
        self._cancel_timer()
        categories = self.load(rs.list_categories)
        if categories is None:
            return
        self.category.set_values([ALL] + categories)
        category = self.category.get()
        dishes = self.load(rs.list_menu, self.search.get(), None if category == ALL else category,
                           available_only=not self.show_sold_out.instate(["selected"]))
        if dishes is None:
            return
        self.table.set_rows(dishes, key="item_id")
        sold_out = sum(1 for d in dishes if not d["available"])
        self.header.set(subtitle=f"{plural(len(dishes), 'dish', 'dishes')} shown" +
                                 (f", {sold_out} sold out." if sold_out else "."))
        self._update_buttons()

    def _refresh_soon(self):
        """Search while typing, but only once the typing pauses."""
        self._cancel_timer()
        self._timer = self.after(250, self.refresh)

    def _cancel_timer(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def destroy(self):
        self._cancel_timer()  # a search still waiting must not run after logout or closing
        super().destroy()

    def _update_buttons(self):
        dish = self.table.selected()
        state = ["!disabled"] if dish else ["disabled"]
        for button in (self.edit, self.availability, self.delete):
            button.state(state)
        self.availability.configure(text="Mark available" if dish and not dish["available"] else "Mark sold out")
