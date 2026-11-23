"""Komunikat głosowy przy zmianie pory dnia: gong i zdanie, np. "Czas na śniadanie".

Sprawdza co ANNOUNCE_CHECK s, czy zmieniła się czynność z planu dnia; przy starcie
aplikacji nic nie mówi (zapamiętuje tylko bieżącą czynność). Nagrania leżą w
assets/komunikaty (tools/make_sounds.py), odtwarza je odtwarzacz domofonu (voice.Player).
"""
from pathlib import Path

from kivy.clock import Clock
from kivy.logger import Logger

from dzieci import plan
from dzieci.clocks import now

SOUNDS = Path(__file__).resolve().parents[1] / "assets" / "komunikaty"
ANNOUNCE_CHECK = 5


class DayAnnouncer:
    def __init__(self, player, enabled: bool = True):
        self.player = player
        self.enabled = enabled
        self._last = self._activity()
        self._event = Clock.schedule_interval(self._check, ANNOUNCE_CHECK)

    @staticmethod
    def _activity():
        t = now()
        i, _frac = plan.current_activity(t)
        return plan.day_plan(t)[i]

    def _check(self, _dt):
        act = self._activity()
        if act == self._last:
            return
        self._last = act
        if self.enabled:
            self.say(act)

    def say(self, act=None):
        """Odtwarza komunikat czynności (domyślnie bieżącej)."""
        act = act or self._activity()
        path = SOUNDS / f"{act.sound_name}.ogg"
        if not path.exists():
            Logger.warning(f"Pora dnia: brak nagrania {path.name}")
            return
        Logger.info(f"Pora dnia: {act.label}")
        self.player.play([path])
