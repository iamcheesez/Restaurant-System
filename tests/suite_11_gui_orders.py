"""Phase 4A GUI integration tests: tables and orders, driven through the real pages and dialogs.

Dialogs are not shown to a person: each one is handed to a "driver" that clicks its real buttons
(choose a table, confirm, cancel...). To reach the service layer's own rejections, some drivers
change the database from a second connection while the dialog is open, the way another terminal
could. After every step the database is checked for consistency.
Needs Tkinter and a display; otherwise SKIPPED.
"""
import os, shutil, sqlite3, sys, time
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
sys.path.insert(0, ROOT)
try:
    import tkinter as tk
    tk.Tk().destroy()
except Exception as e:
    print(f"SKIPPED: the GUI cannot open here ({type(e).__name__}: {str(e).splitlines()[0][:80]})")
    sys.exit(0)

import restaurant_system as rs  # noqa: E402
import seed_database  # noqa: E402
import gui.app as app_module  # noqa: E402
from gui import dialogs  # noqa: E402
from gui.formatting import money  # noqa: E402

WORK = os.path.join(WORK_ROOT, "gui_orders")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
DB = os.path.join(WORK, "restaurant.db")
seed_database.seed(DB)
app_module.ERROR_LOG = os.path.join(WORK, "gui_error.log")

