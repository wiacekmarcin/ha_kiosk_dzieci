"""Szachy dla dwóch graczy na jednym tablecie (Gracz 1 - białe, od dołu).

Pełne zasady ruchu: roszada (gdy król i wieża się nie ruszały, pola między nimi są
puste, a król nie jest szachowany ani nie przechodzi przez atakowane pole), bicie
w przelocie, promocja piona (zawsze na hetmana), zakaz ruchu odsłaniającego własnego
króla. Koniec gry: mat (wygrywa gracz, który go dał) albo pat (remis).
Figury rysowane znakami Unicode z czcionki DejaVu Sans (assets/fonts_dzieci).

Gra z komputerem (1 gracz): dziecko gra białymi, komputer czarnymi na poziomie łatwym -
zwykle zbija najcenniejszą figurę, jaką może, a poza tym gra losowo (nie liczy wariantów).
Gra przez sieć: ruch wysyłany jako [r0, c0, r1, c1].
"""
import random
from pathlib import Path

from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.uix.label import Label

from dzieci.games.board import BoardWidget

N = 8
FONT = str(Path(__file__).resolve().parents[2] / "assets" / "fonts_dzieci" / "DejaVuSans.ttf")
GLYPH = {"K": "♚", "Q": "♛", "R": "♜", "B": "♝", "N": "♞", "P": "♟"}
VALUE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
CAPTURE_CHANCE = 0.7            # poziom łatwy: nie zawsze zauważa bicie
LIGHT = (0.93, 0.85, 0.70, 1)
DARK = (0.55, 0.38, 0.24, 1)
LAST = (1.0, 0.85, 0.20, 0.35)
SELECT = (1.0, 0.85, 0.20, 1)
TARGET = (0.30, 0.80, 0.35, 0.85)
CHECK = (0.90, 0.20, 0.20, 0.6)
KNIGHT = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
KING = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
ROOK = [(-1, 0), (1, 0), (0, -1), (0, 1)]
BISHOP = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


# --- zasady (bez Kivy) ----------------------------------------------------------------------
def other(color):
    return "b" if color == "w" else "w"


def inside(r, c):
    return 0 <= r < N and 0 <= c < N


def initial():
    back = "RNBQKBNR"
    board = [[None] * N for _ in range(N)]
    for c in range(N):
        board[0][c] = ("b", back[c])
        board[1][c] = ("b", "P")
        board[6][c] = ("w", "P")
        board[7][c] = ("w", back[c])
    return {"board": board, "turn": "w", "castle": {"wK", "wQ", "bK", "bQ"}, "ep": None}


def attacked(board, r, c, by):
    """Czy pole (r, c) jest atakowane przez kolor by."""
    pawn_row = r + (1 if by == "w" else -1)       # biały pion atakuje w górę planszy
    for dc in (-1, 1):
        if inside(pawn_row, c + dc) and board[pawn_row][c + dc] == (by, "P"):
            return True
    for dr, dc in KNIGHT:
        if inside(r + dr, c + dc) and board[r + dr][c + dc] == (by, "N"):
            return True
    for dr, dc in KING:
        if inside(r + dr, c + dc) and board[r + dr][c + dc] == (by, "K"):
            return True
    for dirs, kinds in ((ROOK, ("R", "Q")), (BISHOP, ("B", "Q"))):
        for dr, dc in dirs:
            rr, cc = r + dr, c + dc
            while inside(rr, cc):
                piece = board[rr][cc]
                if piece is not None:
                    if piece[0] == by and piece[1] in kinds:
                        return True
                    break
                rr, cc = rr + dr, cc + dc
    return False


def king_pos(board, color):
    for r in range(N):
        for c in range(N):
            if board[r][c] == (color, "K"):
                return r, c
    return None


def in_check(state, color):
    pos = king_pos(state["board"], color)
    return pos is not None and attacked(state["board"], pos[0], pos[1], other(color))


