"""Employees: staff list with their order history. Passwords and hashes are never shown."""
from tkinter import ttk

import restaurant_system as rs
from gui.formatting import plural
from gui.pages.base import Page
from gui.widgets import Card, Column, DataTable


class EmployeesPage(Page):
    key = "employees"
    title = "Employees"

    def build(self):
        self.header.add_action("Add employee", self.later("Adding employees"), style="Primary.TButton")
        card = Card(self.body)
        card.pack(fill="both", expand=True)
        self.table = DataTable(card.body, [
            Column("employee_id", "ID", 60),
            Column("name", "Name", 220, stretch=True),
            Column("username", "Username", 150),
            Column("orders", "Orders taken", 120, anchor="e"),
            Column("receipts", "Receipts issued", 140, anchor="e"),
            Column("note", "", 100),
        ], empty_message="No employees.", on_select=self._selected, height=12)
        self.table.pack(fill="both", expand=True)

        actions = ttk.Frame(card.body, style="Surface.TFrame")
        actions.pack(fill="x", pady=(12, 0))
        self.change_password = ttk.Button(actions, text="Change password", command=self.later("Changing passwords"))
        self.change_password.pack(side="left")
        self.remove = ttk.Button(actions, text="Remove employee", style="Danger.TButton",
                                 command=self.later("Removing employees"))
        self.remove.pack(side="right")
        self.reason = ttk.Label(card.body, style="SurfaceMuted.TLabel", wraplength=700, justify="left")
        self.reason.pack(anchor="w", pady=(10, 0))
        self._selected(None)

    def refresh(self):
        employees = self.load(rs.list_employees)
        if employees is None:
            return
        me = self.app.session.employee_id
        rows = [dict(e, note="You" if e["employee_id"] == me else "") for e in employees]
        self.table.set_rows(rows, key="employee_id")
        self.header.set(subtitle=f"{plural(len(rows), 'employee')}. Staff who have handled orders are kept "
                                 "so the order history stays complete.")
        self._selected(self.table.selected())

    def _selected(self, employee):
        if employee is None:
            self.change_password.state(["disabled"])
            self.remove.state(["disabled"])
            self.reason.configure(text="Select an employee to change their password or remove them.")
            return
        self.change_password.state(["!disabled"])
        # Ask the service whether removal is allowed, so the rule lives in one place.
        ok, problem = self.app.call(rs.check_employee_removable, employee["employee_id"],
                                    self.app.session.employee_id, report=False)
        self.remove.state(["!disabled"] if ok else ["disabled"])
        self.reason.configure(text="" if ok else problem.replace("\n", " "))
