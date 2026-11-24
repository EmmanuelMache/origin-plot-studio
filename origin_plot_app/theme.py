"""
theme.py - the design system of Origin Plot Studio ("Scientific Workbench" look).

One place for every colour, font size, radius and spacing of the window. `install(root)` applies it to
all ttk widgets and returns a Theme object the window code uses (px, fonts, card / pill / bubble styles).

Tkinter has no rounded corners of its own. Cards, buttons, fields, pills and chat bubbles are therefore
drawn as small anti-aliased pictures (made here with Pillow, which matplotlib already installs) that ttk
stretches from their middle ("9-slice"). Without Pillow the same styles fall back to flat, square ones.
Tk cannot draw shadows or letter-spacing: cards rely on their 1 px border, kickers on size and weight.
"""
import base64, io

THEME = {
    # surfaces
    "canvas": "#F4F5F7", "card": "#FFFFFF", "subtle": "#F8FAFC", "preview": "#FAFBFC",
    # lines
    "border": "#E2E8F0", "border_strong": "#CBD5E1", "selected": "#D97742",
    # text
    "text": "#1E293B", "text2": "#475569", "meta": "#64748B", "muted": "#94A3B8", "button_text": "#334155",
    # brand
    "accent": "#C86D3B", "accent_hover": "#B35C2E", "accent_pressed": "#9A4D24", "accent_off": "#E6C3AE", "on_accent": "#FFFFFF",
    # status
    "ok_bg": "#ECFDF5", "ok_border": "#A7F3D0", "ok_text": "#059669", "ok_dot": "#10B981",
    "warn_bg": "#FFFBEB", "warn_border": "#FDE68A", "warn_text": "#B45309", "warn_dot": "#F59E0B",
    "bad_bg": "#FEF2F2", "bad_border": "#FECACA", "bad_text": "#B91C1C", "bad_dot": "#EF4444",
    "idle_bg": "#F1F5F9", "idle_border": "#E2E8F0", "idle_text": "#64748B", "idle_dot": "#94A3B8",
    # chat
    "you_bg": "#FDF4ED", "you_border": "#F3E1D3", "ai_bg": "#F8FAFC", "ai_border": "#E2E8F0",
    # the dark mode switcher
    "switch": "#1F2937", "switch_text": "#E5E7EB", "switch_hover": "#374151",
    # selection in lists and text
    "select": "#FBE9DC",
    # geometry (pixels at 100 % display scaling)
    "r_card": 12, "r_control": 8, "r_pill": 999, "margin": 20, "gap": 16, "pad_card": 20,
    # type (pixels at 100 % display scaling)
    "fonts": ("Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans", "Arial"),
    "size_kicker": 10, "size_title": 21, "size_heading": 15, "size_body": 13, "size_meta": 12,
}


