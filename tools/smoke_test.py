"""Test dymny przed instalacją: uruchamia aplikację (bez HA), przechodzi przez wszystkie
ekrany, stuka w plansze gier, rzuca kostką, rysuje i symuluje grę przez sieć z drugim
tabletem (komunikaty jak z Home Assistant); każdy wyjątek albo zła odpowiedź kończy test
kodem 1.

Uruchomienie (PC, wirtualny ekran): xvfb-run -a python tools/smoke_test.py
"""
import os
import random
import sys
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

    def _post(self, payload):
        self.sent.append(payload)


def msg(**kw):
    return {"from": PEER, "time": datetime.now(timezone.utc).isoformat(), **kw}


def dots(canvas):
    """Liczba kropek (Ellipse) celu ruchu: rozmiar mniejszy niż pół pola."""
    from kivy.graphics import Ellipse
    return sum(1 for i in canvas.children if isinstance(i, Ellipse) and i.size[0] < 40)


def check(cond, text):
    if not cond:
        ERRORS.append("SPRAWDZENIE: " + text)


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
        steps = [lambda: self.nav("games")]
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
            lambda: setattr(GAMES["chess"], "players", 2),
            lambda: [GAMES["chess"].new_game(), GAMES["chess"].tap(6, 4)],
            lambda: check(dots(GAMES["chess"].canvas.after) == 2,
                          f"szachy: kropek {dots(GAMES['chess'].canvas.after)} zamiast 2"),
            lambda: setattr(GAMES["checkers"], "players", 2),
            lambda: [GAMES["checkers"].new_game(), GAMES["checkers"].tap(5, 0)],
            lambda: check(dots(GAMES["checkers"].canvas) >= 1, "warcaby: brak kropek"),
            # sieć: drugi tablet zaprasza do szachów, ten tablet przyjmuje i gra czarnymi
            lambda: self.on_game_event(msg(type="invite", game="chess", session="s1")),
            lambda: check(self._invite is not None, "brak okna zaproszenia"),
            lambda: self._invite.answer(True),
            lambda: check(sm.current == "chess" and GAMES["chess"].players == NETWORK
                          and GAMES["chess"].my_side == 1 and GAMES["chess"].net_ready,
                          "przyjęcie zaproszenia nie otworzyło szachów sieciowych"),
            lambda: check(self.net.sent[-1]["type"] == "accept", "brak odpowiedzi accept"),
            lambda: GAMES["chess"].tap(1, 4),          # nie moja kolej - nic się nie dzieje
            lambda: self.on_game_event(msg(type="move", game="chess", session="s1",
                                           to=self.tablet_name, move=[6, 4, 4, 4])),
            lambda: check(GAMES["chess"].current_side() == 1, "ruch z sieci nie został wykonany"),
            lambda: [GAMES["chess"].tap(1, 4), GAMES["chess"].tap(3, 4)],
            lambda: check(self.net.sent[-1].get("move") == [1, 4, 3, 4],
                          f"ruch nie poszedł do sieci: {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="leave", game="chess", session="s1",
                                           to=self.tablet_name)),
            lambda: check("zakończył" in GAMES["chess"].status, "brak napisu o wyjściu"),
            # sieć: ten tablet zaprasza do warcabów, drugi przyjmuje
            lambda: self.nav("checkers"),
            lambda: setattr(GAMES["checkers"], "players", NETWORK),
            lambda: check(self.net.sent[-1]["type"] == "invite", "brak zaproszenia"),
            lambda: self.on_game_event(msg(type="accept", game="checkers", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: check(GAMES["checkers"].net_ready and GAMES["checkers"].my_side == 0,
                          "przyjęcie nie rozpoczęło warcabów"),
            lambda: [GAMES["checkers"].tap(5, 0), GAMES["checkers"].tap(4, 1)],
            lambda: check(self.net.sent[-1].get("move") == [5, 0, 4, 1],
                          f"ruch warcabów nie poszedł: {self.net.sent[-1]}"),
            lambda: self.on_game_event(msg(type="move", game="checkers", session=self.net.session,
                                           to=self.tablet_name, move=[2, 1, 3, 0])),
            lambda: check(GAMES["checkers"].current_side() == 0, "ruch rywala nie wykonany"),
            # sieć: kółko i krzyżyk
            lambda: self.nav("tictactoe"),
            lambda: check(self.net.sent[-1]["type"] == "leave", "wyjście z warcabów bez leave"),
            lambda: setattr(GAMES["tictactoe"], "players", NETWORK),
            lambda: self.on_game_event(msg(type="accept", game="tictactoe", to=self.tablet_name,
                                           session=self.net.session)),
            lambda: GAMES["tictactoe"].tap(1, 1),
            lambda: check(self.net.sent[-1].get("move") == [4], "ruch kółka nie poszedł"),
            lambda: self.on_game_event(msg(type="move", game="tictactoe", session=self.net.session,
                                           to=self.tablet_name, move=[0])),
            lambda: check(GAMES["tictactoe"].cells[0] == 1, "kółko rywala nie postawione"),
            lambda: self._games_key(None, 27),        # Wstecz: z gry do siatki
            lambda: check(sm.current == "games", "Wstecz nie wróciło do siatki gier"),
            lambda: self._games_key(None, 27),
            lambda: check(sm.current == "start", "Wstecz nie wróciło do ekranu startowego"),
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
if ERRORS:
    print("SMOKE_FAIL")
    print("\n".join(ERRORS[:5]))
    sys.exit(1)
print("SMOKE_OK")
