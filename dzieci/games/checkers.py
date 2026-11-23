"""Warcaby na planszy 8x8 dla dwóch graczy (białe zaczynają, Gracz 1 gra białymi od dołu).

Zasady (warcaby klasyczne, jak w polskich, na mniejszej planszy):
- pionek idzie o jedno pole po skosie do przodu, bije do przodu i do tyłu,
- bicie jest obowiązkowe, a po biciu pionek bije dalej, dopóki może (bicie wielokrotne),
- pionek, który zakończy ruch na ostatnim rzędzie, zostaje damką,
- damka chodzi i bije po skosie na dowolną odległość (damka "latająca"),
- zbite pionki znikają po zakończeniu ruchu i nie można ich przeskoczyć drugi raz,
- przegrywa gracz bez pionków albo bez możliwego ruchu.
Uproszczenie dla dzieci: nie trzeba wybierać bicia z największą liczbą zbitych pionków.

Gra z komputerem (1 gracz): dziecko gra białymi, komputer czarnymi na poziomie łatwym -
wybiera losowy dozwolony ruch, chętniej taki, po którym jego pionek zostaje damką.
"""
import random

from kivy.graphics import Color, Ellipse, Line, Rectangle

from dzieci.games.board import BoardWidget

N = 8
DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
NAMES = ["Gracz 1 (białe)", "Gracz 2 (czarne)"]
COMPUTER = 1                    # w grze z komputerem komputer gra czarnymi
LIGHT = (0.93, 0.85, 0.70, 1)
DARK = (0.55, 0.38, 0.24, 1)
PIECE = [(0.97, 0.96, 0.92, 1), (0.16, 0.16, 0.18, 1)]
RIM = [(0.60, 0.58, 0.52, 1), (0.45, 0.45, 0.48, 1)]
CROWN = (1.0, 0.78, 0.20, 1)
SELECT = (1.0, 0.85, 0.20, 1)
TARGET = (0.30, 0.80, 0.35, 0.85)
MOVABLE = (0.30, 0.80, 0.35, 1)


# --- zasady (bez Kivy) ----------------------------------------------------------------------
def initial():
    board = [[None] * N for _ in range(N)]
    for r in range(N):
        for c in range(N):
            if (r + c) % 2 == 1:
                if r < 3:
                    board[r][c] = (1, False)
                elif r > 4:
                    board[r][c] = (0, False)
    return board


def inside(r, c):
    return 0 <= r < N and 0 <= c < N


def forward(player):
    return -1 if player == 0 else 1


def _captures(board, r, c, piece, captured):
    """Wszystkie pełne sekwencje bicia z (r, c): listy kroków (lądowanie, zbity)."""
    player, king = piece
    result = []
    for dr, dc in DIRS:
        if king:
            rr, cc = r + dr, c + dc
            while inside(rr, cc) and board[rr][cc] is None:
                rr, cc = rr + dr, cc + dc
            if not inside(rr, cc) or (rr, cc) in captured or board[rr][cc][0] == player:
                continue
            victim = (rr, cc)
            landings = []
            lr, lc = rr + dr, cc + dc
            while inside(lr, lc) and board[lr][lc] is None:
                landings.append((lr, lc))
                lr, lc = lr + dr, lc + dc
        else:
            mr, mc, lr, lc = r + dr, c + dc, r + 2 * dr, c + 2 * dc
            if not inside(lr, lc) or board[lr][lc] is not None:
                continue
            if board[mr][mc] is None or board[mr][mc][0] == player or (mr, mc) in captured:
                continue
            victim = (mr, mc)
            landings = [(lr, lc)]
        for land in landings:
            step = (land, victim)
            more = _captures(board, land[0], land[1], piece, captured | {victim})
            if more:
                result.extend([[step] + seq for seq in more])
            else:
                result.append([step])
    return result


def legal_moves(board, player):
    """Ruchy gracza: listy pól [start, pole1, pole2, ...] z listą zbitych pionków.
    Gdy jest jakiekolwiek bicie, dozwolone są tylko bicia."""
    captures, simple = [], []
    for r in range(N):
        for c in range(N):
            piece = board[r][c]
            if piece is None or piece[0] != player:
                continue
            board[r][c] = None                  # pionek opuszcza pole na czas szukania
            for seq in _captures(board, r, c, piece, frozenset()):
                captures.append({"path": [(r, c)] + [s[0] for s in seq],
                                 "captured": [s[1] for s in seq]})
            board[r][c] = piece
            if captures:
                continue
            _, king = piece
            for dr, dc in DIRS:
                if not king and dr != forward(player):
                    continue
                rr, cc = r + dr, c + dc
                while inside(rr, cc) and board[rr][cc] is None:
                    simple.append({"path": [(r, c), (rr, cc)], "captured": []})
                    if not king:
                        break
                    rr, cc = rr + dr, cc + dc
    return captures if captures else simple


def apply(board, move):
    """Nowa plansza po ruchu (z promocją na damkę na ostatnim rzędzie)."""
    new = [row[:] for row in board]
    (r0, c0), (r1, c1) = move["path"][0], move["path"][-1]
    player, king = new[r0][c0]
    new[r0][c0] = None
    for r, c in move["captured"]:
        new[r][c] = None
    if not king and r1 == (0 if player == 0 else N - 1):
        king = True
    new[r1][c1] = (player, king)
    return new


