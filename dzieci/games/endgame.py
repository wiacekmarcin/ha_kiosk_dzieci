"""Okno końca gry (wyskakujące) dla gier planszowych.

Gra z komputerem i przez sieć (z perspektywy tego tabletu): wygrana - "Wygrana!", puchar
i głos "Zwycięstwo!"; przegrana - "Przegrana", smutna buźka i głos "Porażka"; remis - cisza.
Dwóch graczy na jednym tablecie: tylko komunikat, który gracz wygrał (bez dźwięku).
Przyciski: "Nowa gra" (board.restart) i "Zamknij". Okno zamyka się też samo przy
przejściu na inny ekran (close_all z GamesHost.leave_network_games).
Dźwięki i obrazki: koniec/ (tools/make_endgame.py).
"""
from pathlib import Path

from kivy.app import App
from kivy.graphics import Color, RoundedRectangle
from kivy.logger import Logger
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView

FILES = Path(__file__).resolve().parent / "koniec"
TITLES = {"wygrana": "Wygrana!", "przegrana": "Przegrana", "remis": "Remis", "koniec": "Koniec gry"}
SOUNDS = {"wygrana": "zwyciestwo.wav", "przegrana": "porazka.wav"}
NETWORK = 0
_open = []


class EndPopup(ModalView):
    def __init__(self, board, kind, message, **kwargs):
        super().__init__(size_hint=(None, None), size=(660, 420), auto_dismiss=True,
                         background_color=(0, 0, 0, 0.55), **kwargs)
        self.board = board
        box = BoxLayout(orientation="vertical", padding=26, spacing=14)
        with box.canvas.before:
            Color(0.16, 0.19, 0.29, 1)
            self._bg = RoundedRectangle(radius=[30])
        box.bind(pos=lambda w, v: setattr(self._bg, "pos", v),
                 size=lambda w, v: setattr(self._bg, "size", v))
        box.add_widget(Image(source=str(FILES / f"{kind}.png"), fit_mode="contain",
                             size_hint_y=None, height=120))
        box.add_widget(Label(text=TITLES[kind], font_size="46sp", bold=True,
                             color=(1.0, 0.84, 0.40, 1), size_hint_y=None, height=60))
        box.add_widget(Label(text=message, font_size="28sp", color=(0.95, 0.95, 0.98, 1),
                             halign="center", valign="middle", text_size=(600, None)))
        row = BoxLayout(spacing=20, size_hint_y=None, height=84)
        for text, action, color in (("Nowa gra", self.new_game, (0.25, 0.70, 0.25, 1)),
                                    ("Zamknij", self.dismiss, (0.45, 0.45, 0.50, 1))):
            b = Button(text=text, font_size="30sp", bold=True, background_normal="",
                       background_color=color)
            b.bind(on_release=lambda _b, a=action: a())
            row.add_widget(b)
        box.add_widget(row)
        self.add_widget(box)
        self.bind(on_dismiss=lambda *_: _open.remove(self) if self in _open else None)

    def new_game(self):
        self.dismiss()
        self.board.restart()


def show(board, winner):
    """Okno z wynikiem partii; winner - strona zwycięzcy albo None przy remisie."""
    if not board.finished or board.get_root_window() is None:
        return
    close_all()
    message = " ".join(board.status.split())
    if winner is None:
        kind = "remis"
    elif board.players == 2:
        kind = "koniec"
        if board.DOT:                   # w napisie było kółko koloru - tu słowo
            message += f" ({board.SIDE_NAMES[winner]})"
    else:
        mine = board.my_side if board.players == NETWORK else 0
        kind = "wygrana" if winner == mine else "przegrana"
    popup = EndPopup(board, kind, message)
    _open.append(popup)
    popup.open()
    sound = SOUNDS.get(kind)
    app = App.get_running_app()
    if sound and getattr(app, "voice_player", None) is not None:
        try:
            app.voice_player.play([str(FILES / sound)])
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Koniec gry: dźwięk: {e}")


def close_all():
    for popup in list(_open):
        popup.dismiss()
    _open.clear()
