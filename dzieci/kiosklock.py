"""Blokada tabletu (tryb kiosku) i wyjście z aplikacji.

Blokada: aplikacja przypina się do ekranu (Android startLockTask - "przypinanie ekranu"):
Home, lista ostatnich aplikacji i pasek powiadomień nie wyprowadzają z aplikacji. Przyciski
Wstecz i Menu obsługuje GamesHost (zawsze bez reakcji). Przy pierwszym przypięciu Android
pyta "Przypiąć aplikację?" - trzeba potwierdzić; na tabletach z aplikacją jako
właścicielem urządzenia (device owner, tylko Kiosk dzieci - klasa AdminReceiver) przypięcie
jest ciche, nie da się go zdjąć gestem, a aplikacja jest stałym ekranem głównym.
Wyjście: przycisk na dole menu -> okno potwierdzenia, "Tak" trzeba nacisnąć EXIT_PRESSES
razy (dziecko nie wyjdzie przypadkiem). Wyjście zdejmuje przypięcie i otwiera zwykły ekran
główny tabletu (inna aplikacja "Home" niż ta), bo ta aplikacja jest ekranem głównym i
sama by się zaraz uruchomiła ponownie.
"""
import os

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.logger import Logger
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.utils import platform

EXIT_PRESSES = 3
RELOCK_SECONDS = 2.0            # po powrocie do aplikacji przypięcie wraca po chwili
RELEASE_FLAG = "zwolnij_kiosk"  # plik w katalogu plików aplikacji: koniec właściciela urządzenia
ANDROID = platform == "android"
_state = {"locked": False, "leaving": False, "owner": False}


def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def _on_ui(fn):
    """Wywołanie w wątku interfejsu Androida (startLockTask tego wymaga)."""
    from android.runnable import run_on_ui_thread
    run_on_ui_thread(fn)()


def _owner_setup(activity) -> bool:
    """Właściciel urządzenia (adb shell dpm set-device-owner <pakiet>/.AdminReceiver):
    zezwolenie na ciche przypięcie i aplikacja jako stały ekran główny. Plik RELEASE_FLAG
    w katalogu plików aplikacji (adb push) zwalnia właściciela urządzenia - awaryjne wyjście
    z trybu kiosku. False - aplikacja nie jest właścicielem urządzenia."""
    try:
        from jnius import autoclass
        Context = autoclass("android.content.Context")
        ComponentName = autoclass("android.content.ComponentName")
        Intent = autoclass("android.content.Intent")
        IntentFilter = autoclass("android.content.IntentFilter")
        dpm = activity.getSystemService(Context.DEVICE_POLICY_SERVICE)
        pkg = activity.getPackageName()
        if not dpm.isDeviceOwnerApp(pkg):
            return False
        admin = ComponentName(pkg, pkg + ".AdminReceiver")
        ext = activity.getExternalFilesDir(None)
        if ext is not None and os.path.exists(os.path.join(ext.getAbsolutePath(), RELEASE_FLAG)):
            Logger.warning("Blokada: plik zwolnienia - aplikacja przestaje być właścicielem urządzenia")
            dpm.clearPackagePersistentPreferredActivities(admin, pkg)
            dpm.setLockTaskPackages(admin, [])
            dpm.clearDeviceOwnerApp(pkg)
            return False
        if not _state["owner"]:
            dpm.setLockTaskPackages(admin, [pkg])
            home = IntentFilter(Intent.ACTION_MAIN)
            home.addCategory(Intent.CATEGORY_HOME)
            home.addCategory(Intent.CATEGORY_DEFAULT)
            dpm.addPersistentPreferredActivity(
                admin, home, ComponentName(pkg, "org.kivy.android.PythonActivity"))
            _state["owner"] = True
        return True
    except Exception as e:          # noqa: BLE001
        Logger.warning(f"Blokada: właściciel urządzenia: {e}")
        return False


