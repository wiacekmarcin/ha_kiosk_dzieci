"""HA Kiosk dzieci - tablet w pokoju dzieci (Galaxy Tab 3 10.1, LineageOS 14.1, x86).

Ekran startowy: trzy zegary - pory dnia (plan dnia obrazkami), analogowy ze wskazówkami
godzin, minut i sekund oraz pory roku z animowanymi ikonami. Po prawej menu: dom (powrót
do ekranu startowego), godzina HH:MM, data D-M i słuchawka - wiadomości głosowe przez
Home Assistant jak w kiosku w holu (kod domofonu z ha_kiosk_hol, kopiowany przed
budowaniem przez sync_kiosk.sh).

Ustawienia: settings.json (url, token HA, tablet_name) wbudowany w APK; nowszy plik
można wgrać bez przebudowy do /sdcard/Android/data/pl.mieszkanie.hakioskdzieci/files/.
Ten sam APK idzie na oba tablety dzieci; różnią się tylko plikiem tablet.json w tym samym
katalogu (install.sh): child - imię pod zegarami, tablet_name - nazwa tabletu w sieci.
Podgląd na PC: DZIECI_SCREENSHOT=ekran.png python main.py (zrzut ekranu i koniec).
"""
import json
import os
import time
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
from kivy.logger import Logger  # noqa: E402
from kivy.properties import NumericProperty, StringProperty  # noqa: E402

from dzieci import clocks  # noqa: E402 - klasy zegarów dla ekran.kv
from dzieci.announce import DayAnnouncer  # noqa: E402
from dzieci.speech import ClockSpeech  # noqa: E402
from dzieci.display import Display  # noqa: E402
from dzieci.games import chess, checkers, dice, dots, football, paint, pdots, ships, snake, tetris, tictactoe  # noqa: E402,F401 - klasy gier dla gry.kv
from dzieci.games.board import DotStatus  # noqa: E402,F401 - widżet statusu dla gry.kv
from dzieci.games.host import GamesHost  # noqa: E402
from dzieci.music import MusicPlayer  # noqa: E402
from dzieci import coloring  # noqa: E402,F401 - klasy kolorowanek dla kolorowanki.kv
from dzieci import camera  # noqa: E402 - aparat (klasy dla aparat.kv, pauza i wznowienie)
from dzieci import kiosklock  # noqa: E402
from kivy.uix.screenmanager import NoTransition  # noqa: E402
from kiosk import device, icons, voice  # noqa: E402
from kiosk.widgets.voice_dialog import VoiceDialog  # noqa: E402

HERE = Path(__file__).resolve().parent
KV_DIR = HERE / "kiosk" / "kv"


FILES_DIR = Path("/sdcard/Android/data/pl.mieszkanie.hakioskdzieci/files")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_settings() -> dict:
    """settings.json z katalogu plików aplikacji (adb push) albo wbudowany w APK, a na nim
    tablet.json z katalogu plików aplikacji - ustawienia jednego tabletu (child, tablet_name),
    wgrywane przez install.sh. Na PC tablet.json obok main.py (podgląd)."""
    settings = {}
    for path in ([FILES_DIR / "settings.json"] if IS_ANDROID else []) + [HERE / "settings.json"]:
        data = _read_json(path)
        if isinstance(data, dict):
            settings = data
            break
    tablet = _read_json((FILES_DIR if IS_ANDROID else HERE) / "tablet.json")
    if isinstance(tablet, dict):
        if tablet.get("child") and not tablet.get("tablet_name"):
            settings.pop("tablet_name", None)       # nazwa w sieci z imienia, nie wspólna
        settings.update(tablet)
    return settings


