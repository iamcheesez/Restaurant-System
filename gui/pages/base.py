"""Base class for the pages shown inside the main shell."""
from tkinter import ttk

from gui.widgets import PageHeader


class Page(ttk.Frame):
    """A page has a header (title, summary, main actions) and a body.

    Subclasses set key/title, build their widgets in build() and load data in refresh(),
    always through self.call(service, ...). nav_key is the sidebar entry to highlight
    (a detail page like an order highlights "tables").
    """

    key = ""
    title = ""
    subtitle = ""
    nav_key = None

    def __init__(self, parent, app):
        super().__init__(parent, style="Page.TFrame", padding=(28, 22, 28, 18))
        self.app = app
        self.header = PageHeader(self, self.title, self.subtitle, back=self.back_link())
        self.header.pack(fill="x", pady=(0, 18))
        self.body = ttk.Frame(self, style="Page.TFrame")
        self.body.pack(fill="both", expand=True)
        self.build()

    def back_link(self):
        return None

    def build(self):
        pass

    def on_show(self, **kwargs):
        self.refresh()

    def refresh(self):
        pass

    def call(self, service, *args, **kwargs):
        return self.app.call(service, *args, **kwargs)

    def load(self, service, *args, **kwargs):
        """Read data for the page. A failure shows in the status bar (no dialog) and returns None."""
        ok, result = self.app.call(service, *args, dialog=False, **kwargs)
        return result if ok else None

    def later(self, action):
        """Command for a button whose action arrives in Phase 4. It changes nothing."""
        return lambda: self.app.status.info(f"{action} is not available yet. It is added in Phase 4.")
