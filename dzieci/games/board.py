"""Wspólna podstawa gier planszowych: kwadratowa plansza wyśrodkowana w widżecie,
stukanie w pola i tryb gry.

Ruch zawsze dwoma stuknięciami: stuknięcie pionka pokazuje zielone kropki na dozwolonych
polach, stuknięcie w pole z kropką przesuwa pionek (bez przeciągania palcem).

Tryby (players): 2 - dwóch graczy na jednym tablecie, 1 - gra z komputerem (poziom łatwy),
0 - gra przez sieć z innym tabletem (przez Home Assistant, moduł net). W grze sieciowej
zapraszający gra stroną 0 (białe, krzyżyk), przyjmujący stroną 1; każdy tablet stuka tylko
w swojej kolejce, a ruch wysyła drugiemu tabletowi.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

AI_DELAY = 0.8          # s - komputer "myśli", żeby dziecko zobaczyło swój ruch
GAMES = {}              # nazwa gry -> widżet planszy (dla komunikatów z sieci)
NETWORK = 0


class BoardWidget(Widget):
    """Plansza SIZE x SIZE pól; status - napis pod planszą (czyj ruch, kto wygrał)."""
    SIZE = 8
    GAME = ""                           # nazwa gry w komunikatach sieciowych
    SIDE_NAMES = ("białe", "czarne")
    status = StringProperty("")
    players = NumericProperty(2)        # 1 - z komputerem, 2 - dwóch graczy, 0 - przez sieć
    my_side = NumericProperty(0)        # gra sieciowa: którą stroną gra ten tablet
    net_ready = BooleanProperty(False)  # gra sieciowa: drugi tablet przyjął zaproszenie
    peer = StringProperty("")           # gra sieciowa: nazwa tabletu przeciwnika

    def __init__(self, **kwargs):
        self._ai_event = None
        self._joining = False
        super().__init__(**kwargs)
        if self.GAME:
            GAMES[self.GAME] = self
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

    # --- dotyk: tylko stuknięcia ------------------------------------------------------------
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        pos = self.cell_at(*touch.pos)
        if pos is not None and self.human_turn():
            self.tap(*pos)
        return True

    # --- tryby gry ----------------------------------------------------------------------
    def on_players(self, *_):
        if self._joining:
            return
        self.leave_network()
        self.new_game()
        if self.players == NETWORK:
            self.invite()

    def restart(self):
        """Przycisk "Nowa gra": w grze sieciowej nowe zaproszenie."""
        self.leave_network()
        self.new_game()
        if self.players == NETWORK:
            self.invite()

    def human_turn(self) -> bool:
        if self.players == NETWORK:
            return self.net_ready and self.current_side() == self.my_side
        return self.players == 2 or not self.computer_turn()

    def computer_turn(self) -> bool:
        return self.players == 1 and self.current_side() == 1

    def schedule_ai(self):
        """Wołane na początku każdej tury: w grze z komputerem jego ruch po AI_DELAY s."""
        if self._ai_event is not None:
            self._ai_event.cancel()
            self._ai_event = None
        if self.computer_turn() and not self.finished:
            self._ai_event = Clock.schedule_once(lambda _dt: self.ai_move(), AI_DELAY)

    def turn_text(self, side: int) -> str:
        """Napis o kolejce dla danej strony, zależnie od trybu gry."""
        color = self.SIDE_NAMES[side]
        if self.players == NETWORK:
            if not self.net_ready:
                return "Czekam, aż drugi tablet przyjmie zaproszenie…"
            return f"Twój ruch ({color})" if side == self.my_side else f"Ruch: {self.peer} ({color})"
        if self.players == 1:
            return f"Twój ruch ({color})" if side == 0 else f"Ruch komputera ({color})"
        return f"Ruch: Gracz {side + 1} ({color})"

    def winner_text(self, side: int) -> str:
        if self.players == NETWORK:
            return "Wygrywasz! Brawo!" if side == self.my_side else f"Wygrywa {self.peer}"
        if self.players == 1:
            return "Wygrywasz! Brawo!" if side == 0 else "Wygrywa komputer"
        return f"Wygrywa Gracz {side + 1} ({self.SIDE_NAMES[side]})"

    # --- gra przez sieć -------------------------------------------------------------------
    @staticmethod
    def net():
        app = App.get_running_app()
        return getattr(app, "net", None)

    def invite(self):
        net = self.net()
        self.my_side, self.net_ready, self.peer = 0, False, ""
        if net is None:
            self.status = "Gra przez sieć wymaga połączenia z Home Assistant"
            return
        net.invite(self.GAME)
        self.refresh_status()

    def join(self, peer: str):
        """Ten tablet przyjął zaproszenie: gra stroną 1."""
        self._joining = True
        self.players = NETWORK
        self._joining = False
        self.new_game()
        self.my_side, self.peer, self.net_ready = 1, peer, True
        self.refresh_status()

    def accepted(self, peer: str):
        """Drugi tablet przyjął moje zaproszenie."""
        self.peer, self.net_ready = peer, True
        self.refresh_status()

    def leave_network(self):
        net = self.net()
        if net is not None and net.session and getattr(net, "game", self.GAME) == self.GAME:
            net.leave(self.GAME)
        self.net_ready, self.peer = False, ""

    def peer_left(self, text: str):
        self.net_ready = False
        self.status = text

    def send(self, move):
        """Ruch tego tabletu w grze sieciowej idzie do drugiego tabletu."""
        if self.players == NETWORK:
            net = self.net()
            if net is not None:
                net.send_move(self.GAME, move)

    # --- do nadpisania ----------------------------------------------------------------
    finished = False

    def new_game(self, *_):
        raise NotImplementedError

    def tap(self, row: int, col: int):
        raise NotImplementedError

    def current_side(self) -> int:
        return 0

    def refresh_status(self):
        pass

    def remote_move(self, move):
        pass

    def ai_move(self):
        pass

    def _redraw(self, *_):
        self.redraw()

    def redraw(self):
        raise NotImplementedError
