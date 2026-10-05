"""Restaurant Table and Order System - Database Systems Project
Employee (cashier/waiter) program. Python + SQLite (sqlite3 is built in).

The file has two layers:
  * Service functions take parameters, run the SQL and return plain data (dicts and lists).
    Every change runs inside one transaction. When a business rule is broken they raise
    RestaurantError, whose message can be shown to the user as it is. They never call
    input() or print(), so the terminal menu and the GUI use the same functions.
  * CLI functions (the terminal menu, further down) ask for input, call a service
    function and print the result. Run this file to use the terminal menu.
"""
import sqlite3
import hashlib
import math
from datetime import date, datetime
from getpass import getpass

DB_FILE = "restaurant.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS Employees (
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    username    TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS Tables (
    table_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seats    INTEGER NOT NULL CHECK (seats > 0),
    status   TEXT NOT NULL DEFAULT 'free' CHECK (status IN ('free', 'occupied'))
);
CREATE TABLE IF NOT EXISTS MenuItems (
    item_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    category  TEXT NOT NULL,
    price     REAL NOT NULL CHECK (price >= 0),
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1))
);
CREATE TABLE IF NOT EXISTS Orders (
    order_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id    INTEGER NOT NULL REFERENCES Tables(table_id),
    employee_id INTEGER NOT NULL REFERENCES Employees(employee_id),
    order_time  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'paid'))
);
CREATE TABLE IF NOT EXISTS OrderItems (
    order_id       INTEGER NOT NULL REFERENCES Orders(order_id),
    item_id        INTEGER NOT NULL REFERENCES MenuItems(item_id),
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    price_at_order REAL NOT NULL,
    PRIMARY KEY (order_id, item_id)
);
CREATE TABLE IF NOT EXISTS Receipt (
    receipt_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES Orders(order_id),
    employee_id INTEGER NOT NULL REFERENCES Employees(employee_id),
    table_id    INTEGER NOT NULL REFERENCES Tables(table_id),
    amount      REAL NOT NULL CHECK (amount >= 0),
    method      TEXT NOT NULL,
    paid_time   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
-- Receipt <-> MenuItems is many-to-many (the Lists relationship)
CREATE TABLE IF NOT EXISTS ReceiptItems (
    receipt_id INTEGER NOT NULL REFERENCES Receipt(receipt_id),
    item_id    INTEGER NOT NULL REFERENCES MenuItems(item_id),
    PRIMARY KEY (receipt_id, item_id)
);

-- Trigger: when an order is paid, free its table
CREATE TRIGGER IF NOT EXISTS trg_free_table
AFTER UPDATE OF status ON Orders
WHEN NEW.status = 'paid'
BEGIN
    UPDATE Tables SET status = 'free' WHERE table_id = NEW.table_id;
END;

-- View: daily sales report
CREATE VIEW IF NOT EXISTS DailySales AS
SELECT date(paid_time) AS day, COUNT(*) AS receipts, SUM(amount) AS total
FROM Receipt
GROUP BY date(paid_time);
"""


class RestaurantError(Exception):
    """A business rule was broken. str(error) is a message meant for the user."""


class DishInUseError(RestaurantError):
    """The dish is on orders, so renaming or deleting it would change or break their history."""

    def __init__(self, message, item_id, available):
        super().__init__(message)
        self.item_id = item_id
        self.available = available


def connect(path=DB_FILE):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup(db):
    """Create the tables if needed. A brand-new database also gets a default employee (admin / 1234),
    5 tables and a small menu. Returns True when that default data was just created."""
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM Employees").fetchone()[0] == 0:
        pw = hashlib.sha256(b"1234").hexdigest()
        db.execute("INSERT INTO Employees (name, username, password) VALUES (?, ?, ?)",
                   ("Default Employee", "admin", pw))
        db.executemany("INSERT INTO Tables (seats) VALUES (?)", [(2,), (2,), (4,), (4,), (6,)])
        db.executemany(
            "INSERT INTO MenuItems (name, category, price) VALUES (?, ?, ?)",
            [("Pad Thai", "Main", 80), ("Fried Rice", "Main", 70), ("Tom Yum Soup", "Soup", 120),
             ("Spring Rolls", "Starter", 60), ("Iced Tea", "Drink", 30), ("Mango Sticky Rice", "Dessert", 90)])
        db.commit()
        return True
    return False


# =====================================================================================
# Service layer: parameters in, data out. No input() or print().
# =====================================================================================

def _rows(cur):
    """All rows of a query as dicts (column name -> value)."""
    names = [c[0] for c in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _row(cur):
    """The first row of a query as a dict, or None."""
    rows = _rows(cur)
    return rows[0] if rows else None


# ---------- Login ----------

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(db, username, password):
    """Check a login. Returns {'employee_id', 'name'}; never returns the password."""
    emp = _row(db.execute("SELECT employee_id, name FROM Employees WHERE username = ? AND password = ?",
                          ((username or "").strip(), hash_password(password or ""))))
    if emp is None:
        raise RestaurantError("Wrong username or password.")
    return emp


# ---------- Tables and seating ----------

def table_overview(db):
    """Every table with its status and, when occupied, its open order (order_id is None for a free table)."""
    return _rows(db.execute(
        "SELECT t.table_id, t.seats, t.status, o.order_id, o.order_time, e.name AS taken_by, "
        "(SELECT COUNT(*) FROM OrderItems oi WHERE oi.order_id = o.order_id) AS item_count, "
        "(SELECT COALESCE(SUM(oi.quantity * oi.price_at_order), 0) FROM OrderItems oi "
        " WHERE oi.order_id = o.order_id) AS total "
        "FROM Tables t "
        "LEFT JOIN Orders o ON o.order_id = (SELECT MIN(order_id) FROM Orders "
        "                                    WHERE table_id = t.table_id AND status = 'open') "
        "LEFT JOIN Employees e ON e.employee_id = o.employee_id "
        "ORDER BY t.table_id"))


def open_order(db, emp_id, table_id):
    """Seat customers: mark a free table occupied and open an order on it. Returns the new order id."""
    with db:  # one transaction: both statements succeed or neither does
        cur = db.execute("UPDATE Tables SET status = 'occupied' WHERE table_id = ? AND status = 'free'", (table_id,))
        if cur.rowcount == 0:
            raise RestaurantError("Table not found or already occupied.")
        cur = db.execute("INSERT INTO Orders (table_id, employee_id) VALUES (?, ?)", (table_id, emp_id))
    return cur.lastrowid


# ---------- Menu ----------

def list_categories(db):
    return [r[0] for r in db.execute("SELECT DISTINCT category FROM MenuItems ORDER BY category")]


def list_menu(db, keyword="", category=None, available_only=True):
    """Dishes whose name or category contains keyword, sorted by category and name.
    order_count is how many orders (open or paid) include the dish."""
    kw = f"%{(keyword or '').strip()}%"
    sql = ("SELECT item_id, name, category, price, available, "
           "(SELECT COUNT(*) FROM OrderItems oi WHERE oi.item_id = m.item_id) AS order_count "
           "FROM MenuItems m WHERE (name LIKE ? OR category LIKE ?)")
    params = [kw, kw]
    if available_only:
        sql += " AND available = 1"
    if category:
        sql += " AND category = ?"
        params.append(category)
    return _rows(db.execute(sql + " ORDER BY category, name", params))


def _check_price(price):
    try:
        price = float(price)
    except (TypeError, ValueError):
        raise RestaurantError("Price must be a number.") from None
    if not math.isfinite(price):
        raise RestaurantError("Price must be a number.")
    if price < 0:
        raise RestaurantError("Price cannot be negative.")
    return price


def _get_dish(db, item_id):
    dish = _row(db.execute(
        "SELECT item_id, name, category, price, available, "
        "(SELECT COUNT(*) FROM OrderItems oi WHERE oi.item_id = m.item_id) AS order_count "
        "FROM MenuItems m WHERE item_id = ?", (item_id,)))
    if dish is None:
        raise RestaurantError("Item not found.")
    return dish


def add_menu_item(db, name, category, price):
    """Add a dish (available by default). Returns its item id."""
    name, category = (name or "").strip(), (category or "").strip()
    if not name or not category:
        raise RestaurantError("Name and category are required.")
    price = _check_price(price)
    with db:
        cur = db.execute("INSERT INTO MenuItems (name, category, price) VALUES (?, ?, ?)", (name, category, price))
    return cur.lastrowid


def set_menu_price(db, item_id, price):
    price = _check_price(price)
    with db:  # old bills keep their price because OrderItems stores price_at_order
        cur = db.execute("UPDATE MenuItems SET price = ? WHERE item_id = ?", (price, item_id))
        if cur.rowcount == 0:
            raise RestaurantError("Item not found.")


def update_menu_item(db, item_id, name=None, category=None, price=None):
    """Edit a dish. Price and category can always change. The name can only change if the dish has
    never been ordered, because bills and receipts show the current dish name. Returns the dish."""
    dish = _get_dish(db, item_id)
    new_name = dish["name"] if name is None else name.strip()
    new_category = dish["category"] if category is None else category.strip()
    if not new_name or not new_category:
        raise RestaurantError("Name and category are required.")
    new_price = dish["price"] if price is None else _check_price(price)
    renaming = new_name != dish["name"]
    if renaming and dish["order_count"]:
        raise DishInUseError(
            f"{dish['name']} cannot be renamed: it is on {dish['order_count']} order(s), and their bills and "
            "receipts show the dish name. You can still change its price and category.",
            item_id, bool(dish["available"]))
    with db:  # the name only changes if the dish is still not on any order
        cur = db.execute(
            "UPDATE MenuItems SET name = ?, category = ?, price = ? WHERE item_id = ?"
            + (" AND NOT EXISTS (SELECT 1 FROM OrderItems WHERE item_id = ?)" if renaming else ""),
            (new_name, new_category, new_price, item_id) + ((item_id,) if renaming else ()))
        if cur.rowcount == 0:
            raise RestaurantError(f"{dish['name']} was just added to an order, so it cannot be renamed. Nothing changed.")
    return _get_dish(db, item_id)


def delete_menu_item(db, item_id):
    """Delete a dish that has never been ordered. Dishes with order history are kept;
    mark them sold out instead. Returns the deleted dish's name."""
    dish = _get_dish(db, item_id)
    if dish["order_count"]:
        hint = ("It is already sold out, so it cannot be added to new orders." if not dish["available"]
                else "Mark it sold out instead to stop new orders.")
        raise DishInUseError(
            f"{dish['name']} cannot be deleted: it is on {dish['order_count']} order(s), and deleting it would "
            f"break their bills and receipts. {hint}", item_id, bool(dish["available"]))
    with db:  # only deletes if the dish is still on no order or receipt; foreign keys also block it
        cur = db.execute("DELETE FROM MenuItems WHERE item_id = ? "
                         "AND NOT EXISTS (SELECT 1 FROM OrderItems WHERE item_id = ?) "
                         "AND NOT EXISTS (SELECT 1 FROM ReceiptItems WHERE item_id = ?)",
                         (item_id, item_id, item_id))
        if cur.rowcount == 0:
            raise RestaurantError(f"{dish['name']} was just added to an order. Nothing deleted.")
    return dish["name"]


def set_menu_availability(db, item_id, available):
    """Mark a dish available (True) or sold out (False). Sold-out dishes can't be added to orders."""
    with db:
        cur = db.execute("UPDATE MenuItems SET available = ? WHERE item_id = ?", (1 if available else 0, item_id))
        if cur.rowcount == 0:
            raise RestaurantError("Item not found.")


def toggle_menu_availability(db, item_id):
    """Switch a dish between available and sold out. Returns True if it is now available."""
    with db:
        cur = db.execute("UPDATE MenuItems SET available = 1 - available WHERE item_id = ?", (item_id,))
        if cur.rowcount == 0:
            raise RestaurantError("Item not found.")
    return bool(db.execute("SELECT available FROM MenuItems WHERE item_id = ?", (item_id,)).fetchone()[0])


# ---------- Orders ----------

def get_order(db, order_id):
    """Order header: table, who took it, when, status, and its receipt number once paid."""
    order = _row(db.execute(
        "SELECT o.order_id, o.table_id, o.employee_id, e.name AS taken_by, o.order_time, o.status, "
        "(SELECT r.receipt_id FROM Receipt r WHERE r.order_id = o.order_id) AS receipt_id "
        "FROM Orders o JOIN Employees e ON e.employee_id = o.employee_id WHERE o.order_id = ?", (order_id,)))
    if order is None:
        raise RestaurantError("Order not found.")
    return order


def check_order_editable(db, order_id):
    """Raise unless the order exists and is still open. Paid orders cannot be modified."""
    order = db.execute("SELECT status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
    if order is None:
        raise RestaurantError("Order not found.")
    if order[0] != 'open':
        raise RestaurantError(f"Order #{order_id} is already paid. Paid orders cannot be modified.")


def add_order_item(db, order_id, item_id, quantity):
    """Add a dish to an open order at the current menu price. If the dish is already on the order,
    its quantity goes up instead."""
    check_order_editable(db, order_id)
    dish = _row(db.execute("SELECT name, available FROM MenuItems WHERE item_id = ?", (item_id,)))
    if dish is None:
        raise RestaurantError(f"Dish #{item_id} not found.")
    if not dish["available"]:
        raise RestaurantError(f"{dish['name']} is sold out and cannot be ordered.")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise RestaurantError("Quantity must be a whole number of at least 1.")
    with db:
        # price_at_order copies the current menu price, so later price changes don't alter old bills
        cur = db.execute(
            "INSERT INTO OrderItems (order_id, item_id, quantity, price_at_order) "
            "SELECT ?, item_id, ?, price FROM MenuItems WHERE item_id = ? AND available = 1 "
            "AND EXISTS (SELECT 1 FROM Orders WHERE order_id = ? AND status = 'open') "
            "ON CONFLICT(order_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity",
            (order_id, quantity, item_id, order_id))
        if cur.rowcount == 0:  # the order was paid or the dish sold out after the checks above
            check_order_editable(db, order_id)
            raise RestaurantError(f"{dish['name']} is no longer available. Nothing added.")


def remove_order_item(db, order_id, item_id):
    """Remove a dish line from an open order."""
    check_order_editable(db, order_id)
    with db:
        cur = db.execute("DELETE FROM OrderItems WHERE order_id = ? AND item_id = ? "
                         "AND order_id IN (SELECT order_id FROM Orders WHERE status = 'open')", (order_id, item_id))
        if cur.rowcount == 0:
            check_order_editable(db, order_id)  # the order may have been paid meanwhile
            raise RestaurantError("Item not found on that order.")


def get_bill(db, order_id):
    """The order's lines (quantity x price at order) and total. Works for open and paid orders."""
    if db.execute("SELECT 1 FROM Orders WHERE order_id = ?", (order_id,)).fetchone() is None:
        raise RestaurantError("Order not found.")
    lines = _rows(db.execute(
        "SELECT oi.item_id, m.name, oi.quantity, oi.price_at_order, oi.quantity * oi.price_at_order AS subtotal "
        "FROM OrderItems oi JOIN MenuItems m ON m.item_id = oi.item_id WHERE oi.order_id = ?", (order_id,)))
    total = db.execute("SELECT COALESCE(SUM(quantity * price_at_order), 0) FROM OrderItems WHERE order_id = ?",
                       (order_id,)).fetchone()[0]
    return {"order_id": order_id, "lines": lines, "total": total}


# ---------- Payment ----------

def check_order_payable(db, order_id):
    """Raise unless the order exists and is open. Returns its table id."""
    order = db.execute("SELECT table_id, status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
    if order is None or order[1] != 'open':
        raise RestaurantError("Order not found or already paid.")
    return order[0]


def pay_order(db, order_id, emp_id, method="cash"):
    """Issue the receipt for an open order and mark it paid; the trigger frees the table.
    Returns the new receipt id."""
    table_id = check_order_payable(db, order_id)
    total = get_bill(db, order_id)["total"]
    if total == 0:
        raise RestaurantError("Nothing to pay.")
    method = (method or "").strip()
    if not method:
        raise RestaurantError("Choose a payment method.")
    with db:  # receipt, its items, and the order status change succeed or fail together
        cur = db.execute(
            "INSERT INTO Receipt (order_id, employee_id, table_id, amount, method) VALUES (?, ?, ?, ?, ?)",
            (order_id, emp_id, table_id, total, method))
        db.execute("INSERT INTO ReceiptItems (receipt_id, item_id) SELECT ?, item_id FROM OrderItems WHERE order_id = ?",
                   (cur.lastrowid, order_id))
        if db.execute("UPDATE Orders SET status = 'paid' WHERE order_id = ? AND status = 'open'",
                      (order_id,)).rowcount != 1:  # trigger frees the table
            raise RestaurantError("Order not found or already paid.")
    return cur.lastrowid


# ---------- Cancel ----------

def find_open_order(db, table_id):
    """The open order on a table (used to cancel by table number). Returns its order id."""
    if db.execute("SELECT 1 FROM Tables WHERE table_id = ?", (table_id,)).fetchone() is None:
        raise RestaurantError("Table not found.")
    rows = db.execute("SELECT order_id FROM Orders WHERE table_id = ? AND status = 'open'", (table_id,)).fetchall()
    if not rows:
        raise RestaurantError(f"No open order on table {table_id}.")
    if len(rows) > 1:
        raise RestaurantError(f"Table {table_id} has several open orders: " + ", ".join(f"#{r[0]}" for r in rows)
                              + "\nCancel by order id instead.")
    return rows[0][0]


def check_order_cancellable(db, order_id):
    """Raise unless the order exists and is open. Returns its table id."""
    order = db.execute("SELECT order_id, table_id, status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
    if order is None:
        raise RestaurantError("Order not found.")
    if order[2] != 'open':
        raise RestaurantError(f"Order #{order[0]} is already paid and cannot be cancelled. Its receipt is kept.")
    return order[1]


def cancel_open_order(db, order_id):
    """Delete an open order and its items, and free its table.
    Returns {'order_id', 'table_id', 'table_freed'}."""
    table_id = check_order_cancellable(db, order_id)
    with db:  # items, order, and table status change succeed or fail together
        # OrderItems rows go first because they reference the order (foreign key)
        db.execute("DELETE FROM OrderItems WHERE order_id = ? "
                   "AND order_id IN (SELECT order_id FROM Orders WHERE status = 'open')", (order_id,))
        cur = db.execute("DELETE FROM Orders WHERE order_id = ? AND status = 'open'", (order_id,))
        if cur.rowcount == 0:
            raise RestaurantError("Order is no longer open. Nothing cancelled.")
        # free the table unless another open order is still on it
        freed = db.execute(
            "UPDATE Tables SET status = 'free' WHERE table_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM Orders WHERE table_id = ? AND status = 'open')",
            (table_id, table_id)).rowcount
    return {"order_id": order_id, "table_id": table_id, "table_freed": bool(freed)}


# ---------- Transfer ----------

def transfer_order(db, src, dst):
    """Move the open order on table src to free table dst. Returns the order id (unchanged)."""
    if src == dst:
        raise RestaurantError("Source and destination are the same table. Nothing transferred.")
    if db.execute("SELECT 1 FROM Tables WHERE table_id = ?", (src,)).fetchone() is None:
        raise RestaurantError(f"Table {src} not found.")
    rows = db.execute("SELECT order_id FROM Orders WHERE table_id = ? AND status = 'open'", (src,)).fetchall()
    if not rows:
        raise RestaurantError(f"No open order on table {src}. Nothing transferred.")
    if len(rows) > 1:
        raise RestaurantError(f"Table {src} has several open orders: " + ", ".join(f"#{r[0]}" for r in rows)
                              + "\nNothing transferred.")
    order_id = rows[0][0]
    dest = db.execute("SELECT status FROM Tables WHERE table_id = ?", (dst,)).fetchone()
    if dest is None:
        raise RestaurantError(f"Table {dst} not found.")
    if dest[0] != 'free':
        raise RestaurantError(f"Table {dst} is already occupied. Transfer rejected.")
    with db:  # all three changes succeed together; any failure rolls all of them back
        if db.execute("UPDATE Tables SET status = 'occupied' WHERE table_id = ? AND status = 'free'",
                      (dst,)).rowcount != 1:
            raise sqlite3.Error(f"table {dst} is no longer free. Nothing transferred.")
        # only table_id changes: same order_id, same OrderItems and price_at_order, no receipt
        if db.execute("UPDATE Orders SET table_id = ? WHERE order_id = ? AND table_id = ? AND status = 'open'",
                      (dst, order_id, src)).rowcount != 1:
            raise sqlite3.Error(f"order #{order_id} could not be moved. Nothing transferred.")
        if db.execute("UPDATE Tables SET status = 'free' WHERE table_id = ? "
                      "AND NOT EXISTS (SELECT 1 FROM Orders WHERE table_id = ? AND status = 'open')",
                      (src, src)).rowcount != 1:
            raise sqlite3.Error(f"table {src} could not be freed. Nothing transferred.")
    return order_id


# ---------- Reports (optional date range; no dates = all time) ----------

def _date_range(start, end):
    """Check optional dates (YYYY-MM-DD strings or date objects). Returns them as 'YYYY-MM-DD' or None."""
    checked = []
    for label, value in (("Start", start), ("End", end)):
        if value is None or (isinstance(value, str) and not value.strip()):
            checked.append(None)
        elif isinstance(value, datetime):
            checked.append(value.date())
        elif isinstance(value, date):
            checked.append(value)
        else:
            try:
                checked.append(datetime.strptime(str(value).strip(), "%Y-%m-%d").date())
            except ValueError:
                raise RestaurantError(f"{label} date '{value}' is not a valid date. "
                                      "Use YYYY-MM-DD, for example 2026-10-05.") from None
    if checked[0] and checked[1] and checked[0] > checked[1]:
        raise RestaurantError("The start date cannot be after the end date.")
    return tuple(d.isoformat() if d else None for d in checked)


def _date_conditions(column, start, end):
    conditions, params = [], []
    if start:
        conditions.append(f"date({column}) >= ?")
        params.append(start)
    if end:
        conditions.append(f"date({column}) <= ?")
        params.append(end)
    return conditions, params


def daily_sales_report(db, start=None, end=None):
    """Receipts and sales per payment day, newest first."""
    start, end = _date_range(start, end)
    conditions, params = _date_conditions("day", start, end)
    sql = "SELECT day, receipts, total FROM DailySales"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    return _rows(db.execute(sql + " ORDER BY day DESC", params))


def best_sellers_report(db, start=None, end=None, limit=5):
    """Dishes on paid orders by quantity sold. A date range uses the payment date."""
    start, end = _date_range(start, end)
    conditions, params = _date_conditions("paid_time", start, end)
    sql = ("SELECT m.name, SUM(oi.quantity) AS sold FROM OrderItems oi "
           "JOIN MenuItems m ON m.item_id = oi.item_id JOIN Orders o ON o.order_id = oi.order_id "
           "WHERE o.status = 'paid'")
    if conditions:
        sql += " AND o.order_id IN (SELECT order_id FROM Receipt WHERE " + " AND ".join(conditions) + ")"
    return _rows(db.execute(sql + " GROUP BY m.item_id ORDER BY sold DESC LIMIT ?", params + [limit]))


def busiest_hours_report(db, start=None, end=None, limit=5):
    """Hours of the day with the most orders taken (open and paid). A date range uses the order date."""
    start, end = _date_range(start, end)
    conditions, params = _date_conditions("order_time", start, end)
    sql = "SELECT strftime('%H', order_time) AS hour, COUNT(*) AS orders FROM Orders"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    return _rows(db.execute(sql + " GROUP BY hour ORDER BY orders DESC LIMIT ?", params + [limit]))


# ---------- Receipts ----------

def list_receipts(db, start=None, end=None, receipt_id=None, order_id=None, table_id=None):
    """Receipts, newest first, optionally filtered by payment date range, receipt, order or table."""
    start, end = _date_range(start, end)
    conditions, params = _date_conditions("r.paid_time", start, end)
    for column, value in (("r.receipt_id", receipt_id), ("r.order_id", order_id), ("r.table_id", table_id)):
        if value is not None:
            conditions.append(f"{column} = ?")
            params.append(value)
    sql = ("SELECT r.receipt_id, r.order_id, r.table_id, r.paid_time, r.method, r.amount, "
           "e.name AS issued_by, t.name AS taken_by FROM Receipt r "
           "JOIN Employees e ON e.employee_id = r.employee_id "
           "JOIN Orders o ON o.order_id = r.order_id JOIN Employees t ON t.employee_id = o.employee_id")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    return _rows(db.execute(sql + " ORDER BY r.receipt_id DESC", params))


def get_receipt(db, receipt_id):
    """A receipt with who took the order, who issued the receipt, and its lines at historical prices."""
    receipt = _row(db.execute(
        "SELECT r.receipt_id, r.paid_time, r.method, r.amount, r.table_id, e.name AS issued_by, r.order_id, "
        "t.name AS taken_by "
        "FROM Receipt r JOIN Employees e ON e.employee_id = r.employee_id "
        "JOIN Orders o ON o.order_id = r.order_id JOIN Employees t ON t.employee_id = o.employee_id "
        "WHERE r.receipt_id = ?", (receipt_id,)))
    if receipt is None:
        raise RestaurantError("Receipt not found.")
    # ReceiptItems says which dishes are on the receipt; quantity and price come from OrderItems
    receipt["lines"] = _rows(db.execute(
        "SELECT m.name, oi.quantity, oi.price_at_order, oi.quantity * oi.price_at_order AS subtotal "
        "FROM ReceiptItems ri JOIN Receipt r ON r.receipt_id = ri.receipt_id "
        "JOIN OrderItems oi ON oi.order_id = r.order_id AND oi.item_id = ri.item_id "
        "JOIN MenuItems m ON m.item_id = ri.item_id WHERE ri.receipt_id = ?", (receipt_id,)))
    return receipt


# ---------- Employees ----------

def list_employees(db):
    """Employees with how many orders they took and receipts they issued. Passwords are never returned."""
    return _rows(db.execute(
        "SELECT e.employee_id, e.name, e.username, "
        "(SELECT COUNT(*) FROM Orders o WHERE o.employee_id = e.employee_id) AS orders, "
        "(SELECT COUNT(*) FROM Receipt r WHERE r.employee_id = e.employee_id) AS receipts "
        "FROM Employees e ORDER BY e.employee_id"))


def get_employee(db, employee_id):
    emp = _row(db.execute("SELECT employee_id, name, username FROM Employees WHERE employee_id = ?", (employee_id,)))
    if emp is None:
        raise RestaurantError("Employee not found.")
    return emp


def check_new_employee(db, name, username):
    """Raise unless name and username are filled in, the username has no spaces and is not taken.
    Returns the cleaned (name, username)."""
    name, username = (name or "").strip(), (username or "").strip()
    if not name or not username:
        raise RestaurantError("Name and username are required.")
    if any(c.isspace() for c in username):
        raise RestaurantError("Username cannot contain spaces.")
    if db.execute("SELECT 1 FROM Employees WHERE username = ?", (username,)).fetchone():
        raise RestaurantError(f"Username '{username}' is already taken.")
    return name, username


def add_employee(db, name, username, password):
    """Add an employee; the password is stored as a SHA-256 hash. Returns the new employee id."""
    name, username = check_new_employee(db, name, username)
    if not password:
        raise RestaurantError("Password is required.")
    with db:
        try:
            cur = db.execute("INSERT INTO Employees (name, username, password) VALUES (?, ?, ?)",
                             (name, username, hash_password(password)))
        except sqlite3.IntegrityError:  # the username was taken after the check above
            raise RestaurantError(f"Username '{username}' is already taken.") from None
    return cur.lastrowid


def check_employee_removable(db, target, current_emp_id):
    """Raise unless the employee exists, is not the logged-in employee and has no order or receipt
    history. Returns their name."""
    emp = get_employee(db, target)
    if target == current_emp_id:
        raise RestaurantError("You cannot remove yourself while you are logged in.")
    orders = db.execute("SELECT COUNT(*) FROM Orders WHERE employee_id = ?", (target,)).fetchone()[0]
    receipts = db.execute("SELECT COUNT(*) FROM Receipt WHERE employee_id = ?", (target,)).fetchone()[0]
    if orders or receipts:
        raise RestaurantError(f"Employee #{target} ({emp['name']}) cannot be removed: "
                              f"they are recorded on {orders} order(s) and {receipts} receipt(s).\n"
                              "Removing them would erase who handled those orders, so they are kept.")
    return emp["name"]


def remove_employee(db, target, current_emp_id):
    """Remove an employee with no order or receipt history. Returns their name."""
    name = check_employee_removable(db, target, current_emp_id)
    with db:  # only deletes if there is still no order or receipt history; foreign keys also block it
        cur = db.execute("DELETE FROM Employees WHERE employee_id = ? "
                         "AND NOT EXISTS (SELECT 1 FROM Orders WHERE employee_id = ?) "
                         "AND NOT EXISTS (SELECT 1 FROM Receipt WHERE employee_id = ?)",
                         (target, target, target))
        if cur.rowcount == 0:
            raise RestaurantError("Employee now has order history. Nothing removed.")
    return name


def change_password(db, target, new_password):
    """Set a new password for one employee. Returns their name."""
    emp = get_employee(db, target)
    if not new_password:
        raise RestaurantError("Password is required.")
    with db:  # only this employee's row in Employees changes
        db.execute("UPDATE Employees SET password = ? WHERE employee_id = ?", (hash_password(new_password), target))
    return emp["name"]


# =====================================================================================
# Terminal menu (CLI): asks for input, calls a service function, prints the result.
# =====================================================================================

def login(db):
    username = input("Username: ").strip()
    password = getpass("Password: ")
    try:
        emp = authenticate(db, username, password)
    except RestaurantError:
        return None
    return emp["employee_id"], emp["name"]


def show_tables(db):
    for t in table_overview(db):
        print(f"  Table {t['table_id']} | seats {t['seats']} | {t['status']}")


def seat_customers(db, emp_id):
    show_tables(db)
    table_id = int(input("Table to seat: "))
    try:
        order_id = open_order(db, emp_id, table_id)
    except RestaurantError as e:
        print(e)
        return
    print(f"Order #{order_id} opened for table {table_id}.")


def search_menu(db):
    kw = input("Search menu (name or category, blank = all): ").strip()
    rows = list_menu(db, kw)
    for r in rows:
        print(f"  [{r['item_id']}] {r['name']} ({r['category']}) - {r['price']:.2f}")
    if not rows:
        print("  No matching items.")


def add_item(db):
    order_id = int(input("Order id: "))
    try:
        check_order_editable(db, order_id)
        search_menu(db)
        item_id = int(input("Item id: "))
        qty = int(input("Quantity: "))
        add_order_item(db, order_id, item_id, qty)
        print("Item added.")
    except RestaurantError as e:
        print(e)


def remove_item(db):
    order_id = int(input("Order id: "))
    try:
        check_order_editable(db, order_id)
        item_id = int(input("Item id to remove: "))
        remove_order_item(db, order_id, item_id)
        print("Item removed.")
    except RestaurantError as e:
        print(e)


def print_bill(db, order_id=None):
    if order_id is None:
        order_id = int(input("Order id: "))
    try:
        bill = get_bill(db, order_id)
    except RestaurantError as e:
        print(e)
        return None
    print(f"--- Bill for order #{order_id} ---")
    for r in bill["lines"]:
        print(f"  {r['name']:<20} {r['quantity']} x {r['price_at_order']:.2f} = {r['subtotal']:.2f}")
    print(f"  TOTAL: {bill['total']:.2f}")
    return bill["total"]


def pay(db, emp_id):
    order_id = int(input("Order id: "))
    try:
        check_order_payable(db, order_id)
        total = print_bill(db, order_id)
        if total == 0:
            print("Nothing to pay.")
            return
        method = input("Payment method (cash/card): ").strip() or "cash"
        receipt_id = pay_order(db, order_id, emp_id, method)
        print(f"Receipt #{receipt_id} issued. Table is free again.")
    except RestaurantError as e:
        print(e)


def cancel_order(db):
    print("  a) By order id   b) By table number")
    choice = input("Choose: ").strip().lower()
    try:
        if choice == "a":
            order_id = int(input("Order id: "))
        elif choice == "b":
            order_id = find_open_order(db, int(input("Table number: ")))
        else:
            print("Invalid choice.")
            return
        table_id = check_order_cancellable(db, order_id)
        print_bill(db, order_id)
        if input(f"Cancel order #{order_id} on table {table_id}? (y/n): ").strip().lower() != "y":
            print("Nothing cancelled.")
            return
        result = cancel_open_order(db, order_id)
        print(f"Order #{order_id} cancelled." + (f" Table {table_id} is free again." if result["table_freed"] else ""))
    except RestaurantError as e:
        print(e)


def transfer_table(db):
    show_tables(db)
    src = int(input("Move from table: "))
    dst = int(input("Move to table: "))
    try:
        order_id = transfer_order(db, src, dst)
    except RestaurantError as e:
        print(e)
        return
    print(f"Order #{order_id} moved from table {src} to table {dst}.")
    for t in table_overview(db):
        if t["table_id"] in (src, dst):
            print(f"  Table {t['table_id']} | seats {t['seats']} | {t['status']}")


def daily_sales(db):
    print("--- Daily sales ---")
    for r in daily_sales_report(db):
        print(f"  {r['day']} | {r['receipts']} receipts | {r['total']:.2f}")


def best_sellers(db):
    print("--- Best-selling dishes ---")
    for r in best_sellers_report(db):
        print(f"  {r['name']:<20} {r['sold']} sold")


def busiest_hours(db):
    print("--- Busiest hours ---")
    for r in busiest_hours_report(db):
        print(f"  {r['hour']}:00 | {r['orders']} orders")


def reprint_receipt(db):
    receipt_id = int(input("Receipt id: "))
    try:
        receipt = get_receipt(db, receipt_id)
    except RestaurantError as e:
        print(e)
        return
    print(f"--- Receipt #{receipt['receipt_id']} ---")
    print(f"  Table {receipt['table_id']} | Order #{receipt['order_id']} | Issued by {receipt['issued_by']}")
    print(f"  Paid {receipt['paid_time']} by {receipt['method']}")
    for r in receipt["lines"]:
        print(f"  {r['name']:<20} {r['quantity']} x {r['price_at_order']:.2f} = {r['subtotal']:.2f}")
    print(f"  TOTAL: {receipt['amount']:.2f}")


def manage_menu(db):
    print("  a) List all   b) Add dish   c) Change price   d) Mark available/unavailable")
    choice = input("Choose: ").strip().lower()
    try:
        if choice == "a":
            for r in list_menu(db, available_only=False):
                print(f"  [{r['item_id']}] {r['name']} ({r['category']}) - {r['price']:.2f} | "
                      f"{'available' if r['available'] else 'unavailable'}")
        elif choice == "b":
            name = input("Name: ").strip()
            category = input("Category: ").strip()
            price = float(input("Price: "))
            add_menu_item(db, name, category, price)
            print("Dish added.")
        elif choice == "c":
            item_id = int(input("Item id: "))
            price = float(input("New price: "))
            set_menu_price(db, item_id, price)
            print("Price updated (old bills are not affected).")
        elif choice == "d":
            item_id = int(input("Item id: "))
            toggle_menu_availability(db, item_id)
            print("Availability toggled.")
        else:
            print("Invalid choice.")
    except RestaurantError as e:
        print(e)


def ask_new_password(label):
    # getpass (not shown on screen), typed twice; the password is never printed
    password = getpass(f"{label}: ")
    if not password:
        print("Password is required.")
        return None
    if getpass(f"Confirm {label.lower()}: ") != password:
        print("Passwords do not match.")
        return None
    return password


def manage_employees(db, emp_id):
    print("  a) List employees   b) Add employee   c) Remove employee   d) Change employee password   e) Back")
    choice = input("Choose: ").strip().lower()
    try:
        if choice == "a":
            for emp in list_employees(db):
                print(f"  [{emp['employee_id']}] {emp['name']} | username: {emp['username']}"
                      + (" (you)" if emp["employee_id"] == emp_id else ""))
        elif choice == "b":
            name = input("Name: ").strip()
            username = input("Username: ").strip()
            check_new_employee(db, name, username)
            password = ask_new_password("Password")
            if password is None:
                return
            new_id = add_employee(db, name, username, password)
            print(f"Employee #{new_id} ({name}) added. They log in as '{username}'.")
        elif choice == "c":
            target = int(input("Employee id: "))
            name = check_employee_removable(db, target, emp_id)
            if input(f"Remove employee #{target} ({name})? (y/n): ").strip().lower() != "y":
                print("Nothing removed.")
                return
            remove_employee(db, target, emp_id)
            print(f"Employee #{target} ({name}) removed.")
        elif choice == "d":
            target = int(input("Employee id: "))
            name = get_employee(db, target)["name"]
            password = ask_new_password("New password")
            if password is None:
                return
            change_password(db, target, password)
            print(f"Password changed for employee #{target} ({name}).")
        elif choice == "e":
            return
        else:
            print("Invalid choice.")
    except RestaurantError as e:
        print(e)


MENU = """
===== Restaurant System =====
1. Seat customers (open order)
2. Add item to order
3. Remove item from order
4. Show bill
5. Pay and issue receipt
6. Search menu
7. Report: daily sales
8. Report: best-selling dishes
9. Report: busiest hours
10. Reprint receipt
11. Manage menu
12. View tables
13. Cancel open order
14. Transfer a table
15. Manage employees
0. Exit
"""


def main():
    db = connect()
    setup(db)
    emp = login(db)
    if not emp:
        print("Invalid login.")
        return
    print(f"Welcome, {emp[1]}!")
    actions = {"1": lambda: seat_customers(db, emp[0]), "2": lambda: add_item(db), "3": lambda: remove_item(db),
               "4": lambda: print_bill(db), "5": lambda: pay(db, emp[0]), "6": lambda: search_menu(db),
               "7": lambda: daily_sales(db), "8": lambda: best_sellers(db), "9": lambda: busiest_hours(db),
               "10": lambda: reprint_receipt(db), "11": lambda: manage_menu(db), "12": lambda: show_tables(db),
               "13": lambda: cancel_order(db), "14": lambda: transfer_table(db),
               "15": lambda: manage_employees(db, emp[0])}
    while True:
        print(MENU)
        choice = input("Choose: ").strip()
        if choice == "0":
            break
        try:
            actions.get(choice, lambda: print("Invalid choice."))()
        except (ValueError, sqlite3.Error, RestaurantError) as e:
            print("Error:", e)
    db.close()


if __name__ == "__main__":
    main()
