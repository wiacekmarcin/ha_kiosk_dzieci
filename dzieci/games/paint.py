"""Rysowanie palcem, jak w programie Paint: kolory, grubość pędzla, gumka i czyszczenie.

Kartka (PaintCanvas) leży w StencilView, więc kreska nie wychodzi poza jej brzegi.
Kilka palców naraz rysuje kilka kresek (każdy dotyk ma własną linię).
"""
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.properties import ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget

COLORS = [
    (0.10, 0.10, 0.12, 1),   # czarny
    (0.85, 0.20, 0.20, 1),   # czerwony
    (1.00, 0.55, 0.10, 1),   # pomarańczowy
    (1.00, 0.85, 0.10, 1),   # żółty
    (0.25, 0.70, 0.25, 1),   # zielony
    (0.20, 0.50, 0.95, 1),   # niebieski
    (0.55, 0.30, 0.80, 1),   # fioletowy
    (0.95, 0.50, 0.70, 1),   # różowy
    (0.50, 0.32, 0.18, 1),   # brązowy
]
PAPER = (1, 1, 1, 1)
SIZES = [4, 10, 22]
MIN_STEP = 3            # px - bliższe punkty pomijane (palec stoi, ekran drży)
MAX_POINTS = 200        # punktów w jednym odcinku kreski; dłuższa kreska to kilka odcinków


class PaintCanvas(Widget):
    color = ListProperty(list(COLORS[0]))
    brush = NumericProperty(SIZES[1])
    tool = StringProperty("pen")        # pen albo eraser

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._paper, size=self._paper)

    def _paper(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*PAPER)
            Rectangle(pos=self.pos, size=self.size)

    def clear(self):
        self.canvas.clear()

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        color = PAPER if self.tool == "eraser" else tuple(self.color)
        width = self.brush * (2.5 if self.tool == "eraser" else 1)
        with self.canvas:
            Color(*color)
            d = width * 2
            Ellipse(pos=(touch.x - width, touch.y - width), size=(d, d))   # kropka przy stuknięciu
        # kreska powstaje dopiero przy ruchu palca, z punktów oddalonych o MIN_STEP px
        touch.ud["paint"] = {"line": None, "last": touch.pos, "color": color, "width": width}
        touch.grab(self)
        return True

    def on_touch_move(self, touch):
        stroke = touch.ud.get("paint")
        if touch.grab_current is not self or stroke is None:
            return super().on_touch_move(touch)
        lx, ly = stroke["last"]
        if abs(touch.x - lx) < MIN_STEP and abs(touch.y - ly) < MIN_STEP:
            return True                 # palec stoi - bez powtarzania tych samych punktów
        line = stroke["line"]
        if line is None or len(line.points) >= MAX_POINTS * 2:
            # nowy odcinek od ostatniego punktu: krótkie linie zamiast jednej bardzo długiej
            with self.canvas:
                Color(*stroke["color"])
                stroke["line"] = Line(points=[lx, ly, touch.x, touch.y], width=stroke["width"],
                                      cap="round", joint="round")
        else:
            line.points += [touch.x, touch.y]
        stroke["last"] = touch.pos
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)


# Przyciski palety: wygląd w ekran.kv. Właściwość paint ma rebind=True, żeby podświetlenie
# śledziło kolor i pędzel kartki przypisanej już po zbudowaniu przycisku.
class Swatch(ButtonBehavior, Widget):
    rgba = ListProperty([0, 0, 0, 1])
    paint = ObjectProperty(None, rebind=True, allownone=True)

    def on_release(self):
        self.paint.color = list(self.rgba)
        self.paint.tool = "pen"


class BrushButton(ButtonBehavior, Widget):
    brush = NumericProperty(SIZES[1])
    paint = ObjectProperty(None, rebind=True, allownone=True)

    def on_release(self):
        self.paint.brush = self.brush
