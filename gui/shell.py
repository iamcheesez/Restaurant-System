"""The main window after login: sidebar on the left, top bar and the current page on the right."""
from tkinter import ttk

from gui.pages import NAV_ITEMS, PAGES
from gui.widgets import Sidebar, TopBar


class MainShell(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, style="Page.TFrame")
        self.app = app
        self.sidebar = Sidebar(self, NAV_ITEMS, on_select=self.show_page)
        self.sidebar.pack(side="left", fill="y")
        right = ttk.Frame(self, style="Page.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.topbar = TopBar(right, on_logout=app.logout)
        self.topbar.pack(fill="x")
        self.topbar.set_employee(app.session.name)
        self.page_area = ttk.Frame(right, style="Page.TFrame")
        self.page_area.pack(fill="both", expand=True)
        self.pages, self.current = {}, None

    def show_page(self, key, **kwargs):
        """Switch to a page (created on first use) and let it load fresh data.
        kwargs go to the page, for example show_page("order", order_id=27)."""
        page = self.pages.get(key)
        if page is None:
            page = self.pages[key] = PAGES[key](self.page_area, self.app)
        if self.current is not None and self.current is not page:
            self.current.pack_forget()  # hidden pages leave the keyboard focus order
        page.pack(fill="both", expand=True)
        self.current = page
        self.sidebar.set_active(page.nav_key or page.key)
        page.on_show(**kwargs)

    def refresh_current(self):
        if self.current is not None:
            self.current.refresh()
            self.app.status.info("Refreshed.", timeout=3000)
