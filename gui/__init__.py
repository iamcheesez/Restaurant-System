"""Tkinter GUI for the restaurant system.

Layers: gui (this package) -> service functions in restaurant_system.py -> SQLite.
Nothing in this package runs SQL or opens the database itself; every read and change goes
through a restaurant_system service function via RestaurantApp.call().
"""
