"""Trzy zegary ekranu startowego: pory dnia, analogowy i pory roku.

Kąty: stopnie od godziny 12 zgodnie z ruchem wskazówek (jak Ellipse/Line w Kivy).
"""
import math
import os
import time
from datetime import datetime
from pathlib import Path

from kivy.clock import Clock
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix, Rotate, Scale,
                           Translate, Triangle)
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from dzieci import plan

ICONS = Path(__file__).resolve().parents[1] / "assets" / "icons"
MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)

FACE = (0.98, 0.97, 0.93, 1)
INK = (0.16, 0.18, 0.25, 1)
HAND = (0.85, 0.27, 0.27, 1)
RIM = (0.30, 0.34, 0.48, 1)
HIGHLIGHT = (1.0, 0.62, 0.18, 1)

DAY_COLORS = {
    "sen": (0.74, 0.78, 0.95, 1),
    "mycie": (1.0, 0.93, 0.68, 1),
    "sniadanie": (1.0, 0.88, 0.62, 1),
    "zeby": (0.80, 0.93, 0.98, 1),
    "ubieranie": (1.0, 0.93, 0.68, 1),
    "przedszkole": (0.78, 0.92, 0.74, 1),
    "czas_wolny": (1.0, 0.82, 0.64, 1),
    "zabawa": (0.78, 0.92, 0.74, 1),
    "obiad": (1.0, 0.88, 0.62, 1),
    "kolacja": (0.92, 0.82, 0.96, 1),
    "kapiel": (0.80, 0.93, 0.98, 1),
    "ksiazka": (0.86, 0.82, 0.97, 1),
}
SEASON_COLORS = {
    "wiosna": (0.80, 0.93, 0.70, 1),
    "lato": (1.0, 0.90, 0.55, 1),
    "jesien": (1.0, 0.77, 0.56, 1),
    "zima": (0.80, 0.90, 1.0, 1),
}


def polar(cx, cy, r, angle):
    a = math.radians(angle)
    return cx + r * math.sin(a), cy + r * math.cos(a)


def draw_hand(canvas_group, cx, cy, angle, length, width, color, tail=0.0, tip=False):
    """Wskazówka jako linia (opcjonalnie z grotem) - instrukcje dodawane do canvas_group."""
    x0, y0 = polar(cx, cy, -tail, angle)
    x1, y1 = polar(cx, cy, length, angle)
    canvas_group.add(Color(*color))
    canvas_group.add(Line(points=[x0, y0, x1, y1], width=width, cap="round"))
    if tip:
        h = width * 2.4
        bx, by = polar(cx, cy, length - h * 0.2, angle)
        lx, ly = polar(bx, by, h * 0.9, angle - 90)
        rx, ry = polar(bx, by, h * 0.9, angle + 90)
        px, py = polar(cx, cy, length + h * 1.4, angle)
        canvas_group.add(Triangle(points=[lx, ly, rx, ry, px, py]))


class ClockBase(Widget):
    caption = StringProperty("")
    radius = NumericProperty(10)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._layout, size=self._layout)
        self._ticker = Clock.schedule_interval(self._tick, self.TICK)

    TICK = 1.0

    def _layout(self, *_):
        self.radius = min(self.width, self.height) / 2 * 0.96
        self.redraw()
        self._tick(0)

    def redraw(self):
        raise NotImplementedError

    def _tick(self, _dt):
        raise NotImplementedError

    @staticmethod
    def now():
        return now()


def now() -> datetime:
    """Bieżący czas; DZIECI_NOW="2026-04-15 07:20" podstawia czas do podglądu na PC."""
    fake = os.environ.get("DZIECI_NOW")
    return datetime.strptime(fake, "%Y-%m-%d %H:%M") if fake else datetime.now()


