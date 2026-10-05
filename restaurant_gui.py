"""Restaurant System desktop app (Tkinter).

Run from the project folder:
    python restaurant_gui.py              uses restaurant.db next to this file
    python restaurant_gui.py --db PATH    uses another database file

Create demo data first with: python seed_database.py
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description="Restaurant System desktop app")
    parser.add_argument("--db", default=os.path.join(HERE, "restaurant.db"),
                        help="database file (default: restaurant.db next to this file)")
    args = parser.parse_args()
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("Tkinter is not installed for this Python. On Windows and macOS it comes with the python.org "
              "installer; on Linux install the python3-tk package.")
        sys.exit(1)
    if sys.platform == "win32":
        try:  # sharp text on high-resolution Windows screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    sys.path.insert(0, HERE)
    from gui.app import RestaurantApp
    RestaurantApp(args.db).mainloop()


if __name__ == "__main__":
    main()
