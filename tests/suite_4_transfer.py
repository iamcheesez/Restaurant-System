"""Transfer tests. Runs after suite_1_core_and_cancel.py, suite_2_add_item.py and suite_3_remove_item.py, on the database they leave:
paid orders 3, 4, 5, 7 (receipts 1-4), all tables free, next order id 8, Pad Thai now 85."""
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


def snapshot(db=DB):
    con = sqlite3.connect(db)
    try:
        return list(con.iterdump())
    finally:
        con.close()


def table_status(t, db=DB):
    r = q("SELECT status FROM Tables WHERE table_id=?", t, db=db)
    return r[0][0] if r else None


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def tail(out, n=3):
    return " | ".join(out.splitlines()[-n:])


check("setup: all tables free, no open orders",
      q("SELECT COUNT(*) FROM Tables WHERE status='free'") == [(5,)] and
      q("SELECT COUNT(*) FROM Orders WHERE status='open'") == [(0,)])

# ---------------- A + E (before). Successful transfer of an order with items
run("1", "1")                                                            # seat table 1 -> order 8
run("2", "8", "", "1", "2"); run("2", "8", "", "5", "1"); run("2", "8", "", "4", "1")
order_before = q("SELECT order_id, employee_id, order_time, status FROM Orders WHERE order_id=8")
items_before = q("SELECT * FROM OrderItems WHERE order_id=8 ORDER BY item_id")
bill_before = run("4", "8").split("--- Bill")[1]
orders_count, receipts_count = q("SELECT COUNT(*) FROM Orders"), q("SELECT COUNT(*) FROM Receipt")
check("setup: order 8 open on table 1 with 3 dishes",
      q("SELECT table_id, status FROM Orders WHERE order_id=8") == [(1, "open")] and len(items_before) == 3)

out = run("14", "1", "3")
print("     output:", tail(out.split("Move to table: ")[1], 4))
check("A success message", "Order #8 moved from table 1 to table 3." in out)
check("A shows both tables' new status", "Table 1 | seats 2 | free" in out and "Table 3 | seats 4 | occupied" in out)
check("A source table 1 is free", table_status(1) == "free")
check("A destination table 3 is occupied", table_status(3) == "occupied")
check("A same order_id 8 now on table 3, still open",
      q("SELECT table_id, status FROM Orders WHERE order_id=8") == [(3, "open")])
check("A order's other columns unchanged (employee, time, status)",
      q("SELECT order_id, employee_id, order_time, status FROM Orders WHERE order_id=8") == order_before)
check("A no order created or removed", q("SELECT COUNT(*) FROM Orders") == orders_count)
check("A order items unchanged", q("SELECT * FROM OrderItems WHERE order_id=8 ORDER BY item_id") == items_before)
check("A no receipt created", q("SELECT COUNT(*) FROM Receipt") == receipts_count)

# ---------------- B. Destination occupied
run("1", "2")                                                            # seat table 2 -> order 9
before = snapshot()
out = run("14", "3", "2")
check("B transfer to occupied table 2 rejected", "Table 2 is already occupied. Transfer rejected." in out)
check("B both tables and whole database unchanged",
      snapshot() == before and table_status(3) == "occupied" and table_status(2) == "occupied")

# ---------------- C. Source has no open order (free table, and a table whose order is paid)
out = run("14", "4", "5")
check("C free source table 4 rejected", "No open order on table 4. Nothing transferred." in out)
out = run("14", "5", "4")
check("C table 5 (only a paid order) rejected", "No open order on table 5. Nothing transferred." in out)
check("C paid order 5 still on table 5", q("SELECT table_id, status FROM Orders WHERE order_id=5") == [(5, "paid")])
check("C database unchanged", snapshot() == before)

# ---------------- D. Invalid tables
out = run("14", "99", "4");  check("D nonexistent source", "Table 99 not found." in out)
out = run("14", "3", "99");  check("D nonexistent destination", "Table 99 not found." in out)
out = run("14", "3", "3");   check("D same source and destination",
                                   "Source and destination are the same table. Nothing transferred." in out)
out = run("14", "x", "4");   check("D non-numeric table handled", "Error: invalid literal" in out and "Traceback" not in out)
check("D database unchanged", snapshot() == before)

