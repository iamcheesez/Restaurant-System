"""CLI compatibility: the terminal program must behave exactly as it did before the service-layer refactor.

Each scenario is one terminal session. It runs twice, on two copies of the same seeded database:
once with the program from git commit cf298a1 (before the refactor) and once with the current
program. What they print and what they leave in the database must be identical.

A few scenarios are intentionally different (approved validation fixes): there the old program
printed a wrong success message or a raw database error, and the new one prints a clear message.
For those, the outputs must differ only in that message, and the databases must still match.

Needs git and the commit in the local history; otherwise the suite reports SKIPPED.
"""
import os, re, shutil, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
WORK_ROOT = os.environ.get("RESTAURANT_TEST_WORK", os.path.join(ROOT, "tests", "_work"))
BASELINE = "cf298a1"
WORK = os.path.join(WORK_ROOT, "cli_compat")
shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)

old_prog = os.path.join(WORK, "baseline", "restaurant_system.py")
os.makedirs(os.path.dirname(old_prog))
try:
    source = subprocess.run(["git", "-C", ROOT, "show", f"{BASELINE}:restaurant_system.py"],
                            capture_output=True, text=True, check=True).stdout
except (OSError, subprocess.CalledProcessError):
    print(f"SKIPPED: git or commit {BASELINE} is not available")
    sys.exit(0)
open(old_prog, "w").write(source)
new_prog = os.path.join(ROOT, "restaurant_system.py")

sys.path.insert(0, ROOT)
import seed_database  # noqa: E402

SEEDED = os.path.join(WORK, "seeded.db")
seed_database.seed(SEEDED)

results = []
TS = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def session(prog, folder, inputs, user, pw, seeded):
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    db = os.path.join(folder, "restaurant.db")
    if seeded:
        shutil.copy(SEEDED, db)
    stdin = "\n".join([user, pw, *inputs, "0"]) + "\n"
    out = subprocess.run([sys.executable, prog], input=stdin, capture_output=True, text=True, cwd=folder).stdout
    con = sqlite3.connect(db)
    try:
        data = [TS.sub("<time>", line) for line in con.iterdump()]
    finally:
        con.close()
    return TS.sub("<time>", out), data


def run(name, inputs, user="admin", pw="1234", seeded=True):
    old = session(old_prog, os.path.join(WORK, "old"), inputs, user, pw, seeded)
    new = session(new_prog, os.path.join(WORK, "new"), inputs, user, pw, seeded)
    return old, new


# ------------------------------------------------------------ identical behaviour
SAME = [
    ("view tables", ["12"]),
    ("seat a free table", ["1", "2"]),
    ("seat an occupied table", ["1", "3"]),
    ("seat an unknown table", ["1", "99"]),
    ("seat with non-numeric input", ["1", "x"]),
    ("add item", ["2", "27", "", "16", "2"]),
    ("add a dish already on the order", ["2", "27", "", "5", "1"]),
    ("add item after a menu search", ["2", "27", "curry", "8", "1"]),
    ("add item, search with no match", ["2", "27", "zzz", "6", "1"]),
    ("add to a paid order", ["2", "1"]),
    ("add to an unknown order", ["2", "999"]),
    ("add with non-numeric order", ["2", "abc"]),
    ("remove item", ["3", "27", "1"]),
    ("remove a dish not on the order", ["3", "27", "16"]),
    ("remove from a paid order", ["3", "1"]),
    ("remove from an unknown order", ["3", "999"]),
    ("show bill", ["4", "27"]),
    ("show bill of a paid order", ["4", "3"]),
    ("pay by cash", ["5", "27", "cash"]),
    ("pay with blank method (cash)", ["5", "28", ""]),
    ("pay a paid order", ["5", "1"]),
    ("pay an unknown order", ["5", "999"]),
    ("pay an empty order", ["1", "2", "5", "30"]),
    ("search menu (all)", ["6", ""]),
    ("search menu by category", ["6", "drink"]),
    ("search menu, no match", ["6", "zzz"]),
    ("daily sales report", ["7"]),
    ("best sellers report", ["8"]),
    ("busiest hours report", ["9"]),
    ("reprint receipt", ["10", "3"]),
    ("reprint unknown receipt", ["10", "999"]),
    ("menu: list all", ["11", "a"]),
    ("menu: add dish", ["11", "b", "Thai Tea", "Drink", "45"]),
    ("menu: add dish without a name", ["11", "b", "", "Drink", "45"]),
    ("menu: add dish with non-numeric price", ["11", "b", "X", "Main", "cheap"]),
    ("menu: change price", ["11", "c", "5", "85"]),
    ("menu: change price of unknown dish", ["11", "c", "999", "10"]),
    ("menu: toggle availability", ["11", "d", "17"]),
    ("menu: toggle unknown dish", ["11", "d", "999"]),
    ("menu: invalid choice", ["11", "z"]),
    ("cancel by order id", ["13", "a", "29", "y"]),
    ("cancel, answer n", ["13", "a", "29", "n"]),
    ("cancel by table number", ["13", "b", "3", "y"]),
    ("cancel a paid order", ["13", "a", "1"]),
    ("cancel an unknown order", ["13", "a", "999"]),
    ("cancel on an unknown table", ["13", "b", "99"]),
    ("cancel on a free table", ["13", "b", "2"]),
    ("cancel, invalid choice", ["13", "z"]),
    ("transfer", ["14", "1", "6"]),
    ("transfer to the same table", ["14", "1", "1"]),
    ("transfer to an occupied table", ["14", "1", "3"]),
    ("transfer from a free table", ["14", "2", "4"]),
    ("transfer from an unknown table", ["14", "99", "2"]),
    ("transfer to an unknown table", ["14", "1", "99"]),
    ("employees: list", ["15", "a"]),
    ("employees: add", ["15", "b", "New Person", "newp", "pw1", "pw1"]),
    ("employees: add duplicate username", ["15", "b", "X", "admin"]),
    ("employees: add without a name", ["15", "b", "", "x"]),
    ("employees: add username with a space", ["15", "b", "X", "a b"]),
    ("employees: add, passwords differ", ["15", "b", "X", "xx", "p1", "p2"]),
    ("employees: add, empty password", ["15", "b", "X", "xx", ""]),
    ("employees: remove (no history)", ["15", "c", "5", "y"]),
    ("employees: remove, answer n", ["15", "c", "5", "n"]),
    ("employees: remove someone with history", ["15", "c", "2"]),
    ("employees: remove yourself", ["15", "c", "1"]),
    ("employees: remove unknown", ["15", "c", "99"]),
    ("employees: change password", ["15", "d", "2", "np", "np"]),
    ("employees: change password, unknown", ["15", "d", "99"]),
    ("employees: change password, passwords differ", ["15", "d", "2", "a", "b"]),
    ("employees: back", ["15", "e"]),
    ("employees: invalid choice", ["15", "z"]),
    ("invalid main menu choice", ["99"]),
    ("long session: seat, add, transfer, pay, reprint, reports",
     ["1", "2", "2", "30", "", "5", "1", "14", "2", "4", "5", "30", "card", "10", "27", "7", "8", "9", "12"]),
]
for name, inputs in SAME:
    (old_out, old_db), (new_out, new_db) = run(name, inputs)
    check(f"same output: {name}", old_out == new_out)
    check(f"same database: {name}", old_db == new_db)

