"""Modal dialogs: messages, confirmations for destructive actions, and a base class for forms.

Every dialog is centered on the main window, closes with Escape and runs its main button with Enter.
"""
import tkinter as tk
from tkinter import ttk

from gui.theme import COLORS


class Dialog(tk.Toplevel):
    def __init__(self, parent, title, width=420):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(background=COLORS["surface"])
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self._width = width
        self.body = ttk.Frame(self, style="Surface.TFrame", padding=(24, 22, 24, 16))
        self.body.pack(fill="both", expand=True)
        self.button_row = ttk.Frame(self, style="Surface.TFrame", padding=(24, 0, 24, 20))
        self.button_row.pack(fill="x")
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())
        self._default = None

    def add_buttons(self, buttons):
        """buttons: list of (text, command, style), left to right. The last one is the default (Enter)."""
        for text, command, style in reversed(buttons):
            button = ttk.Button(self.button_row, text=text, command=command, style=style)
            button.pack(side="right", padx=(8, 0))
        self._default = buttons[-1][1]
        self.bind("<Return>", lambda e: self._default())

    def show(self, focus=None):
        """Show the dialog, wait until it closes, and return its result."""
        parent = self.master.winfo_toplevel()
        self.update_idletasks()
        width = max(self._width, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass  # the window manager refused the grab; the dialog still works
        (focus or self).focus_set()
        self.wait_window()
        return self.result

    def close(self, result=None):
        self.result = result
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def cancel(self):
        self.close(None)


class MessageDialog(Dialog):
    def __init__(self, parent, title, message, error=False):
        super().__init__(parent, title)
        ttk.Label(self.body, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.body, text=message, style="SurfaceError.TLabel" if error else "Surface.TLabel",
                  wraplength=380, justify="left").pack(anchor="w", pady=(8, 0))
        self.add_buttons([("OK", lambda: self.close(True), "Primary.TButton")])


class ConfirmDialog(Dialog):
    """Ask before an action that can't be undone. The confirm button names the action ('Cancel order')."""

    def __init__(self, parent, title, message, confirm_text, danger=True, cancel_text="Go back"):
        super().__init__(parent, title)
        ttk.Label(self.body, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.body, text=message, style="Surface.TLabel", wraplength=380, justify="left").pack(
            anchor="w", pady=(8, 0))
        self.add_buttons([(cancel_text, self.cancel, "TButton"),
                          (confirm_text, lambda: self.close(True), "Danger.TButton" if danger else "Primary.TButton")])


class FormDialog(Dialog):
    """Base for Phase 4 forms (add dish, change password, pay...).

    Subclasses add fields with add_entry()/add_combo() and implement submit(values), which returns
    None to close the dialog (result = values) or an error message to show inside the dialog.
    """

    def __init__(self, parent, title, submit_text, intro=None, danger=False):
        super().__init__(parent, title)
        ttk.Label(self.body, text=title, style="Section.TLabel").pack(anchor="w")
        if intro:
            ttk.Label(self.body, text=intro, style="SurfaceMuted.TLabel", wraplength=380, justify="left").pack(
                anchor="w", pady=(4, 0))
        self.fields = {}
        self.form = ttk.Frame(self.body, style="Surface.TFrame")
        self.form.pack(fill="x", pady=(14, 0))
        self.error = ttk.Label(self.body, style="SurfaceError.TLabel", wraplength=380, justify="left")
        self.error.pack(anchor="w", pady=(10, 0))
        self.add_buttons([("Cancel", self.cancel, "TButton"),
                          (submit_text, self._submit, "Danger.TButton" if danger else "Primary.TButton")])

    def add_entry(self, key, label, show=None, initial=""):
        ttk.Label(self.form, text=label, style="SurfaceSmall.TLabel").pack(anchor="w", pady=(8, 0))
        var = tk.StringVar(value=initial)
        entry = ttk.Entry(self.form, textvariable=var, show=show or "")
        entry.pack(fill="x", pady=(3, 0))
        self.fields[key] = var
        return entry

    def add_combo(self, key, label, values, initial=None):
        ttk.Label(self.form, text=label, style="SurfaceSmall.TLabel").pack(anchor="w", pady=(8, 0))
        var = tk.StringVar(value=initial if initial is not None else (values[0] if values else ""))
        combo = ttk.Combobox(self.form, textvariable=var, values=list(values), state="readonly")
        combo.pack(fill="x", pady=(3, 0))
        self.fields[key] = var
        return combo

    def values(self):
        return {key: var.get() for key, var in self.fields.items()}

    def submit(self, values):
        return None

    def _submit(self):
        values = self.values()
        problem = self.submit(values)
        if problem:
            self.error.configure(text=problem)
        else:
            self.close(values)


def show_message(parent, title, message, error=False):
    return MessageDialog(parent, title, message, error).show()


def ask_confirm(parent, title, message, confirm_text, danger=True):
    return bool(ConfirmDialog(parent, title, message, confirm_text, danger).show())
