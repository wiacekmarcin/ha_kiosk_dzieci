#!/usr/bin/env python3
"""Lokalne próbki polskiego głosu do odczytu zegara i daty (edge-tts).

Godzina czytana jak u ludzi: „jedenasta godzina trzydzieści dwie minuty” - godzina
liczebnikiem porządkowym, minuty słowami z poprawną odmianą (jedna minuta, dwie minuty,
pięć minut, dwadzieścia jeden minut). Pełna godzina: sama godzina, bez minut.
Uruchomienie: python tools/make_clock_sounds.py [--only hour,minute]
"""
import asyncio
import sys
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
# godzina 0-23 liczebnikiem porządkowym w rodzaju żeńskim („jedenasta godzina”)
HOURS = (
    "zero", "pierwsza", "druga", "trzecia", "czwarta", "piąta", "szósta", "siódma",
    "ósma", "dziewiąta", "dziesiąta", "jedenasta", "dwunasta", "trzynasta", "czternasta",
    "piętnasta", "szesnasta", "siedemnasta", "osiemnasta", "dziewiętnasta", "dwudziesta",
    "dwudziesta pierwsza", "dwudziesta druga", "dwudziesta trzecia",
)
UNITS_F = ("", "jedna", "dwie", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć")
TEENS = ("dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
         "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście")
TENS = {2: "dwadzieścia", 3: "trzydzieści", 4: "czterdzieści", 5: "pięćdziesiąt"}
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
    """Odmiana rzeczownika po liczebniku: 1 minuta, 2-4 minuty (bez 12-14), reszta minut
    (także 21, 31... - „dwadzieścia jeden minut”)."""
    if value == 1:
        return singular
    if value % 10 in (2, 3, 4) and value % 100 not in (12, 13, 14):
        return paucal
    return plural


def number_f(value):
    """Liczebnik 1-59 słowami w rodzaju żeńskim (minuta): dwie, dwadzieścia jeden."""
    if value < 10:
        return UNITS_F[value]
    if value < 20:
        return TEENS[value - 10]
    tens, units = divmod(value, 10)
    if units == 0:
        return TENS[tens]
    return f"{TENS[tens]} {'jeden' if units == 1 else UNITS_F[units]}"


def minute_text(value):
    return f"{number_f(value)} {form(value, 'minuta', 'minuty', 'minut')}"


def hour_text(value):
    return "godzina zero" if value == 0 else f"{HOURS[value]} godzina"


def samples():
    result = {
        "today.mp3": "Dzisiaj jest",
        "season_intro.mp3": "Pora roku",
    }
    for value in range(24):
        result[f"hour_{value:02d}.mp3"] = hour_text(value)
    for value in range(1, 60):
        result[f"minute_{value:02d}.mp3"] = minute_text(value)
    for value in range(60):
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
    only = None
    if len(sys.argv) > 2 and sys.argv[1] == "--only":
        only = tuple(p + "_" for p in sys.argv[2].split(","))
    todo = {n: t for n, t in samples().items() if only is None or n.startswith(only)}
    semaphore = asyncio.Semaphore(4)
    await asyncio.gather(*(generate(n, t, semaphore) for n, t in todo.items()))
    print(f"CLOCK_SOUNDS_OK {len(todo)}")


if __name__ == "__main__":
    asyncio.run(main())
