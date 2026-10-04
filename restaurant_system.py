"""Restaurant Table and Order System - Database Systems Project
Employee (cashier/waiter) console program. Python + SQLite (sqlite3 is built in).
Only connect() is non-SQL setup; every menu action runs SQL.
"""
import sqlite3
import hashlib
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


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup(db):
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


def login(db):
    username = input("Username: ").strip()
    password = getpass("Password: ")
    hashed = hashlib.sha256(password.encode()).hexdigest()
    return db.execute("SELECT employee_id, name FROM Employees WHERE username = ? AND password = ?",
                      (username, hashed)).fetchone()


def show_tables(db):
    for t in db.execute("SELECT table_id, seats, status FROM Tables ORDER BY table_id"):
        print(f"  Table {t[0]} | seats {t[1]} | {t[2]}")


def seat_customers(db, emp_id):
    show_tables(db)
    table_id = int(input("Table to seat: "))
    with db:  # one transaction: both statements succeed or neither does
        cur = db.execute("UPDATE Tables SET status = 'occupied' WHERE table_id = ? AND status = 'free'", (table_id,))
        if cur.rowcount == 0:
            print("Table not found or already occupied.")
            return
        cur = db.execute("INSERT INTO Orders (table_id, employee_id) VALUES (?, ?)", (table_id, emp_id))
    print(f"Order #{cur.lastrowid} opened for table {table_id}.")


def search_menu(db):
    kw = input("Search menu (name or category, blank = all): ").strip()
    rows = db.execute(
        "SELECT item_id, name, category, price FROM MenuItems "
        "WHERE available = 1 AND (name LIKE ? OR category LIKE ?) ORDER BY category, name",
        (f"%{kw}%", f"%{kw}%")).fetchall()
    for r in rows:
        print(f"  [{r[0]}] {r[1]} ({r[2]}) - {r[3]:.2f}")
    if not rows:
        print("  No matching items.")