for label, user, pw in (("wrong password", "admin", "nope"), ("unknown user", "ghost", "1234"),
                        ("other employee", "somchai", "somchai123")):
    (old_out, old_db), (new_out, new_db) = run(f"login: {label}", ["12"], user, pw)
    check(f"same output and database: login, {label}", old_out == new_out and old_db == new_db)

(old_out, old_db), (new_out, new_db) = run("brand-new database", ["12", "6", "", "15", "a"], seeded=False)
check("same output and database: brand-new database gets the same default data", old_out == new_out and old_db == new_db)

# ------------------------------------------------------------ intentional, approved changes
CHANGED = [
    ("add a sold-out dish", ["2", "27", "", "17", "1"],
     "Item added.", "Fresh Coconut is sold out and cannot be ordered."),
    ("add a nonexistent dish", ["2", "27", "", "999", "1"],
     "Item added.", "Dish #999 not found."),
    ("add quantity 0", ["2", "27", "", "16", "0"],
     "Error: CHECK constraint failed: quantity > 0", "Quantity must be a whole number of at least 1."),
    ("add quantity -1 to a dish on the order", ["2", "27", "", "5", "-1"],
     "Error: CHECK constraint failed: quantity > 0", "Quantity must be a whole number of at least 1."),
    ("add a dish with a negative price", ["11", "b", "X", "Main", "-5"],
     "Error: CHECK constraint failed: price >= 0", "Price cannot be negative."),
    ("add a dish with price nan", ["11", "b", "X", "Main", "nan"],
     "Error: NOT NULL constraint failed: MenuItems.price", "Price must be a number."),
    ("change price to a negative number", ["11", "c", "5", "-1"],
     "Error: CHECK constraint failed: price >= 0", "Price cannot be negative."),
    ("show bill of an unknown order", ["4", "999"],
     "--- Bill for order #999 ---\n  TOTAL: 0.00", "Order not found."),
]
for name, inputs, old_text, new_text in CHANGED:
    (old_out, old_db), (new_out, new_db) = run(name, inputs)
    check(f"changed as approved: {name}: old printed '{old_text.splitlines()[0]}'", old_text in old_out)
    check(f"changed as approved: {name}: new prints '{new_text}', nothing else differs",
          old_out.replace(old_text, new_text) == new_out)
    check(f"changed as approved: {name}: same database", old_db == new_db)

check("baseline program really is the pre-refactor version",
      "def add_order_item" not in source and "def add_order_item" in open(new_prog).read())
print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
