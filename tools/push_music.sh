#!/usr/bin/env bash
# Wgrywa piosenki (folder z tools/make_music.py) na tablet przez adb do katalogu plików
# aplikacji: /sdcard/Android/data/<pakiet>/files/muzyka (aplikacja czyta go bez uprawnień).
# --sync wysyła tylko nowe i zmienione pliki.
# Użycie: tools/push_music.sh <urządzenie adb> [pakiet] [folder]
#   tools/push_music.sh 192.168.10.247:5555
#   tools/push_music.sh 192.168.10.246:45331 pl.mieszkanie.haintercom
set -euo pipefail
DEV=${1:?podaj urządzenie adb, np. 192.168.10.247:5555}
PKG=${2:-pl.mieszkanie.hakioskdzieci}
SRC=${3:-/mnt/c/KreionAI/aae_ai_local_data/media/audio/muzyka_dzieci}
ADB=${ADB:-/mnt/c/KreionAI/aae_ai_local_data/misc/android_tools/platform-tools/adb.exe}
DIR=/sdcard/Android/data/$PKG/files/muzyka
"$ADB" connect "$DEV" > /dev/null 2>&1 || true
"$ADB" -s "$DEV" shell mkdir -p "$DIR"
"$ADB" -s "$DEV" push --sync "$(wslpath -w "$SRC")\\." "$DIR/"
echo "PUSH_OK $("$ADB" -s "$DEV" shell ls "$DIR" | wc -l) plików w $DIR"
