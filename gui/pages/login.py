"""Sign-in screen. Checks the login with restaurant_system.authenticate; the password is never shown or kept."""
import tkinter as tk
from tkinter import ttk

import restaurant_system as rs
from gui.theme import COLORS
from gui.widgets import LabeledEntry


class LoginView(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="Page.TFrame")
        self.app = app

        side = tk.Frame(self, background=COLORS["sidebar"], width=420)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        intro = ttk.Frame(side, style="Sidebar.TFrame", padding=(48, 0))
        intro.place(relx=0, rely=0.38, anchor="w", relwidth=1)
        ttk.Label(intro, text="Restaurant System", style="Brand.TLabel").pack(anchor="w")
        ttk.Label(intro, text="Seat guests, take orders and close bills from one screen.", style="BrandSub.TLabel",
                  wraplength=300, justify="left").pack(anchor="w", pady=(8, 0))

        holder = ttk.Frame(self, style="Page.TFrame")
        holder.pack(side="left", fill="both", expand=True)
        card = tk.Frame(holder, background=COLORS["surface"], highlightthickness=1,
                        highlightbackground=COLORS["border"], highlightcolor=COLORS["border"])
        card.place(relx=0.5, rely=0.42, anchor="center")
        form = ttk.Frame(card, style="Surface.TFrame", padding=(36, 32, 36, 30))
        form.pack()
        ttk.Label(form, text="Sign in", style="Section.TLabel").pack(anchor="w")
        ttk.Label(form, text="Use your staff username and password.", style="SurfaceMuted.TLabel").pack(
            anchor="w", pady=(2, 18))
        self.username = LabeledEntry(form, "Username", width=32, surface=True)
        self.username.pack(fill="x")
        self.password = LabeledEntry(form, "Password", width=32, show="*", surface=True)
        self.password.pack(fill="x", pady=(12, 0))
        self.error = ttk.Label(form, style="SurfaceError.TLabel", wraplength=300, justify="left")
        self.error.pack(anchor="w", pady=(12, 0))
        self.button = ttk.Button(form, text="Sign in", style="Primary.TButton", command=self.submit)
        self.button.pack(fill="x", pady=(8, 0))
        for entry in (self.username.entry, self.password.entry):
            entry.bind("<Return>", lambda e: self.submit())

    def focus_first(self):
        self.username.entry.focus_set()

    def submit(self):
        username, password = self.username.get().strip(), self.password.get()
        if not username or not password:
            self._show_error("Enter your username and password.")
            return
        ok, result = self.app.call(rs.authenticate, username, password, report=False)
        self.password.set("")  # never keep the password around
        if not ok:
            self._show_error(result)
            self.password.entry.focus_set()
            return
        self.app.on_login(result)

    def _show_error(self, message):
        self.error.configure(text=message)
