"""Colors, fonts, spacing and ttk styles for the whole GUI.

Change the look here, not in the pages. Pages refer to styles by name
(for example "Primary.TButton") and to COLORS / FONTS / SPACE for the few
plain-Tk widgets (canvas drawings, table cards).
"""
from tkinter import font as tkfont
from tkinter import ttk

COLORS = {
    # text
    "ink": "#1F2933",
    "muted": "#5B6770",
    "subtle": "#8A969E",
    # surfaces
    "page": "#F3F5F4",
    "surface": "#FFFFFF",
    "border": "#DCE3DF",
    "row_alt": "#F7F9F8",
    "select": "#D7EBDF",
    # sidebar
    "sidebar": "#1E3B33",
    "sidebar_text": "#C9D8D1",
    "sidebar_muted": "#8FA89D",
    "sidebar_hover": "#264A40",
    "sidebar_active": "#2F5A4C",
    # actions and states
    "primary": "#1F6F4A",          # basil: primary actions, free tables
    "primary_hover": "#185A3C",
    "primary_tint": "#E3F1E8",
    "saffron": "#E8A317",          # occupied / needs attention
    "saffron_tint": "#FFF4D6",
    "saffron_ink": "#6B4A00",
    "chili": "#B42318",            # destructive actions and errors only
    "chili_hover": "#912018",
    "chili_tint": "#FDECEA",
    "slate_tint": "#EEF1F3",
    "slate_ink": "#4A5560",
    "info_tint": "#E8F0F8",
    "info_ink": "#1D4E89",
}

SPACE = {"xs": 4, "s": 8, "m": 12, "l": 16, "xl": 24, "xxl": 32}

# Filled in by apply_theme() once a Tk root exists (font availability depends on the computer).
FONTS = {}

UI_FAMILIES = ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Noto Sans", "Ubuntu", "Cantarell",
               "DejaVu Sans", "Helvetica", "Arial"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "SF Mono", "Menlo", "Noto Sans Mono", "DejaVu Sans Mono",
                 "Liberation Mono", "Courier New", "Courier"]

# Status labels always say the status in words, never by color alone. Plain words only: Tk 8.6 on
# some computers prints symbols like "●" as "\u25cf" when the font lacks them.
BADGES = {
    "free": ("Free", "primary_tint", "primary"),
    "occupied": ("Occupied", "saffron_tint", "saffron_ink"),
    "open": ("Open", "info_tint", "info_ink"),
    "paid": ("Paid", "slate_tint", "slate_ink"),
    "available": ("Available", "primary_tint", "primary"),
    "sold_out": ("Sold out", "chili_tint", "chili"),
}


def _pick(available, candidates, fallback):
    """The first candidate font installed on this computer (names compared case-insensitively)."""
    installed = {family.lower(): family for family in available}
    for family in candidates:
        if family.lower() in installed:
            return installed[family.lower()]
    return fallback


