"""Create a demonstration restaurant.db with realistic sample data.

FOR DEVELOPMENT AND DEMOS ONLY. The logins below are sample credentials:

    username   password     employee
    admin      1234         Restaurant Manager
    somchai    somchai123   Somchai Jaidee
    nok        nok123       Nok Siriwan
    anan       anan123      Anan Wongsa
    mali       mali123      Mali Chaiyo (new hire, no order history)

Usage (run from the same folder you run restaurant_system.py from):
    python seed_database.py            create restaurant.db (refuses if it already exists)
    python seed_database.py --reset    delete and recreate restaurant.db with fresh sample data
    python seed_database.py --db PATH  use another database file

The tables, trigger and view come from restaurant_system.SCHEMA, so the schema is never duplicated here.
The data is generated from a fixed random seed, so every reset gives the same demo set
(dates are relative to the day you run it). The new database is built in a temporary file,
checked, and only then moved into place, so a failed run never damages an existing database.
"""
import argparse
import hashlib
import os
import random
import sqlite3
from datetime import datetime, timedelta

from restaurant_system import SCHEMA, DB_FILE

EMPLOYEES = [  # name, username, password (demo only)
    ("Restaurant Manager", "admin", "1234"),
    ("Somchai Jaidee", "somchai", "somchai123"),
    ("Nok Siriwan", "nok", "nok123"),
    ("Anan Wongsa", "anan", "anan123"),
    ("Mali Chaiyo", "mali", "mali123"),
]

TABLE_SEATS = [2, 2, 4, 4, 4, 6, 6, 8]  # tables 1-8

MENU = [  # name, category, current price, available
    ("Spring Rolls", "Starter", 60, 1),
    ("Chicken Satay", "Starter", 90, 1),
    ("Fish Cakes", "Starter", 85, 1),
    ("Papaya Salad", "Starter", 70, 1),
    ("Pad Thai", "Main", 80, 1),
    ("Fried Rice", "Main", 70, 1),
    ("Green Curry", "Main", 95, 1),
    ("Massaman Curry", "Main", 110, 1),
    ("Basil Pork with Rice", "Main", 75, 1),
    ("Cashew Chicken", "Main", 100, 1),
    ("Tom Yum Goong", "Soup", 120, 1),
    ("Tom Kha Gai", "Soup", 110, 1),
    ("Iced Tea", "Drink", 30, 1),
    ("Thai Iced Coffee", "Drink", 40, 1),
    ("Lime Soda", "Drink", 35, 1),
    ("Water", "Drink", 15, 1),
    ("Fresh Coconut", "Drink", 50, 0),  # sold out today: shows the availability switch
    ("Mango Sticky Rice", "Dessert", 90, 1),
    ("Coconut Ice Cream", "Dessert", 45, 1),
]

# These dishes were cheaper until PRICE_CHANGE_DAYS_AGO days ago. Older orders keep the old price in
# OrderItems.price_at_order, which shows that history does not follow later menu price changes.
OLD_PRICES = {"Pad Thai": 75, "Green Curry": 90, "Tom Yum Goong": 110, "Thai Iced Coffee": 35}
PRICE_CHANGE_DAYS_AGO = 3

HISTORY_DAYS = 7
ORDER_HOURS = [11, 12, 12, 12, 13, 13, 17, 18, 18, 19, 19, 19, 20]   # lunch and dinner rush
TAKER_WEIGHTS = {"admin": 1, "somchai": 4, "nok": 3, "anan": 2}      # mali has no history on purpose

# Open orders right now, each one set up for a demo. (minutes ago, table, employee, [(dish, quantity)])
OPEN_ORDERS = [
    (35, 3, "somchai", [("Pad Thai", 2), ("Green Curry", 1), ("Spring Rolls", 1), ("Thai Iced Coffee", 2)]),
    (20, 1, "nok", [("Tom Yum Goong", 1), ("Fried Rice", 1), ("Iced Tea", 2)]),
    (10, 7, "anan", [("Lime Soda", 1)]),
]


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()  # same as restaurant_system.login()


