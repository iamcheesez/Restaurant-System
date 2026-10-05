"""Employee-management tests. Runs after the four earlier suites, on the database they leave:
only employee #1 (admin), paid orders 3, 4, 5, 7, 8 and receipts 1-5 all by employee 1, all tables free."""
import hashlib, os, re, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
PROG = os.path.join(ROOT, "restaurant_system.py")
WORK = os.path.join(WORK_ROOT, "testrun")
DB = os.path.join(WORK, "restaurant.db")
results, outputs = [], []
PASSWORDS = ["Som-pass-1", "New-pass-2", "Temp-pw-9", "Nok-pw-7", "Wrong-pw-0"]


def run(*inputs, user="admin", pw="1234"):
    stdin = "\n".join([user, pw, *inputs, "0"]) + "\n"
    out = subprocess.run([sys.executable, PROG], input=stdin, capture_output=True, text=True, cwd=WORK).stdout
    out = "\n".join(l for l in out.splitlines()
                    if l.strip() and not re.match(r"^(=====|\d+\. )", l) and "echo" not in l)
    outputs.append(out)
    return out


def q(sql, *args):
    con = sqlite3.connect(DB)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def dump(tables=None):
    con = sqlite3.connect(DB)
    try:
        lines = list(con.iterdump())
    finally:
        con.close()
    if tables:
        lines = [l for l in lines if any(l.startswith(f'INSERT INTO "{t}"') for t in tables)]
    return lines


HISTORY = ["Orders", "OrderItems", "Receipt", "ReceiptItems", "MenuItems", "Tables"]
h = lambda pw: hashlib.sha256(pw.encode()).hexdigest()


def reports():
    return [run("7"), run("8"), run("9")]


def receipts():
    return {r: run("10", str(r)) for (r,) in q("SELECT receipt_id FROM Receipt ORDER BY receipt_id")}


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


check("setup: only employee 1, 5 receipts",
      q("SELECT employee_id FROM Employees") == [(1,)] and q("SELECT COUNT(*) FROM Receipt") == [(5,)])
history_start, reports_start, receipts_start = dump(HISTORY), reports(), receipts()

# ---------------- A. List employees
out = run("15", "a")
check("A list shows id, name, username and marks you", "[1] Default Employee | username: admin (you)" in out)
check("A list shows no password or hash", h("1234") not in out and "1234" not in out.split("Choose:   a)")[1])

# ---------------- B. Add employee
out = run("15", "b", "Somchai Jaidee", "somchai", "Som-pass-1", "Som-pass-1")
check("B add Somchai -> employee #2", "Employee #2 (Somchai Jaidee) added. They log in as 'somchai'." in out)
check("B stored as SHA-256 hash, not plain text",
      q("SELECT name, username, password FROM Employees WHERE employee_id=2") == [("Somchai Jaidee", "somchai", h("Som-pass-1"))])
check("B new employee can log in", "Welcome, Somchai Jaidee!" in run(user="somchai", pw="Som-pass-1"))
check("B list shows new employee", "[2] Somchai Jaidee | username: somchai" in run("15", "a"))

# ---------------- C. Invalid / duplicate data
count = q("SELECT COUNT(*) FROM Employees")
out = run("15", "b", "", "someone");                         check("C empty name rejected", "Name and username are required." in out)
out = run("15", "b", "Some One", "");                        check("C empty username rejected", "Name and username are required." in out)
out = run("15", "b", "Some One", "some one");                check("C username with space rejected", "Username cannot contain spaces." in out)
out = run("15", "b", "Another Admin", "admin");              check("C duplicate username 'admin' rejected", "Username 'admin' is already taken." in out)
out = run("15", "b", "Somchai Two", "somchai");              check("C duplicate username 'somchai' rejected", "Username 'somchai' is already taken." in out)
out = run("15", "b", "Some One", "someone", "");             check("C empty password rejected", "Password is required." in out)
out = run("15", "b", "Some One", "someone", "Temp-pw-9", "Wrong-pw-0")
check("C mismatched confirmation rejected", "Passwords do not match." in out)
out = run("15", "z");                                        check("C invalid sub-choice", "Invalid choice." in out)
out = run("15", "e");                                        check("C e) Back returns to main menu", "Invalid" not in out and "Error" not in out)
check("C no employee added by invalid attempts", q("SELECT COUNT(*) FROM Employees") == count)

# ---------------- D. Change password
admin_hash = q("SELECT password FROM Employees WHERE employee_id=1")
out = run("15", "d", "2", "New-pass-2", "Wrong-pw-0")
check("D mismatched new password rejected, hash unchanged", "Passwords do not match." in out and
      q("SELECT password FROM Employees WHERE employee_id=2") == [(h("Som-pass-1"),)])
out = run("15", "d", "2", "New-pass-2", "New-pass-2")
check("D password changed message", "Password changed for employee #2 (Somchai Jaidee)." in out)
check("D old password no longer works", "Invalid login." in run(user="somchai", pw="Som-pass-1"))
check("D new password works", "Welcome, Somchai Jaidee!" in run(user="somchai", pw="New-pass-2"))
check("D other employee's password unchanged", q("SELECT password FROM Employees WHERE employee_id=1") == admin_hash)

# ---------------- E. Change password for nonexistent employee
before = dump()
out = run("15", "d", "99");    check("E nonexistent employee rejected", "Employee not found." in out and "New password" not in out)
out = run("15", "d", "abc");   check("E non-numeric id handled", "Error: invalid literal" in out and "Traceback" not in out)
check("E database unchanged", dump() == before)