def add_item(db):
    order_id = int(input("Order id: "))
    order = db.execute("SELECT status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
    if order is None:
        print("Order not found.")
        return
    if order[0] != 'open':
        print(f"Order #{order_id} is already paid. Paid orders cannot be modified.")
        return
    search_menu(db)
    item_id = int(input("Item id: "))
    qty = int(input("Quantity: "))
    with db:
        # price_at_order copies the current menu price, so later price changes don't alter old bills
        db.execute(
            "INSERT INTO OrderItems (order_id, item_id, quantity, price_at_order) "
            "SELECT ?, item_id, ?, price FROM MenuItems WHERE item_id = ? AND available = 1 "
            "ON CONFLICT(order_id, item_id) DO UPDATE SET quantity = quantity + excluded.quantity",
            (order_id, qty, item_id))
    print("Item added.")


def remove_item(db):
    order_id = int(input("Order id: "))
    order = db.execute("SELECT status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
    if order is None:
        print("Order not found.")
        return
    if order[0] != 'open':
        print(f"Order #{order_id} is already paid. Paid orders cannot be modified.")
        return
    item_id = int(input("Item id to remove: "))
    with db:
        cur = db.execute("DELETE FROM OrderItems WHERE order_id = ? AND item_id = ?", (order_id, item_id))
    print("Item removed." if cur.rowcount else "Item not found on that order.")


def print_bill(db, order_id=None):
    if order_id is None:
        order_id = int(input("Order id: "))
    rows = db.execute(
        "SELECT m.name, oi.quantity, oi.price_at_order, oi.quantity * oi.price_at_order "
        "FROM OrderItems oi JOIN MenuItems m ON m.item_id = oi.item_id WHERE oi.order_id = ?", (order_id,)).fetchall()
    total = db.execute("SELECT COALESCE(SUM(quantity * price_at_order), 0) FROM OrderItems WHERE order_id = ?",
                       (order_id,)).fetchone()[0]
    print(f"--- Bill for order #{order_id} ---")
    for r in rows:
        print(f"  {r[0]:<20} {r[1]} x {r[2]:.2f} = {r[3]:.2f}")
    print(f"  TOTAL: {total:.2f}")
    return total


def pay(db, emp_id):
    order_id = int(input("Order id: "))
    order = db.execute("SELECT table_id, status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
    if order is None or order[1] != 'open':
        print("Order not found or already paid.")
        return
    total = print_bill(db, order_id)
    if total == 0:
        print("Nothing to pay.")
        return
    method = input("Payment method (cash/card): ").strip() or "cash"
    with db:  # receipt, its items, and the order status change succeed or fail together
        cur = db.execute(
            "INSERT INTO Receipt (order_id, employee_id, table_id, amount, method) VALUES (?, ?, ?, ?, ?)",
            (order_id, emp_id, order[0], total, method))
        db.execute("INSERT INTO ReceiptItems (receipt_id, item_id) SELECT ?, item_id FROM OrderItems WHERE order_id = ?",
                   (cur.lastrowid, order_id))
        db.execute("UPDATE Orders SET status = 'paid' WHERE order_id = ?", (order_id,))  # trigger frees the table
    print(f"Receipt #{cur.lastrowid} issued. Table is free again.")


def cancel_order(db):
    print("  a) By order id   b) By table number")
    choice = input("Choose: ").strip().lower()
    if choice == "a":
        order_id = int(input("Order id: "))
        order = db.execute("SELECT order_id, table_id, status FROM Orders WHERE order_id = ?", (order_id,)).fetchone()
        if order is None:
            print("Order not found.")
            return
    elif choice == "b":
        table_id = int(input("Table number: "))
        if db.execute("SELECT 1 FROM Tables WHERE table_id = ?", (table_id,)).fetchone() is None:
            print("Table not found.")
            return
        rows = db.execute("SELECT order_id, table_id, status FROM Orders WHERE table_id = ? AND status = 'open'",
                          (table_id,)).fetchall()
        if not rows:
            print(f"No open order on table {table_id}.")
            return
        if len(rows) > 1:
            print(f"Table {table_id} has several open orders: " + ", ".join(f"#{r[0]}" for r in rows))
            print("Cancel by order id instead.")
            return
        order = rows[0]
    else:
        print("Invalid choice.")
        return
    if order[2] != 'open':
        print(f"Order #{order[0]} is already paid and cannot be cancelled. Its receipt is kept.")
        return
    print_bill(db, order[0])
    if input(f"Cancel order #{order[0]} on table {order[1]}? (y/n): ").strip().lower() != "y":
        print("Nothing cancelled.")
        return
    with db:  # items, order, and table status change succeed or fail together
        # OrderItems rows go first because they reference the order (foreign key)
        db.execute("DELETE FROM OrderItems WHERE order_id = ? "
                   "AND order_id IN (SELECT order_id FROM Orders WHERE status = 'open')", (order[0],))
        cur = db.execute("DELETE FROM Orders WHERE order_id = ? AND status = 'open'", (order[0],))
        if cur.rowcount == 0:
            print("Order is no longer open. Nothing cancelled.")
            return
        # free the table unless another open order is still on it
        freed = db.execute(
            "UPDATE Tables SET status = 'free' WHERE table_id = ? "
            "AND NOT EXISTS (SELECT 1 FROM Orders WHERE table_id = ? AND status = 'open')",
            (order[1], order[1])).rowcount
    print(f"Order #{order[0]} cancelled." + (f" Table {order[1]} is free again." if freed else ""))


def transfer_table(db):
    show_tables(db)
    src = int(input("Move from table: "))
    dst = int(input("Move to table: "))
    if src == dst:
        print("Source and destination are the same table. Nothing transferred.")
        return
    if db.execute("SELECT 1 FROM Tables WHERE table_id = ?", (src,)).fetchone() is None:
        print(f"Table {src} not found.")
        return
    rows = db.execute("SELECT order_id FROM Orders WHERE table_id = ? AND status = 'open'", (src,)).fetchall()
    if not rows:
        print(f"No open order on table {src}. Nothing transferred.")
        return
    if len(rows) > 1:
        print(f"Table {src} has several open orders: " + ", ".join(f"#{r[0]}" for r in rows))
        print("Nothing transferred.")
        return
    order_id = rows[0][0]
    dest = db.execute("SELECT status FROM Tables WHERE table_id = ?", (dst,)).fetchone()
    if dest is None:
        print(f"Table {dst} not found.")
        return
    if dest[0] != 'free':
        print(f"Table {dst} is already occupied. Transfer rejected.")
        return
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
    print(f"Order #{order_id} moved from table {src} to table {dst}.")
    for t in db.execute("SELECT table_id, seats, status FROM Tables WHERE table_id IN (?, ?) ORDER BY table_id",
                        (src, dst)):
        print(f"  Table {t[0]} | seats {t[1]} | {t[2]}")


def daily_sales(db):
    print("--- Daily sales ---")
    for r in db.execute("SELECT day, receipts, total FROM DailySales ORDER BY day DESC"):
        print(f"  {r[0]} | {r[1]} receipts | {r[2]:.2f}")


def best_sellers(db):
    print("--- Best-selling dishes ---")
    for r in db.execute(
            "SELECT m.name, SUM(oi.quantity) AS sold FROM OrderItems oi "
            "JOIN MenuItems m ON m.item_id = oi.item_id JOIN Orders o ON o.order_id = oi.order_id "
            "WHERE o.status = 'paid' GROUP BY m.item_id ORDER BY sold DESC LIMIT 5"):
        print(f"  {r[0]:<20} {r[1]} sold")


def busiest_hours(db):
    print("--- Busiest hours ---")
    for r in db.execute(
            "SELECT strftime('%H', order_time) AS hour, COUNT(*) AS orders FROM Orders "
            "GROUP BY hour ORDER BY orders DESC LIMIT 5"):
        print(f"  {r[0]}:00 | {r[1]} orders")


def reprint_receipt(db):
    receipt_id = int(input("Receipt id: "))
    head = db.execute(
        "SELECT r.receipt_id, r.paid_time, r.method, r.amount, r.table_id, e.name, r.order_id "
        "FROM Receipt r JOIN Employees e ON e.employee_id = r.employee_id WHERE r.receipt_id = ?",
        (receipt_id,)).fetchone()
    if head is None:
        print("Receipt not found.")
        return
    print(f"--- Receipt #{head[0]} ---")
    print(f"  Table {head[4]} | Order #{head[6]} | Issued by {head[5]}")
    print(f"  Paid {head[1]} by {head[2]}")
    # ReceiptItems says which dishes are on the receipt; quantity and price come from OrderItems
    for r in db.execute(
            "SELECT m.name, oi.quantity, oi.price_at_order, oi.quantity * oi.price_at_order "
            "FROM ReceiptItems ri JOIN Receipt r ON r.receipt_id = ri.receipt_id "
            "JOIN OrderItems oi ON oi.order_id = r.order_id AND oi.item_id = ri.item_id "
            "JOIN MenuItems m ON m.item_id = ri.item_id WHERE ri.receipt_id = ?", (receipt_id,)):
        print(f"  {r[0]:<20} {r[1]} x {r[2]:.2f} = {r[3]:.2f}")
    print(f"  TOTAL: {head[3]:.2f}")


def manage_menu(db):
    print("  a) List all   b) Add dish   c) Change price   d) Mark available/unavailable")
    choice = input("Choose: ").strip().lower()
    if choice == "a":
        for r in db.execute("SELECT item_id, name, category, price, available FROM MenuItems ORDER BY category, name"):
            print(f"  [{r[0]}] {r[1]} ({r[2]}) - {r[3]:.2f} | {'available' if r[4] else 'unavailable'}")
    elif choice == "b":
        name = input("Name: ").strip()
        category = input("Category: ").strip()
        price = float(input("Price: "))
        if not name or not category:
            print("Name and category are required.")
            return
        with db:
            db.execute("INSERT INTO MenuItems (name, category, price) VALUES (?, ?, ?)", (name, category, price))
        print("Dish added.")
    elif choice == "c":
        item_id = int(input("Item id: "))
        price = float(input("New price: "))
        with db:  # old bills keep their price because OrderItems stores price_at_order
            cur = db.execute("UPDATE MenuItems SET price = ? WHERE item_id = ?", (price, item_id))
        print("Price updated (old bills are not affected)." if cur.rowcount else "Item not found.")
    elif choice == "d":
        item_id = int(input("Item id: "))
        with db:
            cur = db.execute("UPDATE MenuItems SET available = 1 - available WHERE item_id = ?", (item_id,))
        print("Availability toggled." if cur.rowcount else "Item not found.")
    else:
        print("Invalid choice.")


def ask_new_password(label):
    # same handling as login(): getpass (not shown on screen) and a SHA-256 hash; the password is never printed
    password = getpass(f"{label}: ")
    if not password:
        print("Password is required.")
        return None
    if getpass(f"Confirm {label.lower()}: ") != password:
        print("Passwords do not match.")
        return None
    return hashlib.sha256(password.encode()).hexdigest()


def manage_employees(db, emp_id):
    print("  a) List employees   b) Add employee   c) Remove employee   d) Change employee password   e) Back")
    choice = input("Choose: ").strip().lower()
    if choice == "a":
        for e in db.execute("SELECT employee_id, name, username FROM Employees ORDER BY employee_id"):
            print(f"  [{e[0]}] {e[1]} | username: {e[2]}" + (" (you)" if e[0] == emp_id else ""))
    elif choice == "b":
        name = input("Name: ").strip()
        username = input("Username: ").strip()
        if not name or not username:
            print("Name and username are required.")
            return
        if any(c.isspace() for c in username):
            print("Username cannot contain spaces.")
            return
        if db.execute("SELECT 1 FROM Employees WHERE username = ?", (username,)).fetchone():
            print(f"Username '{username}' is already taken.")
            return
        hashed = ask_new_password("Password")
        if hashed is None:
            return
        with db:
            cur = db.execute("INSERT INTO Employees (name, username, password) VALUES (?, ?, ?)",
                             (name, username, hashed))
        print(f"Employee #{cur.lastrowid} ({name}) added. They log in as '{username}'.")
    elif choice == "c":
        target = int(input("Employee id: "))
        emp = db.execute("SELECT name FROM Employees WHERE employee_id = ?", (target,)).fetchone()
        if emp is None:
            print("Employee not found.")
            return
        if target == emp_id:
            print("You cannot remove yourself while you are logged in.")
            return
        orders = db.execute("SELECT COUNT(*) FROM Orders WHERE employee_id = ?", (target,)).fetchone()[0]
        receipts = db.execute("SELECT COUNT(*) FROM Receipt WHERE employee_id = ?", (target,)).fetchone()[0]
        if orders or receipts:
            print(f"Employee #{target} ({emp[0]}) cannot be removed: "
                  f"they are recorded on {orders} order(s) and {receipts} receipt(s).")
            print("Removing them would erase who handled those orders, so they are kept.")
            return
        if input(f"Remove employee #{target} ({emp[0]})? (y/n): ").strip().lower() != "y":
            print("Nothing removed.")
            return
        with db:  # only deletes if there is still no order or receipt history; foreign keys also block it
            cur = db.execute("DELETE FROM Employees WHERE employee_id = ? "
                             "AND NOT EXISTS (SELECT 1 FROM Orders WHERE employee_id = ?) "
                             "AND NOT EXISTS (SELECT 1 FROM Receipt WHERE employee_id = ?)",
                             (target, target, target))
        print(f"Employee #{target} ({emp[0]}) removed." if cur.rowcount
              else "Employee now has order history. Nothing removed.")
    elif choice == "d":
        target = int(input("Employee id: "))
        emp = db.execute("SELECT name FROM Employees WHERE employee_id = ?", (target,)).fetchone()
        if emp is None:
            print("Employee not found.")
            return
        hashed = ask_new_password("New password")
        if hashed is None:
            return
        with db:  # only this employee's row in Employees changes
            db.execute("UPDATE Employees SET password = ? WHERE employee_id = ?", (hashed, target))
        print(f"Password changed for employee #{target} ({emp[0]}).")
    elif choice == "e":
        return
    else:
        print("Invalid choice.")


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
        except (ValueError, sqlite3.Error) as e:
            print("Error:", e)
    db.close()


if __name__ == "__main__":
    main()
