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
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

from dzieci.games.board import GAMES, NETWORK
from dzieci.games.net import GameNet

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


class GamesHost:
    net = None
    _invite = None

    def setup_games(self, settings: dict, name: str):
        """Wołać w build(): sieć gier, gdy jest adres i token HA; przycisk Wstecz."""
        if settings.get("url") and settings.get("token"):
            self.net = GameNet(settings, name, self.on_game_event)
        Window.bind(on_keyboard=self._games_key)

    # --- nawigacja ------------------------------------------------------------------------
    def leave_network_games(self, keep=None):
        """Wyjście z ekranu gry sieciowej kończy partię (drugi tablet dostaje komunikat)."""
        for key, board in GAMES.items():
            active = board.net_ready or getattr(self.net, "game", None) == key
            if key != keep and board.players == NETWORK and active:
                board.leave_network()
                board.status = "Gra przez sieć zakończona"

    def _games_key(self, _window, key, *_args):
        """Przyciski tabletu (Wstecz, Menu): na ekranie startowym działają systemowo
        (Kivy przenosi aplikację w tło jak każdą inną), w grach i oknach nic nie robią -
        do cofania jest przycisk Wstecz u góry ekranu."""
        if key not in HARDWARE_KEYS:
            return False
        on_main = self.root.ids.sm.current == "start" and not any(
            isinstance(w, ModalView) for w in Window.children)
        return not on_main

    # --- komunikaty z sieci -------------------------------------------------------------------
    def on_game_event(self, msg: dict):
        kind, board = msg.get("type"), GAMES.get(msg.get("game"))
        if board is None or self.net is None:
            return
        if kind == "invite":
            busy = any(b.players == NETWORK and b.net_ready for b in GAMES.values())
            if not busy and self._invite is None:
                self._invite = InvitePopup(msg, self._answer_invite)
                self._invite.open()
            return
        if not self.net.mine(msg):
            return
        sender = msg.get("from", "Drugi tablet")
        if kind == "accept" and board.players == NETWORK:
            self.net.peer = sender
            board.accepted(sender)
        elif kind == "decline":
            self.net.session = None
            board.peer_left(f"{sender} nie chce teraz grać")
        elif kind == "move":
            board.remote_move(msg.get("move") or [])
        elif kind == "leave":
            self.net.session = None
            board.peer_left(f"{sender} zakończył grę")

    def _answer_invite(self, msg, ok, silent):
        self._invite = None
        if not ok:
            if not silent:
                self.net.decline(msg)
            return
        board = GAMES.get(msg.get("game"))
        if board is None:
            return
        self.leave_network_games()
        self.net.accept(msg)
        self.nav(msg["game"])
        board.join(msg.get("from", "Drugi tablet"))
