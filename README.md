# Kiosk dzieci

Aplikacja na tablet w pokoju dzieci (Samsung Galaxy Tab 3 10.1 GT-P5210, LineageOS 14.1,
Android 7.1, x86), napisana w Kivy jak [ha_kiosk_hol](https://github.com/wiacekmarcin/ha_kiosk_hol).

## Ekran startowy

Trzy zegary:

- **Pory dnia** (lewy) - plan dnia obrazkami, wskazówka pokazuje bieżącą czynność.
  Każda czynność ma na tarczy równy wycinek (sen u góry), wskazówka przesuwa się w nim
  w miarę upływu czasu. Plan w `dzieci/plan.py`:

  | Czynność | Poniedziałek-piątek | Sobota i niedziela |
  |---|---|---|
  | Sen | 20:00-7:00 | 20:00-7:00 |
  | Mycie | 7:00-7:15 | 7:00-7:15 |
  | Śniadanie | 7:15-7:30 | 7:15-7:30 |
  | Mycie zębów | 7:30-7:45 | 7:30-7:45 |
  | Ubieranie się | 7:45-8:00 | 7:45-8:00 |
  | Zabawa w przedszkolu / Zabawa | 8:00-17:00 | 8:00-15:00 |
  | Obiad | - | 15:00-16:00 |
  | Czas wolny / Plac zabaw | 17:00-19:00 | 16:00-19:00 |
  | Kolacja | 19:00-19:15 | 19:00-19:15 |
  | Mycie | 19:15-19:30 | 19:15-19:30 |
  | Mycie zębów | 19:30-19:45 | 19:30-19:45 |
  | Czytanie książki | 19:45-20:00 | 19:45-20:00 |

  Przy zmianie czynności tablet mówi, co teraz (gong i np. „Czas na śniadanie”);
  dotknięcie tarczy powtarza komunikat. Nagrania w `assets/komunikaty` robi
  `tools/make_sounds.py` (edge-tts, głos pl-PL-ZofiaNeural).

- **Analogowy** (środkowy) - wskazówki godzin, minut i sekund, pod spodem dzień tygodnia.
- **Pory roku** (prawy) - cztery ćwiartki z animowanymi ikonami (zima - wirujący płatek,
  wiosna - kołyszący się tulipan, lato - pulsujące słońce, jesień - opadające liście),
  wskazówka pokazuje bieżącą porę roku (astronomiczną: 21.03, 21.06, 23.09, 22.12).

Menu po prawej: dom (powrót do ekranu startowego), słuchawka - wiadomości głosowe przez
Home Assistant, aparat i galeria zdjęć.

Nad zegarem analogowym widać godzinę HH:MM:SS w formacie 24-godzinnym, a nad zegarem pór
roku - dzień, nazwę miesiąca i aktualną porę roku. Przycisk „Sprawdź” znajduje się blisko
lewego zegara. Kliknięcie godziny odczytuje godziny, minuty i sekundy; kliknięcie daty
odczytuje dzień, miesiąc i porę roku. Odczyty są ograniczone do jednego na 15 sekund.
Pod lewym zegarem są skróty do odtwarzania/pauzy i zatrzymania muzyki oraz suwak
głośności; wygaszacz jest w menu po prawej.

Galeria pod ikoną aparatu pokazuje do 10 miniatur naraz. Przyciski `−1`/`+1` i
`−10`/`+10` przesuwają widok po zdjęciach; dotknięcie miniatury otwiera pełne zdjęcie.

## Budowanie

```
./sync_kiosk.sh "Tablet dzieci"     # kod domofonu z ../ha_kiosk i settings.json
buildozer android release
```

Podgląd na PC (zrzut ekranu i koniec; `DZIECI_NOW` podstawia czas):

```
DZIECI_NOW="2027-04-15 07:20" DZIECI_SCREENSHOT=ekran.png python main.py
```

## Gry

Przycisk z padem w menu po prawej otwiera siatkę gier; w każdej grze u góry jest przycisk
„Wstecz” (do siatki gier).

- **Kółko i krzyżyk** - dwóch graczy na zmianę: Gracz 1 stawia krzyżyki, Gracz 2 kółka;
  trzy w wierszu, kolumnie albo po skosie wygrywają, pełna plansza to remis. Nowa gra
  zaczyna się sama po 3 s.
- **Gra przez sieć** (kółko i krzyżyk, warcaby, szachy) - przycisk z ikoną sieci wysyła
  zaproszenie do pozostałych tabletów z grami (Kiosk dzieci, HA Intercom na Tablecie 2);
  na nich pojawia się okno „… zaprasza do gry” z przyciskami Graj i Nie. Zapraszający
  gra białymi / krzyżykiem, każdy tablet stuka tylko w swojej kolejce. Komunikaty idą
  przez Home Assistant (encja `sensor.kiosk_gra`, `dzieci/games/net.py`), jak domofon.
  Wyjście z gry albo „Nowa gra” kończy partię u obu graczy.
- **Warcaby** (8x8) i **Szachy** - przyciski z jedną głową (1 gracz, gra z komputerem
  na poziomie łatwym; dziecko gra białymi) albo dwiema głowami (2 graczy na zmianę, na dole
  napis, czyja kolej). Podczas tury gracza podświetlone są figury/pionki mogące wykonać
  ruch; stuknięcie pionka lub figury pokazuje zielone kropki na dozwolonych polach.
  Dopiero stuknięcie w pole z kropką przesuwa pionek.
  - Warcaby: bicie obowiązkowe i wielokrotne, pionki biją też do tyłu, damka „latająca”.
    Uproszczenie: nie trzeba wybierać bicia z największą liczbą pionków. Komputer
    wybiera losowy dozwolony ruch, chętniej z promocją na damkę.
  - Szachy: pełne zasady - roszada, bicie w przelocie, promocja (na hetmana), szach,
    mat i pat. Komputer zwykle zbija najcenniejszą figurę, jaką może, poza tym gra losowo.
- **Rysowanie** - 9 kolorów, 3 grubości pędzla, gumka i „Wyczyść”.
- **Rzut kostką** - przycisk „Rzuć”: kostka podskakuje i się obraca, po 1 s pokazuje
  wylosowaną liczbę 1-6 jako ściankę z kropkami.

Zasady gier są w `dzieci/games` bez zależności od ekranu (szachy sprawdzone testem perft).
Figury szachowe: czcionka DejaVu Sans (`assets/fonts_dzieci`, licencja w LICENSE-DejaVu.txt).
Obrazki: [Twemoji](https://github.com/jdecked/twemoji) (CC-BY 4.0), pobierane i
przerabiane na PNG przez `tools/make_icons.sh`.
