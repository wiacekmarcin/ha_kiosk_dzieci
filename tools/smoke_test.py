"""Test dymny przed instalacją: uruchamia aplikację (bez HA), przechodzi przez wszystkie
ekrany, stuka w plansze gier, rzuca kostką, rysuje i symuluje grę przez sieć z drugim
tabletem (komunikaty jak z Home Assistant); każdy wyjątek albo zła odpowiedź kończy test
kodem 1.

Uruchomienie (PC, wirtualny ekran): xvfb-run -a python tools/smoke_test.py
"""
import os
import random
import sys
import shutil
import tempfile
from pathlib import Path
import traceback
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
os.environ["DZIECI_SCREENSHOT"] = "1"          # bez połączenia z HA
import main  # noqa: E402
from kivy.base import ExceptionHandler, ExceptionManager  # noqa: E402
from kivy.clock import Clock  # noqa: E402

from dzieci.games.board import GAMES, NETWORK  # noqa: E402
from dzieci.games.net import GameNet  # noqa: E402
from dzieci.games.direct import DirectNet  # noqa: E402
from dzieci.games.ships import N as N_SHIPS  # noqa: E402
from dzieci import camera as camera_mod  # noqa: E402

# aparat: zdjęcia testowe w katalogu tymczasowym (nie w katalogu aplikacji na PC)
PHOTOS = tempfile.mkdtemp(prefix="aparat_")
for _name in ("a", "b"):
    shutil.copy("dzieci/coloring/pages/chomik.png", os.path.join(PHOTOS, f"zdjecie_{_name}.jpg"))
camera_mod.photos_dir = lambda: (Path(PHOTOS), True)

ERRORS = []
PEER = "Tablet 2"


class Fail(ExceptionHandler):
    def handle_exception(self, inst):
        ERRORS.append("".join(traceback.format_exception(inst)))
        return ExceptionManager.PASS


ExceptionManager.add_handler(Fail())


class FakeNet(GameNet):
    """GameNet bez HA: komunikaty trafiają do listy sent."""
    def __init__(self, name):                   # noqa: D107 - bez wątku i bez HA
        self.name, self.session, self.peer, self.seq, self.sent = name, None, None, 0, []
        self.center, self._session_via = None, None

    def _post(self, payload, via=None):
        self.sent.append(payload)


class FakeDirect(FakeNet):
    def accept(self, invite):
        self.session, self.peer, self.game = invite["session"], invite["from"], invite["game"]
        self.sent.append({"type": "accept", "session": self.session})
        return True


def msg(**kw):
    return {"from": PEER, "time": datetime.now(timezone.utc).isoformat(), **kw}


def test_game_net_pinned_channel():
    from threading import Event, Lock
    from unittest.mock import patch

    class Center:
        connected = True

        def __init__(self):
            self.sent = []

        def send(self, payload):
            self.sent.append(payload)
            return True

    class Response:
        @staticmethod
        def raise_for_status():
            pass

    center = Center()
    net = GameNet.__new__(GameNet)
    net.center, net.name, net.base, net.headers = center, "Tablet 2", "http://ha", {}
    net.on_event = lambda _msg: None
    net.session = net.peer = net.game = net._session_via = None
    net.seq, net._seen, net._lock = 0, None, Lock()
    sent = []
    complete = Event()

    def post(_url, **kwargs):
        sent.append(kwargs["json"]["attributes"]["type"])
        if len(sent) == 2:
            complete.set()
        return Response()

    with patch("dzieci.games.net.requests.post", side_effect=post):
        net.accept({"session": "s1", "from": "Tablet 1", "game": "chess", "_via": "ha"})
        net.ready_ack("chess")
        complete.wait(2)

    check(complete.is_set() and sent == ["accept", "ready_ack"] and not center.sent,
          "odpowiedź na zaproszenie HA została wysłana innym kanałem")

    incoming = []
    net.on_event = incoming.append
    net._center_event({"from": "Tablet 1", "msg": {"type": "invite", "game": "chess",
                                                    "session": "s2"}}, None)
    check(incoming and incoming[0].get("_via") == "center",
          "zaproszenie centrum nie oznaczyło kanału odpowiedzi")


def dots(canvas):
    """Liczba kropek (Ellipse) celu ruchu: rozmiar mniejszy niż pół pola."""
    from kivy.graphics import Ellipse
    return sum(1 for i in canvas.children if isinstance(i, Ellipse) and i.size[0] < 40)


def lines(canvas):
    from kivy.graphics import Line
    return sum(1 for i in canvas.children if isinstance(i, Line) and i.width == 2)


def check(cond, text):
    if not cond:
        ERRORS.append("SPRAWDZENIE: " + text)


def test_clock_readout(app):
    class Capture:
        samples = []

        def play(self, paths):
            self.samples.append([Path(path).name for path in paths])

    original_now = main.clocks.now
    original_monotonic = main.time.monotonic
    original_speech, original_last = app.clock_speech, app._last_clock_read
    speaker = Capture()
    ticks = iter((100, 114, 115))
    try:
        main.clocks.now = lambda: datetime(2026, 1, 2, 3, 4, 5)
        main.time.monotonic = lambda: next(ticks)
        app.clock_speech = main.ClockSpeech(speaker)
        app.read_clock()
        app.read_date()
        app.read_date()
    finally:
        main.clocks.now = original_now
        main.time.monotonic = original_monotonic
        app.clock_speech, app._last_clock_read = original_speech, original_last
    check(speaker.samples == [
        ["hour_03.mp3", "minute_04.mp3"],       # „trzecia godzina cztery minuty”, bez sekund
        ["today.mp3", "day_02.mp3", "month_01.mp3", "season_intro.mp3",
         "season_zima.mp3"],
    ], f"nieprawidłowy odczyt zegara albo limit 15 s: {speaker.samples!r}")


