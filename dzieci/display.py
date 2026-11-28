"""Jasność ekranu i wygaszanie na tabletach dzieci.

Jasność: suwak (i przyciski -/+) albo „Auto” - jasność z czujnika światła tabletu
(device.auto_brightness_for), wygładzona. Ruszenie suwaka wyłącza „Auto”. Wybór
zapamiętany w pliku ekran.json w katalogu danych aplikacji.

Wygaszanie (kiosk/screensaver.py - czarna nakładka i minimalne podświetlenie, aplikacja
działa dalej, dotyk budzi):
- po IDLE_MINUTES minutach bez dotyku, gdy nie gra piosenka (odtwarzanie liczy się jak
  dotyk); bez budzenia ruchem - przednia kamera w pokoju dzieci zostaje wyłączona;
- po zamknięciu klapki: magnes klapki nie jest dostępny dla aplikacji, więc klapkę
  rozpoznaje zasłonięty czujnik światła - ciemność (do COVER_LUX lx) przez COVER_SECONDS s
  bez dotyku; otwarcie klapki (od OPEN_LUX lx) budzi ekran.
"""
import json
import time
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.logger import Logger
from kivy.properties import BooleanProperty, NumericProperty

from kiosk import device

IDLE_MINUTES = 10
COVER_LUX = 1.0             # lx - zasłonięty czujnik (klapka)
OPEN_LUX = 5.0              # lx - klapka otwarta
COVER_SECONDS = 8           # s ciemności i bez dotyku = klapka zamknięta
AUTO_SECONDS = 2            # co ile sekund jasność automatyczna
AUTO_STEP = 0.35            # wygładzanie zmian jasności automatycznej
PREFS = "ekran.json"


class Display(EventDispatcher):
    brightness = NumericProperty(60)        # 1-100 %
    auto = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.saver = None
        self._dark_since = None
        self._cover_blank = False
        self._auto_last = 0.0
        self._load()
        device.light_start()
        device.set_brightness(self.brightness)
        Clock.schedule_interval(self._tick, 1)

    # --- ustawienia -----------------------------------------------------------------------
    def _path(self) -> Path:
        return Path(App.get_running_app().user_data_dir) / PREFS

    def _load(self):
        try:
            data = json.loads(self._path().read_text(encoding="utf-8"))
            self.brightness = max(1, min(100, int(data.get("brightness", self.brightness))))
            self.auto = bool(data.get("auto", self.auto))
        except (OSError, ValueError, TypeError):
            pass

    def _save(self):
        try:
            self._path().write_text(json.dumps({"brightness": round(self.brightness),
                                                "auto": self.auto}), encoding="utf-8")
        except OSError as e:
            Logger.warning(f"Ekran: nie zapisano ustawień jasności: {e}")

    # --- sterowanie z ekranu ----------------------------------------------------------------
    def slider(self, value):
        """Suwak: zmiana przez dziecko wyłącza „Auto” (zmiany z automatu są pomijane)."""
        if abs(value - self.brightness) < 0.5:
            return
        self.auto = False
        self._apply(value)
        self._save()

    def adjust(self, delta):
        self.auto = False
        self._apply(self.brightness + delta)
        self._save()

    def toggle_auto(self):
        self.auto = not self.auto
        self._auto_last = 0.0
        self._save()

    def _apply(self, value):
        self.brightness = max(1, min(100, round(value)))
        device.set_brightness(self.brightness)

    # --- wygaszanie ----------------------------------------------------------------------------
    def attach_saver(self, saver):
        self.saver = saver
        saver.configure(IDLE_MINUTES, False)    # 10 minut, bez budzenia kamerą

    def _music_playing(self) -> bool:
        music = getattr(App.get_running_app(), "music", None)
        return bool(music and music.playing and not music.paused)

    def _tick(self, _dt):
        saver = self.saver
        lux = device.light_lux()
        if saver is not None:
            if self._music_playing():
                saver.activity()                # piosenka gra - ekran nie gaśnie
            self._cover(saver, lux)
        now = time.monotonic()
        if self.auto and lux is not None and now - self._auto_last >= AUTO_SECONDS:
            self._auto_last = now
            target = device.auto_brightness_for(lux)
            step = (target - self.brightness) * AUTO_STEP
            if abs(target - self.brightness) >= 2:
                self._apply(self.brightness + (step if abs(step) >= 1 else target - self.brightness))

    def _cover(self, saver, lux):
        if lux is None:
            return
        now = time.monotonic()
        if lux <= COVER_LUX:
            if self._dark_since is None:
                self._dark_since = now
            if (not saver.blanked and now - self._dark_since >= COVER_SECONDS
                    and saver.idle_seconds() >= COVER_SECONDS):
                Logger.info(f"Ekran: klapka zamknięta ({lux:.1f} lx) - wygaszanie")
                saver.blank()
                self._cover_blank = True
        else:
            self._dark_since = None
            if lux >= OPEN_LUX and self._cover_blank:
                self._cover_blank = False
                if saver.blanked:
                    saver.wake("klapka otwarta")