class Theme:
    def __init__(self, root, ui=1.0):
        import tkinter.font as tkfont
        from tkinter import ttk
        self.root, self.ui, self.c, self._img, self.rounded = root, float(ui), THEME, {}, False
        T = THEME
        try: fams = set(tkfont.families()); self.family = next((f for f in T["fonts"] if f in fams), "Helvetica")
        except Exception: self.family = "Segoe UI"
        f = lambda size, weight="normal": (self.family, -self.px(size), weight)          # negative = pixels: the sizes of the design, on every screen
        self.f_body, self.f_bold, self.f_meta, self.f_meta_bold = f(T["size_body"]), f(T["size_body"], "bold"), f(T["size_meta"]), f(T["size_meta"], "bold")
        self.f_kicker, self.f_title, self.f_heading = f(T["size_kicker"], "bold"), f(T["size_title"], "bold"), f(T["size_heading"], "bold")
        for n_ in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
            try: tkfont.nametofont(n_).configure(family=self.family, size=-self.px(T["size_body"]))
            except Exception: pass
        try: self.linespace = tkfont.Font(font=self.f_body).metrics("linespace")
        except Exception: self.linespace = self.px(18)
        self.style = ttk.Style(root)
        try: self.style.theme_use("clam")
        except Exception: pass
        try:
            from PIL import Image, ImageDraw            # noqa: F401
            self.rounded = True
        except Exception: self.rounded = False
        self._styles()

    # ------------------------------------------------------------------ sizes
    def px(self, v): return int(round(v * self.ui))

    # ------------------------------------------------------------------ pictures
    def image(self, key, fill, border=None, radius=8, outside=None, width=1, size=None, mark=None, gap=0):
        """A rounded rectangle as a Tk picture. `outside` is the colour around the corners (the surface it lies on).
        mark="check": a white tick (for a ticked box); mark="dash": a dashed outline (for the drop zone)."""
        if key in self._img: return self._img[key]
        import tkinter as tk
        from PIL import Image, ImageDraw
        k = 4; r = self.px(radius); w_ = max(1, self.px(width)) if border else 0
        # ttk fills a surface by repeating the middle of the picture. A middle of a few pixels meant tens of thousands of
        # tiny copies for one card, which is what made the window paint slowly. A middle of 160 px needs a handful.
        n = size if size else (2 * min(r, self.px(16)) + 160); n = max(n, 2 * w_ + 4); r = min(r, n // 2)
        im = Image.new("RGBA", (n * k, n * k), outside or (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        if border and mark != "dash":
            d.rounded_rectangle((0, 0, n * k - 1, n * k - 1), radius=r * k, fill=border)
            d.rounded_rectangle((w_ * k, w_ * k, n * k - 1 - w_ * k, n * k - 1 - w_ * k), radius=max(0, (r - w_) * k), fill=fill)
        else: d.rounded_rectangle((0, 0, n * k - 1, n * k - 1), radius=r * k, fill=fill)
        if mark == "cross":
            q = n * k; w2 = max(2, int(q * 0.12)); d.line([(q * 0.30, q * 0.30), (q * 0.70, q * 0.70)], fill="#FFFFFF", width=w2); d.line([(q * 0.70, q * 0.30), (q * 0.30, q * 0.70)], fill="#FFFFFF", width=w2)
        if mark == "check":
            q = n * k; d.line([(q * 0.24, q * 0.52), (q * 0.43, q * 0.70), (q * 0.77, q * 0.31)], fill="#FFFFFF", width=max(2, int(q * 0.12)), joint="curve")
        im = im.resize((n, n), Image.LANCZOS)
        if gap:                                             # room to the right of a tick box, before its text
            wide = Image.new("RGBA", (n + gap, n), outside or (0, 0, 0, 0)); wide.paste(im, (0, 0)); im = wide
        if outside and not gap: im = im.convert("RGB")       # no see-through pixels where the surface around is known: quicker to paint
        b = io.BytesIO(); im.save(b, "PNG")
        ph = tk.PhotoImage(master=self.root, data=base64.b64encode(b.getvalue())); self._img[key] = ph; return ph

    def _element(self, name, key, radius, fill, border, outside, states=(), sticky="nsew", pad=None):
        """One stretchable rounded surface as a ttk element; `states` = ((state, fill, border), ...)."""
        r = min(self.px(radius), self.px(16)); cut = r + self.px(2)
        base = self.image(key, fill, border, radius, outside)
        extra = [(st, self.image(f"{key}-{st}", f_, b_, radius, outside)) for st, f_, b_ in states]
        try: self.style.element_create(name, "image", base, *extra, border=cut, sticky=sticky, padding=pad if pad is not None else 0, width=2 * cut + self.px(4), height=2 * cut + self.px(4))      # the smallest size is the corners, not the size of the picture
        except Exception: pass                              # already made (a second window)

    def icon(self, ok=True):
        """A small round mark for a finished step: a green tick, or a red cross for a step that was not done."""
        if not self.rounded: return None
        n = self.px(16)
        return self.image("ico-ok" if ok else "ico-bad", self.c["ok_dot"] if ok else self.c["bad_dot"], None, 999, None, size=n, mark="check" if ok else "cross")

    # ------------------------------------------------------------------ styles
    def surface(self, style, fill, border, radius, outside, padding=0):
        """A frame style drawn as a rounded surface: cards, sub-cards, bubbles, fields, the switcher."""
        s = self.style
        if self.rounded:
            el = style.replace(".", "_") + ".bg"; self._element(el, "sf-" + style, radius, fill, border, outside)
            s.layout(style, [(el, {"sticky": "nsew"})]); s.configure(style, background=outside, padding=padding, borderwidth=0)
        else: s.configure(style, background=fill, bordercolor=border or fill, relief="solid", borderwidth=1 if border else 0, padding=padding)
        return style

    def pill(self, style, kind, outside):
        """A status pill as a label style, e.g. pill("Ok.Pill.TLabel", "ok", white)."""
        s, c = self.style, self.c
        if self.rounded:
            el = style.replace(".", "_") + ".bg"; self._element(el, "pill-" + style, 11, c[kind + "_bg"], c[kind + "_border"], outside)       # 11 px = half the height of the pill: a full pill
            s.layout(style, [(el, {"sticky": "nsew", "children": [("Label.padding", {"sticky": "nsew", "children": [("Label.label", {"sticky": "nsew"})]})]})])
        s.configure(style, background=outside if self.rounded else c[kind + "_bg"], foreground=c[kind + "_text"], font=self.f_meta_bold, padding=(self.px(10), self.px(3)))
        return style

    def button(self, style, fill, border, text, hover, pressed, outside, off_fill=None, off_text=None, font=None, padding=None, radius=None, hover_border=None, selected=None):
        s, c = self.style, self.c; radius = c["r_control"] if radius is None else radius
        pad = padding or (self.px(14), self.px(7))
        if self.rounded:
            el = style.replace(".", "_") + ".bg"
            states = [("disabled", off_fill or fill, border if not off_fill else off_fill), ("pressed", pressed, hover_border or (border if border != fill else pressed)), ("active", hover, hover_border or (border if border != fill else hover))]
            if selected: states.insert(0, ("selected", selected[0], selected[0]))
            self._element(el, "btn-" + style, radius, fill, border, outside, states)
            s.layout(style, [(el, {"sticky": "nsew", "children": [("Button.focus", {"sticky": "nsew", "children": [("Button.padding", {"sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})]})])
            s.configure(style, background=outside, foreground=text, font=font or self.f_bold, padding=pad, anchor="center", borderwidth=0, focusthickness=0, focuscolor=outside)
            s.map(style, foreground=[("disabled", off_text or c["muted"])] + ([("selected", selected[1])] if selected else []), background=[("active", outside)])
        else:
            s.configure(style, background=fill, foreground=text, font=font or self.f_bold, padding=pad, bordercolor=border, lightcolor=fill, darkcolor=fill, relief="flat", anchor="center")
            s.map(style, background=[("disabled", off_fill or fill), ("pressed", pressed), ("active", hover)], foreground=[("disabled", off_text or c["muted"])], lightcolor=[("active", hover)], darkcolor=[("active", hover)])
        return style

    def _styles(self):
        s, c, px = self.style, self.c, self.px
        W, BG = c["card"], c["canvas"]
        # Nearly everything lives on a white card, so white is the default surface; the window itself uses the Canvas.* styles.
        s.configure(".", background=W, foreground=c["text"], font=self.f_body, bordercolor=c["border"], focuscolor=c["accent"], troughcolor=c["idle_bg"],
                    selectbackground=c["select"], selectforeground=c["text"], insertcolor=c["text"])
        for n_ in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe", "TLabelframe.Label"): s.configure(n_, background=W, foreground=c["text"])
        s.configure("Canvas.TFrame", background=BG); s.configure("Canvas.TLabel", background=BG)
        s.configure("Subtle.TFrame", background=c["subtle"])
        # text
        s.configure("Kicker.TLabel", font=self.f_kicker, foreground=c["muted"]); s.configure("Canvas.Kicker.TLabel", font=self.f_kicker, foreground=c["accent"], background=BG)
        s.configure("Title.TLabel", font=self.f_title, foreground=c["text"]); s.configure("Canvas.Title.TLabel", font=self.f_title, foreground=c["text"], background=BG)
        s.configure("Step.TLabel", font=self.f_heading, foreground=c["text"]); s.configure("StepNo.TLabel", font=self.f_heading, foreground=c["accent"])
        s.configure("Soft.TLabel", font=self.f_meta, foreground=c["meta"]); s.configure("Muted.TLabel", font=self.f_meta, foreground=c["muted"])
        s.configure("Canvas.Soft.TLabel", font=self.f_meta, foreground=c["meta"], background=BG); s.configure("Status.TLabel", foreground=c["text2"]); s.configure("Canvas.Status.TLabel", foreground=c["text2"], background=BG)
        s.configure("Note.TLabel", font=self.f_bold, foreground=c["text"]); s.configure("Name.TLabel", font=self.f_bold, foreground=c["text"])
        # surfaces
        self.surface("Card.TFrame", W, c["border"], c["r_card"], BG)
        self.surface("Sub.TFrame", W, c["border"], c["r_control"], W); self.surface("SubSel.TFrame", W, c["selected"], c["r_control"], W)
        self.surface("Soft.TFrame", c["subtle"], c["border"], c["r_control"], W); self.surface("Preview.TFrame", c["preview"], c["border"], c["r_control"], W)
        self.surface("Drop.TFrame", c["subtle"], c["border_strong"], c["r_card"], W)
        self.surface("BubbleAI.TFrame", c["ai_bg"], c["ai_border"], c["r_card"], W); self.surface("BubbleYou.TFrame", c["you_bg"], c["you_border"], c["r_card"], W)
        self.surface("Field.TFrame", W, c["border_strong"], c["r_control"], W); self.surface("FieldFocus.TFrame", W, c["accent"], c["r_control"], W)
        self.surface("Switch.TFrame", c["switch"], None, 14, BG)
        # pills
        for kind in ("ok", "warn", "bad", "idle"):
            self.pill(kind.capitalize() + ".Pill.TLabel", kind, W); self.pill("Canvas." + kind.capitalize() + ".Pill.TLabel", kind, BG)
        # buttons
        sec = dict(fill=W, border=c["border_strong"], text=c["button_text"], hover=c["subtle"], pressed=c["idle_bg"])
        acc = dict(fill=c["accent"], border=c["accent"], text=c["on_accent"], hover=c["accent_hover"], pressed=c["accent_pressed"], off_fill=c["accent_off"], off_text="#FFFFFF")
        self.button("TButton", outside=W, **sec); self.button("Canvas.TButton", outside=BG, **sec)
        self.button("Accent.TButton", outside=W, **acc); self.button("Canvas.Accent.TButton", outside=BG, **acc)
        self.button("Big.TButton", outside=W, padding=(px(22), px(10)), **acc)
        self.button("Small.TButton", outside=W, font=self.f_meta, padding=(px(10), px(4)), **sec)
        self.button("Ghost.TButton", outside=W, fill=W, border=W, text=c["text2"], hover=c["idle_bg"], pressed=c["border"], font=self.f_meta_bold, padding=(px(8), px(5)))
        self.button("Section.TButton", outside=W, fill=W, border=W, text=c["text"], hover=W, pressed=W, font=self.f_heading, padding=(0, px(2)))
        s.configure("Section.TButton", anchor="w"); s.map("Section.TButton", foreground=[("active", c["accent"])])
        self.button("Seg.TButton", outside=c["switch"], fill=c["switch"], border=c["switch"], text=c["switch_text"], hover=c["switch_hover"], pressed=c["switch_hover"], font=self.f_meta_bold, padding=(px(11), px(7)), radius=10)
        self.button("SegOn.TButton", outside=c["switch"], fill=W, border=W, text=c["text"], hover=W, pressed=W, font=self.f_meta_bold, padding=(px(11), px(7)), radius=10)
        s.configure("TMenubutton", background=W, foreground=c["button_text"], font=self.f_bold, padding=(px(14), px(7)), arrowcolor=c["meta"], bordercolor=c["border_strong"], lightcolor=W, darkcolor=W, relief="flat")
        s.map("TMenubutton", background=[("active", c["subtle"])], lightcolor=[("active", c["subtle"])], darkcolor=[("active", c["subtle"])])
        s.configure("Small.TMenubutton", font=self.f_meta, padding=(px(10), px(4)))
        # fields
        if self.rounded:
            for nm, key in (("Entry", "ent"), ("Combobox", "cmb")):
                self._element(f"R{nm}.field", "fld-" + key, c["r_control"], W, c["border_strong"], W,
                              (("disabled", c["subtle"], c["border"]), ("focus", W, c["accent"])), pad=px(2))          # the arrow and the text stay inside the rounded border
            s.layout("TEntry", [("REntry.field", {"sticky": "nsew", "children": [("Entry.padding", {"sticky": "nsew", "children": [("Entry.textarea", {"sticky": "nsew"})]})]})])
            s.layout("TCombobox", [("RCombobox.field", {"sticky": "nsew", "children": [("Combobox.downarrow", {"side": "right", "sticky": "ns"}),
                                                                                    ("Combobox.padding", {"sticky": "nsew", "children": [("Combobox.textarea", {"sticky": "nsew"})]})]})])
        s.configure("TEntry", fieldbackground=W, foreground=c["text"], padding=(px(7), px(4)), insertcolor=c["text"], bordercolor=c["border_strong"], lightcolor=W, darkcolor=W, borderwidth=0 if self.rounded else 1)
        s.map("TEntry", foreground=[("disabled", c["muted"])], bordercolor=[("focus", c["accent"])])
        s.configure("TCombobox", fieldbackground=W, background=W, foreground=c["text"], padding=(px(7), px(4)), arrowcolor=c["meta"], arrowsize=px(13), bordercolor=W if self.rounded else c["border_strong"], lightcolor=W, darkcolor=W, borderwidth=0 if self.rounded else 1)
        s.map("TCombobox", fieldbackground=[("readonly", W), ("disabled", c["subtle"])], foreground=[("readonly", c["text"]), ("disabled", c["muted"])], background=[("active", W), ("readonly", W)],
              selectbackground=[("readonly", W), ("!focus", W)], selectforeground=[("readonly", c["text"]), ("!focus", c["text"])], arrowcolor=[("active", c["accent"])])
        r = self.root
        for opt, val in (("*TCombobox*Listbox.font", self.f_body), ("*TCombobox*Listbox.background", W), ("*TCombobox*Listbox.foreground", c["text"]), ("*TCombobox*Listbox.selectBackground", c["select"]),
                         ("*TCombobox*Listbox.selectForeground", c["text"]), ("*TCombobox*Listbox.borderWidth", 0), ("*Menu.background", W), ("*Menu.foreground", c["text"]), ("*Menu.activeBackground", c["idle_bg"]),
                         ("*Menu.activeForeground", c["text"]), ("*Menu.relief", "flat"), ("*Menu.activeBorderWidth", 0), ("*Menu.borderWidth", 1)):
            try: r.option_add(opt, val)
            except Exception: pass
        # tick boxes
        if self.rounded:
            n = px(16)
            g = px(8); off = self.image("chk-off", W, c["border_strong"], 4, None, size=n, gap=g); on = self.image("chk-on", c["accent"], c["accent"], 4, None, size=n, mark="check", gap=g)
            dis = self.image("chk-dis", c["subtle"], c["border"], 4, None, size=n, gap=g)
            try: s.element_create("RCheck.indicator", "image", off, ("disabled", dis), ("selected", on), sticky="w", padding=(0, 0, px(8), 0))
            except Exception: pass
            s.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nsew", "children": [("RCheck.indicator", {"side": "left", "sticky": ""}), ("Checkbutton.label", {"side": "left", "sticky": "nsew"})]})])
        s.configure("TCheckbutton", padding=(0, px(3)), indicatorbackground=W, indicatorforeground=c["accent"], focuscolor=W); s.map("TCheckbutton", background=[("active", W)], foreground=[("disabled", c["muted"])])
        # boxes, lines, scroll bars, progress
        s.configure("TLabelframe", bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"], relief="solid", borderwidth=1, background=W)
        s.configure("TLabelframe.Label", font=self.f_kicker, foreground=c["muted"], background=W)
        s.configure("TSeparator", background=c["border"])
        for o in ("Vertical", "Horizontal"):                 # thin, without arrows
            try: s.layout(f"{o}.TScrollbar", [(f"{o}.Scrollbar.trough", {"sticky": "ns" if o == "Vertical" else "we", "children": [(f"{o}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            except Exception: pass
        s.configure("TScrollbar", background=c["border_strong"], troughcolor=W, bordercolor=W, lightcolor=c["border_strong"], darkcolor=c["border_strong"], arrowsize=px(9), gripcount=0, relief="flat")
        s.map("TScrollbar", background=[("active", c["muted"]), ("pressed", c["meta"])], lightcolor=[("active", c["muted"])], darkcolor=[("active", c["muted"])])
        s.configure("TPanedwindow", background=BG); s.configure("Sash", sashthickness=self.c["gap"] and px(self.c["gap"]), gripcount=0, background=BG, lightcolor=BG, bordercolor=BG)
        s.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["border"], bordercolor=c["border"], lightcolor=c["accent"], darkcolor=c["accent"], thickness=px(4))
        # the views are pages of a notebook whose tabs are hidden: the dark switcher at the bottom chooses the page
        try: s.layout("Hidden.TNotebook.Tab", []); s.layout("Hidden.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        except Exception: pass
        s.configure("Hidden.TNotebook", background=BG, borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG, tabmargins=0, padding=0)
        s.configure("TNotebook", background=W, bordercolor=c["border"]); s.configure("TNotebook.Tab", padding=(px(14), px(7)), font=self.f_bold, background=c["subtle"], foreground=c["meta"])
        s.map("TNotebook.Tab", background=[("selected", W)], foreground=[("selected", c["text"])])


def enable_dpi_awareness():
    """Windows only: ask for sharp (not stretched) drawing on high-resolution screens. Call before the window is made."""
    try:
        import ctypes
        try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception: ctypes.windll.user32.SetProcessDPIAware()
        return True
    except Exception: return False


def install(root, ui=None):
    """Apply the theme to a Tk window. `ui` = display scaling (1.0 = 100 %); measured from the screen when not given."""
    if ui is None:
        try: ui = max(1.0, min(3.0, float(root.winfo_fpixels("1i")) / 96.0))
        except Exception: ui = 1.0
    try: root.tk.call("tk", "scaling", ui * 96.0 / 72.0)
    except Exception: pass
    try: root.configure(bg=THEME["canvas"])
    except Exception: pass
    return Theme(root, ui)