# --- zegar analogowy --------------------------------------------------------------------
class AnalogClock(ClockBase):
    TICK = 0.25

    def __init__(self, **kwargs):
        self._numbers = []
        self._last = None
        super().__init__(**kwargs)

    def redraw(self):
        cx, cy, r = self.center_x, self.center_y, self.radius
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*RIM)
            Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            Color(*FACE)
            rf = r * 0.94
            Ellipse(pos=(cx - rf, cy - rf), size=(2 * rf, 2 * rf))
            Color(*INK)
            for i in range(60):
                big = i % 5 == 0
                x0, y0 = polar(cx, cy, rf * (0.86 if big else 0.91), i * 6)
                x1, y1 = polar(cx, cy, rf * 0.96, i * 6)
                Line(points=[x0, y0, x1, y1], width=max(1, r * (0.018 if big else 0.006)))
        for lbl in self._numbers:
            self.remove_widget(lbl)
        self._numbers = []
        for h in range(1, 13):
            x, y = polar(cx, cy, rf * 0.72, h * 30)
            lbl = Label(text=str(h), bold=True, color=INK, font_size=r * 0.17,
                        size=(r * 0.3, r * 0.3), center=(x, y))
            self.add_widget(lbl)
            self._numbers.append(lbl)
        self._last = None

    def _tick(self, _dt):
        now = self.now()
        if now.second == self._last:
            return
        self._last = now.second
        cx, cy, r = self.center_x, self.center_y, self.radius * 0.94
        sec = now.second
        minute = now.minute + sec / 60
        hour = now.hour % 12 + minute / 60
        self.canvas.after.clear()
        draw_hand(self.canvas.after, cx, cy, hour * 30, r * 0.50, r * 0.045, INK, tail=r * 0.08)
        draw_hand(self.canvas.after, cx, cy, minute * 6, r * 0.78, r * 0.030, INK, tail=r * 0.10)
        draw_hand(self.canvas.after, cx, cy, sec * 6, r * 0.84, r * 0.012, HAND, tail=r * 0.16)
        self.canvas.after.add(Color(*HAND))
        c = r * 0.06
        self.canvas.after.add(Ellipse(pos=(cx - c, cy - c), size=(2 * c, 2 * c)))
        self.caption = plan.WEEKDAYS[now.weekday()].capitalize()


# --- zegar pór dnia ---------------------------------------------------------------------
class DayClock(ClockBase):
    """Plan dnia: w tygodniu z przedszkolem, w weekend własny - tarcza przebudowuje się
    sama przy zmianie planu (o północy z piątku na sobotę i z niedzieli na poniedziałek)."""
    TICK = 5.0

    def __init__(self, **kwargs):
        self._images = []
        self._current = None
        self._plan = plan.day_plan(self.now())
        super().__init__(**kwargs)

    def redraw(self):
        cx, cy, r = self.center_x, self.center_y, self.radius
        acts = self._plan
        step = plan.sector(acts)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*RIM)
            Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            rf = r * 0.94
            for i, act in enumerate(acts):
                Color(*DAY_COLORS[act.key])
                a = plan.sector_center(i, acts)
                Ellipse(pos=(cx - rf, cy - rf), size=(2 * rf, 2 * rf),
                        angle_start=a - step / 2, angle_end=a + step / 2)
            Color(1, 1, 1, 0.9)
            for i in range(len(acts)):
                x, y = polar(cx, cy, rf, plan.sector_center(i, acts) - step / 2)
                Line(points=[cx, cy, x, y], width=max(1, r * 0.008))
        for img in self._images:
            self.remove_widget(img)
        self._images = []
        for act in acts:
            img = Image(source=str(ICONS / f"{act.key}.png"), fit_mode="contain")
            self.add_widget(img)
            self._images.append(img)
        self._current = None

    def _icon_size(self):
        # 11-12 obrazków na obwodzie: mniejsze, gdy wycinków jest więcej
        return self.radius * min(0.30, 3.3 / len(self._plan))

    def _tick(self, _dt):
        now = self.now()
        acts = plan.day_plan(now)
        if acts is not self._plan:
            self._plan = acts
            self.redraw()
        i, _frac = plan.current_activity(now)
        cx, cy, r = self.center_x, self.center_y, self.radius
        if i != self._current and self._images:
            self._current = i
            size = self._icon_size()
            for k, img in enumerate(self._images):
                big = size * (1.25 if k == i else 1.0)
                img.size = (big, big)
                img.center = polar(cx, cy, r * 0.72, plan.sector_center(k, acts))
                img.opacity = 1.0 if k == i else 0.7
        self.caption = acts[i].label
        step = plan.sector(acts)
        a = plan.sector_center(i, acts)
        self.canvas.after.clear()
        self.canvas.after.add(Color(*HIGHLIGHT))
        self.canvas.after.add(Line(circle=(cx, cy, r * 0.97, a - step / 2, a + step / 2),
                                   width=r * 0.03, cap="none"))
        draw_hand(self.canvas.after, cx, cy, plan.day_angle(now), r * 0.36, r * 0.045, INK,
                  tip=True)
        self.canvas.after.add(Color(*INK))
        c = r * 0.09
        self.canvas.after.add(Ellipse(pos=(cx - c, cy - c), size=(2 * c, 2 * c)))


