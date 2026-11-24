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
        self.peer, self.peer_events = None, []      # drugi tablet w grze bezpośredniej
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
            # przyciski tabletu: w grze nic nie robią, na ekranie startowym systemowo
            lambda: check(self._games_key(None, 27) is True and sm.current == "tictactoe",
                          "Wstecz w grze nie powinno nic robić"),
            lambda: check(self._games_key(None, 319) is True, "Menu w grze nie powinno nic robić"),
            lambda: self.nav("home"),
            lambda: check(self._games_key(None, 27) is True,
                          "Wstecz na ekranie startowym też ma być zablokowane (kiosk)"),
            # wyjście: okno potwierdzenia, po 2 razy "Tak" jeszcze otwarte (trzeba 3 razy)
            lambda: setattr(self, "exit_popup", __import__("dzieci.kiosklock", fromlist=["x"]).ExitPopup()),
            lambda: [self.exit_popup.open(), self.exit_popup.yes(), self.exit_popup.yes()],
            lambda: check(self.exit_popup.presses == 2 and "1 raz" in self.exit_popup.info.text
                          and self.exit_popup in main.Window.children,
                          f"wyjście: okno po 2 razy Tak ({self.exit_popup.info.text})"),
            lambda: self.exit_popup.dismiss(),
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
            lambda: GAMES["ships"].shuffle(),
            lambda: GAMES["ships"].tap(0, 0),
            lambda: check(self.net.sent[-1].get("move") == [0, 0, 0] and GAMES["ships"].waiting,
                          f"statki: strzał nie poszedł {self.net.sent[-1]}"),
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
            *[lambda: GAMES["football"].play(random.choice(GAMES["football"].legal() or [(0, 0)]))
              for _ in range(30)],
            None, None, None, None, None, None, None, None, None, None, None, None, None, None, None,
            lambda: setattr(GAMES["football"], "players", NETWORK),
            lambda: self.on_game_event(msg(type="accept", game="football", to=self.tablet_name,
                                           session=self.net.session)),
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
