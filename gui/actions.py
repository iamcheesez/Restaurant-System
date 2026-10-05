"""Table and order actions shared by the Tables and Order pages.

Each action asks the service layer whether it is allowed (using its check functions), shows the
dialog, runs exactly one service function and reports the result in the status bar. If the service
refuses, its own message is shown; the GUI never decides the business rules or touches the database.
Each action returns the service result on success and None when cancelled or refused. The calling
page refreshes itself afterwards either way, so the screen always matches the database.
"""
import restaurant_system as rs
from gui import dialogs
from gui.formatting import money, plural
from gui.order_dialogs import AddItemDialog, BillDialog, PayDialog, TransferDialog


def seat_customers(app, table_id):
    """Open a new order on a free table. Returns the new order id."""
    ok, order_id = app.call(rs.open_order, app.session.employee_id, table_id, title="Can't seat customers")
    if not ok:
        return None
    app.status.success(f"Seated customers at table {table_id}. Order #{order_id} is open.")
    return order_id


def add_items(app, order_id, on_added):
    """Open the add-items dialog for an open order. Returns the list of (dish, quantity) added."""
    ok, _ = app.call(rs.check_order_editable, order_id, title="Can't add items")
    if not ok:
        return None
    dialog = AddItemDialog(app, order_id, on_added)
    dialog.show(focus=dialog.search.entry)
    return dialog.added


def remove_item(app, order_id, line):
    """Remove one dish line (a row from get_bill) after confirmation. Returns True when removed."""
    ok, _ = app.call(rs.check_order_editable, order_id, title="Can't remove this item")
    if not ok:
        return None
    if not dialogs.ask_confirm(app, f"Remove {line['name']}?",
                               f"{line['quantity']} x {line['name']} ({money(line['subtotal'])}) will be taken off "
                               f"order #{order_id}.", "Remove item", cancel_text="Keep it"):
        return None
    ok, _ = app.call(rs.remove_order_item, order_id, line["item_id"], title="Can't remove this item")
    if not ok:
        return None
    app.status.success(f"Removed {line['name']} from order #{order_id}.")
    return True


def show_bill(app, order_id):
    ok, order = app.call(rs.get_order, order_id, title="Can't show the bill")
    if not ok:
        return None
    ok, bill = app.call(rs.get_bill, order_id, title="Can't show the bill")
    if not ok:
        return None
    BillDialog(app, order, bill).show()
    return bill


def transfer(app, order_id):
    """Move an open order to a free table the user picks and confirms. Returns the new table id."""
    ok, _ = app.call(rs.check_order_editable, order_id, title="Can't transfer this order")
    if not ok:
        return None
    ok, order = app.call(rs.get_order, order_id, title="Can't transfer this order")
    if not ok:
        return None
    ok, tables = app.call(rs.table_overview, title="Can't transfer this order")
    if not ok:
        return None
    free = [t for t in tables if t["status"] == "free"]
    destination = TransferDialog(app, order, free).show()
    if destination is None:
        return None
    ok, _ = app.call(rs.transfer_order, order["table_id"], destination, title="Can't transfer this order")
    if not ok:
        return None
    app.status.success(f"Moved order #{order_id} from table {order['table_id']} to table {destination}.")
    return destination


def cancel(app, order_id):
    """Cancel an open order after confirmation. Returns the service result (order, table, table_freed)."""
    ok, table_id = app.call(rs.check_order_cancellable, order_id, title="Can't cancel this order")
    if not ok:
        return None
    ok, bill = app.call(rs.get_bill, order_id, title="Can't cancel this order")
    if not ok:
        return None
    if not dialogs.ask_confirm(app, f"Cancel order #{order_id}?",
                               f"This deletes the open order on table {table_id} with its "
                               f"{plural(len(bill['lines']), 'dish', 'dishes')} ({money(bill['total'])}) and frees "
                               "the table. It can't be undone.", "Cancel order", cancel_text="Keep order"):
        return None
    ok, result = app.call(rs.cancel_open_order, order_id, title="Can't cancel this order")
    if not ok:
        return None
    app.status.success(f"Cancelled order #{order_id}." +
                       (f" Table {result['table_id']} is free." if result["table_freed"] else ""))
    return result


def pay(app, order_id):
    """Take payment after confirmation. Returns the new receipt id."""
    ok, _ = app.call(rs.check_order_payable, order_id, title="Can't take payment")
    if not ok:
        return None
    ok, order = app.call(rs.get_order, order_id, title="Can't take payment")
    if not ok:
        return None
    ok, bill = app.call(rs.get_bill, order_id, title="Can't take payment")
    if not ok:
        return None
    method = PayDialog(app, order, bill).show()
    if method is None:
        return None
    ok, receipt_id = app.call(rs.pay_order, order_id, app.session.employee_id, method, title="Can't take payment")
    if not ok:
        return None
    app.status.success(f"Order #{order_id} paid by {method}. Receipt #{receipt_id} issued; "
                       f"table {order['table_id']} is free.")
    return receipt_id
