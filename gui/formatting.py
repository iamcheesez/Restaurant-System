"""Turn service data into display text. Pure functions: no Tk, no database."""
from datetime import datetime, timedelta

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # how SQLite's datetime('now', 'localtime') stores times


def money(amount):
    return f"{(amount or 0):,.2f}"


def parse_time(stamp):
    try:
        return datetime.strptime(stamp, TIME_FORMAT)
    except (TypeError, ValueError):
        return None


def clock(stamp):
    """'2026-10-05 19:05:12' -> '19:05'."""
    t = parse_time(stamp)
    return t.strftime("%H:%M") if t else (stamp or "")


def day_and_time(stamp, now=None):
    """'Today 19:05', 'Yesterday 18:20' or 'Sat 3 Oct 12:10'."""
    t = parse_time(stamp)
    if t is None:
        return stamp or ""
    today = (now or datetime.now()).date()
    if t.date() == today:
        return f"Today {t:%H:%M}"
    if t.date() == today - timedelta(days=1):
        return f"Yesterday {t:%H:%M}"
    return f"{t:%a} {t.day} {t:%b %H:%M}"


def elapsed(stamp, now=None):
    """How long ago, for open orders: '5 min', '1 h 20 min'."""
    t = parse_time(stamp)
    if t is None:
        return ""
    minutes = max(0, int(((now or datetime.now()) - t).total_seconds() // 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"


def long_date(now=None):
    """'Monday 5 October 2026'."""
    now = now or datetime.now()
    return f"{now:%A} {now.day} {now:%B %Y}"


def plural(n, word, plural_word=None):
    return f"{n} {word if n == 1 else (plural_word or word + 's')}"


def receipt_text(receipt, width=40):
    """A receipt (from get_receipt) as fixed-width lines, the way a receipt printer prints it."""
    def row(left, right):
        left = left[:max(0, width - len(right) - 1)]
        return f"{left}{' ' * (width - len(left) - len(right))}{right}"

    t = parse_time(receipt["paid_time"])
    paid = f"{t.day} {t:%b %Y %H:%M}" if t else receipt["paid_time"]
    lines = ["Restaurant System".center(width).rstrip(), f"Receipt #{receipt['receipt_id']}".center(width).rstrip(),
             "",
             row(f"Order #{receipt['order_id']}", f"Table {receipt['table_id']}"),
             row("Paid", paid),
             row("Payment", str(receipt["method"]).capitalize()),
             row("Taken by", receipt["taken_by"]),
             row("Issued by", receipt["issued_by"]),
             "-" * width]
    for line in receipt["lines"]:
        lines.append(line["name"][:width])
        lines.append(row(f"  {line['quantity']} x {money(line['price_at_order'])}", money(line["subtotal"])))
    lines += ["-" * width, row("Total", money(receipt["amount"]))]
    return "\n".join(lines)


def parse_whole_number(text, label):
    """Read an optional whole number typed by the user. Returns (number or None, error message or None)."""
    text = (text or "").strip()
    if not text:
        return None, None
    if not text.isdigit():
        return None, f"{label} must be a whole number."
    return int(text), None
