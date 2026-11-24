"""Piłkarzyki na papierze: boisko w kratkę 8 x 10 z bramkami u góry i na dole. Piłka
startuje na środku; gracze na zmianę przesuwają ją kreską do jednego z 8 sąsiednich punktów
(także po skosie). Po kresce nie wolno przejść drugi raz ani iść wzdłuż bandy. Gdy piłka
trafi w punkt, przy którym jest już kreska albo banda, piłka się odbija - ten sam gracz
rusza dalej. Gol w bramce przeciwnika wygrywa (samobój przegrywa), a gracz bez ruchu
przegrywa. Czerwoni (Gracz 1) atakują górną bramkę, niebiescy dolną.

Tryby: z komputerem (łatwy), dwóch graczy, przez sieć. W sieci ruch to cała lista punktów
od początku partii (odbicia dają kilka ruchów po sobie - zgubiony komunikat nadrabia
następny)."""
import random

from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle

from dzieci.games.board import NETWORK, BoardWidget

W, H = 8, 10                            # kratki boiska
GOAL = (3, 4, 5)                        # kolumny punktów bramki
START = (H // 2, W // 2)
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
PAPER = (0.98, 0.97, 0.93, 1)
GRID = (0.55, 0.70, 0.88, 0.45)
BAND = (0.16, 0.18, 0.25, 1)
HINT = (0.25, 0.70, 0.25, 0.9)
COLORS = ((0.85, 0.27, 0.27, 1), (0.20, 0.45, 0.85, 1))


def valid(p):
    r, c = p
    return (0 <= r <= H and 0 <= c <= W) or (r in (-1, H + 1) and c in GOAL)


def border_edges():
    """Kreski bandy (nie wolno po nich iść): brzegi boiska i bramek, bez wejść do bramek."""
    edges = set()

    def add(a, b):
        edges.add(frozenset((a, b)))
    for r in range(H):
        add((r, 0), (r + 1, 0))
        add((r, W), (r + 1, W))
    for row in (0, H):
        for c in range(W):
            if not (c in GOAL and c + 1 in GOAL):
                add((row, c), (row, c + 1))
    for row, out in ((0, -1), (H, H + 1)):      # bramki: słupki i tył
        add((row, GOAL[0]), (out, GOAL[0]))
        add((row, GOAL[-1]), (out, GOAL[-1]))
        add((out, GOAL[0]), (out, GOAL[1]))
        add((out, GOAL[1]), (out, GOAL[2]))
    return edges


BORDER = border_edges()


def index(p):
    return (p[0] + 1) * (W + 1) + p[1]


def point(i):
    r, c = divmod(i, W + 1)
    return r - 1, c


class Football(BoardWidget):
    SIZE = W + 1
    GAME = "football"
    SIDE_NAMES = ("czerwoni", "niebiescy")

    def __init__(self, **kwargs):
        self._reset()
        super().__init__(**kwargs)
        self.players = 1
        self.new_game()

    def _reset(self):
        self.ball = START
        self.used = set(BORDER)
        self.moves = []                 # (od, do, gracz)
        self.history = []               # numery punktów (dla sieci)
        self.touched = {START}          # punkty, przy których jest kreska
        self.player = 0
        self.finished = False

    # --- partia ---------------------------------------------------------------------
    def new_game(self, *_):
        self._reset()
        self.refresh_status()
        self.redraw()
        self.schedule_ai()

    def current_side(self):
        return self.player

    def refresh_status(self):
        if not self.finished:
            self.status = self.turn_text(self.player)

    def legal(self):
        r, c = self.ball
        out = []
        for dr, dc in DIRS:
            p = (r + dr, c + dc)
            if valid(p) and frozenset((self.ball, p)) not in self.used:
                out.append(p)
        return out

    def _bounces(self, p):
        r, c = p
        return p in self.touched or r in (0, H) or c in (0, W)

    def _move(self, p):
        """Kreska od piłki do p; True, gdy gracz rusza dalej (odbicie)."""
        a = self.ball
        bounce = self._bounces(p)
        self.used.add(frozenset((a, p)))
        self.moves.append((a, p, self.player))
        self.history.append(index(p))
        self.touched.update((a, p))
        self.ball = p
        if p[0] == -1:                  # górna bramka - gol czerwonych
            self._finish(0, "Gol!")
        elif p[0] == H + 1:
            self._finish(1, "Gol!")
        elif not bounce:
            self.player = 1 - self.player
        if not self.finished and not self.legal():
            self._finish(1 - self.player, "Brak ruchu -")
        self.refresh_status()
        self.redraw()

    def _finish(self, winner, why):
        self.finished = True
        self.status = f"{why} {self.winner_text(winner)}"

    def play(self, p):
        if self.finished or p not in self.legal():
            return
        self._move(p)
        self.send(self.history)
        self.schedule_ai()

    def remote_move(self, move):
        if self.finished or self.human_turn() or move[:len(self.history)] != self.history:
            return
        for i in move[len(self.history):]:
            if self.finished or self.human_turn() or point(i) not in self.legal():
                return
            self._move(point(i))

    # --- dotyk: najbliższy dozwolony punkt ------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if self.human_turn():
            best, dist = None, self.step * 0.6
            for p in self.legal():
                x, y = self.pos_of(p)
                d = ((x - touch.x) ** 2 + (y - touch.y) ** 2) ** 0.5
                if d < dist:
                    best, dist = p, d
            if best is not None:
                self.play(best)
        return True

    def tap(self, row, col):
        """Test: ruch do punktu (wiersz, kolumna), jeśli dozwolony."""
        self.play((row, col))

    # --- komputer (łatwy): goni dolną bramkę, unika samobója -------------------------------
    def ai_move(self):
        self._ai_event = None
        if self.finished or not self.computer_turn():
            return
        moves = self.legal()
        if not moves:
            return
        goals = [p for p in moves if p[0] == H + 1]
        safe = [p for p in moves if p[0] != -1] or moves
        if goals and random.random() < 0.85:
            p = goals[0]
        elif random.random() < 0.6:
            p = min(safe, key=lambda q: (abs(q[0] - (H + 1)) + abs(q[1] - W / 2) * 0.5,
                                         random.random()))
        else:
            p = random.choice(safe)
        self._move(p)
        self.send(self.history)
        self.schedule_ai()

    # --- geometria: boisko 8 x 10 kratek + bramki ------------------------------------------
    @property
    def step(self):
        return min(self.width / (W + 1), self.height / (H + 2.6))

    def pos_of(self, p):
        k = self.step
        x0 = self.center_x - W * k / 2
        y0 = self.center_y + H * k / 2
        return x0 + p[1] * k, y0 - p[0] * k

    # --- rysowanie -------------------------------------------------------------------
    def redraw(self):
        if not hasattr(self, "moves"):
            return
        k = self.step
        (lx, ty), (rx, by) = self.pos_of((0, 0)), self.pos_of((H, W))
        self.canvas.clear()
        with self.canvas:
            Color(*PAPER)
            RoundedRectangle(pos=(lx - k * 0.5, by - k * 1.4), size=(W * k + k, H * k + k * 2.8),
                             radius=[k * 0.3])
            Color(*GRID)
            for c in range(W + 1):
                Line(points=[lx + c * k, by - k, lx + c * k, ty + k], width=1)
            for r in range(-1, H + 2):
                y = ty - r * k
                Line(points=[lx - k * 0.3, y, rx + k * 0.3, y], width=1)
            gx, gy = self.pos_of((H // 2, 0))
            Color(*BAND[:3], 0.25)
            Line(points=[lx, gy, rx, gy], width=1.2)       # linia środkowa
            Color(*BAND)
            for e in BORDER:
                a, b = tuple(e)
                Line(points=[*self.pos_of(a), *self.pos_of(b)], width=max(k * 0.06, 2), cap="round")
            for (top, side) in ((-1, 0), (H + 1, 1)):       # pole bramki w kolorze atakującego
                (x1, y1), (x2, y2) = self.pos_of((top, GOAL[0])), self.pos_of((0 if top < 0 else H,
                                                                               GOAL[-1]))
                Color(*COLORS[side][:3], 0.15)
                Rectangle(pos=(x1, min(y1, y2)), size=(x2 - x1, abs(y2 - y1)))
            for a, b, pl in self.moves:
                Color(*COLORS[pl])
                Line(points=[*self.pos_of(a), *self.pos_of(b)], width=max(k * 0.05, 1.5), cap="round")
            if self.human_turn() and not self.finished:
                Color(*HINT)
                d = k * 0.26
                for p in self.legal():
                    x, y = self.pos_of(p)
                    Ellipse(pos=(x - d / 2, y - d / 2), size=(d, d))
            x, y = self.pos_of(self.ball)
            d = k * 0.5
            Color(0.10, 0.10, 0.12, 1)
            Ellipse(pos=(x - d / 2, y - d / 2), size=(d, d))
            Color(1, 1, 1, 1)
            Ellipse(pos=(x - d / 5, y - d / 5), size=(d / 2.5, d / 2.5))
