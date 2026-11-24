"""Wąż: wąż pełznie po planszy i zjada jabłka - po każdym rośnie i przyspiesza. Kierunek
zmieniają strzałki obok planszy albo przesunięcie palcem po planszy (na PC strzałki
klawiatury, P - pauza). Ściany nie są groźne - wąż wychodzi z drugiej strony; gra kończy
się, gdy wąż ugryzie sam siebie. Wyjście z ekranu wstrzymuje grę."""
import random

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

COLS, ROWS = 22, 14
START_SPEED = 0.24                      # s na krok
MIN_SPEED = 0.09
SPEEDUP = 0.006
SWIPE = 30                              # px - krótszy ruch palca to nie przesunięcie
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
KEYS = {273: "up", 274: "down", 276: "left", 275: "right", 112: "pause"}
FIELD = (0.62, 0.82, 0.45, 1)
FIELD_DARK = (0.57, 0.77, 0.41, 1)
BODY = (0.20, 0.45, 0.85, 1)
HEAD = (0.12, 0.30, 0.65, 1)
APPLE = (0.88, 0.22, 0.20, 1)
LEAF = (0.25, 0.60, 0.20, 1)


class Snake(Widget):
    status = StringProperty("")
    score = NumericProperty(0)
    best = NumericProperty(0)
    paused = BooleanProperty(True)
    over = BooleanProperty(False)

    def __init__(self, **kwargs):
        self.body, self.apple = [], (0, 0)
        self.direction, self._queued = "right", []
        self._event = None
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw)
        Window.bind(on_key_down=self._key)
        self.new_game()
        self.pause()

    # --- partia ---------------------------------------------------------------------
    def new_game(self):
        r = ROWS // 2
        self.body = [(r, 6), (r, 5), (r, 4)]
        self.direction, self._queued = "right", []
        self.score, self.over = 0, False
        self.speed = START_SPEED
        self._new_apple()
        self.resume()

    def _new_apple(self):
        free = [(r, c) for r in range(ROWS) for c in range(COLS) if (r, c) not in self.body]
        self.apple = random.choice(free)

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
        self._event = Clock.schedule_interval(lambda _dt: self.step(), self.speed)

    def _update_status(self):
        self.status = f"Jabłka: {self.score}   Rekord: {self.best}"

    # --- sterowanie -----------------------------------------------------------------
    def turn(self, name):
        if name == "pause":
            self.toggle_pause()
            return
        if self.paused and not self.over:
            self.resume()
        last = self._queued[-1] if self._queued else self.direction
        dr, dc = DIRS[name]
        lr, lc = DIRS[last]
        if (dr, dc) != (-lr, -lc) and name != last and len(self._queued) < 3:
            self._queued.append(name)

    def step(self):
        if self.over or self.paused:
            return
        if self._queued:
            self.direction = self._queued.pop(0)
        dr, dc = DIRS[self.direction]
        hr, hc = self.body[0]
        head = ((hr + dr) % ROWS, (hc + dc) % COLS)
        grow = head == self.apple
        if head in (self.body if grow else self.body[:-1]):
            self.over = True
            self._stop_timer()
            self.best = max(self.best, self.score)
            self.status = f"Koniec gry! Jabłka: {self.score}   Rekord: {self.best}"
            self.redraw()
            return
        self.body.insert(0, head)
        if grow:
            self.score += 1
            self.best = max(self.best, self.score)
            self.speed = max(self.speed - SPEEDUP, MIN_SPEED)
            self._restart_timer()
            self._new_apple()
            self._update_status()
        else:
            self.body.pop()
        self.redraw()

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud["snake_start"] = touch.pos
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        start = touch.ud.get("snake_start")
        if start is None:
            return super().on_touch_up(touch)
        dx, dy = touch.x - start[0], touch.y - start[1]
        if max(abs(dx), abs(dy)) < SWIPE:
            if self.paused or self.over:
                self.toggle_pause()     # stuknięcie w planszę - start
        elif abs(dx) > abs(dy):
            self.turn("right" if dx > 0 else "left")
        else:
            self.turn("up" if dy > 0 else "down")
        return True

    def _key(self, _window, key, *_args):
        if self.get_root_window() is None or key not in KEYS:
            return False
        screen = self.parent
        while screen is not None and not hasattr(screen, "manager"):
            screen = screen.parent
        if screen is None or screen.manager is None or screen.manager.current != screen.name:
            return False
        self.turn(KEYS[key])
        return True

    # --- rysowanie -------------------------------------------------------------------
    def redraw(self, *_):
        k = min(self.width / COLS, self.height / ROWS)
        x0 = self.center_x - COLS * k / 2
        y0 = self.center_y - ROWS * k / 2

        def pos(r, c):
            return x0 + c * k, y0 + (ROWS - 1 - r) * k

        self.canvas.clear()
        with self.canvas:
            Color(*FIELD)
            RoundedRectangle(pos=(x0, y0), size=(COLS * k, ROWS * k), radius=[k * 0.4])
            Color(*FIELD_DARK)
            for r in range(ROWS):
                for c in range(r % 2, COLS, 2):
                    x, y = pos(r, c)
                    RoundedRectangle(pos=(x, y), size=(k, k), radius=[2])
            ax, ay = pos(*self.apple)
            Color(*APPLE)
            Ellipse(pos=(ax + k * 0.12, ay + k * 0.08), size=(k * 0.76, k * 0.76))
            Color(*LEAF)
            Line(points=[ax + k * 0.5, ay + k * 0.8, ax + k * 0.65, ay + k * 0.98], width=max(k * 0.06, 1.5))
            for i, (r, c) in enumerate(reversed(self.body)):
                x, y = pos(r, c)
                head = i == len(self.body) - 1
                Color(*(HEAD if head else BODY))
                RoundedRectangle(pos=(x + k * 0.06, y + k * 0.06), size=(k * 0.88, k * 0.88),
                                 radius=[k * (0.4 if head else 0.28)])
            if self.body:                   # oczy
                r, c = self.body[0]
                x, y = pos(r, c)
                Color(1, 1, 1, 1)
                d = k * 0.22
                for ex, ey in ((0.3, 0.6), (0.7, 0.6)):
                    Ellipse(pos=(x + k * ex - d / 2, y + k * ey - d / 2), size=(d, d))
