"""Tetris: spadające klocki z czterech kwadratów. Przyciski obok planszy: w lewo, w prawo,
obrót, w dół (szybciej) i zrzut na sam dół; na PC także strzałki, spacja i P (pauza).
Pełny wiersz znika i daje punkty (1/2/3/4 wiersze naraz: 100/300/500/800 razy poziom).
Co 10 wierszy następny poziom - klocki spadają szybciej. Koniec, gdy nowy klocek się nie
mieści. Wyjście z ekranu wstrzymuje grę."""
import random

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

COLS, ROWS = 10, 20
SHAPES = {                              # kształt w siatce 4x4: lista (wiersz, kolumna)
    "I": [(1, 0), (1, 1), (1, 2), (1, 3)],
    "O": [(0, 1), (0, 2), (1, 1), (1, 2)],
    "T": [(0, 1), (1, 0), (1, 1), (1, 2)],
    "S": [(0, 1), (0, 2), (1, 0), (1, 1)],
    "Z": [(0, 0), (0, 1), (1, 1), (1, 2)],
    "J": [(0, 0), (1, 0), (1, 1), (1, 2)],
    "L": [(0, 2), (1, 0), (1, 1), (1, 2)],
}
COLORS = {"I": (0.30, 0.80, 0.90, 1), "O": (0.98, 0.82, 0.25, 1), "T": (0.65, 0.40, 0.85, 1),
          "S": (0.40, 0.80, 0.35, 1), "Z": (0.90, 0.30, 0.30, 1), "J": (0.30, 0.45, 0.90, 1),
          "L": (0.98, 0.60, 0.20, 1)}
POINTS = (0, 100, 300, 500, 800)
BG = (0.10, 0.12, 0.19, 1)
WELL = (0.06, 0.07, 0.12, 1)
GRID = (1, 1, 1, 0.05)
TEXT = (0.95, 0.95, 0.98, 1)
KEYS = {276: "left", 275: "right", 273: "rotate", 274: "down", 32: "drop", 112: "pause"}


def interval(level: int) -> float:
    return max(0.8 - level * 0.07, 0.12)


