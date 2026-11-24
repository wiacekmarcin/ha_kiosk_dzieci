"""Kolorowanki: lista obrazków z czarnym konturem (motywy Pokemon, Minecraft, Spidey),
po wybraniu - obrazek, paleta kolorów i wypełnianie dotkniętego obszaru wybranym kolorem.

Obrazki: pages/*.png z katalog.json (własne rysunki w klimacie motywów, tools/make_coloring.py)
oraz własne pliki PNG/JPG wgrane na tablet do <pliki aplikacji>/kolorowanki/<motyw>/
(np. adb push kot.png /sdcard/Android/data/<pakiet>/files/kolorowanki/inne/). Kontur to
ciemne piksele (czarne linie na jasnym tle); wypełnianie zatrzymuje się na nich.

Wypełnianie: algorytm wierszami (scanline) na bajtach - szukanie granic odcinka i
zamalowanie całego odcinka to operacje bytearray.find/rfind i przypisanie wycinka, więc
działa szybko także na starym tablecie. Pokolorowane obrazki pamiętane do zamknięcia
aplikacji; Cofnij - do 10 kroków wstecz.
"""
import json
from pathlib import Path

from kivy.app import App
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.graphics.texture import Texture
from kivy.logger import Logger
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.utils import platform

HERE = Path(__file__).resolve().parent
PAGES = HERE / "pages"
THEMES = (("pokemon", "Pokemon"), ("minecraft", "Minecraft"), ("spidey", "Spidey"),
          ("inne", "Moje"))
DARK = 150                              # jasność poniżej - kontur
UNDO = 10
COLORS = [
    (0.90, 0.16, 0.16, 1), (0.98, 0.50, 0.10, 1), (1.00, 0.85, 0.10, 1), (0.55, 0.80, 0.20, 1),
    (0.10, 0.60, 0.25, 1), (0.30, 0.75, 0.95, 1), (0.15, 0.35, 0.85, 1), (0.45, 0.25, 0.70, 1),
    (0.95, 0.50, 0.75, 1), (0.60, 0.40, 0.20, 1), (0.98, 0.85, 0.70, 1), (0.55, 0.55, 0.58, 1),
    (0.15, 0.15, 0.18, 1), (1.00, 1.00, 1.00, 1),
]
# jasność piksela -> 1 (kontur) albo 0 (do malowania)
_MASK = bytes(1 if v < DARK else 0 for v in range(256))
_STATE = {}                             # ścieżka obrazka -> pokolorowane piksele (do zamknięcia)
CANVAS = None                           # widżet kolorowania (dla listy i przycisków)


def user_dir() -> Path | None:
    if platform == "android":
        try:
            from jnius import autoclass
            ext = autoclass("org.kivy.android.PythonActivity").mActivity.getExternalFilesDir(None)
            return Path(ext.getAbsolutePath()) / "kolorowanki" if ext is not None else None
        except Exception:               # noqa: BLE001
            return None
    return HERE.parent.parent / "kolorowanki"


def load_pages() -> list:
    """[{theme, title, path}] - wbudowane z katalogu, potem własne pliki z folderu."""
    pages = []
    try:
        for p in json.loads((PAGES / "katalog.json").read_text(encoding="utf-8")):
            pages.append({"theme": p["theme"], "title": p["title"], "path": str(PAGES / p["file"])})
    except (OSError, ValueError) as e:
        Logger.warning(f"Kolorowanki: katalog: {e}")
    folder = user_dir()
    if folder is not None and folder.is_dir():
        for f in sorted(folder.rglob("*")):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                theme = f.parent.name if f.parent != folder else "inne"
                if theme not in dict(THEMES):
                    theme = "inne"
                pages.append({"theme": theme, "title": f.stem.replace("_", " "), "path": str(f)})
    return pages


def fill(rgba: bytearray, mask: bytes, w: int, h: int, x: int, y: int, color: bytes) -> bool:
    """Wypełnia obszar wokół (x, y) ograniczony konturem; False, gdy to kontur."""
    if not (0 <= x < w and 0 <= y < h) or mask[y * w + x]:
        return False
    blocked = bytearray(mask)
    stack = [(x, y)]
    while stack:
        x, y = stack.pop()
        row = y * w
        if blocked[row + x]:
            continue
        left = blocked.rfind(1, row, row + x)
        left = row if left < 0 else left + 1
        right = blocked.find(1, row + x, row + w)
        right = row + w if right < 0 else right
        n = right - left
        blocked[left:right] = b"\x01" * n
        rgba[left * 4:right * 4] = color * n
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                a, b = left - row + ny * w, right - row + ny * w
                i = a
                while i < b:
                    i = blocked.find(0, i, b)
                    if i < 0:
                        break
                    stack.append((i - ny * w, ny))
                    i = blocked.find(1, i, b)
                    if i < 0:
                        break
    return True


