"""GUI static checks. They read the GUI source code; no window is opened, so Tkinter is not needed.

- No SQL and no direct database access anywhere in the GUI (gui/ and restaurant_gui.py).
- The GUI uses restaurant_system only through service functions, never the terminal (CLI) functions.
- No input(), print() or getpass() in the GUI; all on-screen text is plain Latin-1 (safe on Tk 8.6).
- The display helpers in gui/formatting.py work (they are pure functions).
- restaurant_system.py and seed_database.py are unchanged since Phase 1 (commit 218303b).
"""
import ast, glob, os, py_compile, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the project folder
sys.path.insert(0, ROOT)
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


FILES = sorted(glob.glob(os.path.join(ROOT, "gui", "**", "*.py"), recursive=True)) + [os.path.join(ROOT, "restaurant_gui.py")]
rel = lambda p: os.path.relpath(p, ROOT)
trees = {p: ast.parse(open(p, encoding="utf-8").read(), filename=p) for p in FILES}
check("GUI files found (gui/ and restaurant_gui.py)", len(FILES) >= 14, [rel(p) for p in FILES])
for p in FILES:
    try:
        py_compile.compile(p, doraise=True)
        ok = True
    except py_compile.PyCompileError as e:
        ok = str(e)
    check(f"compiles: {rel(p)}", ok is True, ok)

# ---------------------------------------------------------------- no SQL
SQL_UPPER = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|PRAGMA|FROM|WHERE|JOIN|VALUES)\b")
SQL_SHAPE = re.compile(r"(?i)\binsert\s+into\b|\bdelete\s+from\b|\bupdate\s+\w+\s+set\b|\bselect\s+[\w*,.\s]+\s+from\s+\w+"
                       r"|\bcreate\s+(table|view|trigger|index)\b|\bdrop\s+(table|view|trigger)\b|\bpragma\s+\w+")
strings = [(rel(p), n.lineno, n.value) for p, t in trees.items() for n in ast.walk(t)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)]
sql = [(f, line, s[:60]) for f, line, s in strings if SQL_UPPER.search(s) or SQL_SHAPE.search(s)]
check(f"no SQL in any of the {len(strings)} strings in the GUI", not sql, sql[:5])

DB_METHODS = {"execute", "executemany", "executescript", "cursor", "commit", "rollback", "iterdump", "backup",
              "create_function", "set_authorizer"}
db_calls = [(rel(p), n.lineno, n.func.attr) for p, t in trees.items() for n in ast.walk(t)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in DB_METHODS]
check("no direct database calls (execute, cursor, commit...) in the GUI", not db_calls, db_calls)
sqlite_uses = [(rel(p), n.lineno, n.attr) for p, t in trees.items() for n in ast.walk(t)
               if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "sqlite3"]
check("the GUI uses sqlite3 only to recognise database errors (sqlite3.Error)",
      all(attr == "Error" for _, _, attr in sqlite_uses), sqlite_uses)
importers = sorted({rel(p) for p, t in trees.items() for n in ast.walk(t)
                    if isinstance(n, ast.Import) and any(a.name == "sqlite3" for a in n.names)})
check("only gui/app.py imports sqlite3", importers == [os.path.join("gui", "app.py")], importers)

# ---------------------------------------------------------------- service layer only
import restaurant_system as rs  # noqa: E402

CLI = {"login", "show_tables", "seat_customers", "search_menu", "add_item", "remove_item", "print_bill", "pay",
       "cancel_order", "transfer_table", "daily_sales", "best_sellers", "busiest_hours", "reprint_receipt",
       "manage_menu", "ask_new_password", "manage_employees", "main", "connect", "setup"}
used = {}
for p, t in trees.items():
    for n in ast.walk(t):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "rs":
            used.setdefault(n.attr, set()).add(rel(p))
unknown = [name for name in used if not hasattr(rs, name)]
check("every restaurant_system name the GUI uses exists", not unknown, unknown)
cli_used = {name: sorted(files) for name, files in used.items() if name in CLI}
allowed_setup = {"connect": ["gui/app.py"], "setup": ["gui/app.py"]}
check("the GUI never calls terminal functions (print_bill, pay, manage_menu...)",
      all(name in allowed_setup and files == allowed_setup[name] for name, files in cli_used.items()), cli_used)
private = [name for name in used if name.startswith("_")]
check("the GUI uses no private helpers of restaurant_system (_rows, _date_range...)", not private, private)
other_imports = [(rel(p), n.lineno) for p, t in trees.items() for n in ast.walk(t)
                 if (isinstance(n, ast.ImportFrom) and n.module == "restaurant_system")
                 or (isinstance(n, ast.Import) and any(a.name == "restaurant_system" and a.asname != "rs" for a in n.names))]
check("restaurant_system is always imported as 'rs' (so these checks see every use)", not other_imports, other_imports)
services_used = sorted(n for n in used if n not in ("RestaurantError", "DishInUseError"))
print("     service functions used by the GUI:", ", ".join(services_used))