class Tetris(Widget):
    status = StringProperty("")
    score = NumericProperty(0)
    lines = NumericProperty(0)
    level = NumericProperty(0)
    paused = BooleanProperty(False)
    over = BooleanProperty(False)

    def __init__(self, **kwargs):
        self.grid = [[None] * COLS for _ in range(ROWS)]
        self.piece, self.next_kind = None, random.choice(list(SHAPES))
        self._event = None
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw)
        Window.bind(on_key_down=self._key)
        self.new_game()
        self.pause()

    # --- partia ---------------------------------------------------------------------
    def new_game(self):
        self.grid = [[None] * COLS for _ in range(ROWS)]
        self.score = self.lines = self.level = 0
        self.over = False
        self.next_kind = random.choice(list(SHAPES))
        self._spawn()
        self.resume()

    def _spawn(self):
        kind, self.next_kind = self.next_kind, random.choice(list(SHAPES))
        self.piece = {"kind": kind, "cells": list(SHAPES[kind]), "r": -1 if kind == "I" else 0,
                      "c": 3}
        if not self._fits(self.piece["cells"], self.piece["r"], self.piece["c"]):
            self.over = True
            self._stop_timer()
            self.status = f"Koniec gry! Wynik: {self.score}"
        self.redraw()

    def pause(self):
        self.paused = True
        self._stop_timer()
        if not self.over:
            self.status = "Pauza - naciśnij „Graj”"
        self.redraw()

    def resume(self):
        if self.over:
            return
        self.paused = False
        self._restart_timer()
        self._update_status()

    def toggle_pause(self):
        self.new_game() if self.over else (self.resume() if self.paused else self.pause())

    def _stop_timer(self):
        if self._event is not None:
            self._event.cancel()
            self._event = None

    def _restart_timer(self):
        self._stop_timer()
        self._event = Clock.schedule_interval(lambda _dt: self.step(), interval(self.level))

    def _update_status(self):
        self.status = f"Wynik: {self.score}   Wiersze: {self.lines}   Poziom: {self.level + 1}"

    # --- ruchy ----------------------------------------------------------------------
    def _fits(self, cells, r, c):
        for dr, dc in cells:
            rr, cc = r + dr, c + dc
            if cc < 0 or cc >= COLS or rr >= ROWS:
                return False
            if rr >= 0 and self.grid[rr][cc] is not None:
                return False
        return True

    def action(self, name):
        if self.over or self.paused or self.piece is None:
            if name == "pause":
                self.toggle_pause()
            return
        p = self.piece
        if name == "left" and self._fits(p["cells"], p["r"], p["c"] - 1):
            p["c"] -= 1
        elif name == "right" and self._fits(p["cells"], p["r"], p["c"] + 1):
            p["c"] += 1
        elif name == "rotate" and p["kind"] != "O":
            size = 4 if p["kind"] == "I" else 3
            turned = [(dc, size - 1 - dr) for dr, dc in p["cells"]]
            for shift in (0, -1, 1, -2, 2):     # odbicie od ściany
                if self._fits(turned, p["r"], p["c"] + shift):
                    p["cells"], p["c"] = turned, p["c"] + shift
                    break
        elif name == "down":
            self.step()
            return
        elif name == "drop":
            while self._fits(p["cells"], p["r"] + 1, p["c"]):
                p["r"] += 1
                self.score += 2
            self._lock()
            return
        elif name == "pause":
            self.pause()
            return
        self.redraw()

    def step(self):
        p = self.piece
        if self.over or self.paused or p is None:
            return
        if self._fits(p["cells"], p["r"] + 1, p["c"]):
            p["r"] += 1
            self.redraw()
        else:
            self._lock()

    def _lock(self):
        p = self.piece
        for dr, dc in p["cells"]:
            if p["r"] + dr >= 0:
                self.grid[p["r"] + dr][p["c"] + dc] = p["kind"]
        full = [r for r in range(ROWS) if all(self.grid[r])]
        if full:
            self.grid = [[None] * COLS for _ in full] + \
                        [row for r, row in enumerate(self.grid) if r not in full]
            self.score += POINTS[len(full)] * (self.level + 1)
            self.lines += len(full)
            if self.lines // 10 != self.level:
                self.level = self.lines // 10
                self._restart_timer()
        self._update_status()
        self._spawn()

    def _key(self, _window, key, *_args):
        if self.get_root_window() is None or key not in KEYS:
            return False
        screen = self.parent
        while screen is not None and not hasattr(screen, "manager"):
            screen = screen.parent
        if screen is None or screen.manager is None or screen.manager.current != screen.name:
            return False
        self.action(KEYS[key])
        return True

    # --- rysowanie -------------------------------------------------------------------
    def redraw(self, *_):
        k = min(self.height / ROWS, self.width / (COLS + 6))
        x0 = self.center_x - (COLS + 6) * k / 2
        y0 = self.center_y - ROWS * k / 2
        self.canvas.clear()
        with self.canvas:
            Color(*WELL)
            RoundedRectangle(pos=(x0 - 4, y0 - 4), size=(COLS * k + 8, ROWS * k + 8), radius=[8])
            Color(*GRID)
            for c in range(1, COLS):
                Line(points=[x0 + c * k, y0, x0 + c * k, y0 + ROWS * k], width=1)
            for r in range(ROWS):
                for c in range(COLS):
                    if self.grid[r][c]:
                        self._block(x0, y0, k, r, c, COLORS[self.grid[r][c]])
            p = self.piece
            if p is not None and not self.over:
                ghost = p["r"]          # cień - gdzie klocek spadnie
                while self._fits(p["cells"], ghost + 1, p["c"]):
                    ghost += 1
                for dr, dc in p["cells"]:
                    if ghost + dr >= 0:
                        self._block(x0, y0, k, ghost + dr, p["c"] + dc, (1, 1, 1, 0.12))
                for dr, dc in p["cells"]:
                    if p["r"] + dr >= 0:
                        self._block(x0, y0, k, p["r"] + dr, p["c"] + dc, COLORS[p["kind"]])
            # następny klocek
            nx, ny = x0 + (COLS + 1.2) * k, y0 + (ROWS - 2) * k
            Color(*TEXT[:3], 0.08)
            RoundedRectangle(pos=(nx - k * 0.3, ny - 3.6 * k), size=(k * 4.6, k * 4.6), radius=[10])
            for dr, dc in SHAPES[self.next_kind]:
                Color(*COLORS[self.next_kind])
                RoundedRectangle(pos=(nx + dc * k + 1, ny - dr * k - 1.5 * k + 1),
                                 size=(k - 2, k - 2), radius=[k * 0.18])

    @staticmethod
    def _block(x0, y0, k, r, c, color):
        Color(*color)
        RoundedRectangle(pos=(x0 + c * k + 1, y0 + (ROWS - 1 - r) * k + 1),
                         size=(k - 2, k - 2), radius=[k * 0.18])
