"""GUI smoke tests: open the real window on a seeded database and drive it like a user would.

Needs Tkinter and a display (on Linux without a screen, run it under Xvfb). Otherwise it reports
SKIPPED. Dialogs are replaced by recorders so the run never blocks. Phase 3 is read-only, so the
whole session must leave the database exactly as it was.
"""
import os, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
sys.path.insert(0, ROOT)
try:
    import tkinter as tk
    tk.Tk().destroy()
except Exception as e:  # no Tkinter, or no display
    print(f"SKIPPED: the GUI cannot open here ({type(e).__name__}: {str(e).splitlines()[0][:80]})")
    sys.exit(0)

import restaurant_system as rs  # noqa: E402
import seed_database  # noqa: E402
import gui.app as app_module  # noqa: E402
from gui import dialogs  # noqa: E402

WORK = os.path.join(WORK_ROOT, "gui_smoke")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
DB = os.path.join(WORK, "restaurant.db")
seed_database.seed(DB)
app_module.ERROR_LOG = os.path.join(WORK, "gui_error.log")

results, shown, callback_errors = [], [], []
dialogs.show_message = lambda parent, title, message, error=False: shown.append((title, message, error))


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def dump(path=DB):
    con = sqlite3.connect(path)
    try:
        return list(con.iterdump())
    finally:
        con.close()


def settle(app):
    for _ in range(3):
        app.update_idletasks()
        app.update()


def services(fn, *args, **kwargs):
    con = rs.connect(DB)
    try:
        return fn(con, *args, **kwargs)
    finally:
        con.close()


def disabled(button):
    return button.instate(["disabled"])


def packed(widget):
    return bool(widget.winfo_manager())


start = dump()
background_errors = []
app = app_module.RestaurantApp(DB)
app.report_callback_exception = lambda *a: callback_errors.append(a)
app.tk.createcommand("bgerror", lambda *msg: background_errors.append(msg))  # Tcl errors, e.g. stale timers
settle(app)

# ---------------------------------------------------------------- window and login
check("window title and minimum size", app.title() == "Restaurant System" and app.minsize() == (1100, 680))
check("status bar shows which database file is open", DB in app.status.location.cget("text"))
login = app.login_view
check("starts on the login screen", login is not None and app.shell is None)
check("password field is masked", login.password.entry.cget("show") == "*")
login.submit()
check("empty login -> 'Enter your username and password.'", login.error.cget("text") == "Enter your username and password.")
login.username.set("admin")
login.password.set("wrong")
login.submit()
check("wrong password -> 'Wrong username or password.' on the form", login.error.cget("text") == "Wrong username or password.")
check("... the password field is cleared", login.password.get() == "")
check("... still on the login screen", app.shell is None and app.session is None)
login.username.set("admin")
login.password.set("1234")
login.submit()
settle(app)
check("correct login opens the main window", app.shell is not None and app.login_view is None)
check("session holds the employee id and name only", (app.session.employee_id, app.session.name) == (1, "Restaurant Manager")
      and not any("pass" in k for k in vars(app.session)))
check("top bar shows the signed-in employee", app.shell.topbar.name.cget("text") == "Restaurant Manager")
check("status bar says who signed in", app.status.kind == "success" and "Restaurant Manager" in app.status.text)
check("no password on screen after login", "1234" not in app.status.text)

# ---------------------------------------------------------------- navigation
sidebar = app.shell.sidebar
for key in ("dashboard", "tables", "menu", "receipts", "reports", "employees"):
    sidebar.buttons[key].invoke()
    settle(app)
    page = app.shell.current
    others_hidden = all(not packed(p) for k, p in app.shell.pages.items() if p is not page)
    check(f"sidebar '{key}': page shown, highlighted, others hidden",
          page.key == key and sidebar.active == key and str(sidebar.buttons[key].cget("style")) == "NavActive.TButton"
          and packed(page) and others_hidden)

# ---------------------------------------------------------------- dashboard
app.show_page("dashboard")
settle(app)
dash = app.shell.current
tables = services(rs.table_overview)
free = sum(1 for t in tables if t["status"] == "free")
check("dashboard: free / occupied / open orders match the database",
      [dash.stats.values[k].cget("text") for k in ("free", "occupied", "open")] == [str(free), str(8 - free), "3"])
check("dashboard: open orders list", sorted(dash.orders.rows) == ["27", "28", "29"])
dash.orders.select(27)
dash.orders._activate()
settle(app)
check("dashboard: opening an order goes to its order page", app.shell.current.key == "order"
      and app.shell.current.header.title.cget("text") == "Order #27" and sidebar.active == "tables")

# ---------------------------------------------------------------- tables
app.show_page("tables")
settle(app)
tp = app.shell.current
check("tables: one card per table (8)", len(tp.cards) == 8)
tp.select(2)
check("tables: free table 2 offers only 'Seat customers'",
      [n for n, b in tp.buttons.items() if packed(b)] == ["seat"])
tp.select(3)
check("tables: occupied table 3 offers open / transfer / pay / cancel",
      [n for n, b in tp.buttons.items() if packed(b)] == ["open", "transfer", "pay", "cancel"])
