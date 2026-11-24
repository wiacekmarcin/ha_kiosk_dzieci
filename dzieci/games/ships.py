"""Statki - tylko przez sieć, z drugim tabletem. Po lewej moja flota, po prawej morze
przeciwnika, w które się strzela. Flota jak w klasycznych statkach: jeden czteromasztowiec,
dwa trójmasztowce, trzy dwumasztowce i cztery jednomasztowce, statki nie stykają się
nawet rogami. Ustawienie jest losowe; przycisk "Losuj flotę" zmienia je do pierwszego
strzału. Trafienie - strzelasz dalej, pudło - kolej przeciwnika. Wygrywa ten, kto pierwszy
zatopi całą flotę.

Zaczyna tablet, który zaprosił. Komunikaty (ruch w sieci):
    [0, r, c]                 - strzał w pole (r, c)
    [1, r, c, wynik, *pola]   - odpowiedź: 0 pudło, 1 trafiony, 2 zatopiony, 3 zatopiona
                                cała flota; przy zatopieniu pola statku (r1, c1, r2, c2...)
Strzał i odpowiedź zawsze na zmianę między tabletami, więc żaden komunikat nie ginie.
"""
import random

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.properties import BooleanProperty

from dzieci.games.board import NETWORK, BoardWidget

N = 10
FLEET = (4, 3, 3, 2, 2, 2, 1, 1, 1, 1)
SHOT, REPLY = 0, 1
MISS, HIT, SUNK, ALL_SUNK = 0, 1, 2, 3
GAP = 0.06                              # odstęp między planszami (ułamek szerokości)
WATER = (0.80, 0.90, 0.98, 1)
GRID = (0.45, 0.60, 0.78, 1)
SHIP = (0.38, 0.42, 0.50, 1)
HIT_COLOR = (0.88, 0.25, 0.20, 1)
SUNK_COLOR = (0.45, 0.10, 0.10, 1)
MISS_COLOR = (0.20, 0.30, 0.50, 1)
LABEL = (0.95, 0.95, 0.98, 1)