def test_music_volume(app):
    original_volume = main.device.volume
    original_set_volume = main.device.set_volume
    original_value = app.volume_value
    current = [50]

    def set_volume(value):
        current[0] = max(0, min(100, round(value)))

    try:
        main.device.volume = lambda: current[0]
        main.device.set_volume = set_volume
        app.volume_value = 5
        app.adjust_music_volume(-10)
        lower = app.volume_value
        app.volume_value = 95
        app.adjust_music_volume(10)
        upper = app.volume_value
    finally:
        main.device.volume = original_volume
        main.device.set_volume = original_set_volume
        app.volume_value = original_value
    check(lower == 0 and upper == 100,
          f"przyciski głośności nie ograniczają poziomu do 0-100: {lower}, {upper}")


def test_music_controls_layout(app):
    screen = app.root.ids.sm.get_screen("start")
    controls = app.root.ids.music_controls
    analog = app.root.ids.analog
    symbols = {getattr(child, "symbol", "") for child in controls.children}
    check(symbols >= {"−", "+"} and controls.y < analog.y
          and abs(controls.center_x - screen.center_x) < 40,
          "sterowanie muzyką nie jest wyśrodkowane pod zegarem albo brakuje przycisków głośności")


class FakeTouch:
    """Dotyk do testu rysowania (pozycja, słownik ud, grab jak w Kivy)."""
    def __init__(self, x, y):
        self.x, self.y, self.ud, self.grab_current = x, y, {}, None

    @property
    def pos(self):
        return self.x, self.y

    def grab(self, widget):
        self.grab_current = widget

    def ungrab(self, widget):
        self.grab_current = None


def draw(pc):
    """Trzy długie kreski, w tym palec stojący w miejscu (powtarzane te same punkty)."""
    for tool, brush in (("pen", 22), ("pen", 4), ("eraser", 10)):
        pc.tool, pc.brush = tool, brush
        t = FakeTouch(pc.x + 20, pc.y + 20)
        pc.on_touch_down(t)
        for i in range(1500):
            if i % 3:
                t.x = pc.x + 20 + (i * 7) % (pc.width - 40)
                t.y = pc.y + 20 + (i * 3) % (pc.height - 40)
            t.grab_current = pc
            pc.on_touch_move(t)
        pc.on_touch_up(t)


