"""Kropki (kropki i kreski): gracze na zmianę łączą sąsiednie kropki kreską. Kto postawi
czwarty bok kwadratu, zamyka go (kwadrat dostaje jego kolor) i rusza się jeszcze raz.
Po narysowaniu wszystkich kresek wygrywa ten, kto ma więcej kwadratów (BOXES x BOXES
kwadratów, liczba nieparzysta - bez remisów).

Kreska to numer: poziome 0..H-1 (wiersz kropek r, kolumna c: r * BOXES + c), pionowe
H.. (wiersz r, kolumna kropek c: H + r * (BOXES + 1) + c).
Tryby: z komputerem (łatwy), dwóch graczy, przez sieć. W sieci ruch to cała lista kresek
od początku partii - zgubiony komunikat (dwa ruchy po sobie po zamknięciu kwadratu)
nadrabia następny."""
import random

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle

from dzieci.games.board import NETWORK, BoardWidget

BOXES = 5
DOTS = BOXES + 1
H = DOTS * BOXES                        # liczba kresek poziomych
LINES = 2 * H
RESTART_SECONDS = 6
TAP_RANGE = 0.35                        # dotknięcie dalej niż 0.35 pola od kreski - nic
TAKE_CHANCE = 0.75                      # komputer zamyka kwadrat z takim prawdopodobieństwem
BOARD = (0.98, 0.97, 0.93, 1)
DOT = (0.16, 0.18, 0.25, 1)
FREE = (0.30, 0.34, 0.48, 0.18)
COLORS = ((0.85, 0.27, 0.27, 1), (0.20, 0.45, 0.85, 1))


def line_ends(i):
    """Kropki (wiersz, kolumna) na końcach kreski."""
    if i < H:
        r, c = divmod(i, BOXES)
        return (r, c), (r, c + 1)
    r, c = divmod(i - H, DOTS)
    return (r, c), (r + 1, c)


def box_lines(r, c):
    """Cztery kreski kwadratu (wiersz r, kolumna c)."""
    return (r * BOXES + c, (r + 1) * BOXES + c, H + r * DOTS + c, H + r * DOTS + c + 1)


def line_boxes(i):
    """Kwadraty (1 albo 2) przy kresce."""
    if i < H:
        r, c = divmod(i, BOXES)
        return [(rr, c) for rr in (r - 1, r) if 0 <= rr < BOXES]
    r, c = divmod(i - H, DOTS)
    return [(r, cc) for cc in (c - 1, c) if 0 <= cc < BOXES]