check("tables: details show order #27 and who took it",
      "Order #27" in tp.detail_lines.cget("text") and "Somchai Jaidee" in tp.detail_lines.cget("text"))
tp.buttons["open"].invoke()
settle(app)
op = app.shell.current
check("tables: 'Open order' opens order #27", op.key == "order" and op.order_id == 27)

# ---------------------------------------------------------------- order page
bill = services(rs.get_bill, 27)
check("order: 4 items at their price at order", sorted(op.items.rows) == sorted(str(l["item_id"]) for l in bill["lines"])
      and op.total.cget("text") == "395.00")
check("order: open order can be changed (add, transfer, cancel, pay enabled)",
      not any(disabled(op.buttons[n]) for n in ("add", "transfer", "cancel", "pay")))
check("order: 'Remove item' waits for a selected item", disabled(op.buttons["remove"]))
op.items.select(bill["lines"][0]["item_id"])
settle(app)
check("order: selecting an item enables 'Remove item'", not disabled(op.buttons["remove"]))
check("order: no paid notice on an open order", not packed(op.notice_row))
app.show_page("order", order_id=1)
settle(app)
check("order: paid order shows a notice that it can't be changed",
      packed(op.notice_row) and "Paid orders can't be changed" in op.notice.cget("text"))
op.items.select(op.items.tree.get_children()[0])
settle(app)
check("order: paid order has add, remove, transfer, cancel and pay disabled",
      all(disabled(op.buttons[n]) for n in ("add", "remove", "transfer", "cancel", "pay")))
check("order: the bill can still be shown for a paid order", not disabled(op.buttons["bill"]))
op.receipt_button.invoke()
settle(app)
rp = app.shell.current
check("order: 'View receipt' opens that receipt", rp.key == "receipts" and rp.table.selected()["order_id"] == 1)
app.show_page("order", order_id=999)
settle(app)
check("order: unknown order shows 'Order not found' instead of the order", packed(op.missing) and not packed(op.content))
app.show_page("order", order_id=27)
settle(app)
app.shell.current.header.winfo_children()[0].winfo_children()[0].invoke()  # "Back to tables"
settle(app)
check("order: 'Back to tables' returns to the floor with table 3 selected",
      app.shell.current.key == "tables" and app.shell.current.selected_id == 3)

# ---------------------------------------------------------------- menu
app.show_page("menu")
settle(app)
mp = app.shell.current
check("menu: all 19 dishes with sold-out shown", mp.table.count() == 19)
mp.show_sold_out.state(["!selected"])
mp.refresh()
check("menu: hiding sold-out leaves 18", mp.table.count() == 18 and "17" not in mp.table.rows)
mp.search.set("curry")
mp.refresh()
check("menu: search 'curry'", sorted(r["name"] for r in mp.table.rows.values()) == ["Green Curry", "Massaman Curry"])
mp.search.set("")
mp.category.var.set("Drink")
mp.show_sold_out.state(["selected"])
mp.refresh()
drinks = services(rs.list_menu, category="Drink", available_only=False)
check("menu: category filter", {r["category"] for r in mp.table.rows.values()} == {"Drink"}
      and sorted(mp.table.rows) == sorted(str(d["item_id"]) for d in drinks))
check("menu: dish buttons wait for a selection", disabled(mp.edit) and disabled(mp.delete))
mp.table.select(17)
settle(app)
check("menu: sold-out dish offers 'Mark available'", mp.availability.cget("text") == "Mark available" and not disabled(mp.edit))

# ---------------------------------------------------------------- receipts
app.show_page("receipts")
settle(app)
rp = app.shell.current
rp.clear()
check("receipts: all 26 listed", rp.table.count() == 26)
rp.table.select(3)
settle(app)
paper = rp.paper.get("1.0", "end")
check("receipts: preview shows receipt 3 with historical prices and both employees",
      all(s in paper for s in ("Receipt #3", "Pad Thai", "2 x 75.00", "Taken by", "Issued by", "Total")))
rp.fields["receipt_id"].set("3")
rp.refresh()
check("receipts: filter by receipt number", list(rp.table.rows) == ["3"])
rp.fields["receipt_id"].set("")
rp.fields["table_id"].set("x")
rp.refresh()
check("receipts: non-numeric table -> clear message", rp.error.cget("text") == "Table must be a whole number.")
rp.fields["table_id"].set("")
rp.fields["start"].set("2026-02-30")
rp.refresh()
check("receipts: invalid date -> the service's message", rp.error.cget("text").startswith("Start date '2026-02-30' is not a valid date"))
rp.clear()
app.show_page("receipts", receipt_id=5)
settle(app)
check("receipts: opening with a receipt number selects it", rp.table.selected()["receipt_id"] == 5)