def lock():
    """Przypięcie aplikacji do ekranu (bez skutku na PC)."""
    _state["leaving"] = False
    if not ANDROID or _state["locked"]:
        return

    def work():
        try:
            if _owner_setup(_activity()):
                Logger.info("Blokada: właściciel urządzenia - przypięcie ciche")
            _activity().startLockTask()
            _state["locked"] = True
        except Exception as e:      # noqa: BLE001 - np. wyłączone przypinanie ekranu
            Logger.warning(f"Blokada: startLockTask: {e}")
    _on_ui(work)


def relock_later():
    """Po powrocie do aplikacji (on_resume) - ponowne przypięcie, chyba że wychodzimy."""
    _state["locked"] = False
    if not _state["leaving"]:
        Clock.schedule_once(lambda _dt: lock(), RELOCK_SECONDS)


def leave():
    """Wyjście: zdjęcie przypięcia i przejście do zwykłego ekranu głównego tabletu.
    Przy właścicielu urządzenia aplikacja jest stałym ekranem głównym, więc inny ekran
    główny otwierany jest jawnie (po klasie); powrót klawiszem Home wraca do kiosku."""
    _state["leaving"] = True
    if not ANDROID:
        App.get_running_app().stop()
        return

    def work():
        activity = _activity()
        try:
            activity.stopLockTask()
        except Exception as e:      # noqa: BLE001
            Logger.warning(f"Blokada: stopLockTask: {e}")
        _state["locked"] = False
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            home = Intent(Intent.ACTION_MAIN)
            home.addCategory(Intent.CATEGORY_HOME)
            own = activity.getPackageName()
            for info in activity.getPackageManager().queryIntentActivities(home, 0).toArray():
                pkg = info.activityInfo.packageName
                if pkg != own and pkg != "com.android.settings":
                    home.setClassName(pkg, info.activityInfo.name)
                    home.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    activity.startActivity(home)
                    return
            activity.moveTaskToBack(True)
        except Exception as e:      # noqa: BLE001
            Logger.warning(f"Blokada: ekran główny: {e}")
            activity.moveTaskToBack(True)
    _on_ui(work)


class ExitPopup(ModalView):
    """Okno "Wyjść z aplikacji?" - Tak trzeba nacisnąć EXIT_PRESSES razy, Nie zamyka."""
    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), size=(640, 340), auto_dismiss=False,
                         background_color=(0, 0, 0, 0.6), **kwargs)
        self.presses = 0
        box = BoxLayout(orientation="vertical", padding=28, spacing=22)
        with box.canvas.before:
            Color(0.16, 0.19, 0.29, 1)
            self._bg = RoundedRectangle(radius=[28])
        box.bind(pos=lambda w, v: setattr(self._bg, "pos", v),
                 size=lambda w, v: setattr(self._bg, "size", v))
        box.add_widget(Label(text="Wyjść z aplikacji?", font_size="38sp", bold=True,
                             color=(1.0, 0.84, 0.40, 1), size_hint_y=None, height=56))
        self.info = Label(text=self._info_text(), font_size="26sp",
                          color=(0.95, 0.95, 0.98, 1))
        box.add_widget(self.info)
        row = BoxLayout(spacing=24, size_hint_y=None, height=96)
        for text, action, color in (("Tak", self.yes, (0.80, 0.30, 0.25, 1)),
                                    ("Nie", self.dismiss, (0.25, 0.70, 0.25, 1))):
            b = Button(text=text, font_size="34sp", bold=True, background_normal="",
                       background_color=color)
            b.bind(on_release=lambda _b, a=action: a())
            row.add_widget(b)
        box.add_widget(row)
        self.add_widget(box)

    def _info_text(self):
        left = EXIT_PRESSES - self.presses
        return f"Aby wyjść, naciśnij „Tak” jeszcze {left} " + ("raz" if left == 1 else "razy")

    def yes(self):
        self.presses += 1
        if self.presses >= EXIT_PRESSES:
            self.dismiss()
            leave()
        else:
            self.info.text = self._info_text()


def ask_exit():
    ExitPopup().open()