# --- plansza na ekranie -----------------------------------------------------------------------
class Checkers(BoardWidget):
    SIZE = N

    def __init__(self, **kwargs):
        self.board = initial()
        self.player = 0
        self.moves = []
        self.selected = None        # pole wybranego pionka
        self.candidates = []        # ruchy wybranego pionka zgodne z dotychczasowymi krokami
        self.step = 0               # ile kroków bicia wielokrotnego już zrobiono
        self.finished = False
        super().__init__(**kwargs)
        self.new_game()

    def new_game(self, *_):
        self.board = initial()
        self.player = 0
        self.finished = False
        self._start_turn()

    def _name(self, player):
        if self.players == 1:
            return "Twój ruch (białe)" if player != COMPUTER else "Ruch komputera (czarne)"
        return f"Ruch: {NAMES[player]}"

    def _start_turn(self):
        self.selected, self.candidates, self.step = None, [], 0
        self.moves = legal_moves(self.board, self.player)
        if not self.moves:
            self.finished = True
            winner = 1 - self.player
            if self.players == 1:
                self.status = "Wygrywa komputer!" if winner == COMPUTER else "Wygrywasz! Brawo!"
            else:
                self.status = f"Wygrywa {NAMES[winner]}!"
        else:
            must = " - bicie obowiązkowe" if self.moves[0]["captured"] else ""
            self.status = self._name(self.player) + must
        self.redraw()
        self.schedule_ai()

    def computer_turn(self):
        return self.player == COMPUTER

    def ai_move(self):
        """Poziom łatwy: losowy dozwolony ruch, chętniej z promocją na damkę."""
        if self.finished or not self.moves:
            return
        last_row = N - 1 if self.player == 1 else 0
        promote = [m for m in self.moves if m["path"][-1][0] == last_row
                   and not self.board[m["path"][0][0]][m["path"][0][1]][1]]
        move = random.choice(promote if promote and random.random() < 0.7 else self.moves)
        self.board = apply(self.board, move)
        self.player = 1 - self.player
        self._start_turn()

    def tap(self, row, col):
        if self.finished:
            return
        if self.step == 0:
            own = [m for m in self.moves if m["path"][0] == (row, col)]
            if own:
                self.selected, self.candidates = (row, col), own
                self.redraw()
                return
        if self.selected is None:
            return
        nxt = [m for m in self.candidates if m["path"][self.step + 1] == (row, col)]
        if not nxt:
            return
        self.step += 1
        self.candidates = nxt
        done = [m for m in nxt if len(m["path"]) == self.step + 1]
        if done:
            self.board = apply(self.board, done[0])
            self.player = 1 - self.player
            self._start_turn()
        else:
            self.status = self._name(self.player) + " - bij dalej"
            self.redraw()

    def _current_square(self):
        """Pole wybranego pionka (w trakcie bicia wielokrotnego - pole po ostatnim skoku)."""
        return self.candidates[0]["path"][self.step] if self.candidates else self.selected

    def redraw(self):
        c = self.cell
        self.canvas.clear()
        captured = set()
        if self.step:
            captured = set(self.candidates[0]["captured"][:self.step])
        moving_from = self.selected if self.step else None
        here = self._current_square()
        with self.canvas:
            for r in range(N):
                for col in range(N):
                    Color(*(DARK if (r + col) % 2 else LIGHT))
                    Rectangle(pos=self.cell_pos(r, col), size=(c, c))
            if self.step == 0 and not self.finished:      # pionki, którymi można ruszyć
                Color(*MOVABLE)
                for start in {m["path"][0] for m in self.moves}:
                    x, y = self.cell_pos(*start)
                    Line(rectangle=(x + 2, y + 2, c - 4, c - 4), width=2)
            for r in range(N):
                for col in range(N):
                    piece = self.board[r][col]
                    if piece is None or (r, col) == moving_from:
                        continue
                    self._piece(r, col, piece, 0.35 if (r, col) in captured else 1.0)
            if moving_from is not None:
                self._piece(here[0], here[1], self.board[moving_from[0]][moving_from[1]], 1.0)
            if here is not None:
                Color(*SELECT)
                x, y = self.cell_pos(*here)
                Line(rectangle=(x + 3, y + 3, c - 6, c - 6), width=3)
                Color(*TARGET)                      # zielone kropki: dozwolone pola
                for target in {m["path"][self.step + 1] for m in self.candidates}:
                    cx, cy = self.cell_center(*target)
                    Ellipse(pos=(cx - c * 0.15, cy - c * 0.15), size=(c * 0.3, c * 0.3))

    def _piece(self, r, col, piece, alpha):
        player, king = piece
        c = self.cell
        cx, cy = self.cell_center(r, col)
        rad = c * 0.38
        Color(*RIM[player][:3], alpha)
        Ellipse(pos=(cx - rad, cy - rad), size=(2 * rad, 2 * rad))
        Color(*PIECE[player][:3], alpha)
        rad2 = rad * 0.86
        Ellipse(pos=(cx - rad2, cy - rad2), size=(2 * rad2, 2 * rad2))
        Color(*RIM[player][:3], alpha)
        Line(circle=(cx, cy, rad * 0.55), width=max(1, c * 0.02))
        if king:
            Color(*CROWN[:3], alpha)
            Line(circle=(cx, cy, rad * 0.35), width=max(2, c * 0.05))