# ---------------- E. Order integrity, then pay
bill_after = run("4", "8").split("--- Bill")[1]
check("E bill identical after transfer", bill_after == bill_before, "TOTAL " + bill_after.split("TOTAL: ")[1][:6])
check("E price_at_order values unchanged",
      q("SELECT item_id, price_at_order FROM OrderItems WHERE order_id=8 ORDER BY item_id")
      == [(r[1], r[3]) for r in items_before])
out = run("5", "8", "cash")
check("E pay transferred order 8 -> receipt 5", "Receipt #5 issued." in out)
check("E receipt stores destination table 3", q("SELECT table_id, order_id FROM Receipt WHERE receipt_id=5") == [(3, 8)])
check("E table 3 freed by payment, table 1 still free", table_status(3) == "free" and table_status(1) == "free")
reprint = run("10", "5")
check("E reprint shows table 3 and same dishes",
      "Table 3 | Order #8" in reprint and all(l in reprint for l in bill_before.splitlines()[1:]))
check("E reprint is repeatable", run("10", "5") == reprint)
check("E paid order can't be transferred afterward", "No open order on table 3." in run("14", "3", "4"))

# ---------------- F. Cancel after transfer
run("1", "4"); run("2", "10", "", "6", "1")                              # seat table 4 -> order 10
out = run("14", "4", "5")
check("F transfer order 10 from table 4 to 5", "Order #10 moved from table 4 to table 5." in out)
out = run("13", "b", "5", "y")                                           # cancel by destination table number
check("F cancel by destination table finds order 10", "Order #10 cancelled. Table 5 is free again." in out)
check("F destination 5 free, source 4 still free", table_status(5) == "free" and table_status(4) == "free")
check("F order 10 and its items removed", q("SELECT COUNT(*) FROM Orders WHERE order_id=10") == [(0,)] and
      q("SELECT COUNT(*) FROM OrderItems WHERE order_id=10") == [(0,)])

# ---------------- Atomicity: force a failure inside the transaction (on a copy of the database)
copy_dir = os.path.join(HERE, "atomic")
shutil.rmtree(copy_dir, ignore_errors=True); os.makedirs(copy_dir)
CDB = os.path.join(copy_dir, "restaurant.db")
shutil.copy(DB, CDB)
run("1", "4", cwd=copy_dir)                                              # order 11 on table 4 (copy only)
oid = q("SELECT order_id FROM Orders WHERE table_id=4 AND status='open'", db=CDB)[0][0]


def forced_failure(trigger_sql, label):
    before = snapshot(CDB)  # taken before the test-only fault trigger is added
    con = sqlite3.connect(CDB); con.executescript(trigger_sql); con.close()
    out = run("14", "4", "1", cwd=copy_dir)
    con = sqlite3.connect(CDB); con.execute("DROP TRIGGER test_fail"); con.commit(); con.close()
    check(f"atomic: {label} -> error shown, no success message",
          "Error:" in out and "moved from" not in out, tail(out, 2))
    check(f"atomic: {label} -> table 4 occupied, table 1 free, order on table 4",
          table_status(4, CDB) == "occupied" and table_status(1, CDB) == "free" and
          q("SELECT table_id FROM Orders WHERE order_id=?", oid, db=CDB) == [(4,)])
    check(f"atomic: {label} -> database identical to before", snapshot(CDB) == before)


# fails at step 2, after the destination was already marked occupied
forced_failure("CREATE TRIGGER test_fail BEFORE UPDATE OF table_id ON Orders "
               "BEGIN SELECT RAISE(ABORT, 'simulated failure moving the order'); END;", "failure while moving order")
# fails at step 3, after destination occupied and order moved
forced_failure("CREATE TRIGGER test_fail BEFORE UPDATE OF status ON Tables WHEN NEW.status = 'free' "
               "BEGIN SELECT RAISE(ABORT, 'simulated failure freeing source'); END;", "failure while freeing source")
out = run("14", "4", "1", cwd=copy_dir)
check("atomic: same transfer succeeds once the fault is removed",
      f"Order #{oid} moved from table 4 to table 1." in out and
      table_status(4, CDB) == "free" and table_status(1, CDB) == "occupied")

# ---------------- G (part). Other features with the transferred data
out = run("7");  check("G daily sales includes receipt 5", "5 receipts" in out, [l.strip() for l in out.splitlines() if "receipts" in l])
out = run("12"); check("G view tables: table 2 occupied, others free",
                       "Table 2 | seats 2 | occupied" in out and out.count("| free") == 4)
out = run("13", "a", "9", "y"); check("G cancel order 9 on table 2", "Order #9 cancelled. Table 2 is free again." in out)

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
