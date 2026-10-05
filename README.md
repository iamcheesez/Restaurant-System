# Restaurant Table and Order System

A Database Systems course project: a restaurant system where an employee (cashier or waiter) seats customers, takes orders, issues receipts and views reports. Built with Python and SQLite. Every action runs SQL against the database.

## Requirements

- Python 3.9 or newer. Nothing else to install: SQLite comes with Python.
- For the desktop app: Tkinter, which comes with the python.org installers for Windows and macOS (on Linux, install the `python3-tk` package).

## Quick start

From this folder:

```
python seed_database.py
python restaurant_system.py
```

The first command creates `restaurant.db` with realistic demo data. The second starts the program. Log in as `admin` with password `1234`. The password is not shown while you type.

On Windows, use `py` instead of `python` if `python` isn't found.

### Desktop app (work in progress)

```
python restaurant_gui.py
```

This opens the desktop version on the same `restaurant.db` (the one next to `restaurant_gui.py`; use `--db PATH` for another file). It currently shows the dashboard, tables, orders, menu, receipts, reports and employees, but buttons that change data are not connected yet; they say so in the status bar.

## Demo logins

These are sample accounts created by `seed_database.py`, for development and demos only.

| Username | Password | Employee |
|---|---|---|
| admin | 1234 | Restaurant Manager |
| somchai | somchai123 | Somchai Jaidee |
| nok | nok123 | Nok Siriwan |
| anan | anan123 | Anan Wongsa |
| mali | mali123 | Mali Chaiyo (new hire, no order history) |

## What you can try with the demo data

| Menu option | Try this |
|---|---|
| 12 View tables | Tables 1, 3 and 7 are occupied |
| 4 Show bill | Order `27`: 4 dishes, 395.00 |
| 2 Add item / 3 Remove item | On order `27` |
| 14 Transfer a table | Move order 28 from table `1` (2 seats) to table `6` (6 seats) |
| 5 Pay and issue receipt | Order `27`, paid by cash or card |
| 10 Reprint receipt | Receipt `3` shows Pad Thai at its old price, 75.00 |
| 13 Cancel open order | By table number `7` |
| 7, 8, 9 Reports | Daily sales, best-selling dishes, busiest hours |
| 11 Manage menu | Fresh Coconut is sold out; switch it back on |
| 15 Manage employees | Mali can be removed; staff with order history cannot |

## Reset the demo data

Close the program first, then run:

```
python seed_database.py --reset
```

Without `--reset`, the seed script refuses to overwrite an existing `restaurant.db`. The demo data is the same every time; dates are relative to the day you run it.

## Features

1. Seat customers (opens an order)
2. Add item to order
3. Remove item from order
4. Show bill
5. Pay and issue receipt
6. Search menu
7. Report: daily sales
8. Report: best-selling dishes
9. Report: busiest hours
10. Reprint receipt
11. Manage menu (list, add dish, change price, mark available or sold out)
12. View tables
13. Cancel open order
14. Transfer a table
15. Manage employees (list, add, remove, change password)

## Database design

| Table | Key columns | Keys |
|---|---|---|
| Employees | employee_id, name, username, password (SHA-256 hash) | PK employee_id; username unique |
| Tables | table_id, seats, status (free / occupied) | PK table_id |
| MenuItems | item_id, name, category, price, available | PK item_id |
| Orders | order_id, table_id, employee_id, order_time, status (open / paid) | PK order_id; FK table_id, employee_id |
| OrderItems | order_id, item_id, quantity, price_at_order | PK (order_id, item_id); FK both |
| Receipt | receipt_id, order_id, employee_id, table_id, amount, method, paid_time | PK receipt_id; FK order_id, employee_id, table_id |
| ReceiptItems | receipt_id, item_id | PK (receipt_id, item_id); FK both |

Database concepts used:

- **Normalization (3NF):** order lines live in OrderItems, not inside Orders.
- **Foreign keys and CHECK constraints:** for example, quantity must be more than 0 and a table's status can only be free or occupied.
- **Historical prices:** `price_at_order` keeps old bills and receipts correct after a menu price changes.
- **Trigger:** `trg_free_table` frees a table when its order is paid.
- **View:** `DailySales` totals receipts per day.
- **Transactions:** seating, paying, cancelling and transferring each succeed or fail as a whole.

Business rules the program enforces:

- Paid orders cannot be modified, cancelled or transferred.
- A table is occupied exactly when it has an open order.
- Employees who appear on orders or receipts cannot be removed, so the history stays intact.
- Dishes that appear on orders cannot be renamed or deleted (mark them sold out instead).

## Code structure

`restaurant_system.py` has two layers:

- **Service functions** take parameters, run the SQL and return data. Every change runs in one transaction. A broken business rule raises `RestaurantError` with a message meant for the user. They never read input or print.
- **The terminal menu** asks for input, calls a service function and prints the result.

The desktop app in `gui/` sits on top of the same service functions: GUI → service functions → SQLite. The GUI contains no SQL and never opens the database itself.

| Part of `gui/` | What it does |
|---|---|
| `app.py` | Main window: opens the database, signs employees in and out, and runs every service call through one place that turns errors into readable messages |
| `shell.py` | The layout after sign-in: sidebar, top bar, page area |
| `pages/` | One file per screen (dashboard, tables, order, menu, receipts, reports, employees) plus the login screen |
| `widgets.py` | Reusable parts: status bar, sidebar, page header, cards, data tables, table cards, bar charts |
| `dialogs.py` | Message, confirmation and form dialogs |
| `theme.py` | Colors, fonts and styles for the whole app |
| `formatting.py` | Turns data into display text (money, times, the printed receipt) |

## Running the tests

```
python tests/run_all.py
```

This runs every test suite in order on a fresh test database and prints the total. Suites 1–6 drive the terminal program like a person would, so they need macOS or Linux. Suite 7 tests the service functions directly, and suite 8 checks that the terminal program still behaves exactly as it did before the service layer was added (it needs git). Suite 9 checks the GUI code (no SQL, service functions only), and suite 10 opens the GUI and clicks through every page; it is skipped when Tkinter or a display isn't available.

## Files

| File | Purpose |
|---|---|
| `restaurant_system.py` | The program: database schema, service functions and the terminal menu |
| `restaurant_gui.py` | Starts the desktop app |
| `gui/` | The desktop app (Tkinter) |
| `seed_database.py` | Creates or resets `restaurant.db` with demo data |
| `tests/` | Test suites; `run_all.py` runs them all |
| `restaurant.db` | Created when you run either script; not stored in the repository |