# ---------------- F. Remove an employee with no history
run("15", "b", "Temp Worker", "temp", "Temp-pw-9", "Temp-pw-9")
check("setup: Temp Worker is employee #3", q("SELECT name FROM Employees WHERE employee_id=3") == [("Temp Worker",)])
out = run("15", "c", "3", "n");  check("F answering n keeps employee #3", "Nothing removed." in out and
                                       q("SELECT COUNT(*) FROM Employees WHERE employee_id=3") == [(1,)])
out = run("15", "c", "3", "y");  check("F employee #3 removed", "Employee #3 (Temp Worker) removed." in out and
                                       q("SELECT COUNT(*) FROM Employees WHERE employee_id=3") == [(0,)])
check("F removed employee can't log in", "Invalid login." in run(user="temp", pw="Temp-pw-9"))
out = run("15", "c", "3");       check("F removing #3 again -> not found", "Employee not found." in out)
out = run("15", "c", "99");      check("F nonexistent employee -> not found", "Employee not found." in out)
check("B-F: history tables untouched", dump(HISTORY) == history_start)
check("B-F: reports unchanged", reports() == reports_start)
check("B-F: receipts reprint unchanged", receipts() == receipts_start)

# ---------------- G. Employees with history can't be removed
out = run("1", "2", "2", "11", "", "1", "1", "2", "11", "", "5", "2", "5", "11", "cash", user="somchai", pw="New-pass-2")
check("setup: Somchai seats, orders and pays -> receipt 6", "Receipt #6 issued." in out and
      q("SELECT employee_id FROM Receipt WHERE receipt_id=6") == [(2,)])
run("1", "4", "2", "12", "", "6", "1", user="somchai", pw="New-pass-2")          # open order 12 by Somchai
run("15", "b", "Nok Siri", "nok", "Nok-pw-7", "Nok-pw-7")                       # employee #4
run("1", "5", "2", "13", "", "4", "1", user="nok", pw="Nok-pw-7")               # open order 13 by Nok (no receipt)
check("setup: orders 12 (Somchai) and 13 (Nok) open",
      q("SELECT order_id, employee_id FROM Orders WHERE status='open' ORDER BY order_id") == [(12, 2), (13, 4)])

before, receipts_before, reports_before = dump(), receipts(), reports()
out = run("15", "c", "2")
check("G Somchai refused, with counts and reason",
      "Employee #2 (Somchai Jaidee) cannot be removed: they are recorded on 2 order(s) and 1 receipt(s)." in out
      and "erase who handled those orders" in out and "(y/n)" not in out)
out = run("15", "c", "4")
check("G Nok (open order only) refused", "recorded on 1 order(s) and 0 receipt(s)" in out)
out = run("15", "c", "1", user="somchai", pw="New-pass-2")
check("G admin (5 orders, 5 receipts) refused", "recorded on 5 order(s) and 5 receipt(s)" in out)
out = run("15", "c", "1")
check("G removing yourself refused", "You cannot remove yourself while you are logged in." in out)
try:
    con = sqlite3.connect(DB); con.execute("PRAGMA foreign_keys = ON")
    con.execute("DELETE FROM Employees WHERE employee_id = 2"); con.commit(); fk_blocked = False
except sqlite3.IntegrityError:
    fk_blocked = True
finally:
    con.close()
check("G foreign keys also block a direct DELETE (backstop)", fk_blocked)

# ---------------- H/I/J. History, receipts and reports intact
check("H whole database identical after refused removals", dump() == before)
check("H Somchai's orders 11 and 12 still linked to him",
      q("SELECT order_id FROM Orders WHERE employee_id=2 ORDER BY order_id") == [(11,), (12,)])
check("I all 6 receipts reprint identically", receipts() == receipts_before)
check("I receipt 6 shows 'Issued by Somchai Jaidee'", "Issued by Somchai Jaidee" in receipts_before[6])
run("15", "d", "2", "Som-pass-1", "Som-pass-1")
check("I receipts identical after changing Somchai's password", receipts() == receipts_before)
check("I password change left history tables untouched", dump(HISTORY) == [l for l in before if any(
      l.startswith(f'INSERT INTO "{t}"') for t in HISTORY)])
check("J reports identical after all employee operations", reports() == reports_before)

# ---------------- K. Existing employees keep working
out = run("14", "4", "1", user="somchai", pw="Som-pass-1")
check("K Somchai transfers his open order 12", "Order #12 moved from table 4 to table 1." in out)
out = run("5", "12", "card")
check("K admin pays Somchai's order 12 -> receipt 7", "Receipt #7 issued." in out and
      q("SELECT o.employee_id, r.employee_id FROM Receipt r JOIN Orders o ON o.order_id = r.order_id "
        "WHERE r.receipt_id=7") == [(2, 1)])
out = run("13", "b", "5", "y", user="nok", pw="Nok-pw-7")
check("K Nok cancels her open order 13", "Order #13 cancelled. Table 5 is free again." in out)
out = run("15", "c", "4", "y")
check("K Nok now has no history -> removable", "Employee #4 (Nok Siri) removed." in out)
check("K admin still logs in and lists employees",
      "[1] Default Employee | username: admin (you)" in run("15", "a") and
      "[2] Somchai Jaidee | username: somchai" in run("15", "a"))
check("K all tables free at the end", q("SELECT COUNT(*) FROM Tables WHERE status='free'") == [(5,)])

# ---------------- Security: no password or hash ever printed
stored = [p for (p,) in q("SELECT password FROM Employees")]
leaks = [p for p in PASSWORDS + stored + [h(p) for p in PASSWORDS] if any(p in o for o in outputs)]
check(f"Security: none of {len(PASSWORDS)} test passwords or their hashes appear in {len(outputs)} program outputs",
      not leaks, leaks)

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