# ---------------------------------------------------------------- no terminal I/O, plain text
io_calls = [(rel(p), n.lineno, n.func.id) for p, t in trees.items() for n in ast.walk(t)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("input", "print", "getpass")
            and not rel(p).endswith("restaurant_gui.py")]
check("no input(), print() or getpass() in the GUI", not io_calls, io_calls)
wide = [(f, line, s[:40]) for f, line, s in strings if any(ord(c) > 255 for c in s)]
check("all GUI text is Latin-1 (Tk 8.6 shows other symbols as \\uXXXX on some computers)", not wide, wide)
password_entries = [(rel(p), n.lineno) for p, t in trees.items() for n in ast.walk(t)
                    if isinstance(n, ast.Call) and any(k.arg == "show" and isinstance(k.value, ast.Constant)
                                                       and k.value.value == "*" for k in n.keywords)]
check("the login password field is masked (show='*')",
      any(f.endswith(os.path.join("pages", "login.py")) for f, _ in password_entries), password_entries)
session = [n for n in ast.walk(trees[os.path.join(ROOT, "gui", "app.py")])
           if isinstance(n, ast.ClassDef) and n.name == "Session"][0]
session_params = [a.arg for f in session.body if isinstance(f, ast.FunctionDef) for a in f.args.args]
session_attrs = [n.attr for n in ast.walk(session) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                 and n.value.id == "self"]
check("the Session object stores no password (parameters and attributes)",
      not any("pass" in x.lower() for x in session_params + session_attrs), session_params + session_attrs)

# ---------------------------------------------------------------- formatting helpers
import gui.formatting as fm  # noqa: E402
from datetime import datetime  # noqa: E402

check("gui/formatting.py does not need Tkinter", "tkinter" not in open(fm.__file__).read())
now = datetime(2026, 10, 5, 19, 40)
check("money", (fm.money(395), fm.money(10945.5), fm.money(None)) == ("395.00", "10,945.50", "0.00"))
check("clock", fm.clock("2026-10-05 19:05:12") == "19:05" and fm.clock(None) == "")
check("day_and_time", (fm.day_and_time("2026-10-05 19:05:00", now), fm.day_and_time("2026-10-04 18:20:00", now),
                       fm.day_and_time("2026-10-03 12:10:00", now)) == ("Today 19:05", "Yesterday 18:20", "Sat 3 Oct 12:10"))
check("elapsed", (fm.elapsed("2026-10-05 19:05:00", now), fm.elapsed("2026-10-05 18:20:00", now),
                  fm.elapsed("2026-10-05 17:40:00", now)) == ("35 min", "1 h 20 min", "2 h"))
check("long_date", fm.long_date(now) == "Monday 5 October 2026")
check("plural", (fm.plural(1, "dish", "dishes"), fm.plural(4, "dish", "dishes"), fm.plural(2, "table")) ==
      ("1 dish", "4 dishes", "2 tables"))
check("parse_whole_number", (fm.parse_whole_number("", "Table"), fm.parse_whole_number(" 12 ", "Table"),
                             fm.parse_whole_number("x", "Table"), fm.parse_whole_number("-1", "Table")) ==
      ((None, None), (12, None), (None, "Table must be a whole number."), (None, "Table must be a whole number.")))
receipt = {"receipt_id": 3, "order_id": 3, "table_id": 5, "paid_time": "2026-09-28 20:57:00", "method": "card",
           "amount": 565.0, "taken_by": "Restaurant Manager", "issued_by": "Nok Siriwan",
           "lines": [{"name": "Pad Thai", "quantity": 2, "price_at_order": 75.0, "subtotal": 150.0},
                     {"name": "Massaman Curry", "quantity": 2, "price_at_order": 110.0, "subtotal": 220.0},
                     {"name": "Fresh Coconut", "quantity": 3, "price_at_order": 50.0, "subtotal": 150.0},
                     {"name": "Water", "quantity": 3, "price_at_order": 15.0, "subtotal": 45.0}]}
text = fm.receipt_text(receipt)
lines = text.splitlines()
check("receipt_text: every line fits 40 characters", all(len(l) <= 40 for l in lines), max(len(l) for l in lines))
check("receipt_text: shows receipt, order, table, both employees, items at historical prices and total",
      all(s in text for s in ("Receipt #3", "Order #3", "Table 5", "Taken by", "Restaurant Manager", "Issued by",
                              "Nok Siriwan", "Pad Thai", "2 x 75.00", "150.00", "Total", "565.00", "Card")))

# ---------------------------------------------------------------- backend unchanged since Phase 1
try:
    diff = subprocess.run(["git", "-C", ROOT, "diff", "--stat", "218303b", "--", "restaurant_system.py",
                           "seed_database.py"], capture_output=True, text=True, check=True).stdout.strip()
    check("restaurant_system.py and seed_database.py unchanged since Phase 1 (218303b)", diff == "", diff)
except (OSError, subprocess.CalledProcessError) as e:
    print(f"     (git not available, skipped the unchanged-backend check: {e})")

print(f"\n{sum(ok for _, ok in results)}/{len(results)} checks passed")
