"""Test dymny przed instalacją: uruchamia aplikację (bez HA), przechodzi przez wszystkie
ekrany, stuka w plansze gier, rzuca kostką i rysuje; każdy wyjątek kończy test kodem 1.

Uruchomienie (PC, wirtualny ekran): xvfb-run -a python tools/smoke_test.py
"""
import os
import random
import sys
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
sys.path.insert(0, REPO)
os.environ["DZIECI_SCREENSHOT"] = "1"          # bez połączenia z HA
import main  # noqa: E402
from kivy.base import ExceptionHandler, ExceptionManager  # noqa: E402
from kivy.clock import Clock  # noqa: E402

ERRORS = []


class Fail(ExceptionHandler):
    def handle_exception(self, inst):
        ERRORS.append("".join(traceback.format_exception(inst)))
        return ExceptionManager.PASS


ExceptionManager.add_handler(Fail())


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
            if i % 3:                       # co trzeci ruch to samo miejsce
                t.x = pc.x + 20 + (i * 7) % (pc.width - 40)
                t.y = pc.y + 20 + (i * 3) % (pc.height - 40)
            t.grab_current = pc
            pc.on_touch_move(t)
        pc.on_touch_up(t)


class Smoke(main.DzieciApp):
    def on_start(self):
        ids = self.root.ids
        steps = [lambda: self.nav("games")]
        for screen, board in (("tictactoe", "ttt"), ("checkers", "checkers"), ("chess", "chess")):
            steps.append(lambda s=screen: self.nav(s))
            for players in (2, 1):
                steps.append(lambda b=board, p=players: setattr(ids[b], "players", p)
                             if b != "ttt" else None)
                for _ in range(40):           # losowe stuknięcia, w tym w piony i pola z kropkami
                    steps.append(lambda b=board: ids[b].tap(random.randrange(ids[b].SIZE),
                                                            random.randrange(ids[b].SIZE)))
                steps.append(None)            # czas na ruch komputera
            steps.append(lambda b=board: ids[b].new_game() if b != "ttt" else None)
        steps += [lambda: self.nav("dice"), lambda: ids.dice.roll(), None, None, None,
                  lambda: self.nav("paint"), lambda: draw(ids.canvas_paint),
                  lambda: ids.canvas_paint.clear(),
                  lambda: self.nav("home"), lambda: self.announcer.say(), self.stop]
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
    print(ERRORS[0])
    sys.exit(1)
print("SMOKE_OK")