class Dots(BoardWidget):
    SIZE = DOTS
    GAME = "dots"
    SIDE_NAMES = ("czerwony", "niebieski")

    def __init__(self, **kwargs):
        self.lines = {}                 # kreska -> gracz
        self.history = []
        self.boxes = {}                 # (r, c) -> gracz
        self.player = 0
        self.finished = False
        self.last = None
        self._restart = None
        super().__init__(**kwargs)
        self.players = 1
        self.new_game()

    # --- partia ---------------------------------------------------------------------
    def new_game(self, *_):
        if self._restart is not None:
            self._restart.cancel()
            self._restart = None
        self.lines, self.history, self.boxes = {}, [], {}
        self.player, self.finished, self.last = 0, False, None
        self.refresh_status()
        self.redraw()
        self.schedule_ai()

    def current_side(self):
        return self.player

    def score(self, side):
        return sum(1 for p in self.boxes.values() if p == side)

    def refresh_status(self):
        if not self.finished:
            self.status = f"{self.turn_text(self.player)}   {self.score(0)} : {self.score(1)}"

    def _draw_line(self, i) -> bool:
        """Kreska dla bieżącego gracza; True, gdy zamknęła kwadrat (gracz rusza się dalej)."""
        self.lines[i] = self.player
        self.history.append(i)
        self.last = i
        closed = False
        for r, c in line_boxes(i):
            if all(k in self.lines for k in box_lines(r, c)):
                self.boxes[(r, c)] = self.player
                closed = True
        if len(self.lines) == LINES:
            self._finish()
        elif not closed:
            self.player = 1 - self.player
        self.refresh_status()
        self.redraw()
        return closed

    def _finish(self):
        self.finished = True
        a, b = self.score(0), self.score(1)
        self.status = f"{self.winner_text(0 if a > b else 1)}   {a} : {b}"
        self.game_over(0 if a > b else 1)
        if self.players != NETWORK:
            self._restart = Clock.schedule_once(self.new_game, RESTART_SECONDS)

    def play(self, i):
        if self.finished or i in self.lines:
            return
        self._draw_line(i)
        self.send(self.history)
        self.schedule_ai()

    def remote_move(self, move):
        """Cała lista kresek drugiego tabletu: dorysuj te, których jeszcze nie ma."""
        if self.finished or self.human_turn() or move[:len(self.history)] != self.history:
            return
        for i in move[len(self.history):]:
            if self.human_turn():      # dalsze kreski byłyby już moje - błędna lista
                return
            if self.finished or i in self.lines or not 0 <= i < LINES:
                return
            self._draw_line(i)

    # --- dotyk: najbliższa kreska ----------------------------------------------------
    def nearest_line(self, x, y):
        x0, y0 = self.origin
        step = self.side / DOTS
        gx = (x - x0) / step - 0.5          # współrzędne w kropkach (0..BOXES)
        gy = BOXES - ((y - y0) / step - 0.5)
        best, dist = None, TAP_RANGE
        for i in range(LINES):
            (r1, c1), (r2, c2) = line_ends(i)
            mx, my = (c1 + c2) / 2, (r1 + r2) / 2
            d = abs(gy - my) + max(abs(gx - mx) - 0.5, 0) if r1 == r2 else \
                abs(gx - mx) + max(abs(gy - my) - 0.5, 0)
            if d < dist:
                best, dist = i, d
        return best

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        i = self.nearest_line(*touch.pos)
        if i is not None and self.human_turn():
            self.play(i)
        return True

    def tap(self, row, col):
        """Stuknięcie w kropkę (test): kreska w prawo albo w dół od niej."""
        for i in ([row * BOXES + col] if col < BOXES else []) + \
                ([H + row * DOTS + col] if row < BOXES else []):
            if i not in self.lines:
                self.play(i)
                return

    # --- komputer (łatwy) ----------------------------------------------------------------
    def _sides(self, r, c):
        return sum(1 for k in box_lines(r, c) if k in self.lines)

    def ai_move(self):
        self._ai_event = None
        if self.finished or not self.computer_turn():
            return
        free = [i for i in range(LINES) if i not in self.lines]
        take = [i for i in free if any(self._sides(r, c) == 3 for r, c in line_boxes(i))]
        safe = [i for i in free if all(self._sides(r, c) < 2 for r, c in line_boxes(i))]
        if take and random.random() < TAKE_CHANCE:
            i = random.choice(take)
        elif safe:
            i = random.choice(safe)
        else:
            i = random.choice(free)
        self.play(i)

    # --- rysowanie -------------------------------------------------------------------
    def dot_pos(self, r, c):
        x0, y0 = self.origin
        step = self.side / DOTS
        return x0 + (c + 0.5) * step, y0 + (BOXES - r + 0.5) * step

    def redraw(self):
        if not hasattr(self, "lines"):
            return
        x0, y0 = self.origin
        step = self.side / DOTS
        self.canvas.clear()
        with self.canvas:
            Color(*BOARD)
            RoundedRectangle(pos=(x0, y0), size=(self.side, self.side), radius=[step * 0.2])
            for (r, c), p in self.boxes.items():
                Color(*COLORS[p][:3], 0.30)
                x, y = self.dot_pos(r + 1, c)
                Rectangle(pos=(x, y), size=(step, step))
            for i in range(LINES):
                a, b = line_ends(i)
                (ax, ay), (bx, by) = self.dot_pos(*a), self.dot_pos(*b)
                if i in self.lines:
                    Color(*COLORS[self.lines[i]])
                    w = step * (0.07 if i == self.last else 0.05)
                else:
                    Color(*FREE)
                    w = step * 0.02
                Line(points=[ax, ay, bx, by], width=max(w, 1.5), cap="round")
            Color(*DOT)
            d = step * 0.16
            for r in range(DOTS):
                for c in range(DOTS):
                    x, y = self.dot_pos(r, c)
                    Ellipse(pos=(x - d / 2, y - d / 2), size=(d, d))
