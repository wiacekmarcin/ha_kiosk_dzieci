"""Polskie kropki: gracze na zmianę stawiają kropki na skrzyżowaniach kratek. Kto otoczy
kropki przeciwnika łańcuchem swoich kropek (sąsiednich także po skosie), zdobywa je - obszar
w środku dostaje jego kolor i nikt już w nim nie postawi kropki. Kropka postawiona w cudzym
otoczonym obszarze od razu przepada. Gra kończy się, gdy nie ma wolnych miejsc albo po
przycisku "Zakończ"; wygrywa ten, kto zdobył więcej kropek przeciwnika.

Tryby: z komputerem (łatwy), dwóch graczy, przez sieć. W sieci ruch to [numer pola],
a [-1] to "Zakończ" (koniec gry na obu tabletach)."""
import random

from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle

from dzieci.games.board import NETWORK, BoardWidget

N = 13
END = -1
GREEDY = 0.7                            # komputer bierze najlepsze zdobycie z takim prawd.
PAPER = (0.98, 0.97, 0.93, 1)
GRID = (0.55, 0.70, 0.88, 0.55)
COLORS = ((0.85, 0.27, 0.27, 1), (0.20, 0.45, 0.85, 1))


def neighbors4(i):
    r, c = divmod(i, N)
    if r > 0:
        yield i - N
    if r < N - 1:
        yield i + N
    if c > 0:
        yield i - 1
    if c < N - 1:
        yield i + 1