def pseudo_moves(state, color):
    """Ruchy zgodne z ruchem figur, bez sprawdzania szacha: (r0, c0, r1, c1, rodzaj)."""
    board, moves = state["board"], []
    for r in range(N):
        for c in range(N):
            piece = board[r][c]
            if piece is None or piece[0] != color:
                continue
            kind = piece[1]
            if kind == "P":
                d = -1 if color == "w" else 1
                start = 6 if color == "w" else 1
                if inside(r + d, c) and board[r + d][c] is None:
                    moves.append((r, c, r + d, c, "move"))
                    if r == start and board[r + 2 * d][c] is None:
                        moves.append((r, c, r + 2 * d, c, "double"))
                for dc in (-1, 1):
                    rr, cc = r + d, c + dc
                    if not inside(rr, cc):
                        continue
                    if board[rr][cc] is not None and board[rr][cc][0] != color:
                        moves.append((r, c, rr, cc, "move"))
                    elif state["ep"] == (rr, cc):
                        moves.append((r, c, rr, cc, "ep"))
            elif kind in ("N", "K"):
                for dr, dc in (KNIGHT if kind == "N" else KING):
                    rr, cc = r + dr, c + dc
                    if inside(rr, cc) and (board[rr][cc] is None or board[rr][cc][0] != color):
                        moves.append((r, c, rr, cc, "move"))
            else:
                dirs = {"R": ROOK, "B": BISHOP, "Q": ROOK + BISHOP}[kind]
                for dr, dc in dirs:
                    rr, cc = r + dr, c + dc
                    while inside(rr, cc):
                        if board[rr][cc] is None:
                            moves.append((r, c, rr, cc, "move"))
                        else:
                            if board[rr][cc][0] != color:
                                moves.append((r, c, rr, cc, "move"))
                            break
                        rr, cc = rr + dr, cc + dc
    # roszada
    row = 7 if color == "w" else 0
    if board[row][4] == (color, "K") and not attacked(board, row, 4, other(color)):
        if (color + "K") in state["castle"] and board[row][7] == (color, "R") \
                and board[row][5] is None and board[row][6] is None \
                and not attacked(board, row, 5, other(color)):
            moves.append((row, 4, row, 6, "castle"))
        if (color + "Q") in state["castle"] and board[row][0] == (color, "R") \
                and board[row][1] is None and board[row][2] is None and board[row][3] is None \
                and not attacked(board, row, 3, other(color)):
            moves.append((row, 4, row, 2, "castle"))
    return moves