def stamp(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")  # same format as datetime('now', 'localtime')


def build(con, now):
    rng = random.Random(2026)
    con.execute("PRAGMA foreign_keys = ON")  # same as restaurant_system.connect(): every row must satisfy the FKs
    con.executescript(SCHEMA)

    emp_ids = {}
    for name, username, password in EMPLOYEES:
        emp_ids[username] = con.execute("INSERT INTO Employees (name, username, password) VALUES (?, ?, ?)",
                                        (name, username, hash_password(password))).lastrowid
    con.executemany("INSERT INTO Tables (seats) VALUES (?)", [(s,) for s in TABLE_SEATS])
    item_ids, prices, by_category = {}, {}, {}
    for name, category, price, available in MENU:
        item_ids[name] = con.execute("INSERT INTO MenuItems (name, category, price, available) VALUES (?, ?, ?, ?)",
                                     (name, category, price, available)).lastrowid
        prices[name] = price
        by_category.setdefault(category, []).append(name)

    def price_on(name, day):
        old = OLD_PRICES.get(name)
        return old if old is not None and day < (now - timedelta(days=PRICE_CHANGE_DAYS_AGO)).date() else prices[name]

    # ---- paid history: a week of lunch and dinner orders
    takers = [u for u, w in TAKER_WEIGHTS.items() for _ in range(w)]
    history = []
    for days_ago in range(HISTORY_DAYS, 0, -1):
        day = (now - timedelta(days=days_ago)).date()
        hours = sorted(rng.sample(ORDER_HOURS, rng.randint(3, 5)))
        tables = rng.sample(range(1, len(TABLE_SEATS) + 1), len(hours))  # one order per table per day
        for hour, table in zip(hours, tables):
            order_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=rng.randint(0, 50))
            dishes = {n: rng.randint(1, 2) for n in rng.sample(by_category["Main"], rng.randint(1, 2))}
            dishes.update({n: rng.randint(1, 3) for n in rng.sample(by_category["Drink"], rng.randint(1, 2))})
            for category, chance in (("Starter", 0.5), ("Soup", 0.35), ("Dessert", 0.3)):
                if rng.random() < chance:
                    dishes[rng.choice(by_category[category])] = 1
            taker = rng.choice(takers)
            cashier = taker if rng.random() < 0.6 else rng.choice(["admin", "somchai"])
            history.append((order_time, table, taker, cashier, dishes,
                            order_time + timedelta(minutes=rng.randint(35, 80)), rng.choice(["cash", "card"])))

    paid = []
    for order_time, table, taker, cashier, dishes, paid_time, method in history:  # already in time order
        order_id = con.execute("INSERT INTO Orders (table_id, employee_id, order_time, status) VALUES (?, ?, ?, 'paid')",
                               (table, emp_ids[taker], stamp(order_time))).lastrowid
        lines = [(order_id, item_ids[n], q, price_on(n, order_time.date())) for n, q in dishes.items()]
        con.executemany("INSERT INTO OrderItems (order_id, item_id, quantity, price_at_order) VALUES (?, ?, ?, ?)", lines)
        paid.append((paid_time, order_id, table, cashier, method, sum(q * p for _, _, q, p in lines)))
    for paid_time, order_id, table, cashier, method, amount in sorted(paid):  # receipts in payment order
        receipt_id = con.execute(
            "INSERT INTO Receipt (order_id, employee_id, table_id, amount, method, paid_time) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, emp_ids[cashier], table, amount, method, stamp(paid_time))).lastrowid
        con.execute("INSERT INTO ReceiptItems (receipt_id, item_id) SELECT ?, item_id FROM OrderItems WHERE order_id = ?",
                    (receipt_id, order_id))

    # ---- open orders now (current prices); only their tables are occupied
    for minutes_ago, table, taker, dishes in OPEN_ORDERS:
        order_id = con.execute("INSERT INTO Orders (table_id, employee_id, order_time) VALUES (?, ?, ?)",
                               (table, emp_ids[taker], stamp(now - timedelta(minutes=minutes_ago)))).lastrowid
        con.executemany("INSERT INTO OrderItems (order_id, item_id, quantity, price_at_order) VALUES (?, ?, ?, ?)",
                        [(order_id, item_ids[n], q, prices[n]) for n, q in dishes])
        con.execute("UPDATE Tables SET status = 'occupied' WHERE table_id = ?", (table,))


def validate(con):
    """Raise ValueError if the seeded data breaks a rule the application relies on."""
    problems = []
    if con.execute("PRAGMA foreign_key_check").fetchall():
        problems.append("foreign key violations")
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        problems.append("integrity check failed")
    if con.execute("SELECT COUNT(*) FROM Tables t WHERE (t.status = 'occupied') != "
                   "EXISTS (SELECT 1 FROM Orders o WHERE o.table_id = t.table_id AND o.status = 'open')").fetchone()[0]:
        problems.append("a table's status does not match its open orders")
    if con.execute("SELECT COUNT(*) FROM (SELECT table_id FROM Orders WHERE status = 'open' "
                   "GROUP BY table_id HAVING COUNT(*) > 1)").fetchone()[0]:
        problems.append("a table has more than one open order")
    if con.execute("SELECT COUNT(*) FROM Orders o WHERE (o.status = 'paid') != "
                   "((SELECT COUNT(*) FROM Receipt r WHERE r.order_id = o.order_id) = 1) "
                   "OR (o.status = 'open' AND EXISTS (SELECT 1 FROM Receipt r WHERE r.order_id = o.order_id))"
                   ).fetchone()[0]:
        problems.append("paid orders must have exactly one receipt and open orders none")
    if con.execute("SELECT COUNT(*) FROM Orders o WHERE NOT EXISTS "
                   "(SELECT 1 FROM OrderItems oi WHERE oi.order_id = o.order_id)").fetchone()[0]:
        problems.append("an order has no items")
    if con.execute("SELECT COUNT(*) FROM Receipt r JOIN Orders o ON o.order_id = r.order_id "
                   "WHERE r.table_id != o.table_id OR ABS(r.amount - (SELECT SUM(quantity * price_at_order) "
                   "FROM OrderItems oi WHERE oi.order_id = r.order_id)) > 0.001").fetchone()[0]:
        problems.append("a receipt's table or amount does not match its order")
    if con.execute("SELECT COUNT(*) FROM Receipt r WHERE EXISTS "
                   "(SELECT item_id FROM ReceiptItems WHERE receipt_id = r.receipt_id "
                   " EXCEPT SELECT item_id FROM OrderItems WHERE order_id = r.order_id) OR EXISTS "
                   "(SELECT item_id FROM OrderItems WHERE order_id = r.order_id "
                   " EXCEPT SELECT item_id FROM ReceiptItems WHERE receipt_id = r.receipt_id)").fetchone()[0]:
        problems.append("a receipt's items do not match its order's items")
    if problems:
        raise ValueError("; ".join(problems))


def summary(con):
    one = lambda sql: con.execute(sql).fetchone()[0]
    return {
        "employees": one("SELECT COUNT(*) FROM Employees"),
        "menu_items": one("SELECT COUNT(*) FROM MenuItems"),
        "unavailable": one("SELECT COUNT(*) FROM MenuItems WHERE available = 0"),
        "tables": one("SELECT COUNT(*) FROM Tables"),
        "occupied": one("SELECT COUNT(*) FROM Tables WHERE status = 'occupied'"),
        "open_orders": one("SELECT COUNT(*) FROM Orders WHERE status = 'open'"),
        "paid_orders": one("SELECT COUNT(*) FROM Orders WHERE status = 'paid'"),
        "receipts": one("SELECT COUNT(*) FROM Receipt"),
    }


def seed(db_path=DB_FILE, reset=False, now=None):
    """Build and validate a fresh demo database at db_path. Returns the summary counts."""
    if os.path.exists(db_path) and not reset:
        raise FileExistsError(f"{db_path} already exists. Run again with --reset to delete it and reseed.")
    tmp = db_path + ".seeding"
    for leftover in (tmp, tmp + "-journal"):
        if os.path.exists(leftover):
            os.remove(leftover)
    try:
        con = sqlite3.connect(tmp)
        try:
            with con:
                build(con, now or datetime.now())
            validate(con)
            counts = summary(con)
        finally:
            con.close()
        os.replace(tmp, db_path)  # only now is an existing database replaced
        return counts
    finally:
        for leftover in (tmp, tmp + "-journal"):
            if os.path.exists(leftover):
                os.remove(leftover)


def describe(db_path):
    con = sqlite3.connect(db_path)
    try:
        open_orders = con.execute(
            "SELECT o.order_id, o.table_id, t.seats, e.name, COUNT(oi.item_id), SUM(oi.quantity * oi.price_at_order) "
            "FROM Orders o JOIN Tables t ON t.table_id = o.table_id JOIN Employees e ON e.employee_id = o.employee_id "
            "JOIN OrderItems oi ON oi.order_id = o.order_id WHERE o.status = 'open' "
            "GROUP BY o.order_id ORDER BY COUNT(oi.item_id) DESC").fetchall()
        free = [f"{t} ({s} seats)" for t, s in con.execute(
            "SELECT table_id, seats FROM Tables WHERE status = 'free' ORDER BY table_id")]
        history = con.execute(
            "SELECT e.name, (SELECT COUNT(*) FROM Orders o WHERE o.employee_id = e.employee_id), "
            "(SELECT COUNT(*) FROM Receipt r WHERE r.employee_id = e.employee_id) "
            "FROM Employees e ORDER BY e.employee_id").fetchall()
        last_receipt = con.execute("SELECT MAX(receipt_id) FROM Receipt").fetchone()[0]
        old_price = con.execute(
            "SELECT m.name, oi.price_at_order, m.price, r.receipt_id FROM OrderItems oi "
            "JOIN MenuItems m ON m.item_id = oi.item_id JOIN Receipt r ON r.order_id = oi.order_id "
            "WHERE oi.price_at_order != m.price ORDER BY r.receipt_id LIMIT 1").fetchone()
        sold_out = [n for (n,) in con.execute("SELECT name FROM MenuItems WHERE available = 0")]
    finally:
        con.close()
    return open_orders, free, history, last_receipt, old_price, sold_out


def main():
    parser = argparse.ArgumentParser(description="Create a demonstration restaurant.db with sample data.")
    parser.add_argument("--reset", action="store_true", help="delete the existing database and reseed it")
    parser.add_argument("--db", default=DB_FILE, help=f"database file (default: {DB_FILE})")
    args = parser.parse_args()
    try:
        c = seed(args.db, args.reset)
    except FileExistsError as e:
        print(e)
        raise SystemExit(1)
    except PermissionError:
        print(f"Could not replace {args.db}. Close restaurant_system.py (or anything using the file) and try again.")
        raise SystemExit(1)
    except (ValueError, sqlite3.Error) as e:
        print(f"Seeding failed, nothing was changed: {e}")
        raise SystemExit(1)

    open_orders, free, history, last_receipt, old_price, sold_out = describe(args.db)
    print(f"Seeded {args.db}")
    print(f"  Employees:   {c['employees']}")
    print(f"  Menu items:  {c['menu_items']} ({c['unavailable']} unavailable)")
    print(f"  Tables:      {c['tables']} ({c['occupied']} occupied, {c['tables'] - c['occupied']} free)")
    print(f"  Open orders: {c['open_orders']}")
    print(f"  Paid orders: {c['paid_orders']}")
    print(f"  Receipts:    {c['receipts']}")
    print("\nDemo logins (development/demo only):")
    for name, username, password in EMPLOYEES:
        print(f"  {username:<8} / {password:<11} {name}")
    print("\nOrder history by employee (orders taken / receipts issued):")
    for name, orders, receipts in history:
        print(f"  {name:<19} {orders:>2} / {receipts:>2}" + ("   <- no history, can be removed" if not orders + receipts else ""))
    print("\nReady-to-try scenarios:")
    big, transfer, cancel = open_orders[0], open_orders[1], open_orders[-1]
    print(f"  Order #{big[0]} on table {big[1]} ({big[3]}, {big[4]} dishes, {big[5]:.2f}): "
          "add item, remove item, show bill, pay")
    print(f"  Order #{transfer[0]} on table {transfer[1]} ({transfer[2]} seats): transfer it to a bigger free table")
    print(f"  Order #{cancel[0]} on table {cancel[1]} ({cancel[4]} dish): cancel it")
    print(f"  Free tables: {', '.join(free)}")
    print(f"  Receipts 1-{last_receipt}: reprint any; reports cover the last {HISTORY_DAYS} days")
    if old_price:
        print(f"  Receipt #{old_price[3]}: {old_price[0]} at the old price {old_price[1]:.2f} "
              f"(menu price now {old_price[2]:.2f})")
    print(f"  Sold out: {', '.join(sold_out)} (hidden from menu search; switch it back in Manage menu)")


if __name__ == "__main__":
    main()
