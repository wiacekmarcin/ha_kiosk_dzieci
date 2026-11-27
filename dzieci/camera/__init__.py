"""Aparat dla dzieci: podgląd z kamery tabletu, zdjęcie przyciskiem migawki, przełączanie
kamery (tylna / przednia) i przeglądanie zrobionych zdjęć.

Zdjęcia: JPEG w pełnej rozdzielczości aparatu (Camera.takePicture), zapisywane na karcie SD:
/storage/<karta>/Android/data/pl.mieszkanie.hakioskdzieci/files/Zdjecia - Android 7 pozwala
aplikacji pisać na karcie tylko w jej własnym katalogu (bez dodatkowych zgód). Bez karty -
pamięć wewnętrzna tabletu (ten sam katalog na /sdcard), z informacją na ekranie.
Uwaga: odinstalowanie aplikacji (install.sh --reinstall) usuwa ten katalog razem ze zdjęciami.

Kamera Galaxy Tab 3 (LineageOS) źle znosi szybkie zamykanie i ponowne otwieranie (zob.
ha_kiosk/kiosk/screensaver.py), dlatego między zamknięciem a otwarciem jest REOPEN_GAP.
"""
import time
from datetime import datetime
from pathlib import Path

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.utils import platform

ANDROID = platform == "android"
PHOTO_DIR = "Zdjecia"
MAX_PREVIEW_WIDTH = 1280        # podgląd: największy rozmiar do tej szerokości
FALLBACK_PREVIEW = (640, 480)   # rozmiar podglądu obsługiwany przez każdą kamerę
JPEG_QUALITY = 92
REOPEN_GAP = 1.5                # s od zamknięcia kamery do ponownego otwarcia
GALLERY_WINDOW = 10
THUMBNAIL_SIZE = (320, 240)
_sizes_cache = {}               # indeks kamery -> (podgląd, zdjęcie)
_picture_cb = None              # jeden obiekt Javy na całe życie aplikacji
_screen = None                  # ekran aparatu (pauza / wznowienie aplikacji)


def photos_dir():
    """(katalog zdjęć, czy na karcie SD)."""
    if ANDROID:
        try:
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            Environment = autoclass("android.os.Environment")
            for d in activity.getExternalFilesDirs(None):
                if (d is not None and Environment.isExternalStorageRemovable(d)
                        and Environment.getExternalStorageState(d) == "mounted"):
                    return Path(d.getAbsolutePath()) / PHOTO_DIR, True
            ext = activity.getExternalFilesDir(None)
            if ext is not None:
                return Path(ext.getAbsolutePath()) / PHOTO_DIR, False
        except Exception as e:      # noqa: BLE001
            Logger.warning(f"Aparat: katalog zdjęć: {e}")
    return Path(App.get_running_app().user_data_dir) / PHOTO_DIR, False


def list_photos() -> list:
    """Zdjęcia od najstarszego do najnowszego (nazwy z datą i godziną)."""
    folder, _sd = photos_dir()
    try:
        return sorted(str(p) for p in folder.glob("*.jpg"))
    except OSError:
        return []