def make_move(state, move):
    r0, c0, r1, c1, kind = move
    board = [row[:] for row in state["board"]]
    piece = board[r0][c0]
    color = piece[0]
    board[r0][c0] = None
    if kind == "ep":
        board[r0][c1] = None
    if kind == "castle":
        if c1 == 6:
            board[r0][5], board[r0][7] = board[r0][7], None
        else:
            board[r0][3], board[r0][0] = board[r0][0], None
    if piece[1] == "P" and r1 in (0, N - 1):
        piece = (color, "Q")
    board[r1][c1] = piece
    castle = set(state["castle"])
    if piece[1] == "K":
        castle -= {color + "K", color + "Q"}
    for (r, c), right in (((7, 0), "wQ"), ((7, 7), "wK"), ((0, 0), "bQ"), ((0, 7), "bK")):
        if (r0, c0) == (r, c) or (r1, c1) == (r, c):
            castle.discard(right)
    ep = ((r0 + r1) // 2, c0) if kind == "double" else None
    return {"board": board, "turn": other(color), "castle": castle, "ep": ep}


def legal_moves(state):
    color = state["turn"]
    return [m for m in pseudo_moves(state, color) if not in_check(make_move(state, m), color)]


# --- plansza na ekranie -----------------------------------------------------------------------
class Chess(BoardWidget):
    SIZE = N
    GAME = "chess"
    DOT = True                  # kolor strony jako kółko obok napisu

    def __init__(self, **kwargs):
        self.state = initial()
        self.moves = []
        self.selected = None
        self.last = None
        self.finished = False
        self._labels = {}
        self.taken, self._taken_labels = [], []     # zbite figury i ich napisy z boku
        super().__init__(**kwargs)
        self.new_game()

    def new_game(self, *_):
        self.state = initial()
        self.taken = []
        self.last = None
        self.finished = False
        self._start_turn()

    def current_side(self):
        return 0 if self.state["turn"] == "w" else 1

    def refresh_status(self):
        if self.finished:
            return
        check = in_check(self.state, self.state["turn"])
        self.status = self.turn_text(self.current_side()) + (" - szach!" if check else "")

    def _start_turn(self):
        self.selected = None
        self.moves = legal_moves(self.state)
        if not self.moves:
            self.finished = True
            if in_check(self.state, self.state["turn"]):
                self.status = "Szach mat! " + self.winner_text(1 - self.current_side())
                self.game_over(1 - self.current_side())
            else:
                self.status = "Pat - remis"
                self.game_over(None)
        else:
            self.refresh_status()
        self.redraw()
        self.schedule_ai()

    def _play(self, move):
        board = self.state["board"]
        victim = board[move[0]][move[3]] if move[4] == "ep" else board[move[2]][move[3]]
        if victim is not None:          # zbita figura - na listę z boku planszy
            self.taken.append(victim)
        self.state = make_move(self.state, move)
        self.last = ((move[0], move[1]), (move[2], move[3]))
        self._start_turn()

    def ai_move(self):
        """Poziom łatwy: zwykle bije najcenniejszą figurę, a poza tym ruch losowy."""
        if self.finished or not self.moves:
            return
        board = self.state["board"]
        captures = [m for m in self.moves if board[m[2]][m[3]] is not None or m[4] == "ep"]
        if captures and random.random() < CAPTURE_CHANCE:
            best = max(VALUE[board[m[2]][m[3]][1]] if board[m[2]][m[3]] else 1 for m in captures)
            move = random.choice([m for m in captures
                                  if (VALUE[board[m[2]][m[3]][1]] if board[m[2]][m[3]] else 1) == best])
        else:
            move = random.choice(self.moves)
        self._play(move)

    def remote_move(self, move):
        """Ruch drugiego tabletu: [r0, c0, r1, c1]."""
        if self.finished or self.human_turn():
            return
        for m in self.moves:
            if list(m[:4]) == list(move[:4]):
                self._play(m)
                return

    def tap(self, row, col):
        if self.finished:
            return
        if self.selected is not None:
            for m in self.moves:
                if (m[0], m[1]) == self.selected and (m[2], m[3]) == (row, col):
                    self.send(m[:4])
                    self._play(m)
                    return
        if any((m[0], m[1]) == (row, col) for m in self.moves):
            self.selected = (row, col)
        else:
            self.selected = None
        self.redraw()
    def redraw(self):
        c = self.cell
        board = self.state["board"]
        self.canvas.before.clear()
        with self.canvas.before:
            for r in range(N):
                for col in range(N):
                    Color(*(DARK if (r + col) % 2 else LIGHT))
                    Rectangle(pos=self.cell_pos(r, col), size=(c, c))
            if self.last:
                Color(*LAST)
                for sq in self.last:
                    Rectangle(pos=self.cell_pos(*sq), size=(c, c))
            color = self.state["turn"]
            if in_check(self.state, color):
                Color(*CHECK)
                Rectangle(pos=self.cell_pos(*king_pos(board, color)), size=(c, c))
            if self.selected is not None:
                Color(*SELECT)
                x, y = self.cell_pos(*self.selected)
                Line(rectangle=(x + 3, y + 3, c - 6, c - 6), width=3)
        for lbl in self._labels.values():
            self.remove_widget(lbl)
        self._labels = {}
        for r in range(N):
            for col in range(N):
                piece = board[r][col]
                if piece is None:
                    continue
                white = piece[0] == "w"
                lbl = Label(text=GLYPH[piece[1]], font_name=FONT, font_size=c * 0.78,
                            color=(1, 1, 1, 1) if white else (0.10, 0.10, 0.12, 1),
                            outline_width=max(1, int(c * 0.03)),
                            outline_color=(0.10, 0.10, 0.12) if white else (0.85, 0.85, 0.85),
                            size=(c, c), pos=self.cell_pos(r, col))
                self.add_widget(lbl)
                self._labels[(r, col)] = lbl
        self.canvas.after.clear()
        if self.show_hints and self.selected is not None:
            with self.canvas.after:
                Color(*TARGET)
                for m in self.moves:
                    if (m[0], m[1]) == self.selected:
                        cx, cy = self.cell_center(m[2], m[3])
                        # zielona kropka: pole, na które może pójść wybrana figura
                        Ellipse(pos=(cx - c * 0.14, cy - c * 0.14), size=(c * 0.28, c * 0.28))
        self._draw_taken()

    def _draw_taken(self):
        """Zbite figury z boku planszy: białe po lewej, czarne po prawej (od najcenniejszej)."""
        for lbl in self._taken_labels:
            self.remove_widget(lbl)
        self._taken_labels = []
        x0, y0 = self.origin
        room = x0 - self.x - 12
        if room < 30:
            return
        s = min(self.cell * 0.72, room / 2)
        for color, left in (("w", self.x + 6), ("b", x0 + self.side + 6)):
            pieces = sorted((p for p in self.taken if p[0] == color), key=lambda p: -VALUE[p[1]])
            if pieces:                  # jasne tło jak plansza - czarne figury widoczne
                rows = (len(pieces) + 1) // 2
                with self.canvas.before:
                    Color(*LIGHT)
                    RoundedRectangle(pos=(left - 4, y0 + self.side - rows * s - 4),
                                     size=(2 * s + 8, rows * s + 8), radius=[10])
            for i, piece in enumerate(pieces):
                white = color == "w"
                lbl = Label(text=GLYPH[piece[1]], font_name=FONT, font_size=s * 0.8,
                            color=(1, 1, 1, 1) if white else (0.10, 0.10, 0.12, 1),
                            outline_width=max(1, int(s * 0.03)),
                            outline_color=(0.10, 0.10, 0.12) if white else (0.85, 0.85, 0.85),
                            size=(s, s),
                            pos=(left + (i % 2) * s, y0 + self.side - (i // 2 + 1) * s))
                self.add_widget(lbl)
                self._taken_labels.append(lbl)
