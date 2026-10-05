"""Add-item tests. Runs after suite_1_core_and_cancel.py, on the database it leaves behind:
orders 3 and 4 paid (receipts 1 and 2), order 5 open on table 5 with no items."""
import os, re, shutil, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
PROG = os.path.join(ROOT, "restaurant_system.py")
HERE = WORK_ROOT
WORK = os.path.join(HERE, "testrun")
DB = os.path.join(WORK, "restaurant.db")
results = []


def run(*inputs, cwd=WORK):
    stdin = "\n".join(["admin", "1234", *inputs, "0"]) + "\n"
    out = subprocess.run([sys.executable, PROG], input=stdin, capture_output=True, text=True, cwd=cwd).stdout
    return "\n".join(l for l in out.splitlines()
                     if l.strip() and not re.match(r"^(=====|\d+\. )", l) and "echo" not in l)


def q(sql, *args, db=DB):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def snapshot():
    con = sqlite3.connect(DB)
    try:
        return list(con.iterdump())
    finally:
        con.close()


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


check("setup: order 5 is open with no items",
      q("SELECT status FROM Orders WHERE order_id=5") == [("open",)] and
      q("SELECT COUNT(*) FROM OrderItems WHERE order_id=5") == [(0,)])

# ---- 1. Adding to an open order still works
out = run("2", "5", "", "2", "1")
check("1 add Fried Rice x1 to open order 5", "Item added." in out and
      q("SELECT item_id, quantity, price_at_order FROM OrderItems WHERE order_id=5") == [(2, 1, 70.0)])
out = run("2", "5", "", "2", "2")
check("1 adding same dish again raises quantity to 3", "Item added." in out and
      q("SELECT quantity FROM OrderItems WHERE order_id=5 AND item_id=2") == [(3,)])
out = run("2", "5", "", "1", "1")
check("1 add Pad Thai at its current price (85)", "Item added." in out and
      q("SELECT quantity, price_at_order FROM OrderItems WHERE order_id=5 AND item_id=1") == [(1, 85.0)])
out = run("5", "5", "cash")
check("setup: pay order 5 -> receipt 3 for 295.00", "Receipt #3 issued." in out and
      q("SELECT amount FROM Receipt WHERE order_id=5") == [(295.0,)])

# ---- 2 + 3. Adding to a paid order is rejected and nothing changes
before = snapshot()
receipt1_before, receipt3_before = run("10", "1"), run("10", "3")

out = run("2", "5")
check("2 add to paid order 5 rejected",
      "Order #5 is already paid. Paid orders cannot be modified." in out and "Search menu" not in out)
out = run("2", "3")
check("2 add to paid order 3 rejected", "Order #3 is already paid. Paid orders cannot be modified." in out)
out = run("2", "4")
check("2 add to paid order 4 rejected", "Order #4 is already paid. Paid orders cannot be modified." in out)

after = snapshot()
check("3 whole database identical after rejected attempts", before == after,
      f"{len(set(before) ^ set(after))} differing lines")
check("3 order 5 rows unchanged", q("SELECT status, table_id FROM Orders WHERE order_id=5") == [("paid", 5)] and
      q("SELECT item_id, quantity, price_at_order FROM OrderItems WHERE order_id=5 ORDER BY item_id")
      == [(1, 1, 85.0), (2, 3, 70.0)])
check("3 receipt 1 reprint identical", run("10", "1") == receipt1_before)
check("3 receipt 3 reprint identical", run("10", "3") == receipt3_before)

# other bad input to add-item
out = run("2", "999")
check("extra: nonexistent order gives a clear message", "Order not found." in out and "FOREIGN KEY" not in out)
out = run("2", "abc")
check("extra: non-numeric order id handled", "Error: invalid literal" in out and "Traceback" not in out)
check("extra: database still identical", snapshot() == after)

# ---- 4. Existing features with the new data
out = run("7");  check("4 daily sales: 3 receipts, 445.00", "3 receipts | 445.00" in out)
out = run("8");  check("4 best sellers: Fried Rice 4, Pad Thai 2",
                       re.search(r"Fried Rice\s+4 sold", out) and re.search(r"Pad Thai\s+2 sold", out))
out = run("12"); check("4 all tables free", out.count("| free") == 5)
out = run("1", "2"); check("4 seat new order on table 2", "Order #6 opened for table 2." in out)
out = run("2", "6", "", "4", "2"); check("4 add item to new order", "Item added." in out)
out = run("13", "a", "6", "y"); check("4 cancel new order still works", "Order #6 cancelled. Table 2 is free again." in out)
out = run("13", "a", "5"); check("4 paid order still can't be cancelled", "already paid and cannot be cancelled" in out)

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
