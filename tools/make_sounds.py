"""Komunikaty głosowe pór dnia: gong + zdanie (edge-tts, głos pl-PL-ZofiaNeural) -> OGG.

Użycie: python make_sounds.py <ffmpeg> [katalog_wyjściowy]
Wymaga pakietu edge-tts (pip install edge-tts) i ffmpeg z libvorbis.
Gong taki sam jak w kiosku w holu (zapowiedź godziny i wiadomości głosowej).
"""
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

import edge_tts

VOICE = "pl-PL-ZofiaNeural"
# nazwa pliku = Activity.sound w dzieci/plan.py
TEXTS = {
    "sen": "Czas spać. Dobranoc!",
    "mycie": "Czas na mycie.",
    "sniadanie": "Czas na śniadanie.",
    "zeby": "Czas umyć ząbki.",
    "ubieranie": "Czas się ubrać.",
    "przedszkole": "Czas na zabawę w przedszkolu.",
    "czas_wolny": "Czas wolny. Można się bawić!",
    "zabawa": "Czas na zabawę.",
    "obiad": "Czas na obiad.",
    "plac_zabaw": "Czas na plac zabaw.",
    "kolacja": "Czas na kolację.",
    "kapiel": "Czas na mycie przed snem.",
    "pidzama": "Czas założyć piżamkę.",
}
GONG = ("0.32*(1-exp(-400*t))*exp(-2.2*t)*(sin(2*PI*659*t)+0.5*sin(2*PI*1318*t)+0.25*sin(2*PI*1977*t))"
        "+0.32*gt(t,0.65)*(1-exp(-400*(t-0.65)))*exp(-1.8*(t-0.65))"
        "*(sin(2*PI*523*t)+0.5*sin(2*PI*1046*t)+0.25*sin(2*PI*1569*t))")


def run(ffmpeg, *args):
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


async def main(ffmpeg: str, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        gong = tmp / "gong.wav"
        run(ffmpeg, "-f", "lavfi", "-i", f"aevalsrc='{GONG}':s=44100:d=2.6",
            "-af", "afade=t=out:st=2.1:d=0.5", str(gong))
        for name, text in TEXTS.items():
            speech = tmp / f"{name}.mp3"
            await edge_tts.Communicate(text, VOICE, rate="-10%").save(str(speech))
            run(ffmpeg, "-i", str(gong), "-i", str(speech), "-filter_complex",
                "[0:a]aresample=24000,aformat=channel_layouts=mono,volume=0.8[g];"
                "[1:a]aresample=24000,aformat=channel_layouts=mono,loudnorm=I=-16:TP=-1.5,"
                "adelay=200,apad=pad_dur=0.4[s];[g][s]concat=n=2:v=0:a=1[a]",
                "-map", "[a]", "-c:a", "libvorbis", "-q:a", "4", str(out / f"{name}.ogg"))
            print(name, "-", text)


if __name__ == "__main__":
    default_out = Path(__file__).resolve().parents[1] / "assets" / "komunikaty"
    asyncio.run(main(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) > 2 else default_out))