class DzieciApp(GamesHost, App):
    title = "HA Kiosk dzieci"
    section = StringProperty("home")     # podświetlenie w menu (widgets.kv z kiosku)
    time_text = StringProperty("")
    date_text = StringProperty("")
    clock_time_text = StringProperty("")
    clock_date_text = StringProperty("")
    volume_value = NumericProperty(50)
    voice_last = StringProperty("")
    tablet_name = StringProperty("Tablet dzieci")
    child_name = StringProperty("")     # imię dziecka pod zegarami (tablet.json)
    app_version = StringProperty("")
    battery_text = StringProperty("")

    def build(self):
        Window.clearcolor = (0.10, 0.12, 0.19, 1)
        icons.register_font()
        self.app_version = device.app_version()
        self._update_battery(0)
        Clock.schedule_interval(self._update_battery, 60)
        for name in ("widgets.kv", "settings.kv", "voice_dialog.kv"):
            Builder.load_file(str(KV_DIR / name))
        self.voice = None
        self.voice_recorder = voice.Recorder()
        self.voice_player = voice.Player()
        self.clock_speech = ClockSpeech(self.voice_player)
        self._last_clock_read = float("-inf")
        self.volume_value = device.volume()
        # komunikat głosowy przy zmianie pory dnia ("Czas na śniadanie")
        self.announcer = DayAnnouncer(self.voice_player)
        self.music = MusicPlayer(self.voice_player)    # ekran Muzyka
        self.display = Display()                        # jasność (suwak, Auto) i wygaszanie
        settings = load_settings()
        # tablet.json (install.sh): imię dziecka pod zegarami i nazwa tabletu w sieci -
        # oba tablety dzieci mają ten sam APK, a w sieci muszą mieć różne nazwy
        self.child_name = self._child_name(settings)
        self.tablet_name = settings.get("tablet_name") or (
            f"Tablet {self.child_name}" if self.child_name else self.tablet_name)
        if settings.get("url") and settings.get("token") and not os.environ.get("DZIECI_SCREENSHOT"):
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
        Builder.load_file(str(HERE / "dzieci" / "camera" / "aparat.kv"))
        # ekran.kv celowo nie nazywa się dzieci.kv - Kivy wczytałby go sam przed build()
        return Builder.load_file(str(HERE / "ekran.kv"))

    def _child_name(self, settings: dict) -> str:
        """Imię dziecka z tablet.json (install.sh); kopia w danych aplikacji, bo tablet.json
        leży w pamięci współdzielonej, która może zniknąć (wymiana karty, czyszczenie pamięci,
        niezamontowana pamięć) - wtedy imię zostaje z kopii."""
        copy = Path(self.user_data_dir) / "tablet_kopia.json"
        name = str(settings.get("child") or "").strip()
        if name:
            try:
                if _read_json(copy) != {"child": name}:
                    copy.write_text(json.dumps({"child": name}, ensure_ascii=False), encoding="utf-8")
            except OSError as e:
                Logger.warning(f"Tablet: nie zapisano kopii imienia: {e}")
            return name
        saved = _read_json(copy)
        name = str(saved.get("child") or "") if isinstance(saved, dict) else ""
        if name:
            Logger.warning(f"Tablet: brak tablet.json - imię z kopii: {name}")
            settings.setdefault("child", name)
        return name

    def on_start(self):
        shot = os.environ.get("DZIECI_SCREENSHOT")
        if shot:
            Clock.schedule_once(lambda _dt: self._screenshot(shot), 2.5)
        else:
            if IS_ANDROID:
                clocks.ntp.start()
            kiosklock.lock()            # tryb kiosku: Home i lista aplikacji nie wyprowadzają
        from kiosk.screensaver import ScreenSaver
        self.screensaver = ScreenSaver(lambda: self.nav("home"))
        # wygaszanie: 10 minut bez dotyku (piosenka liczy się jak dotyk) albo zamknięta klapka
        self.display.attach_saver(self.screensaver)

    def _screenshot(self, path):
        Window.screenshot(name=path)
        self.stop()

    def on_pause(self):
        camera.on_app_pause()           # wygaszony ekran: kamera zwolniona
        return True                     # wygaszony ekran nie zamyka aplikacji

    def on_resume(self):
        kiosklock.relock_later()        # po powrocie do aplikacji przypięcie wraca
        camera.on_app_resume()          # aparat wraca, jeśli był otwarty
        self._update_battery(0)

    def _update_clock(self, _dt):
        now = clocks.now()
        self.time_text = now.strftime("%H:%M")
        self.date_text = f"{now.day}-{now.month}"
        self.clock_time_text = now.strftime("%H:%M:%S")
        season = clocks.plan.SEASONS[clocks.plan.current_season(now.date())[0]][1]
        self.clock_date_text = f"{now.day} {clocks.MONTHS[now.month - 1]} • {season}"

    def set_music_volume(self, value):
        device.set_volume(value)
        self.volume_value = device.volume()

    def adjust_music_volume(self, delta):
        self.set_music_volume(max(0, min(100, self.volume_value + delta)))

    def _clock_read_allowed(self):
        now = time.monotonic()
        if now - self._last_clock_read < 15:
            return False
        self._last_clock_read = now
        return True

    def read_clock(self):
        if not self._clock_read_allowed():
            return
        now = clocks.now()
        self.clock_speech.say_time(now)

    def read_date(self):
        if not self._clock_read_allowed():
            return
        now = clocks.now()
        self.clock_speech.say_date(now)

    def _update_battery(self, _dt):
        info = device.battery()
        level = info.get("level") if info else None
        self.battery_text = f"{level}%" if isinstance(level, int) else ""

    def open_photo(self, position: int):
        self.root.ids.sm.get_screen("photos").start_position = position
        self.nav("photos")

    # --- menu -------------------------------------------------------------------------
    def nav(self, target: str):
        """Menu i przyciski: home - ekran startowy, voice - wiadomość głosowa,
        games - siatka gier, inna nazwa - ekran gry (tictactoe, checkers, chess, paint)."""
        if target == "exit":            # wyjście z aplikacji (okno, 3 razy „Tak”)
            kiosklock.ask_exit()
            return
        if target == "screensaver":
            self.screensaver.blank()
            return
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
