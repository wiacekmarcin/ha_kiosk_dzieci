#!/usr/bin/env bash
# Instalacja ostatnio zbudowanego APK (bin/<nazwa>-<wersja>-*-release.apk) na tabletach dzieci
# przez adb w sieci - uruchamiać w WSL: ./install.sh [tablet ...] [opcje]
#   bez tabletu: bliźniaczo na wszystkie tablety z listy TABLETS poniżej (ten sam APK)
#   tablet: imię z listy (antoni, mateusz) albo adres:port (imię z listy po adresie
#           albo z opcji --child=Imię)
# Każdy tablet dostaje swój tablet.json (imię pod zegarami, nazwa tabletu w sieci).
# Po instalacji: zgoda na mikrofon, aplikacja jako ekran główny, przypinanie ekranu,
# piosenki (tylko nowe i zmienione pliki), uruchomienie.
# Opcje:
#   --reinstall    gdy na tablecie jest wersja z innym podpisem: odinstaluj i zainstaluj od nowa
#                  (znikają dane aplikacji na tablecie, także wgrane pliki)
#   --no-music     bez wgrywania piosenek
#   --no-start     bez uruchamiania aplikacji
#   --child=Imię   imię dla tabletu podanego adresem spoza listy
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ADB=${ADB:-/mnt/c/KreionAI/aae_ai_local_data/misc/android_tools/platform-tools/adb.exe}
MUSIC_SRC=${MUSIC_SRC:-/mnt/c/KreionAI/aae_ai_local_data/media/audio/muzyka_dzieci}

# Tablety dzieci: "adres:port Imię" (Galaxy Tab 3, LineageOS). Pusty adres - tablet pomijany.
TABLETS=(
  "192.168.10.247:5555 Antoni"
  "192.168.10.243:5555 Mateusz"
)

TARGETS=()
CHILD_OPT=""
REINSTALL=0
MUSIC=1
START=1
for arg in "$@"; do
  case $arg in
    --reinstall) REINSTALL=1 ;;
    --no-music) MUSIC=0 ;;
    --no-start) START=0 ;;
    --child=*) CHILD_OPT=${arg#--child=} ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    -*) echo "Nieznana opcja: $arg"; exit 2 ;;
    *) TARGETS+=("$arg") ;;
  esac
done

NAME=$(sed -n 's/^package.name *= *//p' buildozer.spec)
DOMAIN=$(sed -n 's/^package.domain *= *//p' buildozer.spec)
VER=$(sed -n 's/^version *= *//p' buildozer.spec)
PKG=$DOMAIN.$NAME
APK=$(ls -t bin/$NAME-$VER-*-release.apk 2>/dev/null | head -1)
[ -n "$APK" ] || { echo "Brak bin/$NAME-$VER-*-release.apk - najpierw ./build.sh"; exit 3; }
APKW=$(wslpath -w "$APK")
FILES=/sdcard/Android/data/$PKG/files

# "adres imię" dla celu podanego imieniem albo adresem
resolve() {
  local want=${1,,} entry dev child
  for entry in "${TABLETS[@]}"; do
    read -r dev child <<< "$entry"
    [ -z "$child" ] && { child=$dev; dev=""; }
    if [ "${child,,}" = "$want" ] || [ "$dev" = "$1" ]; then
      echo "$dev|${CHILD_OPT:-$child}"; return
    fi
  done
  echo "$1|$CHILD_OPT"
}

