"""Plan dnia i pory roku - położenie wskazówek zegarów (bez Kivy, łatwe do testów).

Kąty liczone w stopniach od godziny 12 zgodnie z ruchem wskazówek zegara.
"""
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Activity:
    key: str        # nazwa obrazka w assets/icons
    label: str
    start: int      # minuta doby
    end: int        # minuta doby (koniec wyłączny; sen przechodzi przez północ)


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# Kolejność na tarczy od góry, zgodnie z ruchem wskazówek zegara.
DAY_PLAN = [
    Activity("sen", "Sen", _m("20:00"), _m("07:00")),
    Activity("mycie", "Mycie", _m("07:00"), _m("07:15")),
    Activity("sniadanie", "Śniadanie", _m("07:15"), _m("07:30")),
    Activity("zeby", "Mycie zębów", _m("07:30"), _m("07:45")),
    Activity("ubieranie", "Ubieranie się", _m("07:45"), _m("08:00")),
    Activity("przedszkole", "Zabawa w przedszkolu", _m("08:00"), _m("17:00")),
    Activity("czas_wolny", "Czas wolny", _m("17:00"), _m("19:00")),
    Activity("kolacja", "Kolacja", _m("19:00"), _m("19:15")),
    Activity("kapiel", "Mycie", _m("19:15"), _m("19:30")),
    Activity("zeby", "Mycie zębów", _m("19:30"), _m("19:45")),
    Activity("pidzama", "Ubieranie piżamki", _m("19:45"), _m("20:00")),
]
SECTOR = 360 / len(DAY_PLAN)


def _length(a: Activity) -> int:
    return (a.end - a.start) % 1440


def current_activity(now: datetime):
    """(indeks czynności, ułamek jej upływu 0..1)."""
    minute = now.hour * 60 + now.minute + now.second / 60
    for i, a in enumerate(DAY_PLAN):
        passed = (minute - a.start) % 1440
        if passed < _length(a):
            return i, passed / _length(a)
    return 0, 0.0


def day_angle(now: datetime) -> float:
    """Wskazówka pór dnia: każda czynność ma na tarczy równy wycinek (środek sennego
    wycinka na górze), wskazówka przesuwa się w nim proporcjonalnie do upływu czasu."""
    i, frac = current_activity(now)
    return ((i - 0.5 + frac) * SECTOR) % 360


def sector_center(i: int) -> float:
    return (i * SECTOR) % 360


# Pory roku: ćwiartki tarczy zgodnie z ruchem wskazówek od godziny 12.
# Patrząc przeciwnie do ruchu wskazówek od lewej górnej: zima, jesień, lato, wiosna.
SEASONS = [
    ("wiosna", "Wiosna", (3, 21)),
    ("lato", "Lato", (6, 21)),
    ("jesien", "Jesień", (9, 23)),
    ("zima", "Zima", (12, 22)),
]


def _season_starts(year: int):
    return [date(year, m, d) for _k, _l, (m, d) in SEASONS]


def current_season(today: date):
    """(indeks pory roku, ułamek jej upływu 0..1)."""
    starts = _season_starts(today.year)
    if today < starts[0]:                               # styczeń - 20 marca: zima
        begin = date(today.year - 1, 12, 22)
        return 3, (today - begin).days / (starts[0] - begin).days
    for i in range(3, -1, -1):
        if today >= starts[i]:
            end = starts[i + 1] if i < 3 else date(today.year + 1, 3, 21)
            return i, (today - starts[i]).days / (end - starts[i]).days
    return 0, 0.0


def season_angle(today: date) -> float:
    i, frac = current_season(today)
    return (i + frac) * 90


WEEKDAYS = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