# --- zegar pór roku ---------------------------------------------------------------------
class AnimatedIcon(Image):
    """Obrazek z ruchem: zima - obrót płatka, wiosna - kołysanie kwiatu,
    lato - pulsujące i obracające się słońce, jesień - liść spadający wahadłowo."""
    kind = StringProperty("")
    angle = NumericProperty(0)
    zoom = NumericProperty(1)
    dy = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            PushMatrix()
            self._tr = Translate()
            self._rot = Rotate()
            self._sc = Scale()
        with self.canvas.after:
            PopMatrix()
        self.bind(center=self._apply, angle=self._apply, zoom=self._apply, dy=self._apply)
        self._t0 = time.monotonic()
        Clock.schedule_interval(self._animate, 1 / 20)

    def _apply(self, *_):
        self._tr.xy = (0, self.dy)
        self._rot.origin = self.center
        self._rot.angle = self.angle
        self._sc.origin = self.center
        self._sc.x = self._sc.y = self.zoom

    def _animate(self, _dt):
        t = time.monotonic() - self._t0
        if self.kind == "zima":
            self.angle = -t * 30 % 360
        elif self.kind == "wiosna":
            self.angle = 10 * math.sin(t * 2.2)
            self.zoom = 1 + 0.04 * math.sin(t * 4.4)
        elif self.kind == "lato":
            self.angle = -t * 12 % 360
            self.zoom = 1 + 0.08 * math.sin(t * 3)
        elif self.kind == "jesien":
            self.angle = 20 * math.sin(t * 1.8)
            self.dy = 6 * math.sin(t * 3.6)


class SeasonClock(ClockBase):
    TICK = 60.0

    def __init__(self, **kwargs):
        self._icons = []
        self._current = None
        super().__init__(**kwargs)

    def redraw(self):
        cx, cy, r = self.center_x, self.center_y, self.radius
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*RIM)
            Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            rf = r * 0.94
            for i, (key, _label, _start) in enumerate(plan.SEASONS):
                Color(*SEASON_COLORS[key])
                Ellipse(pos=(cx - rf, cy - rf), size=(2 * rf, 2 * rf),
                        angle_start=i * 90, angle_end=(i + 1) * 90)
            Color(1, 1, 1, 0.9)
            for i in range(4):
                x, y = polar(cx, cy, rf, i * 90)
                Line(points=[cx, cy, x, y], width=max(1, r * 0.01))
        for icon in self._icons:
            self.remove_widget(icon)
        self._icons = []
        for i, (key, _label, _start) in enumerate(plan.SEASONS):
            icon = AnimatedIcon(source=str(ICONS / f"{key}.png"), kind=key, fit_mode="contain")
            self.add_widget(icon)
            self._icons.append(icon)
        self._current = None

    def _tick(self, _dt):
        today = self.now().date()
        i, _frac = plan.current_season(today)
        cx, cy, r = self.center_x, self.center_y, self.radius
        if i != self._current and self._icons:
            self._current = i
            for k, icon in enumerate(self._icons):
                size = r * (0.42 if k == i else 0.34)
                icon.size = (size, size)
                icon.center = polar(cx, cy, r * 0.62, k * 90 + 45)
                icon.opacity = 1.0 if k == i else 0.7
        self.caption = plan.SEASONS[i][1]
        self.canvas.after.clear()
        self.canvas.after.add(Color(*HIGHLIGHT))
        self.canvas.after.add(Line(circle=(cx, cy, r * 0.97, i * 90, (i + 1) * 90),
                                   width=r * 0.03, cap="none"))
        draw_hand(self.canvas.after, cx, cy, plan.season_angle(today), r * 0.30, r * 0.045,
                  INK, tip=True)
        self.canvas.after.add(Color(*INK))
        c = r * 0.09
        self.canvas.after.add(Ellipse(pos=(cx - c, cy - c), size=(2 * c, 2 * c)))
