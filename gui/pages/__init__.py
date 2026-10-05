"""Page registry: the sidebar order and which class draws each page."""
from gui.pages.dashboard import DashboardPage
from gui.pages.employees import EmployeesPage
from gui.pages.menu import MenuPage
from gui.pages.order import OrderPage
from gui.pages.receipts import ReceiptsPage
from gui.pages.reports import ReportsPage
from gui.pages.tables import TablesPage

PAGES = {page.key: page for page in (DashboardPage, TablesPage, OrderPage, MenuPage, ReceiptsPage, ReportsPage,
                                     EmployeesPage)}

NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("tables", "Tables"),
    ("menu", "Menu"),
    ("receipts", "Receipts"),
    ("reports", "Reports"),
    ("employees", "Employees"),
]