def thumbnail_path(photo: str) -> str:
    """Tworzy małą miniaturę w cache, dekodując JPEG z niższą rozdzielczością na Androidzie."""
    if not ANDROID:
        return photo
    source = Path(photo)
    target = Path(App.get_running_app().user_data_dir) / "Galeria" / f"{source.stem}.jpg"
    try:
        if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
            return str(target)
        from jnius import autoclass
        BitmapFactory = autoclass("android.graphics.BitmapFactory")
        Options = autoclass("android.graphics.BitmapFactory$Options")
        options = Options()
        options.inJustDecodeBounds = True
        BitmapFactory.decodeFile(str(source), options)
        sample = 1
        while (options.outWidth // (sample * 2) >= THUMBNAIL_SIZE[0]
               and options.outHeight // (sample * 2) >= THUMBNAIL_SIZE[1]):
            sample *= 2
        options.inJustDecodeBounds = False
        options.inSampleSize = sample
        thumb = BitmapFactory.decodeFile(str(source), options)
        if thumb is None:
            raise RuntimeError(f"nie udało się zdekodować zdjęcia {source.name}")
        width, height = thumb.getWidth(), thumb.getHeight()
        scale = min(THUMBNAIL_SIZE[0] / width, THUMBNAIL_SIZE[1] / height, 1)
        if scale < 1:
            scaled = autoclass("android.graphics.Bitmap").createScaledBitmap(
                thumb, int(width * scale), int(height * scale), True)
            if scaled != thumb:
                thumb.recycle()
            thumb = scaled
        output = autoclass("java.io.ByteArrayOutputStream")()
        bitmap_format = autoclass("android.graphics.Bitmap$CompressFormat").JPEG
        if not thumb.compress(bitmap_format, 82, output):
            raise RuntimeError(f"nie udało się zapisać miniatury {source.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output.toByteArray().tostring())
        thumb.recycle()
        output.close()
        return str(target)
    except Exception as exc:  # noqa: BLE001 - miniatura może zawieść, oryginał nadal działa
        Logger.warning(f"Galeria: miniatura {source.name}: {exc}")
        return photo


def new_photo_path() -> Path:
    folder, _sd = photos_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stem = "zdjecie_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path, n = folder / f"{stem}.jpg", 2
    while path.exists():
        path, n = folder / f"{stem}_{n}.jpg", n + 1
    return path


def choose_sizes(previews, pictures):
    """(rozmiar podglądu, rozmiar zdjęcia): zdjęcie największe, podgląd o tych samych
    proporcjach (kadr podglądu = kadr zdjęcia) i nie szerszy niż MAX_PREVIEW_WIDTH."""
    def area(s):
        return s[0] * s[1]
    picture = max(pictures, key=area) if pictures else None
    fit = [s for s in previews if s[0] <= MAX_PREVIEW_WIDTH]
    if picture:
        aspect = picture[0] / picture[1]
        same = [s for s in fit if abs(s[0] / s[1] - aspect) < 0.03]
        fit = same or fit
    return (max(fit, key=area) if fit else FALLBACK_PREVIEW), picture


def camera_count() -> int:
    if not ANDROID:
        return 1
    try:
        from jnius import autoclass
        return int(autoclass("android.hardware.Camera").getNumberOfCameras())
    except Exception:               # noqa: BLE001
        return 1


def _camera_sizes(index):
    """Obsługiwane rozmiary kamery - odczyt raz na uruchomienie aplikacji."""
    if index not in _sizes_cache:
        sizes = (FALLBACK_PREVIEW, None)
        if ANDROID:
            from jnius import autoclass
            cam = autoclass("android.hardware.Camera").open(index)
            try:
                params = cam.getParameters()
                previews = [(s.width, s.height) for s in params.getSupportedPreviewSizes().toArray()]
                pictures = [(s.width, s.height) for s in params.getSupportedPictureSizes().toArray()]
                sizes = choose_sizes(previews, pictures)
            finally:
                cam.release()
        _sizes_cache[index] = sizes
        Logger.info(f"Aparat: kamera {index} - podgląd {sizes[0]}, zdjęcie {sizes[1]}")
    return _sizes_cache[index]


def _picture_callback(handler):
    """Camera.PictureCallback (jeden obiekt Javy - kolejne zdjęcia podmieniają handler)."""
    global _picture_cb
    if _picture_cb is None:
        from jnius import PythonJavaClass, java_method

        class PictureCallback(PythonJavaClass):
            __javainterfaces__ = ["android/hardware/Camera$PictureCallback"]
            __javacontext__ = "app"

            def __init__(self):
                super().__init__()
                self.handler = None

            @java_method("([BLandroid/hardware/Camera;)V")
            def onPictureTaken(self, data, camera):
                handler = self.handler
                if handler:
                    handler(data.tostring() if data is not None else b"", camera)

        _picture_cb = PictureCallback()
    _picture_cb.handler = handler
    return _picture_cb


def on_app_pause():
    """Wygaszony ekran / aplikacja w tle: kamera zwolniona."""
    if _screen is not None and _screen._core is not None:
        _screen.stop()
        _screen._resume = True


def on_app_resume():
    if _screen is not None and _screen._resume:
        _screen._resume = False
        if _screen.manager is not None and _screen.manager.current == _screen.name:
            _screen.start()


class CameraView(Widget):
    """Podgląd kamery dopasowany do pola (bez rozciągania); przednia kamera jak lustro."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._texture = None
        self._mirror = False
        with self.canvas:
            Color(1, 1, 1, 1)
            self._rect = Rectangle()
        self.bind(pos=self._layout, size=self._layout)

    def show(self, texture, mirror=False):
        self._texture, self._mirror = texture, mirror
        self._layout()

    def refresh(self, *_):
        self.canvas.ask_update()

    def _layout(self, *_):
        tex = self._texture
        if tex is None or not tex.width or not tex.height:
            self._rect.texture, self._rect.size = None, (0, 0)
            return
        scale = min(self.width / tex.width, self.height / tex.height)
        w, h = tex.width * scale, tex.height * scale
        self._rect.texture = tex
        self._rect.pos = (self.center_x - w / 2, self.center_y - h / 2)
        self._rect.size = (w, h)
        tc = list(tex.tex_coords)
        if self._mirror:
            tc = tc[2:4] + tc[0:2] + tc[6:8] + tc[4:6]
        self._rect.tex_coords = tc


class CameraScreen(Screen):
    message = StringProperty("")        # napis na podglądzie (start, brak kamery, zapis)
    storage = StringProperty("")        # gdzie trafiają zdjęcia
    last_photo = StringProperty("")     # miniatura ostatniego zdjęcia
    count = NumericProperty(0)
    busy = BooleanProperty(False)       # trwa robienie zdjęcia
    index = NumericProperty(0)          # 0 - tylna kamera, 1 - przednia
    cameras = NumericProperty(1)

    def __init__(self, **kwargs):
        global _screen
        super().__init__(**kwargs)
        _screen = self
        self._core = None
        self._open_ev = None
        self._closed_at = -REOPEN_GAP
        self._resume = False

    # --- ekran ------------------------------------------------------------------------
    def on_enter(self, *_):
        _folder, on_sd = photos_dir()
        self.storage = "Zdjęcia na karcie SD" if on_sd else "Brak karty SD - zdjęcia w tablecie"
        photos = list_photos()
        self.count = len(photos)
        self.last_photo = photos[-1] if photos else ""
        self.cameras = camera_count()
        self.start()

    def on_leave(self, *_):
        self.stop()

    # --- kamera -----------------------------------------------------------------------
    def start(self):
        if self._core is not None or self._open_ev is not None:
            return
        self.message = "Uruchamianie aparatu…"
        from kiosk.widgets.qr_scanner import ensure_camera_permission
        ensure_camera_permission(self._granted)

    def _granted(self, granted):
        if not granted:
            self.message = "Brak zgody na użycie aparatu"
            return
        if self.manager is None or self.manager.current != self.name or self._open_ev:
            return
        wait = REOPEN_GAP - (time.monotonic() - self._closed_at)
        self._open_ev = Clock.schedule_once(self._open, max(0.05, wait))

    def _open(self, _dt):
        self._open_ev = None
        if self.manager is None or self.manager.current != self.name or self._core is not None:
            return
        try:
            if ANDROID and self.index not in _sizes_cache:
                _camera_sizes(self.index)           # pierwsze otwarcie: odczyt rozmiarów
                self._closed_at = time.monotonic()
                self._open_ev = Clock.schedule_once(self._open, REOPEN_GAP)
                return
            preview, picture = _camera_sizes(self.index)
            from kivy.core.camera import Camera as CoreCamera
            if CoreCamera is None:
                raise RuntimeError("brak obsługi kamery")
            core = CoreCamera(index=self.index, resolution=preview, stopped=True)
            if ANDROID:
                cam = core._android_camera
                params = cam.getParameters()
                if picture:
                    params.setPictureSize(*picture)
                params.setJpegQuality(JPEG_QUALITY)
                cam.setParameters(params)
            core.bind(on_load=self._on_load, on_texture=self.ids.view.refresh)
            self._core = core
            core.start()
        except Exception as e:      # noqa: BLE001 - brak kamery / zajęta / sterownik
            Logger.warning(f"Aparat: kamera {self.index} niedostępna: {e}")
            self.stop()
            self.message = "Aparat niedostępny"

    def _on_load(self, *_):
        if self._core is not None:
            self.ids.view.show(self._core.texture, mirror=self.index == 1)
            self.message = ""

    def stop(self):
        if self._open_ev is not None:
            self._open_ev.cancel()
            self._open_ev = None
        core, self._core = self._core, None
        self.busy = False
        self.ids.view.show(None)
        if core is not None:
            try:
                core.stop()
                if hasattr(core, "_release_camera"):
                    core._release_camera()
            except Exception as e:  # noqa: BLE001
                Logger.warning(f"Aparat: zamykanie kamery: {e}")
            self._closed_at = time.monotonic()

    def switch(self):
        """Tylna <-> przednia kamera."""
        if self.cameras < 2 or self.busy:
            return
        self.stop()
        self.index = (self.index + 1) % self.cameras
        self.start()

    # --- zdjęcie ----------------------------------------------------------------------
    def shoot(self):
        if self._core is None or self.busy:
            return
        self.busy = True
        flash = self.ids.flash
        Animation.cancel_all(flash)
        flash.opacity = 0.85
        Animation(opacity=0, d=0.35).start(flash)
        if ANDROID:
            try:
                self._core._android_camera.takePicture(None, None,
                                                       _picture_callback(self._on_jpeg))
            except Exception as e:  # noqa: BLE001
                Logger.warning(f"Aparat: takePicture: {e}")
                self._saved(None)
            return
        try:                        # komputer: zdjęcie z podglądu
            path = new_photo_path()
            self._core.texture.save(str(path), flipped=False)
            self._saved(str(path))
        except Exception as e:      # noqa: BLE001
            Logger.warning(f"Aparat: zapis zdjęcia: {e}")
            self._saved(None)

    def _on_jpeg(self, data, camera):
        """Wątek Javy: zapis JPEG i wznowienie podglądu (takePicture go zatrzymuje)."""
        try:
            camera.startPreview()
        except Exception as e:      # noqa: BLE001
            Logger.warning(f"Aparat: wznowienie podglądu: {e}")
        path = None
        try:
            if data:
                target = new_photo_path()
                target.write_bytes(bytes(data))
                path = str(target)
        except OSError as e:
            Logger.warning(f"Aparat: zapis zdjęcia: {e}")
        self._saved(path)

    @mainthread
    def _saved(self, path):
        self.busy = False
        if path:
            Logger.info(f"Aparat: zdjęcie {path}")
            self.last_photo = path
            self.count += 1
        else:
            self.message = "Nie udało się zapisać zdjęcia"
            Clock.schedule_once(lambda _dt: setattr(self, "message", ""), 3)


class PhotosScreen(Screen):
    """Przeglądanie zdjęć: od najnowszego, Poprzednie / Następne."""
    source = StringProperty("")
    title = StringProperty("Zdjęcia")
    start_position = NumericProperty(-1)

    def on_enter(self, *_):
        self.photos = list_photos()
        self.position = (int(self.start_position) if self.start_position >= 0
                         else len(self.photos) - 1)
        self.start_position = -1
        self._show()

    def step(self, delta: int):
        if self.photos:
            self.position = (self.position + delta) % len(self.photos)
            self._show()

    def _show(self):
        if not self.photos:
            self.source, self.title = "", "Brak zdjęć"
            return
        self.source = self.photos[self.position]
        self.title = f"Zdjęcie {self.position + 1} z {len(self.photos)}"


class GalleryTile(ButtonBehavior, BoxLayout):
    photo = StringProperty("")
    position = NumericProperty(0)
    caption = StringProperty("")

    def on_release(self):
        App.get_running_app().open_photo(int(self.position))


class GalleryScreen(Screen):
    """Siatka dziesięciu miniatur; nawigacja przewija zdjęcia o 1 albo 10."""
    title = StringProperty("Galeria")
    position = NumericProperty(0)

    def on_enter(self, *_):
        self.photos = list_photos()
        self.position = max(0, len(self.photos) - GALLERY_WINDOW)
        self.refresh()

    def step(self, delta: int):
        if not self.photos:
            return
        self.position = max(0, min(len(self.photos) - GALLERY_WINDOW,
                                   self.position + delta))
        self.refresh()

    def refresh(self):
        photos = getattr(self, "photos", [])
        start = int(self.position)
        end = min(start + GALLERY_WINDOW, len(photos))
        self.title = f"Galeria • zdjęcia {start + 1}-{end} z {len(photos)}" if photos else "Galeria"
        grid = self.ids.gallery_grid
        grid.clear_widgets()
        for i in range(start, end):
            grid.add_widget(GalleryTile(photo=thumbnail_path(photos[i]), position=i,
                                        caption=f"{i + 1}"))
        self.ids.gallery_empty.opacity = 0 if photos else 1
