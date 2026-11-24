#!/usr/bin/env python3
"""Piosenki dla dzieci: katalog (dzieci/music/katalog.json), ikonki utworów z Twemoji
(dzieci/music/icons/<kod>.png, CC-BY 4.0) i kopia plików mp3 do folderu, który
tools/push_music.sh wgrywa na tablet.

Źródła: albumy z dysku F (WSL: /mnt/f). Z płyt z podkładami (wersja z wokalem i bez)
brane są tylko utwory z wokalem. Pliki dostają krótkie nazwy ASCII: <album>_<nr>.mp3.

Użycie: python3 tools/make_music.py [folder_docelowy]
Wymaga: curl, rsvg-convert (librsvg2-bin).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSIC = ROOT / "dzieci" / "music"
ICONS = MUSIC / "icons"
DEST = Path(sys.argv[1] if len(sys.argv) > 1
            else "/mnt/c/KreionAI/aae_ai_local_data/media/audio/muzyka_dzieci")
TWEMOJI = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/svg"
ICON_PX = 96
OLD = "/mnt/f/marcin_oldhome/marcin/Muzyka"
FASOLKI = "/mnt/f/drive.09.2025/1/6A71-6962 (2)/muzyka/Fasolki"

# klucz, tytuł albumu, kolor kafelków, folder, [(plik, tytuł, kod emoji)]
ALBUMS = [
    ("przedszkolak", "Piosenki dla przedszkolaka", [0.42, 0.25, 0.20, 1],
     f"{OLD}/A.Slusarek,_M.Zieba,_M.Czaplak/Piosenki_dla_przedszkolaka_9", [
         ("1_-_Panie_Janie.mp3", "Panie Janie", "1f514"),
         ("2_-_Uciekaj,_myszko.mp3", "Uciekaj, myszko", "1f42d"),
         ("3_-_Kaczuszki.mp3", "Kaczuszki", "1f986"),
         ("4_-_Wlazl_kotek_na_plotek.mp3", "Wlazł kotek na płotek", "1f431"),
         ("5_-_Moja_Ulijanko.mp3", "Moja Ulijanko", "1f469"),
         ("6_-_Jawor,_jawor.mp3", "Jawor, jawor", "1f333"),
         ("7_-_Glowa,_ramiona.mp3", "Głowa, ramiona", "1f9d2"),
         ("8_-_Jada,_jada_misie.mp3", "Jadą, jadą misie", "1f9f8"),
         ("9_-_Miala_baba_koguta.mp3", "Miała baba koguta", "1f413"),
         ("10_-_Sloneczko_pozno_dzisiaj_wstalo.mp3", "Słoneczko późno dzisiaj wstało", "1f31e"),
         ("11_-_Poszla_zabka_po_wode.mp3", "Poszła żabka po wodę", "1f438"),
         ("12_-_Krakowiaczek_jeden.mp3", "Krakowiaczek jeden", "1f57a"),
         ("13_-_Plynie_Wisla,_plynie.mp3", "Płynie Wisła, płynie", "1f30a"),
     ]),
    ("znane", "Piosenki znane i lubiane", [0.20, 0.36, 0.30, 1],
     f"{OLD}/Joanna_Bernat,_Jozefa_Torun-Czernek/Piosenki_znane_i_lubiane_dla_malych_dzieci", [
         ("1_-_Jedzie_pociag-wok.mp3", "Jedzie pociąg", "1f682"),
         ("2_-_Karolinka-_wok-_5.mp3", "Karolinka", "1f467"),
         ("3_-_Jagodki-wok.mp3", "Jagódki", "1fad0"),
         ("4_-_Pieski_male_dwa-wok.mp3", "Pieski małe dwa", "1f415"),
         ("5_-_Malo_nas_-wok.mp3", "Mało nas", "1f46b"),
         ("6_-_Malowany_wozek-wok-2.mp3", "Malowany wózek", "1f6d2"),
         ("7_-_Sanna-wok.mp3", "Sanna", "1f6f7"),
         ("8_-_Co_dzieci__widzialy_w_drodze-wok.mp3", "Co dzieci widziały w drodze", "1f697"),
         ("9_-_Krakowiaczek-wok.mp3", "Krakowiaczek", "1f57a"),
         ("10_-_Stokrotka-wok.mp3", "Stokrotka", "1f33c"),
         ("11_-_Bajka_iskierki_-_wok-5.mp3", "Bajka iskierki", "2728"),
     ]),
    ("fasolki", "Fasolki", [0.22, 0.30, 0.48, 1], FASOLKI, [
         ("Fasolki - Fasola.mp3", "Fasola", "1fad8"),
         ("Fasolki - Gumisie Poland.mp3", "Gumisie", "1f43b"),
         ("Fasolki - Kolorowe Kredki.mp3", "Kolorowe kredki", "1f58d"),
         ("Fasolki - Kubus Puchatek.mp3", "Kubuś Puchatek", "1f36f"),
         ("Fasolki - Muminki.mp3", "Muminki", "1f99b"),
         ("Fasolki - Pies Na Medal.mp3", "Pies na medal", "1f415"),
         ("Mam Chusteczkę.mp3", "Mam chusteczkę haftowaną", "1f9e3"),
     ]),
    ("ciotka", "Piosenki Ciotki Klotki", [0.40, 0.22, 0.38, 1],
     f"{OLD}/Fasolki/Piosenki_Ciotki_Klotki", [
         ("1_-_A_na_razie_rosniemy.mp3", "A na razie rośniemy", "1f331"),
         ("2_-_Myj_zeby.mp3", "Myj zęby", "1faa5"),
         ("3_-_Mydlo_lubi_zabawe.mp3", "Mydło lubi zabawę", "1f9fc"),
         ("4_-_Domowa_piosenka.mp3", "Domowa piosenka", "1f3e0"),
         ("5_-_Kolega_slimak.mp3", "Kolega ślimak", "1f40c"),
         ("6_-_Ropucha_Klamczucha.mp3", "Ropucha Kłamczucha", "1f438"),
         ("7_-_Czuje_glod.mp3", "Czuję głód", "1f37d"),
         ("8_-_Blues_z_kapelusza.mp3", "Blues z kapelusza", "1f3a9"),
         ("9_-_Rolki.mp3", "Rolki", "1f6fc"),
         ("10_-_Stryszaki.mp3", "Stryszaki", "1f3da"),
         ("11_-_Ale_len.mp3", "Ale leń", "1f971"),
         ("12_-_Zabiore_brata.mp3", "Zabiorę brata", "1f466"),
         ("13_-_Marzenia_misski.mp3", "Marzenia miski", "1f963"),
         ("14_-_Gdy_leze_na_plazy.mp3", "Gdy leżę na plaży", "1f3d6"),
         ("15_-_Mop_-_rock.mp3", "Mop - rock", "1f3b8"),
         ("16_-_Gdy_tylko_Cyganie.mp3", "Gdy tylko Cyganie", "1f3bb"),
         ("17_-_Rzepke_sobie_skrobie.mp3", "Rzepkę sobie skrobię", "1f955"),
         ("18_-_Katarynka_Karolinka.mp3", "Katarynka Karolinka", "1f3b6"),
         ("19_-_Moja_fantazja.mp3", "Moja fantazja", "1f308"),
         ("20_-_Wyciagnij_dlon.mp3", "Wyciągnij dłoń", "1f91d"),
     ]),
    ("profesor", "Piosenki Profesora Ciekawskiego", [0.20, 0.34, 0.42, 1],
     f"{OLD}/Fasolki/Piosenki_Profesora_Ciekawskiego", [
         ("1_-_Witaminki_dla_chlopczyka_i_dziewczynki.mp3", "Witaminki", "1f34e"),
         ("2_-_Zajac_Poziomka.mp3", "Zając Poziomka", "1f430"),
         ("3_-_Latajacy_odkurzacz.mp3", "Latający odkurzacz", "1f9f9"),
         ("4_-_Czarownica_z_ksiezyca.mp3", "Czarownica z księżyca", "1f9d9"),
         ("5_-_Duchy_lakomczuchy.mp3", "Duchy łakomczuchy", "1f47b"),
         ("6_-_Srebrna_kolezanka.mp3", "Srebrna koleżanka", "1f31f"),
         ("7_-_Dwie_przyjaciolki_nierozlaczki__Papuzki_.mp3", "Papużki nierozłączki", "1f99c"),
         ("8_-_Zmora_z_telewizora.mp3", "Zmora z telewizora", "1f4fa"),
         ("9_-_Trzy_wesole_wielkoludki.mp3", "Trzy wesołe wielkoludki", "1f9cc"),
         ("10_-_Wujcio_Wariatuncio.mp3", "Wujcio Wariatuncio", "1f92a"),
         ("11_-_Pocaluj_zabke_lapke.mp3", "Pocałuj żabkę w łapkę", "1f438"),
         ("12_-_Pierscionek_od_babci.mp3", "Pierścionek od babci", "1f48d"),
         ("13_-_Pojde_przez_park.mp3", "Pójdę przez park", "1f333"),
         ("14_-_Kapelusz_Usmiechmistrza.mp3", "Kapelusz Uśmiechmistrza", "1f3a9"),
         ("15_-_Jestesmy_jedna_rodzina.mp3", "Jesteśmy jedną rodziną", "1f46a"),
         ("16_-_Dzdzownica_jazz.mp3", "Dżdżownica jazz", "1fab1"),
         ("17_-_Moje_hobby_mniam_mniam.mp3", "Moje hobby mniam mniam", "1f36d"),
         ("18_-_Przedszkolne_sztuczki.mp3", "Przedszkolne sztuczki", "1fa84"),
         ("19_-_Wcale,_wcale,_doskonale.mp3", "Wcale, wcale, doskonale", "1f44d"),
         ("20_-_Kropelka_zlotych_marzen.mp3", "Kropelka złotych marzeń", "1f4a7"),
     ]),
    ("english", "Piosenki po angielsku", [0.36, 0.32, 0.18, 1],
     f"{OLD}/Joanna_Gasieniec/Piosenki_dla_przedszkolaka_13", [
         ("1_-_Ding_Dong_Song.mp3", "Ding Dong Song", "1f514"),
         ("2_-_What_I_Like.mp3", "What I Like", "2764"),
         ("3_-_Let_s_Go_to_The_Zoo.mp3", "Let's Go to the Zoo", "1f981"),
         ("4_-_Moody_Weather.mp3", "Moody Weather", "26c5"),
         ("5_-_My_Family.mp3", "My Family", "1f46a"),
         ("6_-_My_Favorite_Toy.mp3", "My Favorite Toy", "1fa80"),
         ("7_-_When_Music_Plays.mp3", "When Music Plays", "1f3b6"),
         ("8_-_Rain,_Rain,_Go_Away.mp3", "Rain, Rain, Go Away", "2614"),
         ("9_-_Hush,_Little_Baby.mp3", "Hush, Little Baby", "1f476"),
         ("10_-_Hickory_Dickory_Dock.mp3", "Hickory Dickory Dock", "1f570"),
     ]),
]
DEFAULT_ICON = "1f3b5"


def make_icon(code: str) -> bool:
    out = ICONS / f"{code}.png"
    if out.exists():
        return True
    svg = Path(f"/tmp/tw_{code}.svg")
    try:
        subprocess.run(["curl", "-fsSL", f"{TWEMOJI}/{code}.svg", "-o", str(svg)], check=True)
        subprocess.run(["rsvg-convert", "-w", str(ICON_PX), "-h", str(ICON_PX), str(svg),
                        "-o", str(out)], check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"  brak ikonki {code} - będzie nuta")
        return False
    finally:
        svg.unlink(missing_ok=True)


def main():
    ICONS.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    make_icon(DEFAULT_ICON)
    albums, songs, missing = [], [], 0
    for key, title, color, folder, items in ALBUMS:
        albums.append({"key": key, "title": title, "color": color})
        for nr, (src, name, code) in enumerate(items, 1):
            source = Path(folder) / src
            target = f"{key}_{nr:02d}{source.suffix.lower()}"
            if not source.exists():
                print(f"  BRAK: {source}")
                missing += 1
                continue
            if not (DEST / target).exists() or (DEST / target).stat().st_size != source.stat().st_size:
                shutil.copyfile(source, DEST / target)
            icon = code if make_icon(code) else DEFAULT_ICON
            songs.append({"file": target, "title": name, "icon": icon, "album": key})
    (MUSIC / "katalog.json").write_text(
        json.dumps({"albums": albums, "songs": songs}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    size = sum(p.stat().st_size for p in DEST.iterdir()) / 2**20
    print(f"MUSIC_OK utworów {len(songs)}, brakujących {missing}, {size:.0f} MB w {DEST}")


if __name__ == "__main__":
    main()