class ColoringCanvas(Widget):
    """Obrazek do kolorowania dopasowany do widżetu; dotknięcie wypełnia obszar kolorem."""
    color = ListProperty(COLORS[0])
    title = StringProperty("")
    index = NumericProperty(-1)
    pages = ListProperty([])

    def __init__(self, **kwargs):
        global CANVAS
        self.path, self.w, self.h, self.flipped = "", 0, 0, False
        self.rgba, self.orig, self.mask = bytearray(), b"", b""
        self.history = []
        self.texture = None
        super().__init__(**kwargs)
        CANVAS = self
        self.bind(pos=self.redraw, size=self.redraw)

    # --- obrazek ----------------------------------------------------------------------
    def open(self, index: int):
        if not 0 <= index < len(self.pages):
            return
        if self.path:
            _STATE[self.path] = bytes(self.rgba)
        page = self.pages[index]
        try:
            tex = CoreImage(page["path"]).texture
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Kolorowanki: {page['path']}: {e}")
            return
        self.index, self.title, self.path = index, page["title"], page["path"]
        self.w, self.h = tex.size
        self.orig = bytes(tex.pixels)
        # kontur: piksel ciemny we wszystkich trzech kanałach (AND na dużych liczbach - szybko)
        n = self.w * self.h
        r, g, b = (int.from_bytes(self.orig[i::4].translate(_MASK), "big") for i in range(3))
        self.mask = (r & g & b).to_bytes(n, "big")
        self.rgba = bytearray(_STATE.get(self.path, self.orig))
        self.history = []
        # obrazek z pliku ma wiersze od góry (tekstura odwrócona) - nowa tak samo
        self.flipped = tex.tex_coords[1] != 0
        self.texture = Texture.create(size=(self.w, self.h), colorfmt="rgba")
        if self.flipped:
            self.texture.flip_vertical()
        self._upload()

    def step(self, delta: int):
        """Poprzednia / następna kolorowanka z tego samego motywu."""
        if self.index < 0:
            return
        theme = self.pages[self.index]["theme"]
        same = [i for i, p in enumerate(self.pages) if p["theme"] == theme]
        pos = same.index(self.index)
        self.open(same[(pos + delta) % len(same)])

    def _upload(self):
        self.texture.blit_buffer(bytes(self.rgba), colorfmt="rgba", bufferfmt="ubyte")
        self.redraw()

    # --- malowanie --------------------------------------------------------------------
    def box(self):
        """(x, y, skala) - obrazek wyśrodkowany i dopasowany do widżetu."""
        if not self.w:
            return self.x, self.y, 1
        k = min(self.width / self.w, self.height / self.h)
        return self.center_x - self.w * k / 2, self.center_y - self.h * k / 2, k

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or not self.w:
            return super().on_touch_down(touch)
        x0, y0, k = self.box()
        px, py = int((touch.x - x0) / k), int((touch.y - y0) / k)
        self.paint(px, self.h - 1 - py if self.flipped else py)
        return True

    def paint(self, px, py):
        """Wypełnienie w punkcie bufora obrazka (piksele, wiersz w kolejności bufora)."""
        color = bytes(int(c * 255) for c in self.color[:3]) + b"\xff"
        before = bytes(self.rgba)
        if fill(self.rgba, self.mask, self.w, self.h, px, py, color) and bytes(self.rgba) != before:
            self.history = (self.history + [before])[-UNDO:]
            self._upload()

    def undo(self):
        if self.history:
            self.rgba = bytearray(self.history.pop())
            self._upload()

    def clear(self):
        if self.w and bytes(self.rgba) != self.orig:
            self.history = (self.history + [bytes(self.rgba)])[-UNDO:]
            self.rgba = bytearray(self.orig)
            self._upload()

    def redraw(self, *_):
        self.canvas.clear()
        if self.texture is None:
            return
        x0, y0, k = self.box()
        with self.canvas:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=(x0 - 8, y0 - 8), size=(self.w * k + 16, self.h * k + 16), radius=[14])
            Rectangle(texture=self.texture, pos=(x0, y0), size=(self.w * k, self.h * k))


class ColorSwatch(ButtonBehavior, Widget):
    """Kolor w palecie (wybrany ma żółtą obwódkę)."""
    rgba = ListProperty([1, 1, 1, 1])
    target = ObjectProperty(None, allownone=True, rebind=True)

    def on_release(self):
        if self.target is not None:
            self.target.color = list(self.rgba)


class PageTile(ButtonBehavior, BoxLayout):
    """Miniatura kolorowanki na liście."""
    index = NumericProperty(0)
    image = StringProperty("")
    title = StringProperty("")

    def on_release(self):
        open_page(self.index)


class PageList(GridLayout):
    """Siatka miniatur wybranego motywu."""
    theme = StringProperty("pokemon")

    def on_theme(self, *_):
        self.refresh()

    def refresh(self):
        canvas = CANVAS
        if canvas is None:
            return
        canvas.pages = load_pages()
        self.clear_widgets()
        for i, p in enumerate(canvas.pages):
            if p["theme"] == self.theme:
                self.add_widget(PageTile(index=i, image=p["path"], title=p["title"]))


def open_page(index: int):
    if CANVAS is not None:
        CANVAS.open(index)
        App.get_running_app().nav("colorpage")