# ---------------------------------------------------------------- reports
app.show_page("reports")
settle(app)
rep = app.shell.current
daily = services(rs.daily_sales_report)
check("reports: all-time daily sales match the service", rep.tables["daily"].count() == len(daily))
check("reports: best sellers and busiest hours (top 5)", rep.tables["best"].count() == 5 and rep.tables["hours"].count() == 5)
rep.start.set("2026-13-01")
rep.refresh()
check("reports: invalid date -> the service's message", rep.error.cget("text").startswith("Start date '2026-13-01'"))
rep.start.set("2026-10-05")
rep.end.set("2026-10-01")
rep.refresh()
check("reports: start after end -> message", rep.error.cget("text") == "The start date cannot be after the end date.")
day = daily[1]["day"]
rep.start.set(day)
rep.end.set(day)
rep.refresh()
check("reports: one day", rep.error.cget("text") == "" and list(rep.tables["daily"].rows) == [day]
      and rep.header.subtitle.cget("text") == f"Only {day}.")
rep.all_time()
check("reports: 'All time' clears the dates", rep.header.subtitle.cget("text") == "All time."
      and rep.tables["daily"].count() == len(daily))

# ---------------------------------------------------------------- employees
app.show_page("employees")
settle(app)
ep = app.shell.current
check("employees: 5 listed, no password column", ep.table.count() == 5 and
      not any("pass" in c.key for c in ep.table.columns))
hashes = [r[0] for r in sqlite3.connect(DB).execute("SELECT password FROM Employees")]
cells = " ".join(" ".join(map(str, ep.table.tree.item(i, "values"))) for i in ep.table.tree.get_children())
check("employees: no password hash anywhere in the table", not any(h in cells for h in hashes))
ep.table.select(2)
settle(app)
check("employees: someone with history can't be removed, with the reason",
      disabled(ep.remove) and "cannot be removed" in ep.reason.cget("text"))
ep.table.select(1)
settle(app)
check("employees: you can't remove yourself", disabled(ep.remove) and "yourself" in ep.reason.cget("text"))
ep.table.select(5)
settle(app)
check("employees: someone without history can be removed", not disabled(ep.remove) and ep.reason.cget("text") == "")

# ---------------------------------------------------------------- Phase 4 placeholders change nothing
before = dump()
placeholder_buttons = [ep.remove, ep.change_password]
app.show_page("menu")
settle(app)
mp.table.select(5)
placeholder_buttons += [mp.edit, mp.availability, mp.delete]
for b in placeholder_buttons:
    b.invoke()
app.show_page("order", order_id=27)
settle(app)
for name in ("add", "transfer", "cancel", "pay", "bill"):
    op.buttons[name].invoke()
check("placeholder buttons only show a status message", app.status.kind == "info" and "Phase 4" in app.status.text,
      app.status.text)
check("placeholder buttons changed nothing in the database", dump() == before)

# ---------------------------------------------------------------- errors become readable messages
ok, message = app.call(lambda db: (_ for _ in ()).throw(rs.RestaurantError("A rule was broken.")))
check("business-rule error: returned, shown in the status bar and a dialog",
      not ok and message == "A rule was broken." and app.status.kind == "error" and shown[-1][1] == "A rule was broken.")
ok, message = app.call(lambda db: db.execute("SELECT * FROM NoSuchTable"), dialog=False)
check("database error: 'Database error: ...' in the status bar, no dialog",
      not ok and message.startswith("Database error: no such table") and shown[-1][1] == "A rule was broken.")
ok, message = app.call(lambda db: 1 / 0)
check("unexpected error: readable message, details saved to gui_error.log",
      not ok and message.startswith("Something went wrong: division by zero") and "gui_error.log" in message
      and "ZeroDivisionError" in open(app_module.ERROR_LOG).read())
try:
    raise KeyError("boom")
except KeyError as e:
    app_module.RestaurantApp._callback_error(app, KeyError, e, e.__traceback__)
check("error inside a button handler: readable dialog, no traceback on screen",
      shown[-1][0] == "Something went wrong" and "Traceback" not in shown[-1][1] and app.status.kind == "error")

# ---------------------------------------------------------------- refresh, logout, close
app.show_page("menu")
settle(app)
mp.search.set("pad")  # starts the type-to-search timer; logging out right away must cancel it
app.refresh()
check("F5 refreshes the current page", app.status.text == "Refreshed.")
app.shell.topbar.logout.invoke()
settle(app)
check("log out returns to the login screen", app.shell is None and app.session is None and app.login_view is not None
      and app.status.text == "Signed out.")
import time  # noqa: E402
time.sleep(0.4)
settle(app)
check("no unexpected errors in event handlers", not callback_errors, callback_errors[:1])
check("no stale timers or Tcl background errors after logging out", not background_errors, background_errors[:1])
check("the whole read-only session left the database unchanged", dump() == start)
app.close()
check("closing the window closes the database", app.db is None)

# ---------------------------------------------------------------- brand-new database file
NEW = os.path.join(WORK, "new", "restaurant.db")
os.makedirs(os.path.dirname(NEW))
app2 = app_module.RestaurantApp(NEW)
settle(app2)
check("new database: created with default data and the status bar says so",
      os.path.exists(NEW) and app2.status.kind == "info" and "new database was created" in app2.status.text)
check("new database: the notice does not show the default password", "1234" not in app2.status.text)
app2.close()

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