def random_fleet():
    """Lista statków (każdy to lista pól) - losowo, bez stykania się."""
    while True:
        taken, ships = set(), []
        for size in FLEET:
            for _ in range(300):
                horizontal = random.random() < 0.5
                r = random.randrange(N if horizontal else N - size + 1)
                c = random.randrange(N - size + 1 if horizontal else N)
                cells = [(r, c + k) if horizontal else (r + k, c) for k in range(size)]
                ring = {(a + dr, b + dc) for a, b in cells for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
                if not ring & taken:
                    ships.append(cells)
                    taken |= set(cells)
                    break
            else:
                break                   # nie zmieścił się - losuj od nowa
        if len(ships) == len(FLEET):
            return ships


class Battleship(BoardWidget):
    SIZE = N
    GAME = "ships"
    SIDE_NAMES = ("", "")
    started = BooleanProperty(False)    # padł pierwszy strzał - flota ustalona

    def __init__(self, **kwargs):
        self.ships = random_fleet()
        self.incoming = {}              # moje pola ostrzelane: (r, c) -> trafiony?
        self.outgoing = {}              # pola przeciwnika: (r, c) -> MISS / HIT / SUNK
        self.turn = 0
        self.waiting = False            # czekam na odpowiedź na swój strzał
        self.finished = False
        super().__init__(**kwargs)
        self._joining = True            # tylko sieć - bez zaproszenia przy starcie
        self.players = NETWORK
        self._joining = False
        self.new_game()

    # --- partia ---------------------------------------------------------------------
    def new_game(self, *_):
        self.ships = random_fleet()
        self.incoming, self.outgoing = {}, {}
        self.turn, self.waiting, self.finished, self.started = 0, False, False, False
        self.refresh_status()
        self.redraw()

    def shuffle(self):
        """Przycisk "Losuj flotę" - tylko przed pierwszym strzałem."""
        if not self.started:
            self.ships = random_fleet()
            self.redraw()

    def enter_later(self):
        """Wejście na ekran (on_enter): sprawdzenie po chwili - po przyjęciu zaproszenia
        z innego tabletu join() przychodzi zaraz po przejściu na ekran."""
        Clock.schedule_once(lambda _dt: self.enter(), 0.3)

    def enter(self):
        """Nowe zaproszenie, chyba że partia już trwa albo czeka na odpowiedź."""
        net = self.net()
        if not self.net_ready and not (net is not None and net.session):
            self.restart()

    def current_side(self):
        return self.turn

    def human_turn(self):
        return super().human_turn() and not self.waiting and not self.finished

    def computer_turn(self):
        return False

    def refresh_status(self):
        if self.finished:
            return
        if self.players == NETWORK and self.net_ready:
            if self.turn == self.my_side:
                self.status = "Czekam na wynik strzału…" if self.waiting else \
                    "Twój strzał - stuknij w pole po prawej"
            else:
                self.status = f"Strzela {self.peer}"
        else:
            self.status = self.turn_text(self.turn)

    # --- strzał tego tabletu ----------------------------------------------------------
    def tap(self, row, col):
        if (row, col) in self.outgoing or self.finished or self.waiting:
            return
        self.started, self.waiting = True, True
        self.send([SHOT, row, col])
        self.refresh_status()

    def remote_move(self, move):
        if not move:
            return
        if move[0] == SHOT and self.turn != self.my_side:
            self._shot_received(move[1], move[2])
        elif move[0] == REPLY and self.waiting:
            self._reply_received(move[1], move[2], move[3], move[4:])

    def _reply_received(self, r, c, result, cells):
        self.waiting = False
        if result == MISS:
            self.outgoing[(r, c)] = MISS
            self.turn = 1 - self.turn
        else:
            self.outgoing[(r, c)] = HIT
            if result >= SUNK:
                for k in range(0, len(cells) - 1, 2):
                    self.outgoing[(cells[k], cells[k + 1])] = SUNK
        if result == ALL_SUNK:
            self.finished = True
            self.status = "Wygrywasz! Cała flota zatopiona. Brawo!"
        self.refresh_status()
        self.redraw()

    # --- strzał przeciwnika -----------------------------------------------------------
    def _shot_received(self, r, c):
        self.started = True
        ship = next((s for s in self.ships if (r, c) in s), None)
        self.incoming[(r, c)] = ship is not None
        reply = [REPLY, r, c, MISS]
        if ship is None:
            self.turn = 1 - self.turn
        elif all(self.incoming.get(p) for p in ship):
            sunk_all = all(self.incoming.get(p) for s in self.ships for p in s)
            reply = [REPLY, r, c, ALL_SUNK if sunk_all else SUNK] + [v for p in ship for v in p]
            if sunk_all:
                self.finished = True
                self.status = f"Wygrywa {self.peer} - zatopił całą flotę"
        else:
            reply[3] = HIT
        self.send(reply)
        self.refresh_status()
        self.redraw()

    # --- geometria: dwie plansze obok siebie ---------------------------------------------
    @property
    def side(self):
        return min(self.width * (1 - GAP) / 2, self.height - 40) * 0.98

    def board_origin(self, enemy: bool):
        gap = self.width * GAP / 2
        y = self.center_y - self.side / 2 - 18
        return (self.center_x + gap, y) if enemy else (self.center_x - gap - self.side, y)

    @property
    def origin(self):                    # pola do stukania - morze przeciwnika
        return self.board_origin(True)

    def cell_rect(self, r, c, enemy):
        x0, y0 = self.board_origin(enemy)
        k = self.side / N
        return x0 + c * k, y0 + (N - 1 - r) * k, k

    # --- rysowanie -------------------------------------------------------------------
    def redraw(self):
        if not hasattr(self, "outgoing"):
            return
        from kivy.core.text import Label as CoreLabel
        k = self.side / N
        self.canvas.clear()
        with self.canvas:
            for enemy in (False, True):
                x0, y0 = self.board_origin(enemy)
                Color(*WATER)
                RoundedRectangle(pos=(x0, y0), size=(self.side, self.side), radius=[k * 0.2])
                Color(*GRID)
                for i in range(1, N):
                    Line(points=[x0 + i * k, y0, x0 + i * k, y0 + self.side], width=1)
                    Line(points=[x0, y0 + i * k, x0 + self.side, y0 + i * k], width=1)
                title = f"Morze: {self.peer or 'przeciwnik'}" if enemy else "Moja flota"
                tex = CoreLabel(text=title, font_size=26, bold=True)
                tex.refresh()
                Color(*LABEL)
                Rectangle(texture=tex.texture, size=tex.texture.size,
                          pos=(x0 + (self.side - tex.texture.size[0]) / 2, y0 + self.side + 6))
            # moja flota i strzały przeciwnika
            for ship in self.ships:
                sunk = all(self.incoming.get(p) for p in ship)
                Color(*(SUNK_COLOR if sunk else SHIP))
                for r, c in ship:
                    x, y, _ = self.cell_rect(r, c, False)
                    RoundedRectangle(pos=(x + k * 0.08, y + k * 0.08), size=(k * 0.84, k * 0.84),
                                     radius=[k * 0.2])
            for (r, c), hit in self.incoming.items():
                self._mark(r, c, False, HIT if hit else MISS)
            # moje strzały
            for (r, c), result in self.outgoing.items():
                if result == SUNK:
                    Color(*SUNK_COLOR)
                    x, y, _ = self.cell_rect(r, c, True)
                    RoundedRectangle(pos=(x + k * 0.08, y + k * 0.08), size=(k * 0.84, k * 0.84),
                                     radius=[k * 0.2])
                self._mark(r, c, True, result)

    def _mark(self, r, c, enemy, result):
        x, y, k = self.cell_rect(r, c, enemy)
        cx, cy = x + k / 2, y + k / 2
        if result == MISS:
            Color(*MISS_COLOR)
            d = k * 0.24
            Ellipse(pos=(cx - d / 2, cy - d / 2), size=(d, d))
        else:
            Color(*HIT_COLOR)
            a = k * 0.30
            Line(points=[cx - a, cy - a, cx + a, cy + a], width=max(k * 0.07, 2), cap="round")
            Line(points=[cx - a, cy + a, cx + a, cy - a], width=max(k * 0.07, 2), cap="round")
