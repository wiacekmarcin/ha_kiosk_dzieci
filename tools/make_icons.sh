#!/usr/bin/env bash
# Obrazki zegarów z Twemoji (CC-BY 4.0, https://github.com/jdecked/twemoji):
# SVG z jsDelivr -> PNG 256x256 w assets/icons. Wymaga: curl, rsvg-convert (librsvg2-bin).
set -euo pipefail
cd "$(dirname "$0")/.."
BASE=https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/svg
OUT=assets/icons
mkdir -p "$OUT"
# nazwa pliku = kod emoji
declare -A ICONS=(
  [sen]=1f6cc            # osoba w łóżku
  [mycie]=1f9fc          # mydło
  [sniadanie]=1f963      # miska z łyżką
  [zeby]=1faa5           # szczoteczka do zębów
  [ubieranie]=1f455      # koszulka
  [przedszkole]=1f9f8    # miś
  [czas_wolny]=1f6dd     # zjeżdżalnia (też plac zabaw w weekend)
  [zabawa]=1f9e9         # puzzle - zabawa w weekend
  [obiad]=1f372          # garnek z jedzeniem
  [kolacja]=1f37d        # talerz ze sztućcami
  [kapiel]=1f6c1         # wanna
  [ksiazka]=1f4d6        # otwarta książka - czytanie przed snem
  [zima]=2744            # płatek śniegu
  [wiosna]=1f337         # tulipan
  [lato]=2600            # słońce
  [jesien]=1f342         # opadające liście
  [gra_kolko]=23-20e3    # krzyżyk w kratce (#) - kółko i krzyżyk
  [gra_warcaby]=1f3c1    # flaga w szachownicę - warcaby
  [gra_szachy]=265f      # pionek szachowy
  [gra_paint]=1f3a8      # paleta malarza - rysowanie
  [gra_kostka]=1f3b2     # kostka do gry
  [gra_kropki]=1f533     # kwadrat z ramką - kropki
  [gra_statki]=1f6a2     # statek - statki
  [gra_pkropki]=1f534    # czerwona kropka - polskie kropki
  [gra_tetris]=1f9f1     # cegła - tetris
  [gra_waz]=1f40d        # wąż
  [gra_pilkarzyki]=26bd  # piłka - piłkarzyki na papierze
)
for name in "${!ICONS[@]}"; do
  code=${ICONS[$name]}
  curl -fsSL "$BASE/$code.svg" -o "/tmp/tw_$code.svg"
  rsvg-convert -w 256 -h 256 "/tmp/tw_$code.svg" -o "$OUT/$name.png"
  rm -f "/tmp/tw_$code.svg"
  echo "$name <- $code"
done
