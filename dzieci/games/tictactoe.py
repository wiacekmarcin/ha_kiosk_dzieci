"""Kółko i krzyżyk: Gracz 1 stawia krzyżyki, Gracz 2 kółka. Trzy znaki w wierszu,
kolumnie albo po skosie wygrywają; pełna plansza bez trójki to remis. Po końcu partii
nowa gra zaczyna się sama po RESTART_SECONDS.

Tryby: dwóch graczy na jednym tablecie albo gra przez sieć z innym tabletem (krzyżykami
gra tablet, który zaprosił). Ruch w sieci to numer pola 0-8."""
from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle

from dzieci.games.board import BoardWidget

RESTART_SECONDS = 3
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
BOARD = (0.98, 0.97, 0.93, 1)
GRID = (0.30, 0.34, 0.48, 1)
X_COLOR = (0.85, 0.27, 0.27, 1)
O_COLOR = (0.20, 0.45, 0.85, 1)
WIN = (1.0, 0.62, 0.18, 1)


def winner(cells):
    """(znak, linia) zwycięzcy albo (None, None)."""
    for line in LINES:
        a, b, c = (cells[i] for i in line)
        if a is not None and a == b == c:
            return a, line
    return None, None


class TicTacToe(BoardWidget):
    SIZE = 3
    GAME = "tictactoe"
    SIDE_NAMES = ("krzyżyk", "kółko")

    def __init__(self, **kwargs):
        self.cells = [None] * 9
        self.player = 0
        self.win_line = None
        self.finished = False
        self._restart = None
        super().__init__(**kwargs)
        self.new_game()

    def new_game(self, *_):
        if self._restart is not None:
            self._restart.cancel()
            self._restart = None
        self.cells = [None] * 9
        self.player = 0
        self.win_line = None
        self.finished = False
        self.refresh_status()
        self.redraw()

    def current_side(self):
        return self.player

    def refresh_status(self):
        if not self.finished:
            self.status = self.turn_text(self.player)

    def tap(self, row, col):
        i = row * 3 + col
        if self.finished or self.cells[i] is not None:
            return
        self.send([i])
        self._place(i)

    def remote_move(self, move):
        if not self.finished and not self.human_turn() and self.cells[move[0]] is None:
            self._place(move[0])

    def _place(self, i):
        self.cells[i] = self.player
        mark, line = winner(self.cells)
        if mark is not None:
            self.win_line = line
            self.status = self.winner_text(mark)
            self._finish()
        elif all(c is not None for c in self.cells):
            self.status = "Remis!"
            self._finish()
        else:
            self.player = 1 - self.player
            self.refresh_status()
        self.redraw()

    def _finish(self):
        self.finished = True
        # nowa partia sama, także w grze sieciowej (obie strony liczą ten sam czas)
        self._restart = Clock.schedule_once(self.new_game, RESTART_SECONDS)

    def computer_turn(self):
        return False                    # w kółko i krzyżyk bez gry z komputerem

    def redraw(self):
        c = self.cell
        x0, y0 = self.origin
        self.canvas.clear()
        with self.canvas:
            Color(*BOARD)
            RoundedRectangle(pos=(x0, y0), size=(self.side, self.side), radius=[c * 0.12])
            if self.win_line:
                Color(*WIN[:3], 0.35)
                for i in self.win_line:
                    Rectangle(pos=self.cell_pos(i // 3, i % 3), size=(c, c))
            Color(*GRID)
            w = max(2, c * 0.04)
            for k in (1, 2):
                Line(points=[x0 + k * c, y0 + c * 0.08, x0 + k * c, y0 + self.side - c * 0.08], width=w, cap="round")
                Line(points=[x0 + c * 0.08, y0 + k * c, x0 + self.side - c * 0.08, y0 + k * c], width=w, cap="round")
            for i, mark in enumerate(self.cells):
                if mark is None:
                    continue
                cx, cy = self.cell_center(i // 3, i % 3)
                r = c * 0.30
                if mark == 0:
                    Color(*X_COLOR)
                    Line(points=[cx - r, cy - r, cx + r, cy + r], width=c * 0.06, cap="round")
                    Line(points=[cx - r, cy + r, cx + r, cy - r], width=c * 0.06, cap="round")
                else:
                    Color(*O_COLOR)
                    Line(circle=(cx, cy, r), width=c * 0.06)
            if self.win_line:
                a, b = self.win_line[0], self.win_line[2]
                ax, ay = self.cell_center(a // 3, a % 3)
                bx, by = self.cell_center(b // 3, b % 3)
                Color(*WIN)
                Line(points=[ax, ay, bx, by], width=c * 0.05, cap="round")
