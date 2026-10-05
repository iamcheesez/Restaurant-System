import os, re, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
PROG = os.path.join(ROOT, "restaurant_system.py")
WORK = os.path.join(WORK_ROOT, "testrun")
os.makedirs(WORK, exist_ok=True)
DB = os.path.join(WORK, "restaurant.db")
if os.path.exists(DB):
    os.remove(DB)

results = []


def run(*inputs):
    """Log in, feed the menu inputs, exit. Returns program output without menu noise."""
    stdin = "\n".join(["admin", "1234", *inputs, "0"]) + "\n"
    out = subprocess.run([sys.executable, PROG], input=stdin, capture_output=True, text=True, cwd=WORK).stdout
    keep = [l for l in out.splitlines()
            if l.strip() and not re.match(r"^(=====|\d+\. )", l) and "echo" not in l]
    return "\n".join(keep)


def q(sql, *args):
    con = sqlite3.connect(DB)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


# ---- Test 1 + 2: cancel an open order by order id; table becomes free
out = run("1", "1", "2", "1", "", "1", "2", "2", "1", "", "5", "1")   # seat T1 -> order 1; Pad Thai x2, Iced Tea x1
check("setup: order 1 open on table 1", q("SELECT status FROM Orders WHERE order_id=1") == [("open",)])
check("setup: table 1 occupied", q("SELECT status FROM Tables WHERE table_id=1") == [("occupied",)])
check("setup: order 1 has 2 item rows", q("SELECT COUNT(*) FROM OrderItems WHERE order_id=1") == [(2,)])
out = run("13", "a", "1", "y")
print(out.split("Welcome")[1])
check("T1 cancel by order id: success message", "Order #1 cancelled. Table 1 is free again." in out)
check("T1 order 1 row removed", q("SELECT COUNT(*) FROM Orders WHERE order_id=1") == [(0,)])
check("T1 order 1 items removed", q("SELECT COUNT(*) FROM OrderItems WHERE order_id=1") == [(0,)])
check("T2 table 1 free after cancel", q("SELECT status FROM Tables WHERE table_id=1") == [("free",)])

# cancel by table number
run("1", "2", "2", "2", "", "3", "1")                                 # seat T2 -> order 2; Fried Rice x1
out = run("13", "b", "2", "y")
check("T1 cancel by table number: success message", "Order #2 cancelled. Table 2 is free again." in out)
check("T2 table 2 free after cancel", q("SELECT status FROM Tables WHERE table_id=2") == [("free",)])
check("T1 order 2 and items removed",
      q("SELECT COUNT(*) FROM Orders WHERE order_id=2") == [(0,)] and
      q("SELECT COUNT(*) FROM OrderItems WHERE order_id=2") == [(0,)])

# answering 'n' cancels nothing
run("1", "3", "2", "3", "", "1", "1")                                 # seat T3 -> order 3; Pad Thai x1
out = run("13", "a", "3", "n")
check("T1 answering n keeps the order", "Nothing cancelled." in out and
      q("SELECT status FROM Orders WHERE order_id=3") == [("open",)] and
      q("SELECT status FROM Tables WHERE table_id=3") == [("occupied",)])

# ---- Test 3: a paid order cannot be cancelled
run("5", "3", "cash")                                                 # pay order 3 -> receipt 1
check("setup: order 3 paid, receipt 1 exists",
      q("SELECT status FROM Orders WHERE order_id=3") == [("paid",)] and
      q("SELECT COUNT(*) FROM Receipt WHERE order_id=3") == [(1,)])
out = run("13", "a", "3")
check("T3 paid order refused by order id", "Order #3 is already paid and cannot be cancelled." in out, out.splitlines()[-1])
out = run("13", "b", "3")
check("T3 paid table has no open order", "No open order on table 3." in out)
check("T3 paid order, items, receipt untouched",
      q("SELECT status FROM Orders WHERE order_id=3") == [("paid",)] and
      q("SELECT COUNT(*) FROM OrderItems WHERE order_id=3") == [(1,)] and
      q("SELECT COUNT(*) FROM Receipt") == [(1,)] and
      q("SELECT COUNT(*) FROM ReceiptItems") == [(1,)])

# ---- Test 4: invalid / nonexistent inputs
before = q("SELECT COUNT(*) FROM Orders")
out = run("13", "a", "999");     check("T4 order 999 not found", "Order not found." in out)
out = run("13", "a", "1");       check("T4 already-cancelled order 1 not found", "Order not found." in out)
out = run("13", "b", "99");      check("T4 table 99 not found", "Table not found." in out)
out = run("13", "b", "4");       check("T4 free table 4 has no open order", "No open order on table 4." in out)
out = run("13", "a", "abc");     check("T4 non-numeric order id handled", "Error: invalid literal" in out and "Traceback" not in out)
out = run("13", "b", "x");       check("T4 non-numeric table handled", "Error: invalid literal" in out and "Traceback" not in out)
out = run("13", "z");            check("T4 invalid sub-choice handled", "Invalid choice." in out)
check("T4 nothing changed by invalid attempts", q("SELECT COUNT(*) FROM Orders") == before)

# ---- Test 5: existing features still work
run("1", "1", "2", "4", "", "6", "2")                                 # T1 reused after cancel -> order 4
check("T5 cancelled table can be seated again", q("SELECT table_id, status FROM Orders WHERE order_id=4") == [(1, "open")])
out = run("3", "4", "6");        check("T5 remove item", "Item removed." in out)
out = run("2", "4", "", "2", "1"); check("T5 add item", "Item added." in out)
out = run("4", "4");             check("T5 show bill", "Fried Rice" in out and "TOTAL: 70.00" in out)
out = run("6", "Soup");          check("T5 search menu", "Tom Yum Soup" in out)
out = run("5", "4", "card");     check("T5 pay and issue receipt", "Receipt #2 issued. Table is free again." in out)
out = run("10", "1");            check("T5 reprint receipt 1", "Receipt #1" in out and "Pad Thai" in out and "TOTAL: 80.00" in out)
out = run("7");                  check("T5 daily sales", "2 receipts | 150.00" in out, [l for l in out.splitlines() if "receipts" in l])
out = run("8");                  check("T5 best sellers (paid only)", re.search(r"Pad Thai\s+1 sold", out) and "Iced Tea" not in out)
out = run("9");                  check("T5 busiest hours", ":00 |" in out)
out = run("11", "a");            check("T5 manage menu list", "Mango Sticky Rice" in out)
out = run("11", "c", "1", "85"); check("T5 manage menu change price", "Price updated" in out)
out = run("10", "1");            check("T5 old receipt keeps old price", "1 x 80.00" in out)
out = run("12");                 check("T5 view tables all free", out.count("| free") == 5)
out = run("1", "5");             check("T5 seat customers", "Order #5 opened for table 5." in out)

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
