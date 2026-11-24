#!/usr/bin/env python3
"""Okno końca gry: dźwięki i obrazki do dzieci/games/koniec/.

Dźwięki to same słowa, czytane głosem pl-PL-ZofiaNeural (edge-tts), bez muzyki i szumu:
  zwyciestwo.wav - wygrana: "Zwycięstwo!" (wyżej, radośnie)
  porazka.wav    - przegrana: "Porażka." (niżej, spokojnie)
Obrazki z Twemoji (CC-BY 4.0): puchar, smutna buźka, uścisk dłoni, flaga mety.

Użycie: python tools/make_endgame.py   (python z edge-tts, ffmpeg.exe z AtnelMEDIA,
obrazki: curl, rsvg-convert)
"""
import asyncio
import struct
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dzieci" / "games" / "koniec"
RATE = 22050
TWEMOJI = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/svg"
ICONS = {"wygrana": "1f3c6", "przegrana": "1f622", "remis": "1f91d", "koniec": "1f3c1"}
VOICE = "pl-PL-ZofiaNeural"
FFMPEG = "/mnt/c/ProgramData/Atnel/AtnelMEDIA/bin/ffmpeg.exe"
TMP = Path("/mnt/c/KreionAI/aae_ai_local_data/temp")   # pliki robocze widoczne dla ffmpeg.exe
# plik, tekst, wysokość i tempo głosu
WORDS = (("zwyciestwo.wav", "Zwycięstwo!", "+25Hz", "+5%"),
         ("porazka.wav", "Porażka.", "-10Hz", "-10%"))


def win(path: Path) -> str:
    return subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True,
                          check=True).stdout.strip()


def speak(name, text, pitch, rate):
    """Słowo z edge-tts -> WAV mono 22050 Hz, z ciszą 0,1 s na początku (bez obcinania)."""
    import edge_tts
    mp3 = TMP / f"koniec_{name}.mp3"
    asyncio.run(edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch).save(str(mp3)))
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", win(mp3),
                    "-af", "adelay=100,loudnorm=I=-14:TP=-1", "-ac", "1", "-ar", str(RATE),
                    win(OUT / name)], check=True)
    mp3.unlink()


def icon(name, code):
    svg = Path(f"/tmp/kon_{code}.svg")
    subprocess.run(["curl", "-fsSL", f"{TWEMOJI}/{code}.svg", "-o", str(svg)], check=True)
    subprocess.run(["rsvg-convert", "-w", "160", "-h", "160", str(svg), "-o",
                    str(OUT / f"{name}.png")], check=True)
    svg.unlink()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in ("oklaski.wav", "brawo.wav", "buczenie.wav"):
        (OUT / old).unlink(missing_ok=True)
    for name, text, pitch, rate in WORDS:
        speak(name, text, pitch, rate)
    for name, code in ICONS.items():
        icon(name, code)
    print("ENDGAME_OK", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
