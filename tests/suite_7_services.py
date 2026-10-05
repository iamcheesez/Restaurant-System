"""Service-layer tests: every service function called directly with parameters, no terminal involved.
Each section starts from its own fresh database (the seed_database.py demo data unless noted).

Checked throughout: business-rule failures raise RestaurantError with a clear message and leave the
database exactly as it was; service functions never print, ask for input or return passwords."""
import ast, builtins, contextlib, hashlib, io, os, re, shutil, sqlite3, sys
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
sys.path.insert(0, ROOT)
import restaurant_system as rs  # noqa: E402
import seed_database  # noqa: E402

results, printed, messages = [], [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def _no_terminal(*args, **kwargs):
    raise AssertionError("a service function asked for terminal input")


builtins.input = _no_terminal  # any service calling input() or getpass() crashes this suite
rs.getpass = _no_terminal


def call(fn, *args, **kwargs):
    """Call a service function and record anything it prints (it must print nothing)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*args, **kwargs)
    finally:
        if buf.getvalue():
            printed.append((fn.__name__, buf.getvalue()))


def fails(fn, *args, **kwargs):
    """The RestaurantError a call raises (or None if it raises none)."""
    try:
        call(fn, *args, **kwargs)
    except rs.RestaurantError as e:
        messages.append(str(e))
        return e
    return None


def msg(fn, *args, **kwargs):
    e = fails(fn, *args, **kwargs)
    return str(e) if e else None


def fresh(name, seeded=True):
    d = os.path.join(WORK_ROOT, "services", name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    path = os.path.join(d, "restaurant.db")
    if seeded:
        seed_database.seed(path)
    return rs.connect(path)


def dump(db):
    return list(db.iterdump())


def q(db, sql, *args):
    return db.execute(sql, args).fetchall()


def dish(db, name):
    return db.execute("SELECT item_id FROM MenuItems WHERE name = ?", (name,)).fetchone()[0]


def unchanged_after(db, fn, *args, expect=None, **kwargs):
    """Run a call that must fail; returns (message, database unchanged?)."""
    before = dump(db)
    e = fails(fn, db, *args, **kwargs)
    text = str(e) if e else None
    ok = text is not None and (expect is None or expect in text)
    return ok, dump(db) == before, text


def rejects(label, db, fn, *args, expect, **kwargs):
    ok, same, text = unchanged_after(db, fn, *args, expect=expect, **kwargs)
    check(f"{label}: rejected with a clear message", ok, text)
    check(f"{label}: database unchanged", same)


# ============================================================ 0. Structure
SERVICES = ["connect", "setup", "hash_password", "authenticate", "table_overview", "open_order", "list_categories",
            "list_menu", "add_menu_item", "set_menu_price", "update_menu_item", "delete_menu_item",
            "set_menu_availability", "toggle_menu_availability", "get_order", "check_order_editable",
            "add_order_item", "remove_order_item", "get_bill", "check_order_payable", "pay_order", "find_open_order",
            "check_order_cancellable", "cancel_open_order", "transfer_order", "daily_sales_report",
            "best_sellers_report", "busiest_hours_report", "list_receipts", "get_receipt", "list_employees",
            "get_employee", "check_new_employee", "add_employee", "check_employee_removable", "remove_employee",
            "change_password"]
CLI = {"login", "show_tables", "seat_customers", "search_menu", "add_item", "remove_item", "print_bill", "pay",
       "cancel_order", "transfer_table", "daily_sales", "best_sellers", "busiest_hours", "reprint_receipt",
       "manage_menu", "ask_new_password", "manage_employees", "main"}
missing = [n for n in SERVICES if not callable(getattr(rs, n, None))]
check("0 all service functions exist", not missing, missing)
tree = ast.parse(open(os.path.join(ROOT, "restaurant_system.py")).read())
io_calls = [(f.name, n.func.id) for f in tree.body if isinstance(f, ast.FunctionDef) and f.name not in CLI
            for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in ("input", "print", "getpass")]
check("0 no service function calls input(), print() or getpass()", not io_calls, io_calls)
check("0 RestaurantError is an Exception; DishInUseError is a RestaurantError",
      issubclass(rs.RestaurantError, Exception) and issubclass(rs.DishInUseError, rs.RestaurantError))

# ============================================================ 1. connect / setup
db = fresh("setup", seeded=False)
check("1 connect() turns foreign keys on", db.execute("PRAGMA foreign_keys").fetchone()[0] == 1)
check("1 setup() on a new database creates default data and returns True", call(rs.setup, db) is True)
check("1 setup() a second time returns False and adds nothing",
      call(rs.setup, db) is False and q(db, "SELECT COUNT(*) FROM Employees") == [(1,)])
check("1 connect(path) uses the given file", os.path.exists(os.path.join(WORK_ROOT, "services", "setup", "restaurant.db")))

# ============================================================ 2. Login
db = fresh("login")
emp = call(rs.authenticate, db, "admin", "1234")
check("2 authenticate returns id and name only", emp == {"employee_id": 1, "name": "Restaurant Manager"}, emp)
check("2 username is trimmed", call(rs.authenticate, db, "  somchai ", "somchai123")["employee_id"] == 2)
for label, u, p in (("wrong password", "admin", "nope"), ("unknown user", "ghost", "1234"), ("empty", "", "")):
    check(f"2 {label} -> 'Wrong username or password.'", msg(rs.authenticate, db, u, p) == "Wrong username or password.")
check("2 hash_password is SHA-256", rs.hash_password("1234") == hashlib.sha256(b"1234").hexdigest())

# ============================================================ 3. Tables and seating
db = fresh("tables")
tables = call(rs.table_overview, db)
occ = {t["table_id"]: t["order_id"] for t in tables if t["status"] == "occupied"}
check("3 table_overview: 8 tables, 1/3/7 occupied with orders 28/27/29", len(tables) == 8 and occ == {1: 28, 3: 27, 7: 29}, occ)
check("3 free tables have no order, 0 items, total 0",
      all(t["order_id"] is None and t["item_count"] == 0 and t["total"] == 0 for t in tables if t["status"] == "free"))
t3 = [t for t in tables if t["table_id"] == 3][0]
check("3 table 3 shows order 27: Somchai, 4 dishes, 395.00",
      (t3["taken_by"], t3["item_count"], t3["total"]) == ("Somchai Jaidee", 4, 395.0), t3)
check("3 table totals match get_bill", all(t["total"] == call(rs.get_bill, db, t["order_id"])["total"]
                                          for t in tables if t["order_id"]))
order = call(rs.open_order, db, 1, 2)
check("3 open_order on free table 2 -> new order 30, table occupied",
      order == 30 and q(db, "SELECT status FROM Tables WHERE table_id=2") == [("occupied",)]
      and call(rs.get_order, db, 30)["status"] == "open")
rejects("3 open_order on occupied table 3", db, rs.open_order, 1, 3, expect="Table not found or already occupied.")
rejects("3 open_order on unknown table 99", db, rs.open_order, 1, 99, expect="Table not found or already occupied.")

# ============================================================ 4. Menu lists
db = fresh("menu_lists")
check("4 list_categories", call(rs.list_categories, db) == ["Dessert", "Drink", "Main", "Soup", "Starter"])
names = [d["name"] for d in call(rs.list_menu, db)]
check("4 list_menu hides sold-out dishes by default", "Fresh Coconut" not in names and len(names) == 18)
allm = call(rs.list_menu, db, available_only=False)
check("4 list_menu(available_only=False) includes sold-out Fresh Coconut",
      len(allm) == 19 and [d["available"] for d in allm if d["name"] == "Fresh Coconut"] == [0])
check("4 keyword search is case-insensitive", [d["name"] for d in call(rs.list_menu, db, "CURRY")] ==
      ["Green Curry", "Massaman Curry"])
drinks = call(rs.list_menu, db, category="Drink")
check("4 category filter", {d["category"] for d in drinks} == {"Drink"} and "Fresh Coconut" not in
      [d["name"] for d in drinks])
check("4 no match -> empty list", call(rs.list_menu, db, "zzz") == [])
oc = {d["name"]: d["order_count"] for d in allm}
check("4 order_count matches OrderItems", all(oc[n] == q(db, "SELECT COUNT(*) FROM OrderItems WHERE item_id=?",
                                                         dish(db, n))[0][0] for n in oc))

# ============================================================ 5. Orders: get, add, remove, bill
db = fresh("orders")
o27 = call(rs.get_order, db, 27)
check("5 get_order(27): table 3, taken by Somchai, open, no receipt",
      (o27["table_id"], o27["taken_by"], o27["status"], o27["receipt_id"]) == (3, "Somchai Jaidee", "open", None), o27)
o1 = call(rs.get_order, db, 1)
check("5 get_order(1) is paid and has its receipt id",
      o1["status"] == "paid" and o1["receipt_id"] == q(db, "SELECT receipt_id FROM Receipt WHERE order_id=1")[0][0])
check("5 unknown order -> 'Order not found.' (get_order, get_bill, check_order_editable)",
      msg(rs.get_order, db, 999) == msg(rs.get_bill, db, 999) == msg(rs.check_order_editable, db, 999) == "Order not found.")
check("5 paid order is not editable",
      msg(rs.check_order_editable, db, 1) == "Order #1 is already paid. Paid orders cannot be modified.")

water = dish(db, "Water")
call(rs.add_order_item, db, 27, water, 2)
call(rs.add_order_item, db, 27, water, 1)
check("5 add_order_item adds at the current price and merges quantity",
      q(db, "SELECT quantity, price_at_order FROM OrderItems WHERE order_id=27 AND item_id=?", water) == [(3, 15.0)])
rejects("5 add nonexistent dish 999", db, rs.add_order_item, 27, 999, 1, expect="Dish #999 not found.")
rejects("5 add sold-out Fresh Coconut", db, rs.add_order_item, 27, dish(db, "Fresh Coconut"), 1,
        expect="Fresh Coconut is sold out and cannot be ordered.")
QTY = "Quantity must be a whole number of at least 1."
rejects("5 add quantity 0", db, rs.add_order_item, 27, water, 0, expect=QTY)
rejects("5 add quantity -1 to a dish already on the order", db, rs.add_order_item, 27, water, -1, expect=QTY)
rejects("5 add quantity 1.5", db, rs.add_order_item, 27, water, 1.5, expect=QTY)
rejects("5 add to unknown order", db, rs.add_order_item, 999, water, 1, expect="Order not found.")
rejects("5 add to paid order", db, rs.add_order_item, 1, water, 1, expect="Paid orders cannot be modified.")

call(rs.remove_order_item, db, 27, water)
check("5 remove_order_item removes the line",
      q(db, "SELECT COUNT(*) FROM OrderItems WHERE order_id=27 AND item_id=?", water) == [(0,)])
rejects("5 remove a dish that is not on the order", db, rs.remove_order_item, 27, water,
        expect="Item not found on that order.")
rejects("5 remove from unknown order", db, rs.remove_order_item, 999, 1, expect="Order not found.")
paid_item = q(db, "SELECT item_id FROM OrderItems WHERE order_id=1")[0][0]
rejects("5 remove from paid order", db, rs.remove_order_item, 1, paid_item, expect="Paid orders cannot be modified.")

bill = call(rs.get_bill, db, 27)
check("5 get_bill(27): 4 lines, subtotals = quantity x price, total 395.00",
      len(bill["lines"]) == 4 and all(abs(l["subtotal"] - l["quantity"] * l["price_at_order"]) < 1e-9
                                      for l in bill["lines"]) and bill["total"] == 395.0, bill["total"])
check("5 get_bill works for a paid order and matches its receipt",
      call(rs.get_bill, db, 1)["total"] == q(db, "SELECT amount FROM Receipt WHERE order_id=1")[0][0])

# ============================================================ 6. Payment
db = fresh("pay")
items_27 = q(db, "SELECT item_id FROM OrderItems WHERE order_id=27 ORDER BY item_id")
receipt = call(rs.pay_order, db, 27, 1, "card")
check("6 pay_order(27) -> receipt 27", receipt == 27)
check("6 receipt amount 395.00, method card, issued by employee 1, table 3",
      q(db, "SELECT amount, method, employee_id, table_id FROM Receipt WHERE receipt_id=27") == [(395.0, "card", 1, 3)])
check("6 ReceiptItems copy the order's dishes",
      q(db, "SELECT item_id FROM ReceiptItems WHERE receipt_id=27 ORDER BY item_id") == items_27)
check("6 order paid and table 3 freed",
      call(rs.get_order, db, 27)["status"] == "paid" and q(db, "SELECT status FROM Tables WHERE table_id=3") == [("free",)])
rejects("6 pay an already paid order", db, rs.pay_order, 27, 1, "cash", expect="Order not found or already paid.")
rejects("6 pay an unknown order", db, rs.pay_order, 999, 1, "cash", expect="Order not found or already paid.")
empty = call(rs.open_order, db, 1, 2)
rejects("6 pay an empty order", db, rs.pay_order, empty, 1, "cash", expect="Nothing to pay.")
rejects("6 pay with a blank method", db, rs.pay_order, 28, 1, "  ", expect="Choose a payment method.")
check("6 check_order_payable returns the table", call(rs.check_order_payable, db, 28) == 1)

# ============================================================ 7. Cancel
db = fresh("cancel")
check("7 find_open_order(3) -> 27", call(rs.find_open_order, db, 3) == 27)
check("7 find_open_order on a free table", msg(rs.find_open_order, db, 2) == "No open order on table 2.")
check("7 find_open_order on unknown table", msg(rs.find_open_order, db, 99) == "Table not found.")
check("7 check_order_cancellable(27) -> table 3", call(rs.check_order_cancellable, db, 27) == 3)
result = call(rs.cancel_open_order, db, 29)
check("7 cancel_open_order(29) frees table 7", result == {"order_id": 29, "table_id": 7, "table_freed": True}, result)
check("7 order 29 and its items are gone", q(db, "SELECT COUNT(*) FROM Orders WHERE order_id=29") == [(0,)]
      and q(db, "SELECT COUNT(*) FROM OrderItems WHERE order_id=29") == [(0,)])
rejects("7 cancel a paid order", db, rs.cancel_open_order, 1,
        expect="Order #1 is already paid and cannot be cancelled. Its receipt is kept.")
rejects("7 cancel an unknown order", db, rs.cancel_open_order, 999, expect="Order not found.")

# ============================================================ 8. Transfer
db = fresh("transfer")
items_28 = q(db, "SELECT * FROM OrderItems WHERE order_id=28 ORDER BY item_id")
check("8 transfer_order(1 -> 6) returns the same order 28", call(rs.transfer_order, db, 1, 6) == 28)
check("8 table 1 free, table 6 occupied, order 28 on table 6, items unchanged",
      q(db, "SELECT status FROM Tables WHERE table_id IN (1, 6) ORDER BY table_id") == [("free",), ("occupied",)]
      and q(db, "SELECT table_id FROM Orders WHERE order_id=28") == [(6,)]
      and q(db, "SELECT * FROM OrderItems WHERE order_id=28 ORDER BY item_id") == items_28)
rejects("8 same table", db, rs.transfer_order, 6, 6, expect="Source and destination are the same table.")
rejects("8 unknown source table", db, rs.transfer_order, 99, 2, expect="Table 99 not found.")
rejects("8 unknown destination table", db, rs.transfer_order, 6, 99, expect="Table 99 not found.")
rejects("8 occupied destination", db, rs.transfer_order, 6, 3, expect="Table 3 is already occupied. Transfer rejected.")
rejects("8 source with no open order", db, rs.transfer_order, 2, 4, expect="No open order on table 2. Nothing transferred.")

# ============================================================ 9. Reports
db = fresh("reports")
OLD_DAILY = "SELECT day, receipts, total FROM DailySales ORDER BY day DESC"
OLD_BEST = ("SELECT m.name, SUM(oi.quantity) AS sold FROM OrderItems oi JOIN MenuItems m ON m.item_id = oi.item_id "
            "JOIN Orders o ON o.order_id = oi.order_id WHERE o.status = 'paid' GROUP BY m.item_id ORDER BY sold DESC LIMIT 5")
OLD_HOURS = ("SELECT strftime('%H', order_time) AS hour, COUNT(*) AS orders FROM Orders "
             "GROUP BY hour ORDER BY orders DESC LIMIT 5")
tup = lambda rows: [tuple(r.values()) for r in rows]
check("9 no dates: daily sales identical to the original all-time query", tup(call(rs.daily_sales_report, db)) == q(db, OLD_DAILY))
check("9 no dates: best sellers identical to the original query", tup(call(rs.best_sellers_report, db)) == q(db, OLD_BEST))
check("9 no dates: busiest hours identical to the original query", tup(call(rs.busiest_hours_report, db)) == q(db, OLD_HOURS))
check("9 blank date strings mean all time",
      call(rs.daily_sales_report, db, "", " ") == call(rs.daily_sales_report, db))

days = [r[0] for r in q(db, OLD_DAILY)]
first, last, mid = days[-1], days[0], days[len(days) // 2]
one_day = call(rs.daily_sales_report, db, mid, mid)
check("9 daily sales for one day = that day's all-time row",
      tup(one_day) == [r for r in q(db, OLD_DAILY) if r[0] == mid], one_day)
check("9 daily sales over the full range = all time", call(rs.daily_sales_report, db, first, last) ==
      call(rs.daily_sales_report, db))
check("9 start date only", [r["day"] for r in call(rs.daily_sales_report, db, start=mid)] == [d for d in days if d >= mid])
check("9 end date only", [r["day"] for r in call(rs.daily_sales_report, db, end=mid)] == [d for d in days if d <= mid])
check("9 range with no sales -> empty", call(rs.daily_sales_report, db, "2000-01-01", "2000-01-31") == [])
today = date.today()
check("9 date objects accepted", call(rs.daily_sales_report, db, today, datetime.now()) ==
      call(rs.daily_sales_report, db, today.isoformat(), today.isoformat()))

paid_lines = q(db, "SELECT date(r.paid_time), m.name, oi.quantity FROM OrderItems oi JOIN Orders o ON o.order_id = "
                   "oi.order_id JOIN Receipt r ON r.order_id = o.order_id JOIN MenuItems m ON m.item_id = oi.item_id "
                   "WHERE o.status = 'paid'")
order_rows = q(db, "SELECT date(order_time), strftime('%H', order_time) FROM Orders")


def expected_sold(lo, hi):
    out = {}
    for d, name, n in paid_lines:
        if lo <= d <= hi:
            out[name] = out.get(name, 0) + n
    return out


def expected_hours(lo, hi):
    out = {}
    for d, h in order_rows:
        if lo <= d <= hi:
            out[h] = out.get(h, 0) + 1
    return out


for lo, hi in ((mid, mid), (first, mid), (mid, last), (first, last)):
    got_best = {r["name"]: r["sold"] for r in call(rs.best_sellers_report, db, lo, hi, limit=100)}
    got_hours = {r["hour"]: r["orders"] for r in call(rs.busiest_hours_report, db, lo, hi, limit=100)}
    check(f"9 best sellers {lo}..{hi} match a hand count (by payment date)", got_best == expected_sold(lo, hi))
    check(f"9 busiest hours {lo}..{hi} match a hand count (by order date)", got_hours == expected_hours(lo, hi))
check("9 limit is respected", len(call(rs.best_sellers_report, db, first, last, limit=3)) == 3)

for report in (rs.daily_sales_report, rs.best_sellers_report, rs.busiest_hours_report):
    name = report.__name__
    for bad in ("2026-13-01", "2026-02-30", "abc", "05/10/2026", "2026/10/05"):
        m = msg(report, db, bad, None)
        check(f"9 {name}: invalid start '{bad}' rejected", m == f"Start date '{bad}' is not a valid date. "
              "Use YYYY-MM-DD, for example 2026-10-05.", m)
    check(f"9 {name}: invalid end date rejected", (msg(report, db, None, "2026-10-32") or "").startswith("End date '2026-10-32'"))
    check(f"9 {name}: start after end rejected",
          msg(report, db, "2026-10-05", "2026-10-01") == "The start date cannot be after the end date.")

# ============================================================ 10. Receipts
db = fresh("receipts")
receipts = call(rs.list_receipts, db)
check("10 list_receipts: 26 receipts, newest first", [r["receipt_id"] for r in receipts] == list(range(26, 0, -1)))
check("10 list rows carry issued_by and taken_by, nothing secret",
      set(receipts[0]) == {"receipt_id", "order_id", "table_id", "paid_time", "method", "amount", "issued_by", "taken_by"})
check("10 filter by receipt id", [r["receipt_id"] for r in call(rs.list_receipts, db, receipt_id=3)] == [3])
check("10 filter by order id", [r["order_id"] for r in call(rs.list_receipts, db, order_id=5)] == [5])
by_table = call(rs.list_receipts, db, table_id=2)
check("10 filter by table", by_table and all(r["table_id"] == 2 for r in by_table) and
      len(by_table) == q(db, "SELECT COUNT(*) FROM Receipt WHERE table_id=2")[0][0])
by_day = call(rs.list_receipts, db, mid, mid)
check("10 filter by payment date", by_day and all(r["paid_time"].startswith(mid) for r in by_day) and
      len(by_day) == q(db, "SELECT COUNT(*) FROM Receipt WHERE date(paid_time)=?", mid)[0][0])
check("10 invalid date rejected", msg(rs.list_receipts, db, "nope") is not None)
r3 = call(rs.get_receipt, db, 3)
check("10 get_receipt(3) shows Pad Thai at the old price 75.00",
      any(l["name"] == "Pad Thai" and l["price_at_order"] == 75.0 for l in r3["lines"]))
check("10 receipt total = sum of its lines",
      abs(r3["amount"] - sum(l["subtotal"] for l in r3["lines"])) < 1e-9)
raw = q(db, "SELECT r.receipt_id, te.name, ie.name FROM Receipt r JOIN Orders o ON o.order_id = r.order_id "
            "JOIN Employees te ON te.employee_id = o.employee_id JOIN Employees ie ON ie.employee_id = r.employee_id "
            "WHERE te.employee_id != ie.employee_id LIMIT 1")[0]
split = call(rs.get_receipt, db, raw[0])
check("10 get_receipt shows who took the order and who issued the receipt",
      (split["taken_by"], split["issued_by"]) == (raw[1], raw[2]), raw)
check("10 unknown receipt", msg(rs.get_receipt, db, 999) == "Receipt not found.")

# ============================================================ 11. Menu management
db = fresh("menu_admin")
history = lambda: (q(db, "SELECT * FROM OrderItems ORDER BY order_id, item_id"),
                   [call(rs.get_receipt, db, r) for r in range(1, 27)])
hist0 = history()
tea = call(rs.add_menu_item, db, "  Thai Tea ", "Drink", 45)
check("11 add_menu_item adds an available dish (name trimmed)",
      q(db, "SELECT name, category, price, available FROM MenuItems WHERE item_id=?", tea) == [("Thai Tea", "Drink", 45.0, 1)])
rejects("11 add without a name", db, rs.add_menu_item, " ", "Drink", 10, expect="Name and category are required.")
rejects("11 add with a negative price", db, rs.add_menu_item, "X", "Main", -5, expect="Price cannot be negative.")
for bad in ("abc", float("nan"), float("inf"), None):
    rejects(f"11 add with price {bad!r}", db, rs.add_menu_item, "X", "Main", bad, expect="Price must be a number.")

pad = dish(db, "Pad Thai")
call(rs.set_menu_price, db, pad, 85)
check("11 set_menu_price changes the menu price only", q(db, "SELECT price FROM MenuItems WHERE item_id=?", pad) == [(85.0,)]
      and history() == hist0)
rejects("11 set a negative price", db, rs.set_menu_price, pad, -1, expect="Price cannot be negative.")
rejects("11 set price of unknown dish", db, rs.set_menu_price, 999, 10, expect="Item not found.")

e = fails(rs.update_menu_item, db, pad, name="Pad Thai Special")
check("11 renaming an ordered dish raises DishInUseError",
      isinstance(e, rs.DishInUseError) and "cannot be renamed" in str(e) and "order(s)" in str(e) and e.item_id == pad, e)
rejects("11 renaming an ordered dish", db, rs.update_menu_item, pad, name="Pad Thai Special", expect="cannot be renamed")
check("11 ... its name, old bills and receipts are unchanged",
      q(db, "SELECT name FROM MenuItems WHERE item_id=?", pad) == [("Pad Thai",)] and history() == hist0)
upd = call(rs.update_menu_item, db, pad, name="Pad Thai", category="Noodles", price=82)
check("11 ordered dish: price and category can change (same name is fine)",
      (upd["name"], upd["category"], upd["price"]) == ("Pad Thai", "Noodles", 82.0) and history() == hist0, upd)
upd = call(rs.update_menu_item, db, tea, name="Thai Milk Tea", price=50)
check("11 renaming a never-ordered dish works",
      q(db, "SELECT name, price FROM MenuItems WHERE item_id=?", tea) == [("Thai Milk Tea", 50.0)] and upd["name"] == "Thai Milk Tea")
rejects("11 update with an empty name", db, rs.update_menu_item, tea, name=" ", expect="Name and category are required.")
rejects("11 update with an invalid price", db, rs.update_menu_item, tea, price="x", expect="Price must be a number.")
rejects("11 update an unknown dish", db, rs.update_menu_item, 999, price=1, expect="Item not found.")

check("11 deleting a never-ordered dish works", call(rs.delete_menu_item, db, tea) == "Thai Milk Tea"
      and q(db, "SELECT COUNT(*) FROM MenuItems WHERE item_id=?", tea) == [(0,)])
e = fails(rs.delete_menu_item, db, pad)
check("11 deleting an ordered dish raises DishInUseError suggesting sold out",
      isinstance(e, rs.DishInUseError) and "cannot be deleted" in str(e) and "Mark it sold out instead" in str(e)
      and e.available is True, e)
rejects("11 deleting an ordered dish", db, rs.delete_menu_item, pad, expect="cannot be deleted")
call(rs.set_menu_availability, db, pad, False)
e = fails(rs.delete_menu_item, db, pad)
check("11 deleting an ordered, sold-out dish says it is already sold out",
      isinstance(e, rs.DishInUseError) and "already sold out" in str(e) and e.available is False, e)
check("11 ... the dish and all history are still there",
      q(db, "SELECT COUNT(*) FROM MenuItems WHERE item_id=?", pad) == [(1,)] and history() == hist0)
spare = call(rs.add_menu_item, db, "Spare", "Main", 10)
call(rs.set_menu_availability, db, spare, False)
check("11 a never-ordered sold-out dish can be deleted", call(rs.delete_menu_item, db, spare) == "Spare")
rejects("11 delete an unknown dish", db, rs.delete_menu_item, 999, expect="Item not found.")
try:
    db.execute("DELETE FROM MenuItems WHERE item_id = ?", (pad,))
    fk = False
except sqlite3.IntegrityError:
    fk = True
db.rollback()
check("11 foreign keys also block deleting an ordered dish directly", fk)
check("11 sold-out dish hidden from list_menu, shown again when available",
      pad not in [d["item_id"] for d in call(rs.list_menu, db)]
      and (call(rs.set_menu_availability, db, pad, True) is None) and pad in [d["item_id"] for d in call(rs.list_menu, db)])
check("11 toggle_menu_availability returns the new state",
      call(rs.toggle_menu_availability, db, pad) is False and call(rs.toggle_menu_availability, db, pad) is True)
rejects("11 set availability of unknown dish", db, rs.set_menu_availability, 999, True, expect="Item not found.")
rejects("11 toggle unknown dish", db, rs.toggle_menu_availability, 999, expect="Item not found.")

# ============================================================ 12. Employees
db = fresh("employees")
emps = call(rs.list_employees, db)
check("12 list_employees: 5 employees, no password field",
      len(emps) == 5 and all(set(e) == {"employee_id", "name", "username", "orders", "receipts"} for e in emps))
check("12 order/receipt counts match the database", all(
    (e["orders"], e["receipts"]) == (q(db, "SELECT COUNT(*) FROM Orders WHERE employee_id=?", e["employee_id"])[0][0],
                                     q(db, "SELECT COUNT(*) FROM Receipt WHERE employee_id=?", e["employee_id"])[0][0])
    for e in emps) and [(e["orders"], e["receipts"]) for e in emps if e["username"] == "mali"] == [(0, 0)])
check("12 get_employee", call(rs.get_employee, db, 2) == {"employee_id": 2, "name": "Somchai Jaidee", "username": "somchai"})
check("12 get_employee unknown", msg(rs.get_employee, db, 99) == "Employee not found.")
check("12 check_new_employee trims and returns the values", call(rs.check_new_employee, db, " Pim ", " pim ") == ("Pim", "pim"))
for label, n, u, expect in (("empty name", "", "x", "Name and username are required."),
                            ("username with a space", "X", "a b", "Username cannot contain spaces."),
                            ("taken username", "X", "admin", "Username 'admin' is already taken.")):
    rejects(f"12 add employee: {label}", db, rs.add_employee, n, u, "pw", expect=expect)
rejects("12 add employee: empty password", db, rs.add_employee, "Pim", "pim", "", expect="Password is required.")
new_id = call(rs.add_employee, db, "Pim Sukjai", "pim", "pim-pass")
check("12 add_employee stores the SHA-256 hash and the new login works",
      q(db, "SELECT password FROM Employees WHERE employee_id=?", new_id) == [(hashlib.sha256(b"pim-pass").hexdigest(),)]
      and call(rs.authenticate, db, "pim", "pim-pass")["employee_id"] == new_id)

hist_tables = lambda: [l for l in dump(db) if not l.startswith('INSERT INTO "Employees"')]
h0 = hist_tables()
check("12 check_employee_removable: unknown", msg(rs.check_employee_removable, db, 99, 1) == "Employee not found.")
check("12 ... yourself", msg(rs.check_employee_removable, db, 1, 1) == "You cannot remove yourself while you are logged in.")
m = msg(rs.check_employee_removable, db, 2, 1)
check("12 ... someone with history, with counts and reason",
      m is not None and m.startswith("Employee #2 (Somchai Jaidee) cannot be removed: they are recorded on")
      and "erase who handled those orders" in m, m)
rejects("12 remove_employee with history", db, rs.remove_employee, 2, 1, expect="cannot be removed")
check("12 remove_employee without history", call(rs.remove_employee, db, 5, 1) == "Mali Chaiyo"
      and q(db, "SELECT COUNT(*) FROM Employees WHERE employee_id=5") == [(0,)])
check("12 removing again -> not found", msg(rs.remove_employee, db, 5, 1) == "Employee not found.")
other_hashes = q(db, "SELECT employee_id, password FROM Employees WHERE employee_id != 2 ORDER BY employee_id")
check("12 change_password returns the name", call(rs.change_password, db, 2, "new-som") == "Somchai Jaidee")
check("12 ... new password works, old one fails",
      call(rs.authenticate, db, "somchai", "new-som")["employee_id"] == 2
      and msg(rs.authenticate, db, "somchai", "somchai123") == "Wrong username or password.")
check("12 ... other employees' passwords unchanged",
      q(db, "SELECT employee_id, password FROM Employees WHERE employee_id != 2 ORDER BY employee_id") == other_hashes)
rejects("12 change_password: empty", db, rs.change_password, 2, "", expect="Password is required.")
rejects("12 change_password: unknown employee", db, rs.change_password, 99, "x", expect="Employee not found.")
check("12 employee operations never touched orders, receipts, tables or menu", hist_tables() == h0)

# ============================================================ 13. Nothing printed, no secrets in messages
check("13 no service function printed anything", not printed, printed[:3])
secrets = ["1234", "somchai123", "nok123", "anan123", "mali123", "pim-pass", "new-som"]
leaks = [m for m in messages if any(s in m for s in secrets) or re.search(r"[0-9a-f]{64}", m)]
check(f"13 none of the {len(messages)} error messages contains a password or hash", not leaks, leaks[:3])

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