class PolishDots(BoardWidget):
    SIZE = N
    GAME = "pdots"
    SIDE_NAMES = ("czerwone", "niebieskie")

    def __init__(self, **kwargs):
        self._reset()
        super().__init__(**kwargs)
        self.players = 1
        self.new_game()

    def _reset(self):
        self.owner = [None] * (N * N)   # kto postawił kropkę
        self.captured = [False] * (N * N)
        self.area = [None] * (N * N)    # czyj otoczony obszar
        self.score = [0, 0]
        self.player = 0
        self.last = None
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
            self.status = f"{self.turn_text(self.player)}   zdobyte: {self.score[0]} : {self.score[1]}"

    def free(self, i):
        return self.owner[i] is None and self.area[i] is None

    def tap(self, row, col):
        i = row * N + col
        if self.finished or not self.free(i):
            return
        self.send([i])
        self._place(i)
        self.schedule_ai()

    def finish_button(self):
        """Przycisk "Zakończ"."""
        if self.finished or not (self.players != NETWORK or self.net_ready):
            return
        self.send([END])
        self._finish()

    def remote_move(self, move):
        if self.finished or not move:
            return
        if move[0] == END:
            self._finish()
        elif not self.human_turn() and 0 <= move[0] < N * N and self.free(move[0]):
            self._place(move[0])

    def _place(self, i):
        p = self.player
        self.owner[i] = p
        self.last = i
        self._capture(p, apply=True)
        self._capture(1 - p, apply=True)  # kropka w cudzym domku przepada
        self.player = 1 - p
        if not any(self.free(k) for k in range(N * N)):
            self._finish()
        self.refresh_status()
        self.redraw()

    def _finish(self):
        self.finished = True
        a, b = self.score
        self.status = (f"Remis!   {a} : {b}" if a == b else
                       f"{self.winner_text(0 if a > b else 1)}   {a} : {b}")
        self.redraw()

    # --- otaczanie ------------------------------------------------------------------
    def _capture(self, p, apply):
        """Obszary otoczone kropkami gracza p z kropkami przeciwnika w środku.
        apply=True - zabiera je; zwraca liczbę zdobytych kropek."""
        walls = {k for k in range(N * N) if self.owner[k] == p and not self.captured[k]}
        outside = set()
        stack = [k for k in range(N * N)
                 if (k < N or k >= N * (N - 1) or k % N in (0, N - 1)) and k not in walls]
        outside.update(stack)
        while stack:
            k = stack.pop()
            for m in neighbors4(k):
                if m not in walls and m not in outside:
                    outside.add(m)
                    stack.append(m)
        inner = {k for k in range(N * N) if k not in walls and k not in outside}
        gained = 0
        while inner:
            comp, stack = set(), [inner.pop()]
            comp.add(stack[0])
            while stack:
                k = stack.pop()
                for m in neighbors4(k):
                    if m in inner:
                        inner.discard(m)
                        comp.add(m)
                        stack.append(m)
            enemies = [k for k in comp if self.owner[k] == 1 - p and not self.captured[k]]
            if not enemies:
                continue
            gained += len(enemies)
            if apply:
                for k in comp:
                    self.area[k] = p
                    if self.owner[k] == 1 - p:
                        self.captured[k] = True
        if apply:
            self.score[p] += gained
        return gained

    # --- komputer (łatwy) ------------------------------------------------------------
    def ai_move(self):
        self._ai_event = None
        if self.finished or not self.computer_turn():
            return
        free = [k for k in range(N * N) if self.free(k)]
        if not free:
            return
        best, gain = None, 0
        if random.random() < GREEDY:
            for k in free:
                self.owner[k] = 1
                g = self._capture(1, apply=False)
                self.owner[k] = None
                if g > gain:
                    best, gain = k, g
        if best is None:
            near = [k for k in free if self.last is not None
                    and max(abs(k // N - self.last // N), abs(k % N - self.last % N)) == 1]
            best = random.choice(near or free)
        self._place(best)
        self.schedule_ai()

    # --- rysowanie -------------------------------------------------------------------
    def redraw(self):
        if not hasattr(self, "area"):
            return
        c = self.cell
        x0, y0 = self.origin
        self.canvas.clear()
        with self.canvas:
            Color(*PAPER)
            RoundedRectangle(pos=(x0, y0), size=(self.side, self.side), radius=[c * 0.3])
            for k, p in enumerate(self.area):
                if p is not None:
                    Color(*COLORS[p][:3], 0.22)
                    Rectangle(pos=self.cell_pos(k // N, k % N), size=(c, c))
            Color(*GRID)
            for j in range(N):
                a = x0 + (j + 0.5) * c
                Line(points=[a, y0 + c / 2, a, y0 + self.side - c / 2], width=1)
                b = y0 + (j + 0.5) * c
                Line(points=[x0 + c / 2, b, x0 + self.side - c / 2, b], width=1)
            # obwódki zdobytych obszarów: kreski między sąsiednimi kropkami przy obszarze
            for k in range(N * N):
                p = self.owner[k]
                if p is None or self.captured[k] or not self._borders(k, p):
                    continue
                r, col = divmod(k, N)
                for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                    rr, cc = r + dr, col + dc
                    if 0 <= rr < N and 0 <= cc < N:
                        m = rr * N + cc
                        # skos tylko, gdy na rogu nie ma mojej kropki (bez krzyżyków w środku)
                        corner = dr and dc and any(self.owner[x] == p and not self.captured[x]
                                                   for x in (r * N + cc, rr * N + col))
                        if self.owner[m] == p and not self.captured[m] and self._borders(m, p) \
                                and not corner:
                            Color(*COLORS[p])
                            ax, ay = self.cell_center(r, col)
                            bx, by = self.cell_center(rr, cc)
                            Line(points=[ax, ay, bx, by], width=max(c * 0.06, 1.5))
            for k, p in enumerate(self.owner):
                if p is None:
                    continue
                cx, cy = self.cell_center(k // N, k % N)
                d = c * (0.32 if self.captured[k] else 0.46)
                Color(*COLORS[p][:3], 0.45 if self.captured[k] else 1)
                Ellipse(pos=(cx - d / 2, cy - d / 2), size=(d, d))
                if k == self.last:
                    Color(1, 1, 1, 0.9)
                    Ellipse(pos=(cx - d / 6, cy - d / 6), size=(d / 3, d / 3))

    def _borders(self, k, p):
        """Kropka leży przy zdobytym obszarze gracza p (8 sąsiadów)."""
        r, c = divmod(k, N)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if (dr or dc) and 0 <= rr < N and 0 <= cc < N and self.area[rr * N + cc] == p \
                        and self.owner[rr * N + cc] != p:
                    return True
        return False
