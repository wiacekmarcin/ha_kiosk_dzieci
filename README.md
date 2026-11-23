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
  | Ubieranie piżamki | 19:45-20:00 | 19:45-20:00 |

- **Analogowy** (środkowy) - wskazówki godzin, minut i sekund, pod spodem dzień tygodnia.
- **Pory roku** (prawy) - cztery ćwiartki z animowanymi ikonami (zima - wirujący płatek,
  wiosna - kołyszący się tulipan, lato - pulsujące słońce, jesień - opadające liście),
  wskazówka pokazuje bieżącą porę roku (astronomiczną: 21.03, 21.06, 23.09, 22.12).

Menu po prawej: dom (powrót do ekranu startowego), godzina HH:MM, data D-M i słuchawka -
wiadomości głosowe przez Home Assistant, tak samo jak w kiosku w holu.

## Budowanie

```
./sync_kiosk.sh "Tablet dzieci"     # kod domofonu z ../ha_kiosk i settings.json
buildozer android release
```

Podgląd na PC (zrzut ekranu i koniec; `DZIECI_NOW` podstawia czas):

```
DZIECI_NOW="2027-04-15 07:20" DZIECI_SCREENSHOT=ekran.png python main.py
```

Obrazki: [Twemoji](https://github.com/jdecked/twemoji) (CC-BY 4.0), pobierane i
przerabiane na PNG przez `tools/make_icons.sh`.
