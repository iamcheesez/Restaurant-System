"""The application window.

RestaurantApp owns the database connection and the signed-in employee, switches between the
login screen and the main shell, and runs every service call through call(), which turns
errors into readable messages. Pages never touch the database; they call
app.call(restaurant_system.some_service, ...).
"""
import os
import sqlite3
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import ttk

import restaurant_system as rs
from gui import dialogs, theme
from gui.widgets import StatusBar

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERROR_LOG = os.path.join(PROJECT_DIR, "gui_error.log")


class Session:
    """The signed-in employee. Holds no password."""

    def __init__(self, employee_id, name):
        self.employee_id, self.name = employee_id, name


class RestaurantApp(tk.Tk):
    def __init__(self, db_path):
        super().__init__(className="RestaurantSystem")
        self.title("Restaurant System")
        self.minsize(1100, 680)
        self._place_window(1320, 820)
        theme.apply_theme(self)
        self.report_callback_exception = self._callback_error
        self.db_path = os.path.abspath(db_path)
        self.db, self.session, self.shell, self.login_view = None, None, None, None
        self.status = StatusBar(self)
        self.status.pack(side="bottom", fill="x")
        self.content = ttk.Frame(self, style="Page.TFrame")
        self.content.pack(fill="both", expand=True)
        self.status.set_location(f"Database: {self.db_path}")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind_all("<F5>", lambda e: self.refresh())
        self._open_database()
        self.show_login()

    # ---------------------------------------------------------------- database and service calls

    def _open_database(self):
        try:
            self.db = rs.connect(self.db_path)
            created = rs.setup(self.db)
        except sqlite3.Error as e:
            self.db = None
            self.status.error(f"The database could not be opened: {e}")
            return
        if created:
            self.status.info("A new database was created with default data. Run seed_database.py to load the "
                             "demo data.", timeout=None)

    def call(self, service, *args, dialog=True, report=True, title="That didn't work", **kwargs):
        """Run a service function with the open database.

        Returns (True, result) on success and (False, message) on failure. Failures are shown in the
        status bar (report=True) and in a dialog (dialog=True); nothing is ever silently ignored.
        """
        if self.db is None:
            message = "The database is not open. Check the file shown at the bottom right and restart the app."
        else:
            try:
                return True, service(self.db, *args, **kwargs)
            except rs.RestaurantError as e:
                message = str(e)
            except sqlite3.Error as e:
                message = f"Database error: {e}"
            except Exception as e:  # a bug, not a business rule: keep the details for whoever fixes it
                message = self._log_unexpected(e)
        if report:
            self.status.error(message.splitlines()[0])
            if dialog:
                dialogs.show_message(self, title, message, error=True)
        return False, message

    def _log_unexpected(self, error):
        try:
            with open(ERROR_LOG, "a", encoding="utf-8") as log:
                log.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S}\n{traceback.format_exc()}")
            where = f" Details were saved to {os.path.basename(ERROR_LOG)}."
        except OSError:
            where = ""
        return f"Something went wrong: {error}.{where}"

    def _callback_error(self, exc_type, value, tb):
        """Any unexpected error in a button or event handler: log it and show a readable message."""
        try:
            raise value
        except Exception as e:
            message = self._log_unexpected(e)
        self.status.error(message)
        dialogs.show_message(self, "Something went wrong", message, error=True)

    # ---------------------------------------------------------------- login, logout, navigation

    def show_login(self):
        from gui.pages.login import LoginView
        if self.shell is not None:
            self.shell.destroy()
            self.shell = None
        self.login_view = LoginView(self.content, self)
        self.login_view.pack(fill="both", expand=True)
        self.login_view.focus_first()

    def on_login(self, employee):
        from gui.shell import MainShell
        self.session = Session(employee["employee_id"], employee["name"])
        self.login_view.destroy()
        self.login_view = None
        self.shell = MainShell(self.content, self)
        self.shell.pack(fill="both", expand=True)
        self.shell.show_page("dashboard")
        self.status.success(f"Signed in as {employee['name']}.")

    def logout(self):
        self.session = None
        self.show_login()
        self.status.info("Signed out.")

    def show_page(self, key, **kwargs):
        if self.shell is not None:
            self.shell.show_page(key, **kwargs)

    def refresh(self):
        if self.shell is not None:
            self.shell.refresh_current()

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None
        self.destroy()

    def _place_window(self, width, height):
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(width, screen_w - 40), min(height, screen_h - 80)
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}")
