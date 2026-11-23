"""Wspólna podstawa gier planszowych: kwadratowa plansza wyśrodkowana w widżecie,
stukanie w pola, przeciąganie pionka palcem i tryb gry (1 gracz z komputerem / 2 graczy).

Przeciąganie: dotknięcie pionka wybiera go (jak stuknięcie) i pokazuje możliwe ruchy;
gdy palec przesunie się po ekranie, pionek jedzie za palcem, a puszczenie nad innym
polem działa jak stuknięcie w to pole (ruch, jeśli jest dozwolony).
"""
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.widget import Widget

AI_DELAY = 0.8          # s - komputer "myśli", żeby dziecko zobaczyło swój ruch


class BoardWidget(Widget):
    """Plansza SIZE x SIZE pól; status - napis pod planszą (czyj ruch, kto wygrał)."""
    SIZE = 8
    status = StringProperty("")
    players = NumericProperty(2)        # 1 - gra z komputerem, 2 - dwóch graczy

    def __init__(self, **kwargs):
        self.drag_from = None           # pole przeciąganego pionka
        self.drag_xy = None             # pozycja palca przy przeciąganiu
        self._ai_event = None
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    # --- geometria ----------------------------------------------------------------------
    @property
    def side(self) -> float:
        return min(self.width, self.height) * 0.98

    @property
    def origin(self):
        return (self.center_x - self.side / 2, self.center_y - self.side / 2)

    @property
    def cell(self) -> float:
        return self.side / self.SIZE

    def cell_pos(self, row: int, col: int):
        """Lewy dolny róg pola; wiersz 0 jest na górze planszy."""
        x0, y0 = self.origin
        return x0 + col * self.cell, y0 + (self.SIZE - 1 - row) * self.cell

    def cell_center(self, row: int, col: int):
        x, y = self.cell_pos(row, col)
        return x + self.cell / 2, y + self.cell / 2

    def cell_at(self, x: float, y: float):
        """(wiersz, kolumna) pola pod palcem albo None poza planszą."""
        x0, y0 = self.origin
        if x < x0 or y < y0:
            return None
        col = int((x - x0) // self.cell)
        row = self.SIZE - 1 - int((y - y0) // self.cell)
        if 0 <= row < self.SIZE and 0 <= col < self.SIZE:
            return row, col
        return None

    # --- dotyk: stuknięcie i przeciąganie ---------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        pos = self.cell_at(*touch.pos)
        if pos is not None and self.human_turn():
            self.tap(*pos)
            if self.can_drag(*pos):
                touch.grab(self)
                touch.ud["board_from"] = pos
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        start = touch.ud.get("board_from")
        if start is not None and self.can_drag(*start):
            self.drag_from, self.drag_xy = start, touch.pos
            self.redraw_drag()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        start = touch.ud.get("board_from")
        dragged = self.drag_from is not None
        self.drag_from = self.drag_xy = None
        pos = self.cell_at(*touch.pos)
        if dragged and pos is not None and pos != start:
            self.tap(*pos)
        self.redraw()                   # pionek wraca na pole, gdy ruch był niedozwolony
        return True

    # --- tryb gry i komputer ------------------------------------------------------------------
    def on_players(self, *_):
        self.new_game()

    def human_turn(self) -> bool:
        return self.players == 2 or not self.computer_turn()

    def schedule_ai(self):
        """Wołane na początku każdej tury: w grze z komputerem jego ruch po AI_DELAY s."""
        if self._ai_event is not None:
            self._ai_event.cancel()
            self._ai_event = None
        if self.players == 1 and self.computer_turn() and not self.finished:
            self._ai_event = Clock.schedule_once(lambda _dt: self.ai_move(), AI_DELAY)

    # --- do nadpisania ----------------------------------------------------------------
    finished = False

    def new_game(self, *_):
        raise NotImplementedError

    def tap(self, row: int, col: int):
        raise NotImplementedError

    def can_drag(self, row: int, col: int) -> bool:
        return False

    def computer_turn(self) -> bool:
        return False

    def ai_move(self):
        pass

    def _redraw(self, *_):
        self.redraw()

    def redraw(self):
        raise NotImplementedError

    def redraw_drag(self):
        self.redraw()