results, LOG, PLAN, callback_errors, background_errors = [], [], [], [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def driven_show(dialog, focus=None):
    """Replaces Dialog.show: log the dialog, let the planned driver click it, close anything left open."""
    dialog.update_idletasks()
    LOG.append({"kind": type(dialog).__name__, "title": dialog.title_text,
                "message": getattr(dialog, "message_text", ""), "error": getattr(dialog, "error", False)})
    if PLAN and PLAN[0][0] == type(dialog).__name__:
        PLAN.pop(0)[1](dialog)
    if dialog.winfo_exists():
        dialog.cancel()
    return dialog.result


dialogs.Dialog.show = driven_show


def plan(kind, driver):
    PLAN.append((kind, driver))


def errors_since(n):
    return [e["message"] for e in LOG[n:] if e["kind"] == "MessageDialog" and e["error"]]


confirm = lambda d: d.confirm_button.invoke()
decline = lambda d: d.cancel_button.invoke()


def other(fn, *args, **kwargs):
    """Change the database from a second connection, like another terminal would."""
    con = rs.connect(DB)
    try:
        return fn(con, *args, **kwargs)
    finally:
        con.close()


def q(sql, *args):
    con = sqlite3.connect(DB)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def dump():
    con = sqlite3.connect(DB)
    try:
        return list(con.iterdump())
    finally:
        con.close()


def consistent():
    """The rules every operation must keep. Returns a list of problems (empty = fine)."""
    one = lambda sql: q(sql)[0][0]
    problems = []
    if q("PRAGMA foreign_key_check"):
        problems.append("foreign keys")
    if one("SELECT COUNT(*) FROM Tables t WHERE (t.status = 'occupied') != "
           "EXISTS (SELECT 1 FROM Orders o WHERE o.table_id = t.table_id AND o.status = 'open')"):
        problems.append("table status does not match open orders")
    if one("SELECT COUNT(*) FROM (SELECT table_id FROM Orders WHERE status = 'open' GROUP BY table_id HAVING COUNT(*) > 1)"):
        problems.append("two open orders on one table")
    if one("SELECT COUNT(*) FROM Orders o WHERE (o.status = 'paid') != ((SELECT COUNT(*) FROM Receipt r "
           "WHERE r.order_id = o.order_id) = 1)"):
        problems.append("paid orders need exactly one receipt, open orders none")
    if one("SELECT COUNT(*) FROM Receipt r JOIN Orders o ON o.order_id = r.order_id WHERE r.table_id != o.table_id "
           "OR ABS(r.amount - (SELECT SUM(quantity * price_at_order) FROM OrderItems WHERE order_id = r.order_id)) > 0.001"):
        problems.append("receipt table or amount wrong")
    if q("SELECT receipt_id, item_id FROM ReceiptItems ORDER BY 1, 2") != q(
            "SELECT r.receipt_id, oi.item_id FROM Receipt r JOIN OrderItems oi ON oi.order_id = r.order_id ORDER BY 1, 2"):
        problems.append("receipt items differ from order items")
    return problems


def check_db(label):
    problems = consistent()
    check(f"{label}: database consistent", not problems, problems)


def settle():
    for _ in range(3):
        app.update_idletasks()
        app.update()


def disabled(button):
    return button.instate(["disabled"])


def packed(widget):
    return bool(widget.winfo_manager())


def dish_id(name):
    return q("SELECT item_id FROM MenuItems WHERE name = ?", name)[0][0]


def lines(order_id):
    return q("SELECT item_id, quantity, price_at_order FROM OrderItems WHERE order_id = ? ORDER BY item_id", order_id)


def table_status(t):
    return q("SELECT status FROM Tables WHERE table_id = ?", t)[0][0]


# ================================================================== start, sign in
app = app_module.RestaurantApp(DB)
app.report_callback_exception = lambda *a: callback_errors.append(a)
app.tk.createcommand("bgerror", lambda *m: background_errors.append(m))
app.login_view.username.set("admin")
app.login_view.password.set("1234")
app.login_view.submit()
settle()
check("signed in", app.session is not None and app.session.employee_id == 1)

# ================================================================== A. seat customers
app.show_page("tables")
settle()
tp = app.shell.current
tp.select(2)
check("A free table 2 offers 'Seat customers' only", [n for n, b in tp.buttons.items() if packed(b)] == ["seat"])
tp.buttons["seat"].invoke()
settle()
new_order = q("SELECT order_id, employee_id, status FROM Orders WHERE table_id = 2 AND status = 'open'")
check("A seat table 2: new open order taken by the signed-in employee", len(new_order) == 1 and new_order[0][1:] == (1, "open"),
      new_order)
SEATED = new_order[0][0]
check("A table 2 is now occupied", table_status(2) == "occupied")
check("A tables page refreshed: card 2 shows the new order, still selected, order actions offered",
      tp.cards[2].table["order_id"] == SEATED and tp.selected_id == 2
      and [n for n, b in tp.buttons.items() if packed(b)] == ["open", "transfer", "pay", "cancel"])
check("A status message says what happened", app.status.kind == "success" and f"Order #{SEATED} is open" in app.status.text,
      app.status.text)
check_db("A after seating")

tp.select(4)
other(rs.open_order, 3, 4)  # another terminal seats table 4 while this screen still shows it free
before, n = dump(), len(LOG)
tp.buttons["seat"].invoke()
settle()
check("A seating an already occupied table is refused with the service's message",
      errors_since(n) == ["Table not found or already occupied."], errors_since(n))
check("A ... nothing else changed", dump() == before)
check("A ... the page refreshed and shows table 4 as occupied", tp.cards[4].table["status"] == "occupied"
      and "seat" not in [n_ for n_, b in tp.buttons.items() if packed(b)])
check_db("A after the refused seat")
OTHER_ORDER = q("SELECT order_id FROM Orders WHERE table_id = 4 AND status = 'open'")[0][0]

# ================================================================== B. open an existing order
card = tp.cards[3]
settle()
for _ in range(2):  # two quick clicks = a double-click (Tk can't generate <Double-Button-1> itself)
    card.event_generate("<ButtonPress-1>", x=20, y=20)
    card.event_generate("<ButtonRelease-1>", x=20, y=20)
settle()
op = app.shell.current
check("B double-clicking occupied table 3 opens order #27", op.key == "order" and op.order_id == 27)
order, bill = other(rs.get_order, 27), other(rs.get_bill, 27)
check("B header: order number, table, employee, open time and duration",
      op.header.title.cget("text") == "Order #27" and op.facts["table"].cget("text") == "Table 3"
      and op.facts["taken_by"].cget("text") == "Somchai Jaidee" and op.facts["opened"].cget("text").startswith("Today")
      and op.header.subtitle.cget("text").startswith("Open for "))
rows = [op.items.tree.item(i, "values") for i in op.items.tree.get_children()]
expected = [(l["name"], str(l["quantity"]), money(l["price_at_order"]), money(l["subtotal"])) for l in bill["lines"]]
check("B dishes, quantities, prices at order and subtotals come from get_bill", [tuple(r) for r in rows] == expected, rows)
check("B total shows get_bill's total", op.total.cget("text") == money(bill["total"]) == "395.00")
app.show_page("dashboard")
settle()
dash = app.shell.current
dash.orders.select(28)
dash.orders._activate()
settle()
check("B the dashboard's open-order list opens that order", app.shell.current.key == "order" and op.order_id == 28)

# ================================================================== C. add items
app.show_page("order", order_id=SEATED)
settle()
check("C the new order starts empty", op.items.count() == 0 and op.total.cget("text") == "0.00")
messages = []


def add_valid(d):
    d.search.set("pad")
    d.update_idletasks()
    d.menu.select(dish_id("Pad Thai"))
    d.quantity.set("2")
    d.add_button.invoke()
    messages.append(d.message.cget("text"))
    d.search.set("")
    d.menu.select(dish_id("Iced Tea"))
    d.add_button.invoke()
    messages.append(d.message.cget("text"))
    d.menu.select(dish_id("Pad Thai"))
    d.add_button.invoke()  # quantity was reset to 1; same dish again raises the quantity
    messages.append(d.message.cget("text"))
    d.close_button.invoke()


plan("AddItemDialog", add_valid)
op.buttons["add"].invoke()
settle()
check("C add Pad Thai x2, Iced Tea x1, Pad Thai x1: success messages in the dialog",
      messages == [f"Added 2 x Pad Thai to order #{SEATED}.", f"Added 1 x Iced Tea to order #{SEATED}.",
                   f"Added 1 x Pad Thai to order #{SEATED}."], messages)
check("C database: Pad Thai x3 and Iced Tea x1 at current menu prices",
      lines(SEATED) == sorted([(dish_id("Pad Thai"), 3, 80.0), (dish_id("Iced Tea"), 1, 30.0)]), lines(SEATED))
check("C order page refreshed with the service's total", op.items.count() == 2
      and op.total.cget("text") == money(other(rs.get_bill, SEATED)["total"]) == "270.00")
check_db("C after adding")

special = other(rs.add_menu_item, "Chef Special", "Main", 150)
before, result = dump(), {}


def nonexistent(d):
    d.load_menu()
    d.menu.select(special)
    other(rs.delete_menu_item, special)  # another terminal deletes the dish while the dialog is open
    d.add_button.invoke()
    result["message"], result["still_listed"] = d.message.cget("text"), str(special) in d.menu.rows
    d.close_button.invoke()


plan("AddItemDialog", nonexistent)
op.buttons["add"].invoke()
settle()
check("C a dish that no longer exists is refused with the service's message",
      result["message"] == f"Dish #{special} not found.", result)
check("C ... the dish leaves the list and the order is unchanged",
      not result["still_listed"] and lines(SEATED) == sorted([(dish_id("Pad Thai"), 3, 80.0), (dish_id("Iced Tea"), 1, 30.0)]))
water = dish_id("Water")


def sold_out(d):
    d.menu.select(water)
    other(rs.set_menu_availability, water, False)  # sold out while the dialog is open
    d.add_button.invoke()
    result["message"], result["still_listed"] = d.message.cget("text"), str(water) in d.menu.rows
    d.close_button.invoke()


plan("AddItemDialog", sold_out)
op.buttons["add"].invoke()
settle()
check("C a sold-out dish is refused with the service's message",
      result["message"] == "Water is sold out and cannot be ordered." and not result["still_listed"], result)
other(rs.set_menu_availability, water, True)
bad_quantities = {}


def invalid_quantities(d):
    d.menu.select(dish_id("Fried Rice"))
    for text in ("0", "-1", "abc", "1.5", ""):
        d.quantity.set(text)
        d.add_button.invoke()
        bad_quantities[text] = d.message.cget("text")
    d.menu.tree.selection_set(())
    d.update_idletasks()
    d.add_button.invoke()
    bad_quantities["no dish"] = d.message.cget("text")
    d.close_button.invoke()


before = dump()
plan("AddItemDialog", invalid_quantities)
op.buttons["add"].invoke()
settle()
QTY = "Quantity must be a whole number of at least 1."
check("C invalid quantities 0, -1, abc, 1.5 and empty are refused with the service's message",
      all(bad_quantities[t] == QTY for t in ("0", "-1", "abc", "1.5", "")), bad_quantities)
check("C no dish selected -> 'Select a dish first.'", bad_quantities["no dish"] == "Select a dish first.")
check("C refused adds changed nothing", dump() == before)
check_db("C after refused adds")

# ================================================================== D. remove items
iced = dish_id("Iced Tea")
op.items.select(iced)
settle()
before, n = dump(), len(LOG)
plan("ConfirmDialog", decline)
op.buttons["remove"].invoke()
settle()
check("D removing asks for confirmation first", LOG[n]["kind"] == "ConfirmDialog" and LOG[n]["title"] == "Remove Iced Tea?")
check("D 'Keep it' removes nothing", dump() == before)
op.items.select(iced)
plan("ConfirmDialog", confirm)
op.buttons["remove"].invoke()
settle()
check("D confirmed: Iced Tea removed from the order", lines(SEATED) == [(dish_id("Pad Thai"), 3, 80.0)])
check("D order page refreshed", op.items.count() == 1 and op.total.cget("text") == "240.00"
      and app.status.text == f"Removed Iced Tea from order #{SEATED}.")
check_db("D after removing")

# ================================================================== E. show bill
plan("BillDialog", lambda d: result.update(text=d.text_content))
op.buttons["bill"].invoke()
settle()
service_bill = other(rs.get_bill, SEATED)
check("E the bill lists the dishes and get_bill's total", "Pad Thai" in result["text"] and "3 x 80.00" in result["text"]
      and result["text"].rstrip().endswith(money(service_bill["total"])), result["text"].splitlines()[-1])

# ================================================================== F. transfer
app.show_page("tables")
settle()
tp.select(1)
free_now = [t["table_id"] for t in other(rs.table_overview) if t["status"] == "free"]
seen = {}


def to_table_6(d):
    seen["choices"] = sorted(int(k) for k in d.choice.rows)
    seen["disabled_before_choice"] = disabled(d.confirm_button)
    d.choice.select(6)
    d.update()  # let the selection event run, as it does after a real click
    seen["button"] = d.confirm_button.cget("text")
    d.confirm_button.invoke()


plan("TransferDialog", to_table_6)
tp.buttons["transfer"].invoke()
settle()
check("F the transfer dialog lists only the free tables", seen["choices"] == sorted(free_now), (seen, free_now))
check("F confirm waits for a choice, then names it", seen["disabled_before_choice"] and seen["button"] == "Transfer to table 6")
check("F order #28 moved to table 6: table 1 free, table 6 occupied, same items",
      q("SELECT table_id FROM Orders WHERE order_id = 28") == [(6,)] and table_status(1) == "free"
      and table_status(6) == "occupied")
check("F tables page refreshed both tables and follows the moved order",
      tp.cards[1].table["status"] == "free" and tp.cards[6].table["order_id"] == 28 and tp.selected_id == 6)
check_db("F after transferring")

before = dump()
plan("TransferDialog", decline)
tp.buttons["transfer"].invoke()
settle()
check("F 'Keep it here' moves nothing", dump() == before)

app.show_page("order", order_id=27)
settle()
n = len(LOG)


def to_table_8_taken_meanwhile(d):
    d.choice.select(8)
    d.update()
    other(rs.open_order, 2, 8)  # another terminal seats table 8 before this transfer is confirmed
    d.confirm_button.invoke()


plan("TransferDialog", to_table_8_taken_meanwhile)
op.buttons["transfer"].invoke()
settle()
check("F transfer to a table that became occupied is refused with the service's message",
      errors_since(n) == ["Table 8 is already occupied. Transfer rejected."], errors_since(n))
check("F ... order #27 stays on table 3", q("SELECT table_id FROM Orders WHERE order_id = 27") == [(3,)]
      and table_status(3) == "occupied")
check_db("F after the refused transfer")

# ================================================================== G. cancel
app.show_page("order", order_id=29)
settle()
before = dump()
plan("ConfirmDialog", decline)
op.buttons["cancel"].invoke()
settle()
check("G cancelling asks first and explains it", LOG[-1]["title"] == "Cancel order #29?"
      and "deletes the open order on table 7" in LOG[-1]["message"] and "can't be undone" in LOG[-1]["message"])
check("G 'Keep order' changes nothing", dump() == before)
plan("ConfirmDialog", confirm)
op.buttons["cancel"].invoke()
settle()
check("G order #29 cancelled: order and its items gone, table 7 free",
      q("SELECT COUNT(*) FROM Orders WHERE order_id = 29") == [(0,)]
      and q("SELECT COUNT(*) FROM OrderItems WHERE order_id = 29") == [(0,)] and table_status(7) == "free")
check("G the app shows the freed table on the floor", app.shell.current.key == "tables" and tp.selected_id == 7
      and tp.cards[7].table["status"] == "free" and app.status.text == "Cancelled order #29. Table 7 is free.")
check_db("G after cancelling")

app.show_page("order", order_id=1)
settle()
before, n = dump(), len(LOG)
op.cancel()  # the button is disabled for a paid order; call the action anyway, as a stale screen could
settle()
check("G cancelling a paid order is refused by the service, with no confirmation asked",
      [e["kind"] for e in LOG[n:]] == ["MessageDialog"]
      and errors_since(n) == ["Order #1 is already paid and cannot be cancelled. Its receipt is kept."], LOG[n:])
check("G ... nothing changed", dump() == before)

# ================================================================== H. pay
app.show_page("order", order_id=SEATED)
settle()
before = dump()
plan("PayDialog", decline)
op.buttons["pay"].invoke()
settle()
check("H 'Not yet' takes no payment", dump() == before)
seen = {}


def pay_by_card(d):
    seen["button"] = d.confirm_button.cget("text")
    d.method_buttons["card"].invoke()
    d.confirm_button.invoke()


plan("PayDialog", pay_by_card)
op.buttons["pay"].invoke()
settle()
check("H the pay dialog names the amount from get_bill", seen["button"] == "Pay 240.00", seen)
receipt = q("SELECT receipt_id, amount, method, employee_id, table_id FROM Receipt WHERE order_id = ?", SEATED)
check("H receipt created: 240.00 by card, issued by the signed-in employee, table 2",
      len(receipt) == 1 and receipt[0][1:] == (240.0, "card", 1, 2), receipt)
RECEIPT = receipt[0][0]
check("H receipt items copied from the order", q("SELECT item_id FROM ReceiptItems WHERE receipt_id = ?", RECEIPT)
      == [(dish_id("Pad Thai"),)])
check("H order is paid and table 2 is free", q("SELECT status FROM Orders WHERE order_id = ?", SEATED) == [("paid",)]
      and table_status(2) == "free")
check("H status message names the receipt", f"Receipt #{RECEIPT} issued" in app.status.text, app.status.text)
check_db("H after paying")
check("H the paid order now shows read-only with its receipt", packed(op.notice_row)
      and f"receipt #{RECEIPT}" in op.notice.cget("text") and op.badge.kind == "paid")
op.items.select(dish_id("Pad Thai"))
settle()
check("H add, remove, transfer, cancel and pay are disabled; the bill is still available",
      all(disabled(op.buttons[b]) for b in ("add", "remove", "transfer", "cancel", "pay")) and not disabled(op.buttons["bill"]))
before, n = dump(), len(LOG)
op.pay()
op.add_items()
op.transfer()
op.remove_item()
settle()
check("H actions on the paid order are refused by the service, not just by disabled buttons",
      errors_since(n) == ["Order not found or already paid.",
                          f"Order #{SEATED} is already paid. Paid orders cannot be modified.",
                          f"Order #{SEATED} is already paid. Paid orders cannot be modified.",
                          f"Order #{SEATED} is already paid. Paid orders cannot be modified."], errors_since(n))
check("H ... and nothing changed", dump() == before)

app.show_page("tables")
settle()
tp.select(5)
tp.buttons["seat"].invoke()
settle()
empty = q("SELECT order_id FROM Orders WHERE table_id = 5 AND status = 'open'")[0][0]
n = len(LOG)
plan("PayDialog", confirm)
tp.buttons["pay"].invoke()
settle()
check("H paying an empty order is refused with the service's message", errors_since(n) == ["Nothing to pay."]
      and table_status(5) == "occupied")
plan("ConfirmDialog", confirm)
tp.buttons["cancel"].invoke()
settle()
check("H ... and it can be cancelled from the Tables page", table_status(5) == "free"
      and q("SELECT COUNT(*) FROM Orders WHERE order_id = ?", empty) == [(0,)])
tp.select(6)
plan("PayDialog", confirm)  # cash is the default
tp.buttons["pay"].invoke()
settle()
check("H pay from the Tables page (cash): order #28 paid, table 6 free, card updated",
      q("SELECT method FROM Receipt WHERE order_id = 28") == [("cash",)] and table_status(6) == "free"
      and tp.cards[6].table["status"] == "free")
check_db("H after all payments")

# ================================================================== I. views match the database
app.show_page("dashboard")
settle()
tables = other(rs.table_overview)
today = other(rs.daily_sales_report, date.today(), date.today())
check("I dashboard figures match the database after all changes",
      dash.stats.values["free"].cget("text") == str(sum(t["status"] == "free" for t in tables))
      and dash.stats.values["open"].cget("text") == str(sum(1 for t in tables if t["order_id"]))
      and dash.stats.values["sales"].cget("text") == money(today[0]["total"] if today else 0))
check("I dashboard open orders match", sorted(int(k) for k in dash.orders.rows) == sorted(t["order_id"] for t in tables
                                                                                         if t["order_id"]))
app.show_page("tables")
settle()
check("I table cards match the database", all(tp.cards[t["table_id"]].table["status"] == t["status"]
                                              and tp.cards[t["table_id"]].table["order_id"] == t["order_id"] for t in tables))

# ================================================================== J. errors are readable
shown_errors = [e["message"] for e in LOG if e["kind"] == "MessageDialog" and e["error"]]
check(f"J all {len(shown_errors)} error dialogs show the service's own message, never a traceback",
      shown_errors and not any("Traceback" in m or "File \"" in m for m in shown_errors))
time.sleep(0.3)
settle()
check("J no unexpected errors in event handlers and no Tcl background errors",
      not callback_errors and not background_errors, (callback_errors[:1], background_errors[:1]))
check("J no gui_error.log written", not os.path.exists(app_module.ERROR_LOG))
check("J every planned dialog was used", not PLAN, PLAN)
check_db("J at the end")
app.close()

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
