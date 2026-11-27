[app]
title = Kiosk dzieci
package.name = hakioskdzieci
package.domain = pl.mieszkanie
version = 0.39
source.dir = .
source.include_exts = py,png,kv,ttf,json,ogg,mp3
source.exclude_dirs = tools, bin, .buildozer, __pycache__, .venv, venv
source.exclude_patterns = buildozer.spec, sync_kiosk.sh, README.md
# kiosk/ i assets/fonts, assets/sounds kopiuje sync_kiosk.sh z ../ha_kiosk (ha_kiosk_hol);
# settings.json (z tokenem HA) jest wbudowany w APK - nie udostępniaj pliku APK.
requirements = python3,kivy==2.3.1,requests,urllib3,certifi,charset-normalizer,idna,openssl
orientation = landscape
fullscreen = 1
android.permissions = INTERNET, ACCESS_NETWORK_STATE, RECORD_AUDIO, WAKE_LOCK, ACCESS_WIFI_STATE, CHANGE_WIFI_MULTICAST_STATE, CAMERA, WRITE_SECURE_SETTINGS, cyanogenmod.permission.WRITE_SECURE_SETTINGS
# tryb kiosku jako właściciel urządzenia (dzieci/kiosklock.py): odbiornik administratora
# urządzenia. Szablon manifestu python-for-android nie ma miejsca na <receiver>, więc
# element wchodzi przez wpis uses-library (dwie opcjonalne biblioteki "kiosk.*" na brzegach).
android.add_src = android_src
android.add_resources = android_res/device_admin.xml:xml/device_admin.xml
android.uses_library = kiosk.admin.start" android:required="false" /><receiver android:name="pl.mieszkanie.hakioskdzieci.AdminReceiver" android:permission="android.permission.BIND_DEVICE_ADMIN" android:exported="true"><meta-data android:name="android.app.device_admin" android:resource="@xml/device_admin" /><intent-filter><action android:name="android.app.action.DEVICE_ADMIN_ENABLED" /></intent-filter></receiver><uses-library android:required="false" android:name="kiosk.admin.end
android.api = 33
android.minapi = 21
android.ndk_api = 21
# Galaxy Tab 3 10.1 (GT-P5210) - procesor Intel Atom
android.archs = x86
android.accept_sdk_license = True
android.allow_backup = False
android.wakelock = True
# jedna aktywność: sygnał "ekran główny" (Home) trafia do działającej aplikacji; przy
# domyślnym trybie Android tworzył drugą aktywność, SDL się wywracał (NullPointerException
# w SDLSurface), a system kasował ustawienie aplikacji jako ekranu głównego
android.manifest.launch_mode = singleTask
# aplikacja może być ekranem głównym (launcherem) tabletu
android.home_app = True
android.release_artifact = apk

[buildozer]
# wspólny katalog budowania kiosków (ha_kiosk, ha_kiosk_dzieci, ha_intercom) - biblioteki
# skompilowane raz dla danej architektury; budować po kolei, nie równolegle
build_dir = ../.buildozer-wspolny
log_level = 2
warn_on_root = 1
