"""Seed-script tests. Everything runs in fresh folders created here."""
import hashlib, importlib, os, re, shutil, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
OUT = ROOT
PROG, SEED = os.path.join(OUT, "restaurant_system.py"), os.path.join(OUT, "seed_database.py")
HERE = WORK_ROOT
results, outputs = [], []
LOGINS = [("admin", "1234", "Restaurant Manager"), ("somchai", "somchai123", "Somchai Jaidee"),
          ("nok", "nok123", "Nok Siriwan"), ("anan", "anan123", "Anan Wongsa"), ("mali", "mali123", "Mali Chaiyo")]
CATEGORIES = {"Starter", "Main", "Soup", "Drink", "Dessert"}


def fresh(name):
    d = os.path.join(HERE, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


def seed_cli(cwd, *args):
    p = subprocess.run([sys.executable, SEED, *args], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def app(cwd, *inputs, user="admin", pw="1234"):
    stdin = "\n".join([user, pw, *inputs, "0"]) + "\n"
    out = subprocess.run([sys.executable, PROG], input=stdin, capture_output=True, text=True, cwd=cwd).stdout
    out = "\n".join(l for l in out.splitlines() if l.strip() and not re.match(r"^(=====|\d+\. )", l) and "echo" not in l)
    outputs.append(out)
    return out


def q(db, sql, *args):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def one(db, sql, *args):
    return q(db, sql, *args)[0][0]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


# ======================= 1. Fresh seed
d = fresh("seed_fresh"); db = os.path.join(d, "restaurant.db")
code, out = seed_cli(d)
check("1 fresh folder: seed exits 0 and creates restaurant.db", code == 0 and os.path.exists(db), out.splitlines()[0])
check("1 no temporary files left behind", sorted(os.listdir(d)) == ["restaurant.db"], os.listdir(d))
counts = {k: int(v) for k, v in re.findall(r"^\s+(Employees|Menu items|Tables|Open orders|Paid orders|Receipts):\s+(\d+)", out, re.M)}
real = {"Employees": one(db, "SELECT COUNT(*) FROM Employees"), "Menu items": one(db, "SELECT COUNT(*) FROM MenuItems"),
        "Tables": one(db, "SELECT COUNT(*) FROM Tables"),
        "Open orders": one(db, "SELECT COUNT(*) FROM Orders WHERE status='open'"),
        "Paid orders": one(db, "SELECT COUNT(*) FROM Orders WHERE status='paid'"), "Receipts": one(db, "SELECT COUNT(*) FROM Receipt")}
check("1 summary shows all six counts and they match the database", counts == real, counts)

# ======================= 2. Same schema as the application
d_app = fresh("seed_appschema"); app(d_app)
schema = lambda p: sorted(q(p, "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
check("2 schema identical to the one restaurant_system.py creates", schema(db) == schema(os.path.join(d_app, "restaurant.db")))

# ======================= 3. Constraints and consistency
check("3 PRAGMA foreign_key_check is empty", q(db, "PRAGMA foreign_key_check") == [])
check("3 PRAGMA integrity_check ok", one(db, "PRAGMA integrity_check") == "ok")
sys.path.insert(0, OUT)
seedmod = importlib.import_module("seed_database")
con = sqlite3.connect(db)
try:
    seedmod.validate(con); validated = True
except ValueError as e:
    validated = str(e)
finally:
    con.close()
check("3 seed's own validate() passes on the result", validated is True, validated)
occupied = {t for (t,) in q(db, "SELECT table_id FROM Tables WHERE status='occupied'")}
open_tables = [t for (t,) in q(db, "SELECT table_id FROM Orders WHERE status='open'")]
check("3 occupied tables are exactly the tables with an open order (one each)",
      occupied == set(open_tables) and len(open_tables) == len(set(open_tables)), sorted(occupied))
check("3 every paid order has exactly one receipt; open orders none",
      one(db, "SELECT COUNT(*) FROM Orders o WHERE status='paid' AND (SELECT COUNT(*) FROM Receipt r WHERE r.order_id=o.order_id) != 1") == 0
      and one(db, "SELECT COUNT(*) FROM Receipt r JOIN Orders o ON o.order_id=r.order_id WHERE o.status='open'") == 0)
check("3 receipt amounts equal the sum of quantity x price_at_order",
      one(db, "SELECT COUNT(*) FROM Receipt r WHERE ABS(amount - (SELECT SUM(quantity*price_at_order) FROM OrderItems "
              "WHERE order_id=r.order_id)) > 0.001") == 0)
check("3 receipt table matches its order's table",
      one(db, "SELECT COUNT(*) FROM Receipt r JOIN Orders o ON o.order_id=r.order_id WHERE r.table_id != o.table_id") == 0)
check("3 ReceiptItems match each order's dishes",
      q(db, "SELECT receipt_id, item_id FROM ReceiptItems ORDER BY 1, 2") ==
      q(db, "SELECT r.receipt_id, oi.item_id FROM Receipt r JOIN OrderItems oi ON oi.order_id=r.order_id ORDER BY 1, 2"))
check("3 receipts paid after their order was taken",
      one(db, "SELECT COUNT(*) FROM Receipt r JOIN Orders o ON o.order_id=r.order_id WHERE r.paid_time <= o.order_time") == 0)
check("3 no timestamps in the future", one(db, "SELECT COUNT(*) FROM Orders WHERE order_time > datetime('now','localtime')") == 0
      and one(db, "SELECT COUNT(*) FROM Receipt WHERE paid_time > datetime('now','localtime')") == 0)

# ======================= 4. Realistic, feature-oriented data
check("4 menu covers all five categories", {c for (c,) in q(db, "SELECT DISTINCT category FROM MenuItems")} == CATEGORIES)
check("4 one dish is unavailable", q(db, "SELECT name FROM MenuItems WHERE available=0") == [("Fresh Coconut",)])
takers = q(db, "SELECT employee_id, COUNT(*) FROM Orders WHERE status='paid' GROUP BY employee_id")
cashiers = q(db, "SELECT employee_id, COUNT(*) FROM Receipt GROUP BY employee_id")
check("4 different employees took paid orders (>=4)", len(takers) >= 4, takers)
check("4 different employees issued receipts (>=3)", len(cashiers) >= 3, cashiers)
check("4 some receipts issued by someone other than the order taker",
      one(db, "SELECT COUNT(*) FROM Receipt r JOIN Orders o ON o.order_id=r.order_id WHERE r.employee_id != o.employee_id") > 0)
check("4 Mali has no history", one(db, "SELECT COUNT(*) FROM Orders WHERE employee_id=5") == 0 and
      one(db, "SELECT COUNT(*) FROM Receipt WHERE employee_id=5") == 0)
check("4 paid orders use many tables (>=6)", one(db, "SELECT COUNT(DISTINCT table_id) FROM Orders WHERE status='paid'") >= 6)
check("4 every paid order has at least 2 dishes",
      one(db, "SELECT MIN(n) FROM (SELECT COUNT(*) n FROM OrderItems oi JOIN Orders o ON o.order_id=oi.order_id "
              "WHERE o.status='paid' GROUP BY oi.order_id)") >= 2)
check("4 history spans 7 days", one(db, "SELECT COUNT(DISTINCT date(paid_time)) FROM Receipt") == 7)
check("4 free tables exist", one(db, "SELECT COUNT(*) FROM Tables WHERE status='free'") >= 3)
check("4 an open order has 3+ dishes", one(db, "SELECT MAX(n) FROM (SELECT COUNT(*) n FROM OrderItems oi JOIN Orders o "
                                             "ON o.order_id=oi.order_id WHERE o.status='open' GROUP BY oi.order_id)") >= 3)
check("4 an open order sits on a table smaller than a free table (transfer demo)",
      one(db, "SELECT COUNT(*) FROM Orders o JOIN Tables t ON t.table_id=o.table_id WHERE o.status='open' AND "
              "EXISTS (SELECT 1 FROM Tables f WHERE f.status='free' AND f.seats > t.seats)") > 0)

# ======================= 5. price_at_order independent of current prices
old = seedmod.OLD_PRICES
check("5 open orders use current menu prices",
      one(db, "SELECT COUNT(*) FROM OrderItems oi JOIN Orders o ON o.order_id=oi.order_id JOIN MenuItems m "
              "ON m.item_id=oi.item_id WHERE o.status='open' AND oi.price_at_order != m.price") == 0)
rows = q(db, "SELECT m.name, oi.price_at_order, m.price, date(o.order_time) < date('now','localtime','-3 days') "
             "FROM OrderItems oi JOIN Orders o ON o.order_id=oi.order_id JOIN MenuItems m ON m.item_id=oi.item_id "
             "WHERE o.status='paid'")
bad = [r for r in rows if r[1] != (old[r[0]] if r[0] in old and r[3] else r[2])]
check("5 history uses the old price before the price change and the current price after", not bad, bad[:3])
check("5 some historical lines keep an old price that differs from today's menu",
      sum(1 for r in rows if r[1] != r[2]) >= 3, sum(1 for r in rows if r[1] != r[2]))

# ======================= 6. Passwords
stored = dict(q(db, "SELECT username, password FROM Employees"))
check("6 passwords stored as the same SHA-256 hash the login uses",
      all(stored[u] == hashlib.sha256(p.encode()).hexdigest() for u, p, _ in LOGINS))
check("6 no plain-text password stored", not any(p in stored.values() for _, p, _ in LOGINS))
check("6 seed output documents every demo login", all(f"{u:<8} / {p}" in out for u, p, _ in LOGINS))

# ======================= 7. Safe to run repeatedly
before = sha(db)
code, out2 = seed_cli(d)
check("7 rerun without --reset refuses (exit 1)", code == 1 and "already exists" in out2 and "--reset" in out2, out2.strip())
check("7 refused rerun leaves the database byte-for-byte unchanged", sha(db) == before)
items_before = q(db, "SELECT * FROM OrderItems ORDER BY 1, 2")
code, out3 = seed_cli(d, "--reset")
check("7 --reset exits 0", code == 0)
check("7 --reset does not duplicate data (same counts)",
      {k: int(v) for k, v in re.findall(r"^\s+(Employees|Menu items|Tables|Open orders|Paid orders|Receipts):\s+(\d+)", out3, re.M)} == counts)
check("7 --reset rebuilds the same demo set (identical OrderItems)", q(db, "SELECT * FROM OrderItems ORDER BY 1, 2") == items_before)
d_alt = fresh("seed_alt")
code, _ = seed_cli(d_alt, "--db", "demo.db")
check("7 --db writes to another file", code == 0 and os.listdir(d_alt) == ["demo.db"])

# ======================= 8. A failed seed never damages an existing database
before = sha(db)
saved_menu = list(seedmod.MENU)
seedmod.MENU.append(("Broken Dish", "Main", -5, 1))        # violates CHECK (price >= 0)
try:
    seedmod.seed(db, reset=True); failed = False
except sqlite3.IntegrityError:
    failed = True
finally:
    seedmod.MENU[:] = saved_menu
check("8 constraint failure during build raises", failed)
check("8 ... existing database unchanged, no temp files", sha(db) == before and sorted(os.listdir(d)) == ["restaurant.db"])
saved_open = list(seedmod.OPEN_ORDERS)
seedmod.OPEN_ORDERS.append((5, 3, "nok", [("Water", 1)]))  # second open order on table 3: contradictory state
try:
    seedmod.seed(db, reset=True); failed = False
except ValueError as e:
    failed = "more than one open order" in str(e)
finally:
    seedmod.OPEN_ORDERS[:] = saved_open
check("8 validation catches a contradictory table state", failed)
check("8 ... existing database unchanged, no temp files", sha(db) == before and sorted(os.listdir(d)) == ["restaurant.db"])

# ======================= 9. Every demo scenario works in the real program
demo = fresh("seed_demo"); seed_cli(demo)
ddb = os.path.join(demo, "restaurant.db")
big, transfer, cancel = 27, 28, 29
for u, p, name in LOGINS:
    check(f"9 login {u}", f"Welcome, {name}!" in app(demo, user=u, pw=p))
out = app(demo, "15", "a")
check("9 employee list shows no passwords", all(p not in out.split("a) List")[1] for _, p, _ in LOGINS if p != "1234")
      and all(stored[u] not in out for u in stored))
out = app(demo, "12")
check("9 view tables: 1, 3, 7 occupied; others free",
      all(f"Table {t} |" in out and (("occupied" if t in (1, 3, 7) else "free") in
          [l for l in out.splitlines() if f"Table {t} |" in l][0]) for t in range(1, 9)))
out = app(demo, "4", str(big));                    check("9 show bill for order 27 (395.00)", "TOTAL: 395.00" in out)
out = app(demo, "2", str(big), "", "18", "1");     check("9 add Mango Sticky Rice to order 27", "Item added." in out)
out = app(demo, "3", str(big), "1");               check("9 remove Spring Rolls from order 27", "Item removed." in out)
out = app(demo, "4", str(big));                    check("9 bill now 425.00", "TOTAL: 425.00" in out)
out = app(demo, "6", "Drink");                     check("9 menu search hides sold-out Fresh Coconut", "Iced Tea" in out and "Fresh Coconut" not in out)
out = app(demo, "11", "a");                        check("9 manage menu lists Fresh Coconut as unavailable", "Fresh Coconut (Drink) - 50.00 | unavailable" in out)
out = app(demo, "14", "1", "6", user="nok", pw="nok123")
check("9 transfer order 28 from table 1 (2 seats) to table 6 (6 seats)",
      f"Order #{transfer} moved from table 1 to table 6." in out)
out = app(demo, "13", "b", "7", "y", user="anan", pw="anan123")
check("9 cancel order 29 on table 7", f"Order #{cancel} cancelled. Table 7 is free again." in out)
out = app(demo, "5", str(big), "card", user="somchai", pw="somchai123")
check("9 pay order 27 -> receipt 27", "Receipt #27 issued. Table is free again." in out)
out = app(demo, "10", "27");                       check("9 reprint new receipt 27", "Table 3 | Order #27" in out and "TOTAL: 425.00" in out)
out = app(demo, "10", "3");                        check("9 reprint receipt 3 shows Pad Thai at old price 75.00", re.search(r"Pad Thai\s+\d x 75\.00", out))
out = app(demo, "2", "1", user="nok", pw="nok123"); check("9 historical order 1 can't be modified", "Paid orders cannot be modified." in out)
out = app(demo, "7");  check("9 daily sales lists 8 days (7 history + today)", len(re.findall(r"\d{4}-\d\d-\d\d \| \d+ receipts", out)) == 8)
out = app(demo, "8");  check("9 best sellers lists 5 dishes", len(re.findall(r"\d+ sold", out)) == 5)
out = app(demo, "9");  check("9 busiest hours lists 5 hours", len(re.findall(r"\d\d:00 \| \d+ orders", out)) == 5)
out = app(demo, "15", "c", "2");      check("9 removing Somchai refused (history)", "cannot be removed" in out)
out = app(demo, "15", "c", "5", "y"); check("9 removing Mali (no history) works", "Employee #5 (Mali Chaiyo) removed." in out)
check("9 tables consistent after the demo (only table 6 occupied)",
      q(ddb, "SELECT table_id FROM Tables WHERE status='occupied'") == [(6,)] and
      q(ddb, "SELECT table_id FROM Orders WHERE status='open'") == [(6,)])
con = sqlite3.connect(ddb)
try:
    seedmod.validate(con); ok = True
except ValueError as e:
    ok = str(e)
finally:
    con.close()
check("9 database still passes every seed consistency check after the demo", ok is True, ok)

# ======================= 10. Passwords never appear in application output
leaks = [p for _, p, _ in LOGINS if p != "1234" and any(p in o for o in outputs)] + \
        [h for h in stored.values() if any(h in o for o in outputs)]
check(f"10 no demo password or hash in {len(outputs)} application outputs", not leaks, leaks)

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