install_one() {
  local DEV=$1 CHILD=$2
  if [ -z "$DEV" ]; then
    echo "== $CHILD: brak adresu tabletu - uzupełnij TABLETS w install.sh"; return 4
  fi
  echo "== $PKG $VER -> $DEV (${CHILD:-bez imienia})"
  "$ADB" connect "$DEV" > /dev/null 2>&1
  if ! timeout 10 "$ADB" -s "$DEV" get-state 2>/dev/null | grep -q device; then
    echo "Tablet $DEV niedostępny (włączony? debugowanie przez sieć? inny port?)"; return 4
  fi
  local OUT
  OUT=$(timeout 300 "$ADB" -s "$DEV" install -r "$APKW" 2>&1)
  if ! echo "$OUT" | grep -q Success; then
    if echo "$OUT" | grep -q INSTALL_FAILED_UPDATE_INCOMPATIBLE; then
      if [ "$REINSTALL" = 1 ]; then
        echo "Inny podpis - odinstalowanie i instalacja od nowa"
        timeout 60 "$ADB" -s "$DEV" uninstall "$PKG"
        OUT=$(timeout 300 "$ADB" -s "$DEV" install "$APKW" 2>&1)
      else
        echo "Na tablecie jest wersja z innym podpisem. Uruchom: ./install.sh $DEV --reinstall"
        return 5
      fi
    fi
    echo "$OUT" | grep -q Success || { echo "$OUT" | tail -3; echo "INSTALACJA NIE UDAŁA SIĘ"; return 5; }
  fi
  echo "INSTALL_OK"
  timeout 20 "$ADB" -s "$DEV" shell pm grant "$PKG" android.permission.RECORD_AUDIO 2>/dev/null
  if ! timeout 20 "$ADB" -s "$DEV" shell pm grant "$PKG" android.permission.WRITE_SECURE_SETTINGS \
    2>/dev/null; then
    echo "UWAGA: nie przyznano WRITE_SECURE_SETTINGS; Android nie zsynchronizuje czasu systemowego." >&2
  fi
  timeout 20 "$ADB" -s "$DEV" shell pm grant "$PKG" cyanogenmod.permission.WRITE_SECURE_SETTINGS 2>/dev/null
  # aparat: zgoda nadana z góry - w trybie kiosku okno zgody Androida może być zablokowane
  timeout 20 "$ADB" -s "$DEV" shell pm grant "$PKG" android.permission.CAMERA 2>/dev/null
  timeout 20 "$ADB" -s "$DEV" shell cmd package set-home-activity "$PKG/org.kivy.android.PythonActivity" \
    > /dev/null 2>&1
  # przypinanie ekranu (tryb kiosku aplikacji): bez tej opcji Android ignoruje startLockTask
  timeout 20 "$ADB" -s "$DEV" shell settings put secure lock_to_app_enabled 1
  if [ -n "$CHILD" ]; then
    # tablet.json: imię pod zegarami i własna nazwa tabletu w sieci (wiadomości, gry)
    local TJ
    TJ=$(mktemp --suffix=.json)
    printf '{"child": "%s", "tablet_name": "Tablet %s"}\n' "$CHILD" "$CHILD" > "$TJ"
    timeout 20 "$ADB" -s "$DEV" shell mkdir -p "$FILES" 2>/dev/null
    if timeout 30 "$ADB" -s "$DEV" push "$(wslpath -w "$TJ")" "$FILES/tablet.json" > /dev/null 2>&1; then
      echo "TABLET_OK $CHILD"
    else
      echo "Nie udało się wgrać tablet.json ($CHILD)"
    fi
    rm -f "$TJ"
  fi
  local PUSH=tools/push_music.sh
  if [ "$MUSIC" = 1 ] && [ -d dzieci/music ] && [ -f "$PUSH" ] && [ -d "$MUSIC_SRC" ]; then
    echo "== piosenki"
    ADB="$ADB" timeout 900 bash "$PUSH" "$DEV" "$PKG" "$MUSIC_SRC" 2>&1 | grep -E 'PUSH_OK|error|files pushed'
  fi
  if [ "$START" = 1 ]; then
    timeout 20 "$ADB" -s "$DEV" shell am force-stop "$PKG"
    timeout 30 "$ADB" -s "$DEV" shell am start -n "$PKG/org.kivy.android.PythonActivity" > /dev/null 2>&1
  fi
  echo "GOTOWE: $PKG $(timeout 20 "$ADB" -s "$DEV" shell dumpsys package "$PKG" \
    | sed -n 's/.*versionName=//p' | head -1) -> ${CHILD:-$DEV}"
}

if [ ${#TARGETS[@]} -eq 0 ]; then
  for entry in "${TABLETS[@]}"; do
    read -r dev child <<< "$entry"
    [ -z "$child" ] && child=$dev
    TARGETS+=("$child")
  done
fi

FAILED=()
for target in "${TARGETS[@]}"; do
  IFS='|' read -r dev child <<< "$(resolve "$target")"
  install_one "$dev" "$child" || FAILED+=("${child:-$dev}")
done
if [ ${#FAILED[@]} -gt 0 ]; then
  echo "NIE ZAINSTALOWANO: ${FAILED[*]}"; exit 4
fi
echo "WSZYSTKIE_OK"
