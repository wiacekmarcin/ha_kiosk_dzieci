#!/usr/bin/env python3
"""Generate local Polish speech samples for the clock readouts."""
import asyncio
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "clock_audio"
VOICE = "pl-PL-ZofiaNeural"
RATE = "-10%"
ORDINALS = (
    "pierwszego", "drugiego", "trzeciego", "czwartego", "piątego", "szóstego",
    "siódmego", "ósmego", "dziewiątego", "dziesiątego", "jedenastego",
    "dwunastego", "trzynastego", "czternastego", "piętnastego", "szesnastego",
    "siedemnastego", "osiemnastego", "dziewiętnastego", "dwudziestego",
)
MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)
SEASONS = {"wiosna": "wiosna", "lato": "lato", "jesien": "jesień", "zima": "zima"}


def ordinal(day):
    if day <= 20:
        return ORDINALS[day - 1]
    tens, units = divmod(day, 10)
    decade = {2: "dwudziestego", 3: "trzydziestego"}[tens]
    return decade if units == 0 else f"{decade} {ORDINALS[units - 1]}"


def form(value, singular, paucal, plural):
    last_two = value % 100
    if value % 10 == 1 and last_two != 11:
        return singular
    if value % 10 in (2, 3, 4) and last_two not in (12, 13, 14):
        return paucal
    return plural


def samples():
    result = {
        "today.mp3": "Dzisiaj jest",
        "season_intro.mp3": "Pora roku",
    }
    for value in range(24):
        result[f"hour_{value:02d}.mp3"] = f"{value} " + form(
            value, "godzina", "godziny", "godzin")
    for value in range(60):
        result[f"minute_{value:02d}.mp3"] = f"{value} " + form(
            value, "minuta", "minuty", "minut")
        result[f"second_{value:02d}.mp3"] = f"{value} " + form(
            value, "sekunda", "sekundy", "sekund")
    for day in range(1, 32):
        result[f"day_{day:02d}.mp3"] = ordinal(day)
    for month, name in enumerate(MONTHS, 1):
        result[f"month_{month:02d}.mp3"] = name
    for key, name in SEASONS.items():
        result[f"season_{key}.mp3"] = name
    return result


async def generate(name, text, semaphore):
    async with semaphore:
        await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(OUT / name))


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(4)
    tasks = [generate(name, text, semaphore) for name, text in samples().items()]
    await asyncio.gather(*tasks)
    print(f"CLOCK_SOUNDS_OK {len(tasks)}")


if __name__ == "__main__":
    asyncio.run(main())
