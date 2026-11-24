"""HA Kiosk dzieci - tablet w pokoju dzieci (Galaxy Tab 3 10.1, LineageOS 14.1, x86).

Ekran startowy: trzy zegary - pory dnia (plan dnia obrazkami), analogowy ze wskazówkami
godzin, minut i sekund oraz pory roku z animowanymi ikonami. Po prawej menu: dom (powrót
do ekranu startowego), godzina HH:MM, data D-M i słuchawka - wiadomości głosowe przez
Home Assistant jak w kiosku w holu (kod domofonu z ha_kiosk_hol, kopiowany przed
budowaniem przez sync_kiosk.sh).

Ustawienia: settings.json (url, token HA, tablet_name) wbudowany w APK; nowszy plik
można wgrać bez przebudowy do /sdcard/Android/data/pl.mieszkanie.hakioskdzieci/files/.
Podgląd na PC: DZIECI_SCREENSHOT=ekran.png python main.py (zrzut ekranu i koniec).
"""
import json
import os
from datetime import datetime
from pathlib import Path

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ
os.environ.setdefault("KIVY_NO_ARGS", "1")
if IS_ANDROID:
    # układ w pikselach jak w kiosku - bez skalowania DPI
    os.environ.setdefault("KIVY_METRICS_DENSITY", "1")
    os.environ.setdefault("KIVY_METRICS_FONTSCALE", "1")

from kivy.config import Config  # noqa: E402

if IS_ANDROID:
    # SDL zamienia dotyk także na zdarzenie myszy - bez dostawcy myszy (podwójne dotknięcia)
    if Config.has_section("input"):
        for key in list(Config.options("input")):
            if Config.get("input", key).startswith("mouse"):
                Config.remove_option("input", key)
else:
    Config.set("graphics", "width", "1280")
    Config.set("graphics", "height", "800")
    Config.set("input", "mouse", "mouse,disable_multitouch")
# Esc nie zamyka aplikacji na PC; przyciski tabletu obsługuje GamesHost (systemowo tylko na
# ekranie startowym)
Config.set("kivy", "exit_on_escape", "0")

from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.lang import Builder  # noqa: E402
from kivy.properties import StringProperty  # noqa: E402

from dzieci import clocks  # noqa: E402 - klasy zegarów dla ekran.kv
from dzieci.announce import DayAnnouncer  # noqa: E402
from dzieci.games import chess, checkers, dice, dots, football, paint, pdots, ships, snake, tetris, tictactoe  # noqa: E402,F401 - klasy gier dla gry.kv
from dzieci.games.host import GamesHost  # noqa: E402
from dzieci.music import MusicPlayer  # noqa: E402
from dzieci import coloring  # noqa: E402,F401 - klasy kolorowanek dla kolorowanki.kv
from kivy.uix.screenmanager import NoTransition  # noqa: E402
from kiosk import icons, voice  # noqa: E402
from kiosk.widgets.voice_dialog import VoiceDialog  # noqa: E402

HERE = Path(__file__).resolve().parent
KV_DIR = HERE / "kiosk" / "kv"


def load_settings() -> dict:
    """settings.json z katalogu plików aplikacji (adb push) albo wbudowany w APK."""
    candidates = []
    if IS_ANDROID:
        candidates.append(Path("/sdcard/Android/data/pl.mieszkanie.hakioskdzieci/files/settings.json"))
    candidates.append(HERE / "settings.json")
    for path in candidates:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


class DzieciApp(GamesHost, App):
    title = "HA Kiosk dzieci"
    section = StringProperty("home")     # podświetlenie w menu (widgets.kv z kiosku)
    time_text = StringProperty("")
    date_text = StringProperty("")
    voice_last = StringProperty("")
    tablet_name = StringProperty("Tablet dzieci")

    def build(self):
        Window.clearcolor = (0.10, 0.12, 0.19, 1)
        icons.register_font()
        for name in ("widgets.kv", "settings.kv", "voice_dialog.kv"):
            Builder.load_file(str(KV_DIR / name))
        self.voice = None
        self.voice_recorder = voice.Recorder()
        self.voice_player = voice.Player()
        # komunikat głosowy przy zmianie pory dnia ("Czas na śniadanie")
        self.announcer = DayAnnouncer(self.voice_player)
        self.music = MusicPlayer(self.voice_player)    # ekran Muzyka
        settings = load_settings()
        if settings.get("url") and settings.get("token") and not os.environ.get("DZIECI_SCREENSHOT"):
            self.tablet_name = settings.get("tablet_name", self.tablet_name)
            self.voice = voice.VoiceLink(settings, self.tablet_name, voice.cache_dir(),
                                         self._on_message)
            self.voice.start()
            # gra przez sieć z innymi tabletami (przez HA)
            self.setup_games(settings, self.tablet_name)
        else:
            self.setup_games({}, self.tablet_name)
        self._update_clock(0)
        Clock.schedule_interval(self._update_clock, 1)
        Builder.load_file(str(HERE / "dzieci" / "games" / "gry.kv"))
        Builder.load_file(str(HERE / "dzieci" / "music" / "muzyka.kv"))
        Builder.load_file(str(HERE / "dzieci" / "coloring" / "kolorowanki.kv"))
        # ekran.kv celowo nie nazywa się dzieci.kv - Kivy wczytałby go sam przed build()
        return Builder.load_file(str(HERE / "ekran.kv"))

    def on_start(self):
        shot = os.environ.get("DZIECI_SCREENSHOT")
        if shot:
            Clock.schedule_once(lambda _dt: self._screenshot(shot), 2.5)

    def _screenshot(self, path):
        Window.screenshot(name=path)
        self.stop()

    def on_pause(self):
        return True                     # wygaszony ekran nie zamyka aplikacji

    def _update_clock(self, _dt):
        now = clocks.now()
        self.time_text = now.strftime("%H:%M")
        self.date_text = f"{now.day}-{now.month}"

    # --- menu -------------------------------------------------------------------------
    def nav(self, target: str):
        """Menu i przyciski: home - ekran startowy, voice - wiadomość głosowa,
        games - siatka gier, inna nazwa - ekran gry (tictactoe, checkers, chess, paint)."""
        if target == "voice":
            VoiceDialog().open()
            return
        sm = self.root.ids.sm
        screen = "start" if target == "home" else target
        if sm.has_screen(screen):
            self.leave_network_games(keep=screen)   # wyjście z gry sieciowej kończy partię
            sm.transition = NoTransition()
            sm.current = screen
            self.section = "home" if screen == "start" else "games"

    def _on_message(self, info, path):
        """Nowa wiadomość od innego tabletu: zapowiedź (gong + głos) i nagranie."""
        dur = info.get("duration")
        self.voice_last = (f"od: {info.get('from', '?')}, {info.get('time', '')}"
                           + (f", {dur:.0f} s" if isinstance(dur, (int, float)) else ""))
        self.voice_player.play([voice.INTRO, path])


if __name__ == "__main__":
    DzieciApp().run()