def apply_theme(root):
    """Set up fonts and every ttk style. Call once, right after creating the Tk root."""
    available = tkfont.families(root)
    ui = _pick(available, UI_FAMILIES, tkfont.nametofont("TkDefaultFont").actual("family"))
    mono = _pick(available, MONO_FAMILIES, tkfont.nametofont("TkFixedFont").actual("family"))
    FONTS.update({
        "body": (ui, 10),
        "body_bold": (ui, 10, "bold"),
        "small": (ui, 9),
        "small_bold": (ui, 9, "bold"),
        "nav": (ui, 11),
        "nav_active": (ui, 11, "bold"),
        "brand": (ui, 13, "bold"),
        "title": (ui, 18, "bold"),
        "section": (ui, 12, "bold"),
        "stat": (ui, 20, "bold"),
        "table_number": (ui, 22, "bold"),
        "mono": (mono, 10),
        "mono_bold": (mono, 10, "bold"),
    })
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        tkfont.nametofont(name).configure(family=ui, size=10)
    tkfont.nametofont("TkHeadingFont").configure(family=ui, size=9, weight="bold")
    tkfont.nametofont("TkFixedFont").configure(family=mono, size=10)
    root.configure(background=COLORS["page"])
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["select"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["ink"])

    c = COLORS
    style = ttk.Style(root)
    style.theme_use("clam")  # the most configurable built-in theme, same look on every OS

    style.configure(".", background=c["page"], foreground=c["ink"], font=FONTS["body"],
                    bordercolor=c["border"], lightcolor=c["page"], darkcolor=c["page"],
                    troughcolor=c["page"], focuscolor=c["primary"], selectbackground=c["select"],
                    selectforeground=c["ink"], insertcolor=c["ink"])

    # ---- frames
    style.configure("TFrame", background=c["page"])
    style.configure("Page.TFrame", background=c["page"])
    style.configure("Surface.TFrame", background=c["surface"])
    style.configure("Card.TFrame", background=c["surface"], relief="solid", borderwidth=1,
                    bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"])
    style.configure("TopBar.TFrame", background=c["surface"])
    style.configure("StatusBar.TFrame", background=c["surface"])
    style.configure("Sidebar.TFrame", background=c["sidebar"])
    style.configure("TSeparator", background=c["border"])

    # ---- labels
    style.configure("TLabel", background=c["page"], foreground=c["ink"], font=FONTS["body"])
    style.configure("Title.TLabel", background=c["page"], font=FONTS["title"])
    style.configure("Subtitle.TLabel", background=c["page"], foreground=c["muted"])
    style.configure("Muted.TLabel", background=c["page"], foreground=c["muted"])
    style.configure("Small.TLabel", background=c["page"], foreground=c["muted"], font=FONTS["small"])
    style.configure("Error.TLabel", background=c["page"], foreground=c["chili"])
    style.configure("Surface.TLabel", background=c["surface"])
    style.configure("SurfaceBold.TLabel", background=c["surface"], font=FONTS["body_bold"])
    style.configure("SurfaceMuted.TLabel", background=c["surface"], foreground=c["muted"])
    style.configure("SurfaceSmall.TLabel", background=c["surface"], foreground=c["muted"], font=FONTS["small"])
    style.configure("SurfaceError.TLabel", background=c["surface"], foreground=c["chili"])
    style.configure("SurfaceSuccess.TLabel", background=c["surface"], foreground=c["primary"])
    style.configure("Section.TLabel", background=c["surface"], font=FONTS["section"])
    style.configure("Stat.TLabel", background=c["surface"], font=FONTS["stat"])
    style.configure("Total.TLabel", background=c["surface"], font=FONTS["section"])
    style.configure("TopBar.TLabel", background=c["surface"], foreground=c["muted"])
    style.configure("TopBarName.TLabel", background=c["surface"], font=FONTS["body_bold"])
    style.configure("Status.TLabel", background=c["surface"], foreground=c["ink"])
    style.configure("StatusError.TLabel", background=c["surface"], foreground=c["chili"])
    style.configure("StatusMuted.TLabel", background=c["surface"], foreground=c["subtle"], font=FONTS["small"])
    style.configure("Brand.TLabel", background=c["sidebar"], foreground="#FFFFFF", font=FONTS["brand"])
    style.configure("BrandSub.TLabel", background=c["sidebar"], foreground=c["sidebar_muted"], font=FONTS["small"])
    for kind, (_, bg, fg) in BADGES.items():
        style.configure(f"{kind}.Badge.TLabel", background=c[bg], foreground=c[fg], font=FONTS["small_bold"],
                        padding=(8, 2))
    style.configure("Notice.TLabel", background=c["slate_tint"], foreground=c["slate_ink"], padding=(12, 8))
    style.configure("NoticeError.TLabel", background=c["chili_tint"], foreground=c["chili"], padding=(12, 8))

    # ---- buttons: default (secondary), primary, danger, link, sidebar navigation
    style.configure("TButton", background=c["surface"], foreground=c["ink"], padding=(14, 6),
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                    focuscolor=c["primary"], focusthickness=1, relief="solid", borderwidth=1)
    style.map("TButton",
              background=[("disabled", c["page"]), ("pressed", c["select"]), ("active", c["row_alt"])],
              foreground=[("disabled", c["subtle"])],
              bordercolor=[("focus", c["primary"])],
              lightcolor=[("disabled", c["page"]), ("pressed", c["select"]), ("active", c["row_alt"])],
              darkcolor=[("disabled", c["page"]), ("pressed", c["select"]), ("active", c["row_alt"])])
    for name, base, hover in (("Primary", c["primary"], c["primary_hover"]),
                              ("Danger", c["chili"], c["chili_hover"])):
        style.configure(f"{name}.TButton", background=base, foreground="#FFFFFF", bordercolor=base,
                        lightcolor=base, darkcolor=base, focuscolor="#FFFFFF", font=FONTS["body_bold"])
        style.map(f"{name}.TButton",
                  background=[("disabled", c["page"]), ("pressed", hover), ("active", hover)],
                  foreground=[("disabled", c["subtle"])],
                  bordercolor=[("disabled", c["border"]), ("focus", c["ink"])],
                  lightcolor=[("disabled", c["page"]), ("pressed", hover), ("active", hover)],
                  darkcolor=[("disabled", c["page"]), ("pressed", hover), ("active", hover)])
    style.configure("Link.TButton", background=c["page"], foreground=c["primary"], padding=(0, 0),
                    borderwidth=0, bordercolor=c["page"], lightcolor=c["page"], darkcolor=c["page"],
                    focuscolor=c["primary"])
    style.map("Link.TButton", foreground=[("active", c["primary_hover"])],
              background=[("active", c["page"]), ("pressed", c["page"])])
    for name, bg, fg, font in (("Nav", c["sidebar"], c["sidebar_text"], FONTS["nav"]),
                               ("NavActive", c["sidebar_active"], "#FFFFFF", FONTS["nav_active"])):
        style.configure(f"{name}.TButton", background=bg, foreground=fg, font=font, anchor="w",
                        padding=(16, 9), borderwidth=0, relief="flat", bordercolor=bg, lightcolor=bg,
                        darkcolor=bg, focuscolor=c["saffron"])
        style.map(f"{name}.TButton",
                  background=[("pressed", c["sidebar_active"]), ("active", c["sidebar_hover"] if name == "Nav"
                                                                 else c["sidebar_active"])],
                  foreground=[("active", "#FFFFFF")])
    style.configure("Logout.TButton", padding=(10, 4))

    # ---- inputs
    style.configure("TEntry", fieldbackground=c["surface"], foreground=c["ink"], padding=(8, 5),
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"])
    style.map("TEntry", bordercolor=[("focus", c["primary"])], lightcolor=[("focus", c["primary"])],
              fieldbackground=[("disabled", c["page"]), ("readonly", c["page"])])
    style.configure("TCombobox", fieldbackground=c["surface"], background=c["surface"], foreground=c["ink"],
                    padding=(8, 5), bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                    arrowcolor=c["muted"])
    style.map("TCombobox", bordercolor=[("focus", c["primary"])],
              fieldbackground=[("readonly", c["surface"])], selectbackground=[("readonly", c["surface"])],
              selectforeground=[("readonly", c["ink"])])
    style.configure("TSpinbox", fieldbackground=c["surface"], foreground=c["ink"], padding=(8, 5),
                    bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"], arrowcolor=c["muted"],
                    background=c["surface"])
    style.map("TSpinbox", bordercolor=[("focus", c["primary"])])
    style.configure("Surface.TRadiobutton", background=c["surface"], foreground=c["ink"], focuscolor=c["primary"],
                    indicatorbackground=c["surface"], indicatorforeground=c["primary"], padding=(0, 4))
    style.map("Surface.TRadiobutton", background=[("active", c["surface"])],
              indicatorbackground=[("pressed", c["select"]), ("selected", c["surface"])])
    style.configure("TCheckbutton", background=c["page"], foreground=c["ink"], focuscolor=c["primary"],
                    indicatorbackground=c["surface"], indicatorforeground=c["primary"])
    style.map("TCheckbutton", indicatorbackground=[("pressed", c["select"]), ("selected", c["surface"])],
              background=[("active", c["page"])])

    # ---- data tables
    body = tkfont.Font(root=root, font=FONTS["body"])
    style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["ink"],
                    rowheight=body.metrics("linespace") + 14, bordercolor=c["border"], lightcolor=c["border"],
                    darkcolor=c["border"], borderwidth=1, relief="solid")
    style.map("Treeview", background=[("selected", c["select"])], foreground=[("selected", c["ink"])])
    style.configure("Treeview.Heading", background=c["row_alt"], foreground=c["muted"], font=FONTS["small_bold"],
                    padding=(8, 6), relief="flat", bordercolor=c["border"], lightcolor=c["row_alt"],
                    darkcolor=c["border"])
    style.map("Treeview.Heading", background=[("active", c["slate_tint"])])
    style.configure("Vertical.TScrollbar", background=c["border"], troughcolor=c["surface"], bordercolor=c["surface"],
                    lightcolor=c["border"], darkcolor=c["border"], arrowcolor=c["muted"], gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", c["subtle"])])

    # ---- report tabs
    style.configure("TNotebook", background=c["page"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", background=c["page"], foreground=c["muted"], padding=(16, 7),
                    bordercolor=c["border"], lightcolor=c["page"], darkcolor=c["page"])
    style.map("TNotebook.Tab", background=[("selected", c["surface"])], foreground=[("selected", c["ink"])],
              lightcolor=[("selected", c["surface"])], font=[("selected", FONTS["body_bold"])])
    return style
