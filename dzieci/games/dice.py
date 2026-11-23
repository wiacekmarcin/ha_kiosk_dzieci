"""Rzut kostką: przycisk "Rzuć" uruchamia animację (kostka podskakuje, obraca się
i zmienia ścianki), a po ROLL_SECONDS s pokazuje wylosowaną liczbę 1-6 jako ściankę
z kropkami."""
import math
import random
import time

from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, PopMatrix, PushMatrix, Rotate, RoundedRectangle,
                           Translate)
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

ROLL_SECONDS = 1.0
FRAME = 1 / 30
FACE = (0.98, 0.97, 0.93, 1)
EDGE = (0.30, 0.34, 0.48, 1)
PIP = (0.16, 0.18, 0.25, 1)
PIP_ONE = (0.85, 0.27, 0.27, 1)     # jedynka czerwona, jak na prawdziwej kostce
# położenie kropek na ściance (0..1 od lewego dolnego rogu)
PIPS = {
    1: [(0.5, 0.5)],
    2: [(0.25, 0.75), (0.75, 0.25)],
    3: [(0.25, 0.75), (0.5, 0.5), (0.75, 0.25)],
    4: [(0.25, 0.25), (0.25, 0.75), (0.75, 0.25), (0.75, 0.75)],
    5: [(0.25, 0.25), (0.25, 0.75), (0.5, 0.5), (0.75, 0.25), (0.75, 0.75)],
    6: [(0.25, 0.2), (0.25, 0.5), (0.25, 0.8), (0.75, 0.2), (0.75, 0.5), (0.75, 0.8)],
}


class Dice(Widget):
    value = NumericProperty(6)
    rolling = BooleanProperty(False)
    status = StringProperty("Naciśnij „Rzuć”")
    angle = NumericProperty(0)
    lift = NumericProperty(0)

    def __init__(self, **kwargs):
        self._event = None
        self._t0 = 0.0
        self._last_face = 0.0
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw, value=self.redraw, angle=self.redraw,
                  lift=self.redraw)

    def roll(self):
        if self.rolling:
            return
        self.rolling = True
        self.status = "Rzucam…"
        self._t0 = self._last_face = time.monotonic()
        self._event = Clock.schedule_interval(self._frame, FRAME)

    def _frame(self, _dt):
        t = time.monotonic() - self._t0
        if t >= ROLL_SECONDS:
            self._event.cancel()
            self._event = None
            self.angle, self.lift = 0, 0
            self.value = random.randint(1, 6)
            self.rolling = False
            self.status = f"Wypadło: {self.value}"
            return
        p = t / ROLL_SECONDS
        self.angle = 720 * p * (1 - p * 0.5)                # szybko, potem coraz wolniej
        self.lift = abs(math.sin(p * 3 * math.pi)) * self.height * 0.12 * (1 - p)   # podskoki
        if time.monotonic() - self._last_face > 0.08:       # migające ścianki
            self._last_face = time.monotonic()
            self.value = random.choice([v for v in range(1, 7) if v != self.value])

    def redraw(self, *_):
        s = min(self.width, self.height) * 0.62
        cx, cy = self.center_x, self.center_y
        x, y = cx - s / 2, cy - s / 2
        self.canvas.clear()
        with self.canvas:
            PushMatrix()
            Translate(0, self.lift)
            Rotate(angle=self.angle, origin=(cx, cy))
            Color(0, 0, 0, 0.25)                             # cień
            RoundedRectangle(pos=(x + s * 0.04, y - s * 0.05), size=(s, s), radius=[s * 0.16])
            Color(*EDGE)
            RoundedRectangle(pos=(x - s * 0.02, y - s * 0.02), size=(s * 1.04, s * 1.04),
                             radius=[s * 0.17])
            Color(*FACE)
            RoundedRectangle(pos=(x, y), size=(s, s), radius=[s * 0.16])
            Color(*(PIP_ONE if self.value == 1 else PIP))
            r = s * (0.11 if self.value == 1 else 0.085)
            for px, py in PIPS[self.value]:
                Ellipse(pos=(x + px * s - r, y + py * s - r), size=(2 * r, 2 * r))
            PopMatrix()
