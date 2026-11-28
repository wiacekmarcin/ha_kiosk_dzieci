"""Odczyt zegara z lokalnych próbek polskiego głosu (tools/make_clock_sounds.py).

Godzina: „jedenasta godzina trzydzieści dwie minuty” (bez sekund; pełna godzina - bez
minut). Data: „Dzisiaj jest dwudziestego ósmego listopada, pora roku jesień”.
"""
from pathlib import Path

from kivy.logger import Logger

from dzieci import plan

AUDIO = Path(__file__).resolve().parents[1] / "assets" / "clock_audio"


def time_samples(now) -> list:
    samples = [f"hour_{now.hour:02d}.mp3"]
    if now.minute:
        samples.append(f"minute_{now.minute:02d}.mp3")
    return samples


class ClockSpeech:
    def __init__(self, player):
        self.player = player

    def say_time(self, now):
        self._play(time_samples(now))

    def say_date(self, now):
        season = plan.SEASONS[plan.current_season(now.date())[0]][0]
        samples = [
            "today.mp3",
            f"day_{now.day:02d}.mp3",
            f"month_{now.month:02d}.mp3",
            "season_intro.mp3",
            f"season_{season}.mp3",
        ]
        self._play(samples)

    def _play(self, samples):
        paths = [AUDIO / name for name in samples]
        missing = [path.name for path in paths if not path.is_file()]
        if missing:
            Logger.error(f"Zegar: brakuje próbek głosu: {', '.join(missing)}")
            return
        if self.player is None:
            Logger.error("Zegar: odtwarzacz komunikatów nie jest dostępny")
            return
        Logger.info(f"Zegar: odtwarzam próbki: {', '.join(samples)}")
        self.player.play(paths)