class Smoke(main.DzieciApp):
    def on_start(self):
        sm = self.root.ids.sm
        self.net = FakeNet(self.tablet_name)
        self.peer, self.peer_events = None, []      # drugi tablet w grze bezpośredniej
        self.original_battery = main.device.battery
        steps = [
            test_game_net_pinned_channel,
            lambda: setattr(main.device, "battery", lambda: {"level": 74}),
            lambda: self._update_battery(0),
            lambda: check(self.battery_text == "74%", "poziom baterii nie został pokazany"),
            lambda: setattr(main.device, "battery", self.original_battery),
            lambda: check(sm.current == "start" and self.root.ids.rail.opacity == 1
                          and self.root.ids.rail.width == 128,
                          "pasek boczny nie jest widoczny na ekranie głównym"),
            lambda: check(len(self.clock_time_text) == 8
                          and self.clock_time_text[2] == ":"
                          and self.clock_time_text[5] == ":"
                          and " • " in self.clock_date_text,
                          "na ekranie głównym brakuje czasu 24-godzinnego albo daty i pory roku"),
            lambda: check(any(getattr(w, "text", "") == "Sprawdź"
                              for w in sm.get_screen("start").walk()),
                          "brak przycisku Sprawdź na ekranie głównym"),
            lambda: test_clock_readout(self),
            lambda: test_music_volume(self),
            lambda: test_music_controls_layout(self),
            lambda: self.nav("gallery"),
            None,
            lambda: check(sm.current == "gallery" and self.root.ids.rail.width == 0
                          and len(sm.get_screen("gallery").ids.gallery_grid.children) == 2,
                          f"galeria: ekran={sm.current}, rail={self.root.ids.rail.width}, "
                          f"miniatur={len(sm.get_screen('gallery').ids.gallery_grid.children)}, "
                          f"zdjęć={len(sm.get_screen('gallery').photos)}"),
            lambda: [setattr(sm.get_screen("gallery"), "photos",
                             [sm.get_screen("gallery").photos[0]] * 25),
                     setattr(sm.get_screen("gallery"), "position", 0),
                     sm.get_screen("gallery").step(10)],
            lambda: check(sm.get_screen("gallery").position == 10,
                          "galeria: skok o 10 zdjęć nie działa"),
            lambda: sm.get_screen("gallery").step(-10),
            lambda: check(sm.get_screen("gallery").position == 0,
                          "galeria: cofnięcie o 10 zdjęć nie działa"),
            lambda: sm.get_screen("gallery").step(50),
            lambda: check(sm.get_screen("gallery").position == 15,
                          "galeria: skok o 50 zdjęć nie ograniczył się do końca listy"),
            lambda: sm.get_screen("gallery").step(-50),
            lambda: check(sm.get_screen("gallery").position == 0,
                          "galeria: cofnięcie o 50 zdjęć nie ograniczyło się do początku"),
            lambda: next(w for w in sm.get_screen("gallery").ids.gallery_grid.children
                         if w.position == 0).on_release(),
            lambda: check(sm.current == "photos" and sm.get_screen("photos").position == 0,
                          "wybór miniatury nie otworzył odpowiedniego zdjęcia"),
            lambda: self.nav("home"),
            lambda: self.nav("games"),
            lambda: check(self.root.ids.rail.opacity == 0 and self.root.ids.rail.width == 0
                          and self.root.ids.rail.disabled,
                          "pasek boczny nadal jest widoczny poza ekranem głównym"),
        ]
        for game in ("tictactoe", "checkers", "chess"):
            steps.append(lambda g=game: self.nav(g))
            for players in ((2,) if game == "tictactoe" else (2, 1)):
                steps.append(lambda g=game, p=players: setattr(GAMES[g], "players", p))
                for _ in range(40):           # losowe stuknięcia, w tym w piony i pola z kropkami
                    steps.append(lambda g=game: GAMES[g].tap(random.randrange(GAMES[g].SIZE),
                                                             random.randrange(GAMES[g].SIZE)))
                steps.append(None)            # czas na ruch komputera
            steps.append(lambda g=game: GAMES[g].restart())
        steps += [
            # zielone kropki: pion e2 ma 2 pola (e3, e4), pionek warcabów z (5, 0) - 1 pole
            lambda: GAMES["chess"].set_mode(1),
            lambda: [GAMES["chess"].new_game(), GAMES["chess"].tap(6, 4)],
            lambda: check(dots(GAMES["chess"].canvas.after) == 2,
                          f"szachy: podpowiedzi dla jednego gracza {dots(GAMES['chess'].canvas.after)}"),
            lambda: GAMES["chess"].set_mode(NETWORK, "ha"),
            lambda: setattr(GAMES["chess"], "net_ready", True),
            lambda: [GAMES["chess"].new_game(), GAMES["chess"].tap(6, 4)],
            lambda: check(dots(GAMES["chess"].canvas.after) == 2,
                          "szachy nie pokazują podpowiedzi w Twojej turze sieciowej"),
            lambda: GAMES["chess"].tap(4, 4),
            lambda: check(dots(GAMES["chess"].canvas.after) == 0,
                          "szachy pokazują podpowiedzi w turze przeciwnika"),
            lambda: GAMES["chess"].set_mode(1),
            lambda: GAMES["chess"].set_mode(2),
            lambda: check(GAMES["chess"].show_hints
                          and lines(GAMES["chess"].canvas.before)
                          == len({(m[0], m[1]) for m in GAMES["chess"].moves}),
                          "szachy: brak podświetlenia figur z legalnymi ruchami"),
            lambda: [GAMES["chess"].new_game(), GAMES["chess"].tap(6, 4)],
            lambda: check(GAMES["chess"].show_hints
                          and dots(GAMES["chess"].canvas.after) == 2,
                          "szachy: brak podpowiedzi w trybie dwóch graczy"),
            lambda: GAMES["chess"].set_mode(1),
            lambda: GAMES["checkers"].set_mode(1),
            lambda: [GAMES["checkers"].new_game(), GAMES["checkers"].tap(5, 0)],
            lambda: check(dots(GAMES["checkers"].canvas) >= 1,
                          "warcaby: brak podpowiedzi dla jednego gracza"),
            lambda: GAMES["checkers"].set_mode(NETWORK, "ha"),
            lambda: setattr(GAMES["checkers"], "net_ready", True),
            lambda: [GAMES["checkers"].new_game(), GAMES["checkers"].tap(5, 0)],
            lambda: check(dots(GAMES["checkers"].canvas) >= 1,
                          "warcaby nie pokazują podpowiedzi w Twojej turze sieciowej"),
            lambda: GAMES["checkers"].tap(4, 1),
            lambda: check(dots(GAMES["checkers"].canvas) == 0,
                          "warcaby pokazują podpowiedzi w turze przeciwnika"),
            lambda: GAMES["checkers"].set_mode(2),
            lambda: check(GAMES["checkers"].show_hints
                          and lines(GAMES["checkers"].canvas)
                          == len({m["path"][0] for m in GAMES["checkers"].moves}),
                          "warcaby: brak podświetlenia pionków z legalnymi ruchami"),
            lambda: [GAMES["checkers"].new_game(), GAMES["checkers"].tap(5, 0)],
            lambda: check(GAMES["checkers"].show_hints
                          and dots(GAMES["checkers"].canvas) >= 1,
                          "warcaby: brak podpowiedzi w trybie dwóch graczy"),
            lambda: GAMES["checkers"].set_mode(1),
            # wybór strony w szachach poprzedza wysłanie zaproszenia i oczekiwanie
            lambda: self.nav("chess"),
            lambda: self.activate_game_mode(GAMES["chess"], NETWORK, "ha", True),
            lambda: check(self._side_popup is not None and self._waiting_popup is None
                          and self.net.session is None,
                          "szachy rozpoczęły oczekiwanie przed wyborem strony"),
            lambda: self._side_popup.select(1),
            None,
            lambda: check(self._waiting_popup is not None
                          and self.net.sent[-1].get("side") == 1
                          and GAMES["chess"].network_color_text == "Kolor Twoich pionków: czarne"
                          and any(getattr(w.ids.get("side"), "text", "") == "Kolor Twoich pionków: czarne"
                                  for w in sm.get_screen("chess").walk() if hasattr(w, "board")),
                          "wybór czarnych nie pokazał koloru na ekranie"),
            # inicjator może przerwać oczekiwanie i wrócić do trybu lokalnego
            lambda: self._waiting_popup.cancel(),
            lambda: check(GAMES["chess"].players == 1 and self.net.session is None,
                          "Przerwij nie wróciło do gry lokalnej"),
            # sieć: drugi tablet wybiera czarne w szachach, ten tablet gra białymi
            lambda: self.on_game_event(msg(type="invite", game="chess", session="s1", side=1)),
            lambda: check(self._invite is not None, "brak okna zaproszenia"),
            lambda: self._invite.answer(True),
            lambda: check(sm.current == "chess" and GAMES["chess"].players == 1
                          and self._join_pending is not None,
                          "przyjęcie nie rozpoczęło sprawdzania połączenia"),
            lambda: check(self.net.sent[-1]["type"] == "accept", "brak odpowiedzi accept"),
            lambda: self._join_timed_out(0, self._join_pending),
            lambda: check(GAMES["chess"].players == 1 and self.net.session is None
                          and "Gra lokalna" in GAMES["chess"].status,
                          "brak połączenia nie wrócił do trybu lokalnego"),
            lambda: self.on_game_event(msg(type="invite", game="chess", session="s2", side=1)),
            lambda: self._invite.answer(True),
            lambda: self.on_game_event(msg(type="ready", game="chess", session="s2",
                                           to=self.tablet_name)),
            lambda: check(sm.current == "chess" and GAMES["chess"].players == NETWORK
                          and GAMES["chess"].my_side == 0 and GAMES["chess"].net_ready
                          and GAMES["chess"].human_turn()
                          and GAMES["chess"].status == "Czekam na Twój ruch"
                          and GAMES["chess"].network_color_text == "Kolor Twoich pionków: białe",
                          f"potwierdzenie: players={GAMES['chess'].players}, side={GAMES['chess'].my_side}, "
                          f"ready={GAMES['chess'].net_ready}, status={GAMES['chess'].status!r}, "
                          f"color={GAMES['chess'].network_color_text!r}, "
                          f"hints={dots(GAMES['chess'].canvas.after)}"),
            lambda: GAMES["chess"].tap(6, 4),
            lambda: check(dots(GAMES["chess"].canvas.after) == 2,
                          "szachy: brak podpowiedzi po wybraniu figury we własnej turze"),
            lambda: [GAMES["chess"].tap(6, 4), GAMES["chess"].tap(4, 4)],
            lambda: check(self.net.sent[-1].get("move") == [6, 4, 4, 4],
                          "biały ruch po akceptacji nie został wysłany"),
            lambda: self.on_game_event(msg(type="move", game="chess", session="s2",
                                           to=self.tablet_name, move=[1, 4, 3, 4])),
            lambda: check(GAMES["chess"].current_side() == 0
                          and GAMES["chess"].human_turn(),
                          "ruch czarnych z sieci nie został wykonany"),
            lambda: [GAMES["chess"].tap(7, 6), GAMES["chess"].tap(5, 5)],
            lambda: check(self.net.sent[-1].get("move") == [7, 6, 5, 5],
                          f"ruch nie poszedł do sieci: {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="leave", game="chess", session="s2",
                                           to=self.tablet_name)),
            lambda: check("zakończył" in GAMES["chess"].status, "brak napisu o wyjściu"),
            # gdy obaj inicjują równocześnie, tablet o niższej nazwie zostaje inicjatorem
            lambda: self.activate_game_mode(GAMES["chess"], NETWORK, "ha", False),
            lambda: self.on_game_event({**msg(type="invite", game="chess", session="collision",
                                              side=0), "from": "!Drugi tablet"}),
            lambda: check(self._waiting_popup is None and self._invite is not None
                          and GAMES["chess"].players == 1,
                          "równoczesne zaproszenia nie zamknęły oczekiwania przegranego"),
            lambda: self._invite.answer(True),
            lambda: self.on_game_event(msg(type="ready", game="chess", session="collision",
                                           to=self.tablet_name)),
            lambda: check(self._waiting_popup is None and self._join_pending is None
                          and GAMES["chess"].net_ready,
                          "po dołączeniu zostało okno oczekiwania inicjatora"),
            lambda: self.nav("chess"),
            # sieć: ten tablet zaprasza do warcabów, drugi przyjmuje
            lambda: self.nav("checkers"),
            lambda: self.activate_game_mode(GAMES["checkers"], NETWORK, "ha", False, 1),
            lambda: check(GAMES["checkers"].status == "Oczekiwanie na gracza"
                          and self.net.sent[-1].get("side") == 1
                          and self._waiting_popup is not None,
                          "zaproszenie do warcabów nie pokazuje oczekiwania albo wybranej strony"),
            lambda: check(self.net.sent[-1]["type"] == "invite", "brak zaproszenia"),
            lambda: self.on_game_event(msg(type="accept", game="checkers", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: check(self._waiting_popup is not None and self.net.sent[-1]["type"] == "ready"
                          and not GAMES["checkers"].net_ready,
                          "inicjator zamknął oczekiwanie przed potwierdzeniem"),
            lambda: self.on_game_event(msg(type="ready_ack", game="checkers",
                                           to=self.tablet_name, session=self.net.session)),
            lambda: check(self._waiting_popup is None and GAMES["checkers"].net_ready
                          and GAMES["checkers"].my_side == 1
                          and not GAMES["checkers"].human_turn()
                          and GAMES["checkers"].status == "Czekam na ruch przeciwnika"
                          and GAMES["checkers"].network_color_text == "Kolor Twoich pionków: czarne",
                          "akceptacja nie odblokowała stanu warcabów albo strony"),
            lambda: self.on_game_event(msg(type="move", game="checkers", session=self.net.session,
                                           to=self.tablet_name, move=[5, 0, 4, 1])),
            lambda: check(GAMES["checkers"].current_side() == 1
                          and GAMES["checkers"].human_turn(), "ruch białych nie przekazał tury"),
            lambda: [GAMES["checkers"].tap(2, 1), GAMES["checkers"].tap(3, 0)],
            lambda: check(self.net.sent[-1].get("move") == [2, 1, 3, 0],
                          f"ruch wybraną stroną nie poszedł: {self.net.sent[-1]}"),
            # sieć: kółko i krzyżyk
            lambda: self.nav("tictactoe"),
            lambda: check(self.net.sent[-1]["type"] == "leave", "wyjście z warcabów bez leave"),
            lambda: setattr(GAMES["tictactoe"], "players", NETWORK),
            lambda: self.on_game_event(msg(type="accept", game="tictactoe", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: self.on_game_event(msg(type="ready_ack", game="tictactoe",
                                           to=self.tablet_name, session=self.net.session)),
            lambda: GAMES["tictactoe"].tap(1, 1),
            lambda: check(self.net.sent[-1].get("move") == [4], "ruch kółka nie poszedł"),
            lambda: self.on_game_event(msg(type="move", game="tictactoe", session=self.net.session,
                                           to=self.tablet_name, move=[0])),
            lambda: check(GAMES["tictactoe"].cells[0] == 1, "kółko rywala nie postawione"),
            # przyciski tabletu: w grze nic nie robią, na ekranie startowym systemowo
            lambda: check(self._games_key(None, 27) is True and sm.current == "tictactoe",
                          "Wstecz w grze nie powinno nic robić"),
            lambda: check(self._games_key(None, 319) is True, "Menu w grze nie powinno nic robić"),
            lambda: self.nav("home"),
            lambda: check(self.root.ids.rail.opacity == 1 and self.root.ids.rail.width == 128
                          and not self.root.ids.rail.disabled,
                          "pasek boczny nie wrócił na ekran główny"),
            lambda: check(self._games_key(None, 27) is True,
                          "Wstecz na ekranie startowym też ma być zablokowane (kiosk)"),
            # wyjście: okno potwierdzenia, po 2 razy "Tak" jeszcze otwarte (trzeba 3 razy)
            lambda: setattr(self, "exit_popup", __import__("dzieci.kiosklock", fromlist=["x"]).ExitPopup()),
            lambda: [self.exit_popup.open(), self.exit_popup.yes(), self.exit_popup.yes()],
            lambda: check(self.exit_popup.presses == 2 and "1 raz" in self.exit_popup.info.text
                          and self.exit_popup in main.Window.children,
                          f"wyjście: okno po 2 razy Tak ({self.exit_popup.info.text})"),
            lambda: self.exit_popup.dismiss(),
            # Internet: wykryty serwer jest przyjmowany automatycznie, bez okna zaproszenia
            lambda: setattr(self, "real_direct", self.direct),
            lambda: setattr(self, "direct", FakeDirect(self.tablet_name)),
            lambda: self.on_game_event(msg(type="invite", game="tictactoe", session="auto",
                                           _via="direct")),
            lambda: check(self._invite is None and self._join_pending is not None
                          and GAMES["tictactoe"].players == 2
                          and self.direct.sent[-1]["type"] == "accept",
                          "Internet nie zaakceptował automatycznie wykrytego serwera"),
            lambda: self.on_game_event(msg(type="ready", game="tictactoe", session="auto",
                                           to=self.tablet_name, _via="direct")),
            lambda: check(GAMES["tictactoe"].players == NETWORK
                          and GAMES["tictactoe"].link == "direct"
                          and GAMES["tictactoe"].net_ready
                          and self.direct.sent[-1]["type"] == "ready_ack",
                          "Internet nie uruchomił gry po potwierdzeniu połączenia"),
            lambda: self.nav("home"),
            lambda: setattr(self, "direct", self.real_direct),
            # kropki: z komputerem i we dwóch, potem przez sieć (ruch to cała lista kresek)
            lambda: self.nav("dots"),
            lambda: setattr(GAMES["dots"], "players", 2),
            lambda: [GAMES["dots"].play(i) for i in random.sample(range(60), 60)],
            lambda: check(len(GAMES["dots"].history) == 60 and GAMES["dots"].finished,
                          f"kropki: {len(GAMES['dots'].history)} kresek, koniec={GAMES['dots'].finished}"),
            lambda: setattr(GAMES["dots"], "players", 1),
            *[lambda: GAMES["dots"].tap(random.randrange(6), random.randrange(6)) for _ in range(30)],
            None, None, None, None, None, None, None, None, None, None, None, None, None, None, None,
            lambda: setattr(GAMES["dots"], "players", NETWORK),
            lambda: self.on_game_event(msg(type="accept", game="dots", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: self.on_game_event(msg(type="ready_ack", game="dots",
                                           to=self.tablet_name, session=self.net.session)),
            lambda: GAMES["dots"].play(0),
            lambda: check(self.net.sent[-1].get("move") == [0], f"kropki: {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="move", game="dots", session=self.net.session,
                                           to=self.tablet_name, move=[0, 1, 2])),
            lambda: check(GAMES["dots"].history == [0, 1] and GAMES["dots"].current_side() == 0,
                          f"kropki: kreski z sieci {GAMES['dots'].history}"),
            # statki: wejście na ekran zaprasza, drugi tablet przyjmuje, strzały i odpowiedzi
            lambda: [self.nav("ships"), GAMES["ships"].set_mode(NETWORK)],
            None, None, None, None, None, None, None, None, None, None,
            lambda: check(self.net.sent[-1]["type"] == "invite" and self.net.sent[-1]["game"] == "ships",
                          f"statki: brak zaproszenia {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="accept", game="ships", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: self.on_game_event(msg(type="ready_ack", game="ships",
                                           to=self.tablet_name, session=self.net.session)),
            lambda: check(GAMES["ships"].status == "Czekam na Twój ruch",
                          "statki: brak informacji o własnej turze"),
            lambda: GAMES["ships"].shuffle(),
            lambda: GAMES["ships"].tap(0, 0),
            lambda: check(self.net.sent[-1].get("move") == [0, 0, 0] and GAMES["ships"].waiting,
                          f"statki: strzał nie poszedł {self.net.sent[-1]}"),
            lambda: check(GAMES["ships"].status == "Czekam na ruch przeciwnika",
                          "statki: brak informacji o oczekiwaniu na przeciwnika"),
            lambda: GAMES["ships"].tap(5, 5),         # czekam na wynik - drugi strzał nic nie robi
            lambda: check(self.net.sent[-1].get("move") == [0, 0, 0], "statki: dwa strzały naraz"),
            lambda: self.on_game_event(msg(type="move", game="ships", session=self.net.session,
                                           to=self.tablet_name, move=[1, 0, 0, 0])),
            lambda: check(GAMES["ships"].current_side() == 1 and GAMES["ships"].started,
                          "statki: po pudle kolej nie przeszła"),
            lambda: self.on_game_event(msg(type="move", game="ships", session=self.net.session,
                                           to=self.tablet_name, move=[0, *GAMES["ships"].ships[-1][0]])),
            lambda: check(self.net.sent[-1].get("move", [None])[0] == 1
                          and self.net.sent[-1]["move"][3] == 2,
                          f"statki: brak odpowiedzi o zatopieniu {self.net.sent[-1]}"),
            lambda: check(GAMES["ships"].current_side() == 1, "statki: po trafieniu strzela dalej rywal"),
            # statki z komputerem: mój strzał, potem strzały komputera
            lambda: GAMES["ships"].set_mode(1),
            lambda: check(GAMES["ships"].players == 1 and not GAMES["ships"].finished,
                          "statki: brak trybu z komputerem"),
            lambda: [GAMES["ships"].tap(r, c) for r in range(N_SHIPS) for c in range(N_SHIPS)
                     if GAMES["ships"].human_turn()],
            lambda: check(GAMES["ships"].current_side() == 1 or GAMES["ships"].finished,
                          "statki: po pudle kolej nie przeszła na komputer"),
            None, None, None, None, None, None, None, None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None, None, None, None, None, None, None, None,
            lambda: check(len(GAMES["ships"].incoming) >= 1, "statki: komputer nie strzelał"),
            # gra bezpośrednia (bez HA): prawdziwe gniazda TCP na tym komputerze
            lambda: [self.nav("tictactoe"), GAMES["tictactoe"].set_mode(NETWORK, "direct")],
            lambda: check(self.direct is not None and self.direct.session
                          and self.direct._server is not None, "bezpośrednio: brak serwera"),
            lambda: setattr(self, "peer", DirectNet(PEER, self.peer_events.append)),
            lambda: self.peer.accept({"session": self.direct.session, "from": self.tablet_name,
                                      "game": "tictactoe", "_addr": "127.0.0.1",
                                      "port": self.direct._server.getsockname()[1]}),
            None, None, None, None, None, None, None, None, None, None,
            lambda: check(any(m.get("type") == "ready" for m in self.peer_events),
                          f"bezpośrednio: brak potwierdzenia serwera {self.peer_events}"),
            lambda: self.peer.ready_ack("tictactoe"),
            None, None, None, None, None, None, None, None, None, None,
            lambda: check(GAMES["tictactoe"].net_ready and GAMES["tictactoe"].link == "direct",
                          "bezpośrednio: drugi tablet nie dołączył"),
            lambda: GAMES["tictactoe"].tap(1, 1),
            None, None, None, None, None, None, None, None, None, None,
            lambda: check(any(m.get("type") == "move" and m.get("move") == [4]
                              for m in self.peer_events), f"bezpośrednio: ruch nie doszedł {self.peer_events}"),
            lambda: self.peer.send_move("tictactoe", [0]),
            None, None, None, None, None, None, None, None, None, None,
            lambda: check(GAMES["tictactoe"].cells[0] == 1, "bezpośrednio: ruch drugiego tabletu"),
            lambda: self.peer.leave("tictactoe"),
            None, None, None, None, None, None, None, None, None, None,
            lambda: check("zakończył" in GAMES["tictactoe"].status,
                          f"bezpośrednio: brak końca gry ({GAMES['tictactoe'].status})"),
            lambda: GAMES["tictactoe"].set_mode(2),
            # polskie kropki: otoczenie niebieskiej kropki czerwonymi, komputer, sieć
            lambda: self.nav("pdots"),
            lambda: setattr(GAMES["pdots"], "players", 2),
            lambda: [GAMES["pdots"].tap(r, c) for r, c in
                     ((4, 5), (5, 5), (5, 4), (0, 0), (6, 5), (0, 1), (5, 6))],
            lambda: check(GAMES["pdots"].score == [1, 0] and GAMES["pdots"].captured[5 * 13 + 5],
                          f"polskie kropki: brak zdobycia {GAMES['pdots'].score}"),
            lambda: GAMES["pdots"].tap(5, 5),         # pole w zdobytym obszarze - nic
            lambda: check(GAMES["pdots"].player == 1, "polskie kropki: ruch w zdobyty obszar"),
            lambda: setattr(GAMES["pdots"], "players", 1),
            *[lambda: GAMES["pdots"].tap(random.randrange(13), random.randrange(13)) for _ in range(25)],
            None, None, None, None, None, None, None, None, None, None, None, None, None, None, None,
            lambda: GAMES["pdots"].finish_button(),
            lambda: check(GAMES["pdots"].finished, "polskie kropki: Zakończ nie kończy gry"),
            lambda: setattr(GAMES["pdots"], "players", NETWORK),
            lambda: self.on_game_event(msg(type="accept", game="pdots", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: self.on_game_event(msg(type="ready_ack", game="pdots",
                                           to=self.tablet_name, session=self.net.session)),
            lambda: GAMES["pdots"].tap(2, 2),
            lambda: check(self.net.sent[-1].get("move") == [28], f"polskie kropki: {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="move", game="pdots", session=self.net.session,
                                           to=self.tablet_name, move=[29])),
            lambda: check(GAMES["pdots"].owner[29] == 1, "polskie kropki: ruch z sieci"),
            # tetris i wąż: przyciski i kroki gry aż do końca
            lambda: self.nav("tetris"),
            lambda: sm.get_screen("tetris").ids.tetris.toggle_pause(),
            *[lambda: sm.get_screen("tetris").ids.tetris.action(
                random.choice(("left", "right", "rotate", "down", "drop", "rotate"))) for _ in range(250)],
            lambda: check(sm.get_screen("tetris").ids.tetris.over, "tetris: gra nie doszła do końca"),
            lambda: sm.get_screen("tetris").ids.tetris.toggle_pause(),
            lambda: check(not sm.get_screen("tetris").ids.tetris.over, "tetris: brak nowej gry"),
            lambda: self.nav("snake"),
            None, None,                       # on_leave ekranu przychodzi w kolejnej klatce
            lambda: check(sm.get_screen("tetris").ids.tetris.paused, "tetris: wyjście bez pauzy"),
            lambda: sm.get_screen("snake").ids.snake.toggle_pause(),
            *[lambda: [sm.get_screen("snake").ids.snake.turn(random.choice(("up", "down", "left", "right"))),
                       sm.get_screen("snake").ids.snake.step()] for _ in range(150)],
            lambda: [setattr(sm.get_screen("snake").ids.snake, "apple",
                             (sm.get_screen("snake").ids.snake.body[0][0],
                              (sm.get_screen("snake").ids.snake.body[0][1] + 1) % 22)),
                     sm.get_screen("snake").ids.snake.new_game()],
            lambda: [setattr(sm.get_screen("snake").ids.snake, "apple", (7, 7)),
                     sm.get_screen("snake").ids.snake.step()],
            lambda: check(sm.get_screen("snake").ids.snake.score == 1, "wąż: jabłko nie zjedzone"),
            # piłkarzyki: odbicie (ten sam gracz dalej), komputer, sieć
            lambda: self.nav("football"),
            lambda: setattr(GAMES["football"], "players", 2),
            lambda: GAMES["football"].tap(4, 4),       # w górę - zwykły ruch, kolej niebieskich
            lambda: check(GAMES["football"].current_side() == 1, "piłkarzyki: kolej nie przeszła"),
            lambda: GAMES["football"].tap(5, 4),       # z powrotem po tej samej kresce - zakaz
            lambda: check(len(GAMES["football"].moves) == 1, "piłkarzyki: ruch po użytej kresce"),
            lambda: GAMES["football"].tap(4, 5),       # niebiescy w prawo - kolej czerwonych
            lambda: GAMES["football"].tap(5, 4),       # do punktu startu (jest kreska) - odbicie
            lambda: check(GAMES["football"].current_side() == 0 and len(GAMES["football"].moves) == 3,
                          "piłkarzyki: brak odbicia"),
            lambda: setattr(GAMES["football"], "players", 1),
            lambda: check(dots(GAMES["football"].canvas) > 1,
                          "piłkarzyki: brak podpowiedzi dla jednego gracza"),
            *[lambda: GAMES["football"].play(random.choice(GAMES["football"].legal() or [(0, 0)]))
              for _ in range(30)],
            None, None, None, None, None, None, None, None, None, None, None, None, None, None, None,
            lambda: setattr(GAMES["football"], "players", NETWORK),
            lambda: self.on_game_event(msg(type="accept", game="football", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: self.on_game_event(msg(type="ready_ack", game="football",
                                           to=self.tablet_name, session=self.net.session)),
            lambda: [GAMES["football"].redraw(),
                     check(dots(GAMES["football"].canvas) > 2,
                           "piłkarzyki nie pokazują podpowiedzi w Twojej turze sieciowej")],
            lambda: GAMES["football"].tap(4, 4),
            lambda: check(self.net.sent[-1].get("move") == [5 * 9 + 4],
                          f"piłkarzyki: {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="move", game="football", session=self.net.session,
                                           to=self.tablet_name, move=[5 * 9 + 4, 4 * 9 + 3])),
            lambda: check(GAMES["football"].ball == (3, 3) and GAMES["football"].current_side() == 0,
                          f"piłkarzyki: ruch z sieci {GAMES['football'].ball}"),
            # przyciski Poprzednia / Następna gra i piosenka
            lambda: self.nav("football"),
            lambda: __import__("dzieci.games.host", fromlist=["GameBar"]).GameBar.go(1),
            lambda: check(sm.current == "tictactoe", f"następna gra po ostatniej: {sm.current}"),
            lambda: __import__("dzieci.games.host", fromlist=["GameBar"]).GameBar.go(-1),
            lambda: check(sm.current == "football", f"poprzednia gra: {sm.current}"),
            lambda: check(sum(1 for w in sm.get_screen("chess").walk()
                              if type(w).__name__ == "NavButton") == 2,
                          "brak przycisków Poprzednia / Następna na belce"),
            # sprawdzenie w tym samym kroku - na PC bez dźwięku utwór od razu się "kończy"
            lambda: [setattr(self.music, "songs", [{"path": f"/x/{i}.mp3", "title": str(i),
                                                     "icon": "", "album": "A"} for i in range(3)]),
                     self.music.step(-1),
                     check(self.music._index == 2, "poprzednia piosenka bez wyboru"),
                     self.music.step(1),
                     check(self.music._index == 0, "następna piosenka po ostatniej"),
                     self.music.stop()],
            # kolorowanki: lista motywu, wypełnienie obszaru, Cofnij, następna, Wyczyść
            lambda: self.nav("coloring"),
            None, None,
            lambda: check(len(sm.get_screen("coloring").ids.page_list.children) == 4,
                          "kolorowanki: lista Pokemon bez 4 obrazków"),
            lambda: __import__("dzieci.coloring", fromlist=["open_page"]).open_page(0),
            lambda: check(sm.current == "colorpage" and sm.get_screen("colorpage").ids.kol.w == 600,
                          "kolorowanki: obrazek się nie otworzył"),
            lambda: [setattr(sm.get_screen("colorpage").ids.kol, "color", [0.9, 0.16, 0.16, 1]),
                     sm.get_screen("colorpage").ids.kol.paint(300, 150)],
            lambda: check(sm.get_screen("colorpage").ids.kol.rgba[(150 * 600 + 300) * 4] == 229
                          and len(sm.get_screen("colorpage").ids.kol.history) == 1,
                          "kolorowanki: obszar nie wypełniony"),
            lambda: check(sm.get_screen("colorpage").ids.kol.rgba[(450 * 600 + 300) * 4] == 255,
                          "kolorowanki: kolor wylał się za kontur"),
            lambda: sm.get_screen("colorpage").ids.kol.undo(),
            lambda: check(sm.get_screen("colorpage").ids.kol.rgba[(150 * 600 + 300) * 4] == 255,
                          "kolorowanki: Cofnij nie działa"),
            lambda: sm.get_screen("colorpage").ids.kol.step(1),
            lambda: check(sm.get_screen("colorpage").ids.kol.title == "Elektryczny chomik",
                          f"kolorowanki: następna {sm.get_screen('colorpage').ids.kol.title}"),
            lambda: [sm.get_screen("colorpage").ids.kol.paint(300, 450),
                     sm.get_screen("colorpage").ids.kol.clear()],
            # aparat: rozmiary (kadr podglądu = kadr zdjęcia), ekran bez kamery na PC,
            # przeglądanie zdjęć z katalogu testowego
            lambda: check(camera_mod.choose_sizes(
                [(1920, 1080), (1280, 720), (1024, 768), (640, 480)],
                [(2048, 1536), (1920, 1080)]) == ((1024, 768), (2048, 1536)),
                "aparat: zły wybór rozmiaru podglądu"),
            lambda: self.nav("camera"),
            None, None, None, None,
            lambda: check(sm.current == "camera" and sm.get_screen("camera").message
                          in ("", "Aparat niedostępny"),
                          f"aparat: {sm.get_screen('camera').message}"),
            lambda: sm.get_screen("camera").shoot(),
            lambda: self.nav("photos"),
            lambda: check(sm.get_screen("photos").title == "Zdjęcie 2 z 2",
                          f"aparat: przeglądanie {sm.get_screen('photos').title}"),
            lambda: sm.get_screen("photos").step(1),
            lambda: check(sm.get_screen("photos").title == "Zdjęcie 1 z 2"
                          and sm.get_screen("photos").source.endswith("a.jpg"),
                          "aparat: następne zdjęcie"),
            lambda: self.nav("camera"),
            lambda: check(sm.get_screen("camera").count == 2
                          and sm.get_screen("camera").last_photo.endswith("b.jpg"),
                          "aparat: miniatura ostatniego zdjęcia"),
            lambda: self.nav("home"),
            lambda: check(sm.get_screen("camera")._core is None, "aparat: kamera nie zamknięta"),
            lambda: self.nav("dice"), lambda: sm.get_screen("dice").ids.dice.roll(),
            None, None, None,
            lambda: self.nav("paint"),
            lambda: draw(sm.get_screen("paint").ids.canvas_paint),
            lambda: sm.get_screen("paint").ids.canvas_paint.clear(),
            lambda: self.nav("home"), lambda: self.announcer.say(), self.stop,
        ]
        self._steps = steps
        Clock.schedule_interval(self._step, 0.05)

    def _step(self, _dt):
        if self._steps:
            step = self._steps.pop(0)
            try:
                if step:
                    step()
            except Exception:                 # noqa: BLE001
                ERRORS.append(traceback.format_exc())


Smoke().run()
shutil.rmtree(PHOTOS, ignore_errors=True)
if ERRORS:
    print("SMOKE_FAIL")
    print("\n".join(ERRORS[:5]))
    sys.exit(1)
print("SMOKE_OK")
