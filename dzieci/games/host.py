"""Część aplikacji wspólna dla tabletów z grami (Kiosk dzieci, HA Intercom).

GamesHost to mieszanka dla klasy App: łączy gry z siecią (GameNet przez Home Assistant),
pokazuje okno zaproszenia od innego tabletu, przekazuje ruchy do planszy i obsługuje
przyciski tabletu (Wstecz, Menu): systemowo tylko na ekranie startowym, w grach nic nie
robią. Aplikacja musi mieć metodę nav(cel) i ScreenManager w self.root.ids.sm.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.graphics import Color, RoundedRectangle
from kivy.logger import Logger
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

from dzieci.games.board import GAMES, NETWORK
from dzieci.games.net import GameNet
from dzieci.games.direct import DirectNet
from dzieci.games import endgame

# kolejność gier jak w siatce gier - dla przycisków Poprzednia / Następna
GAME_SCREENS = ("tictactoe", "checkers", "chess", "paint", "dice", "dots", "ships", "pdots",
                "tetris", "snake", "football")
TITLES = {"tictactoe": "kółko i krzyżyk", "checkers": "warcaby", "chess": "szachy",
          "dots": "kropki", "ships": "statki", "pdots": "polskie kropki",
          "football": "piłkarzyki"}
# Material Design Icons: chevron-left, chevron-right
PREV_GLYPH, NEXT_GLYPH = 0xF0141, 0xF0142


class GameBar(BoxLayout):
    """Belka u góry gry (wygląd w gry.kv): Wstecz, tytuł, przyciski gry, a na drugim końcu
    Poprzednia i Następna gra - dokładane po przyciskach z ekranu gry."""
    title = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_once(self._add_nav)

    def _add_nav(self, _dt):
        for code, step in ((PREV_GLYPH, -1), (NEXT_GLYPH, 1)):
            button = Factory.NavButton(code=code)
            button.bind(on_release=lambda _b, s=step: self.go(s))
            self.add_widget(button)

    @staticmethod
    def go(step: int):
        app = App.get_running_app()
        current = app.root.ids.sm.current
        if current in GAME_SCREENS:
            i = GAME_SCREENS.index(current)
            app.nav(GAME_SCREENS[(i + step) % len(GAME_SCREENS)])


INVITE_SECONDS = 60     # tyle czeka okno zaproszenia
CONNECTION_SECONDS = 12
# przyciski tabletu: 27 - Wstecz (Esc na PC), 319 i 1073741942 - Menu (Kivy / SDL)
HARDWARE_KEYS = {27, 319, 1073741942}


class InvitePopup(ModalView):
    """Okno "Tablet X zaprasza do gry w szachy" z przyciskami Graj i Nie."""
    def __init__(self, msg, on_answer, **kwargs):
        super().__init__(size_hint=(None, None), size=(640, 320), auto_dismiss=False,
                         background_color=(0, 0, 0, 0.6), **kwargs)
        self.msg, self.on_answer = msg, on_answer
        box = BoxLayout(orientation="vertical", padding=28, spacing=24)
        with box.canvas.before:
            Color(0.16, 0.19, 0.29, 1)
            self._bg = RoundedRectangle(radius=[28])
        box.bind(pos=lambda w, v: setattr(self._bg, "pos", v),
                 size=lambda w, v: setattr(self._bg, "size", v))
        game = TITLES.get(msg.get("game"), msg.get("game", "grę"))
        box.add_widget(Label(text=f"{msg.get('from', 'Inny tablet')}\nzaprasza do gry: {game}",
                             font_size="32sp", bold=True, halign="center",
                             color=(1.0, 0.84, 0.40, 1)))
        row = BoxLayout(spacing=24, size_hint_y=None, height=96)
        for text, ok, color in (("Graj", True, (0.25, 0.70, 0.25, 1)),
                                ("Nie", False, (0.45, 0.45, 0.50, 1))):
            b = Button(text=text, font_size="34sp", bold=True, background_normal="",
                       background_color=color)
            b.bind(on_release=lambda _b, ok=ok: self.answer(ok))
            row.add_widget(b)
        box.add_widget(row)
        self.add_widget(box)
        self._timeout = Clock.schedule_once(lambda _dt: self.answer(False, silent=True),
                                            INVITE_SECONDS)

    def answer(self, ok, silent=False):
        self._timeout.cancel()
        self.dismiss()
        self.on_answer(self.msg, ok, silent)


class NetworkWaitPopup(ModalView):
    """Oczekiwanie inicjatora na drugiego gracza; Przerwij wraca do gry lokalnej."""
    def __init__(self, on_cancel, **kwargs):
        super().__init__(size_hint=(None, None), size=(640, 300), auto_dismiss=False,
                         background_color=(0, 0, 0, 0.6), **kwargs)
        box = BoxLayout(orientation="vertical", padding=28, spacing=24)
        box.add_widget(Label(text="Trwa oczekiwanie na drugiego gracza",
                             font_size="32sp", bold=True, halign="center",
                             color=(1.0, 0.84, 0.40, 1)))
        button = Button(text="Przerwij", font_size="34sp", bold=True, background_normal="",
                        background_color=(0.45, 0.45, 0.50, 1), size_hint_y=None, height=96)
        button.bind(on_release=lambda _button: self.cancel())
        box.add_widget(button)
        self.add_widget(box)
        self._on_cancel = on_cancel

    def cancel(self):
        self.dismiss()
        self._on_cancel()


class NetworkSidePopup(ModalView):
    """Wybór koloru pionków lub figur przez gracza rozpoczynającego grę."""
    def __init__(self, on_select, **kwargs):
        super().__init__(size_hint=(None, None), size=(640, 320), auto_dismiss=False,
                         background_color=(0, 0, 0, 0.6), **kwargs)
        box = BoxLayout(orientation="vertical", padding=28, spacing=24)
        box.add_widget(Label(text="Wybierz kolor", font_size="32sp", bold=True,
                             color=(1.0, 0.84, 0.40, 1)))
        row = BoxLayout(spacing=24, size_hint_y=None, height=96)
        for text, side in (("Białe", 0), ("Czarne", 1)):
            button = Button(text=text, font_size="34sp", bold=True, background_normal="",
                            background_color=(0.25, 0.70, 0.25, 1))
            button.bind(on_release=lambda _button, selected=side: self.select(selected))
            row.add_widget(button)
        box.add_widget(row)
        self.add_widget(box)
        self._on_select = on_select

    def select(self, side):
        self.dismiss()
        self._on_select(side)


class GamesHost:
    net = None                          # gra przez Home Assistant (GameNet)
    direct = None                       # gra bezpośrednio między tabletami (DirectNet)
    _invite = None

    def setup_games(self, settings: dict, name: str):
        """Wołać w build(): sieć gier przez HA (gdy jest adres i token), gra bezpośrednia
        (zawsze, także bez HA) i przyciski tabletu."""
        if settings.get("url") and settings.get("token"):
            # Kiosk Center (połączenie z VoiceLink): gdy działa, gra idzie przez centrum
            center = getattr(getattr(self, "voice", None), "center", None)
            self.net = GameNet(settings, name, self.on_game_event, center=center)
        try:
            self.direct = DirectNet(name, self.on_game_event)
        except OSError as e:
            Logger.warning(f"Gra bezpośrednia niedostępna: {e}")
        self._waiting_popup = None
        self._waiting_board = None
        self._side_popup = None
        self._ready_timeout = None
        self._join_pending = None
        self._join_timeout = None
        Window.bind(on_keyboard=self._games_key)

    def transport(self, msg: dict):
        """Połączenie, którym przyszedł komunikat."""
        return self.direct if msg.get("_via") == "direct" else self.net

    def choose_network_side(self, board, link: str):
        """Pokaż wybór strony przed wysłaniem zaproszenia do warcabów lub szachów."""
        def selected(side):
            self._side_popup = None
            self.activate_game_mode(board, NETWORK, link, False, side)

        self._side_popup = NetworkSidePopup(selected)
        self._side_popup.open()

    def activate_game_mode(self, board, players: int, link: str, choose_side: bool,
                           side: int = 0):
        if choose_side:
            self.choose_network_side(board, link)
            return
        net = board.net()
        previous_session = getattr(net, "session", None)
        board.set_mode(players, link, side)
        net = board._used or board.net()
        if players == NETWORK and net is not None and net.session \
                and net.session != previous_session:
            self._show_waiting(board)

    def _show_waiting(self, board):
        if self._waiting_board is board:
            return
        self._close_waiting()
        self._waiting_board = board
        self._waiting_popup = NetworkWaitPopup(lambda: self._cancel_waiting(board))
        self._waiting_popup.open()

    def _resolve_invite_collision(self, msg, net):
        board = self._waiting_board
        if board is None or board.GAME != msg.get("game") \
                or (board._used or board.net()) is not net:
            return False

        local_key = (str(net.name).casefold(), str(net.session or ""))
        remote_key = (str(msg.get("from", "")).casefold(), str(msg.get("session", "")))
        if local_key < remote_key:
            return True

        self._close_waiting(board)
        board.return_to_local_mode()
        if net is self.direct:
            self._answer_invite(msg, True, silent=True)
        elif self._invite is None:
            self._invite = InvitePopup(msg, self._answer_invite)
            self._invite.open()
        return True

    def _close_waiting(self, board=None):
        if board is not None and self._waiting_board is not board:
            return
        if self._ready_timeout is not None:
            self._ready_timeout.cancel()
            self._ready_timeout = None
        popup, self._waiting_popup = self._waiting_popup, None
        self._waiting_board = None
        if popup is not None:
            popup.dismiss()

    def _cancel_waiting(self, board):
        if self._waiting_board is not board:
            return
        self._close_waiting(board)
        board.return_to_local_mode()

    def _ready_ack_timed_out(self, board, net, session):
        if self._waiting_board is board and net.session == session and not board.net_ready:
            self._close_waiting(board)
            board.return_to_local_mode("Nie udało się połączyć. Gra lokalna.")

    def _cancel_pending_join(self, status: str, notify_peer: bool = True):
        pending = self._join_pending
        if pending is None:
            return
        self._join_pending = None
        if self._join_timeout is not None:
            self._join_timeout.cancel()
            self._join_timeout = None
        board, net, msg, link, side = pending
        if notify_peer:
            net.leave(msg["game"])
        else:
            net.session = net.peer = net.game = None
        board.return_to_local_mode(status)

    def _join_timed_out(self, _dt, pending):
        if self._join_pending is pending:
            self._cancel_pending_join("Nie udało się połączyć. Gra lokalna.")

    # --- nawigacja ------------------------------------------------------------------------
    def leave_network_games(self, keep=None):
        """Wyjście z ekranu gry sieciowej kończy partię (drugi tablet dostaje komunikat)."""
        endgame.close_all()             # okno końca gry nie zostaje na innym ekranie
        for key, board in GAMES.items():
            if self._waiting_board is board and key != keep:
                self._close_waiting(board)
            active = board.net_ready or any(getattr(t, "game", None) == key
                                            for t in (self.net, self.direct) if t is not None)
            if key != keep and board.players == NETWORK and active:
                board.return_to_local_mode("Gra przez sieć zakończona")
            if self._join_pending and self._join_pending[0] is board and key != keep:
                self._cancel_pending_join("Gra lokalna.")

    def _games_key(self, _window, key, *_args):
        """Przyciski tabletu (Wstecz, Menu) są zablokowane wszędzie, także na ekranie
        startowym - aplikacji nie da się nimi opuścić (tryb kiosku). Do cofania jest
        przycisk Wstecz u góry ekranu, a do wyjścia przycisk na dole menu."""
        return key in HARDWARE_KEYS

    # --- komunikaty z sieci -------------------------------------------------------------------
    def on_game_event(self, msg: dict):
        kind, board = msg.get("type"), GAMES.get(msg.get("game"))
        net = self.transport(msg)
        if board is None or net is None:
            return
        if kind == "invite":
            if self._resolve_invite_collision(msg, net):
                return
            busy = self._waiting_board is not None or self._join_pending is not None or any(
                b.players == NETWORK for b in GAMES.values())
            if net is self.direct:
                if not busy:
                    self._answer_invite(msg, True, silent=True)
                return
            if not busy and self._invite is None:
                self._invite = InvitePopup(msg, self._answer_invite)
                self._invite.open()
            return
        if not net.mine(msg):
            return
        sender = msg.get("from", "Drugi tablet")
        if kind == "accept" and board.players == NETWORK:
            net.peer = sender
            net.ready(board.GAME)
            self._show_waiting(board)
            if self._ready_timeout is not None:
                self._ready_timeout.cancel()
            session = net.session
            self._ready_timeout = Clock.schedule_once(
                lambda _dt: self._ready_ack_timed_out(board, net, session),
                CONNECTION_SECONDS)
        elif kind == "ready" and self._join_pending:
            pending = self._join_pending
            if pending[0] is board and pending[1] is net \
                    and pending[2]["session"] == msg.get("session"):
                if self._join_timeout is not None:
                    self._join_timeout.cancel()
                    self._join_timeout = None
                self._join_pending = None
                self._close_waiting(board)
                board.join(sender, pending[3], side=pending[4])
                net.ready_ack(board.GAME)
        elif kind == "ready_ack" and board.players == NETWORK:
            self._close_waiting(board)
            net.peer = sender
            board.accepted(sender)
        elif kind == "decline":
            self._close_waiting(board)
            net.session = net.peer = net.game = None
            board.return_to_local_mode(f"{sender} nie chce teraz grać")
        elif kind == "move":
            board.remote_move(msg.get("move") or [])
        elif kind == "leave":
            if self._join_pending and self._join_pending[1] is net \
                    and self._join_pending[2]["session"] == msg.get("session"):
                self._cancel_pending_join(f"{sender} zakończył grę", notify_peer=False)
            else:
                self._close_waiting(board)
                net.session = net.peer = net.game = None
                board.return_to_local_mode(f"{sender} zakończył grę")

    def _answer_invite(self, msg, ok, silent):
        self._invite = None
        net = self.transport(msg)
        if not ok:
            if not silent:
                net.decline(msg)
            return
        board = GAMES.get(msg.get("game"))
        if board is None:
            return
        self.leave_network_games()
        link = "direct" if net is self.direct else "ha"
        side = 1 - msg.get("side", 0)
        self.nav(msg["game"])
        self._join_pending = (board, net, msg, link, side)
        self._join_timeout = Clock.schedule_once(
            lambda dt, pending=self._join_pending: self._join_timed_out(dt, pending),
            CONNECTION_SECONDS)
        board.status = "Sprawdzam połączenie..."
        if net is self.direct:
            if not net.accept(msg):
                self._cancel_pending_join("Nie udało się połączyć. Gra lokalna.",
                                          notify_peer=False)
        else:
            net.accept(msg)
