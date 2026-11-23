#!/usr/bin/env bash
# Przed budowaniem: wspólny kod (domofon, ikony, okna) i zasoby z ../ha_kiosk
# oraz settings.json (token HA z kiosku, adres HA w sieci lokalnej, nazwa tabletu).
# Użycie: ./sync_kiosk.sh ["Nazwa tabletu"] ["http://adres-ha:8123"]
set -euo pipefail
cd "$(dirname "$0")"
KIOSK=../ha_kiosk
NAME="${1:-Tablet dzieci}"
URL="${2:-http://192.168.10.250:8123}"
rm -rf kiosk assets/fonts assets/sounds
mkdir -p assets
cp -r "$KIOSK/kiosk" kiosk
cp -r "$KIOSK/assets/fonts" assets/fonts
cp -r "$KIOSK/assets/sounds" assets/sounds
find kiosk -name __pycache__ -type d -prune -exec rm -rf {} +
python3 - "$KIOSK/settings.json" settings.json "$NAME" "$URL" <<'EOF'
import json, sys
src, dst, name, url = sys.argv[1:5]
s = json.load(open(src, encoding="utf-8"))
out = {"url": url, "token": s["token"], "tablet_name": name}
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("settings.json:", out["url"], "/", name)
EOF
