"""Remove-item tests. Runs after suite_1_core_and_cancel.py and suite_2_add_item.py, on the database they leave:
paid orders 3, 4, 5 (receipts 1, 2, 3), order 6 cancelled, all tables free, next order id 7."""
import os, re, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
PROG = os.path.join(ROOT, "restaurant_system.py")
WORK = os.path.join(WORK_ROOT, "testrun")
DB = os.path.join(WORK, "restaurant.db")
results = []


def run(*inputs):
    stdin = "\n".join(["admin", "1234", *inputs, "0"]) + "\n"
    out = subprocess.run([sys.executable, PROG], input=stdin, capture_output=True, text=True, cwd=WORK).stdout
    return "\n".join(l for l in out.splitlines()
                     if l.strip() and not re.match(r"^(=====|\d+\. )", l) and "echo" not in l)


def q(sql, *args):
    con = sqlite3.connect(DB)
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


def paid_order_state(order_id):
    """Everything stored about one paid order."""
    return {
        "order": q("SELECT * FROM Orders WHERE order_id=?", order_id),
        "items": q("SELECT * FROM OrderItems WHERE order_id=? ORDER BY item_id", order_id),
        "receipt": q("SELECT * FROM Receipt WHERE order_id=?", order_id),
        "receipt_items": q("SELECT ri.* FROM ReceiptItems ri JOIN Receipt r ON r.receipt_id = ri.receipt_id "
                           "WHERE r.order_id=? ORDER BY ri.item_id", order_id),
    }


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


check("setup: orders 3, 4, 5 are paid",
      q("SELECT order_id FROM Orders WHERE status='paid' ORDER BY order_id") == [(3,), (4,), (5,)])

# ---- 1. Removing from an open order still works
out = run("1", "4")
check("setup: seat table 4 -> order 7", "Order #7 opened for table 4." in out)
run("2", "7", "", "1", "2"); run("2", "7", "", "5", "1"); run("2", "7", "", "4", "1")
check("setup: order 7 has Pad Thai x2, Spring Rolls x1, Iced Tea x1",
      q("SELECT item_id, quantity FROM OrderItems WHERE order_id=7 ORDER BY item_id") == [(1, 2), (4, 1), (5, 1)])
out = run("3", "7", "5")
check("1 remove Iced Tea from open order 7", "Item removed." in out and
      q("SELECT item_id FROM OrderItems WHERE order_id=7 ORDER BY item_id") == [(1,), (4,)])
out = run("3", "7", "6")
check("1 removing a dish not on the order keeps the old message", "Item not found on that order." in out)
out = run("4", "7")
check("1 bill after removal is 230.00", "TOTAL: 230.00" in out)

# ---- 2-6. Removing from a paid order is rejected and nothing changes
state_before = {o: paid_order_state(o) for o in (3, 4, 5)}
db_before = snapshot()
reprints_before = {r: run("10", str(r)) for r in (1, 2, 3)}

out = run("3", "5")
check("2 remove from paid order 5 rejected",
      "Order #5 is already paid. Paid orders cannot be modified." in out and "Item id to remove" not in out)
out = run("3", "3")
check("2 remove from paid order 3 rejected", "Order #3 is already paid. Paid orders cannot be modified." in out)
out = run("3", "4")
check("2 remove from paid order 4 rejected", "Order #4 is already paid. Paid orders cannot be modified." in out)

state_after = {o: paid_order_state(o) for o in (3, 4, 5)}
check("3 paid Orders rows unchanged", all(state_before[o]["order"] == state_after[o]["order"] for o in (3, 4, 5)))
check("4 paid OrderItems unchanged", all(state_before[o]["items"] == state_after[o]["items"] for o in (3, 4, 5)),
      f"order 5 items: {state_after[5]['items']}")
check("5 Receipt rows unchanged", all(state_before[o]["receipt"] == state_after[o]["receipt"] for o in (3, 4, 5)))
check("5 ReceiptItems rows unchanged",
      all(state_before[o]["receipt_items"] == state_after[o]["receipt_items"] for o in (3, 4, 5)))
check("3-5 whole database identical", snapshot() == db_before)
check("6 reprints of receipts 1, 2, 3 identical", all(run("10", str(r)) == reprints_before[r] for r in (1, 2, 3)))
print("     receipt 3 reprint:", " | ".join(reprints_before[3].split("--- ")[1].splitlines()[:6]))

# ---- 7. Nonexistent / bad order ids
out = run("3", "999")
check("7 nonexistent order: clear message", "Order not found." in out and "Item id to remove" not in out
      and "Error" not in out)
out = run("3", "1")
check("7 cancelled (deleted) order 1: clear message", "Order not found." in out)
out = run("3", "abc")
check("7 non-numeric order id handled", "Error: invalid literal" in out and "Traceback" not in out)
check("7 database still identical", snapshot() == db_before)

# ---- An order that was open becomes locked once paid
out = run("5", "7", "card")
check("extra: pay order 7 -> receipt 4", "Receipt #4 issued." in out)
items_7 = q("SELECT * FROM OrderItems WHERE order_id=7")
out = run("3", "7");  check("extra: remove from just-paid order 7 rejected", "Paid orders cannot be modified." in out)
out = run("2", "7");  check("extra: add to just-paid order 7 rejected", "Paid orders cannot be modified." in out)
check("extra: order 7 items unchanged", q("SELECT * FROM OrderItems WHERE order_id=7") == items_7)

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
