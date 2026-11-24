"""Muzyka dla dzieci: siatka utworów z małymi ikonkami, dotknięcie kafelka odtwarza utwór.

Pliki mp3 nie są w APK (setki MB) - wgrywa je tools/push_music.sh przez adb do katalogu
plików aplikacji /sdcard/Android/data/<pakiet>/files/muzyka (bez dodatkowych uprawnień).
Tytuły, albumy i ikonki: katalog.json obok (tools/make_music.py). Pliki mp3 spoza katalogu
w tym folderze też się pokazują - z ikonką nuty i nazwą pliku jako tytułem.

Po utworze gra następny z tego samego albumu. Komunikaty (wiadomość głosowa, godzina,
pora dnia) ściszają muzykę na czas swojego odtwarzania.
"""
import json
import os
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.logger import Logger
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty, ObjectProperty,
                             StringProperty)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.utils import platform

HERE = Path(__file__).resolve().parent
ICONS = HERE / "icons"
CATALOG = HERE / "katalog.json"
DEFAULT_ICON = "1f3b5"                  # nuta
DEFAULT_COLOR = [0.20, 0.24, 0.36, 1]
ANDROID = platform == "android"
STREAM_MUSIC = 3
DUCK = 0.15                             # głośność muzyki w czasie komunikatu
TICK = 0.5                              # s - sprawdzanie końca utworu i komunikatów
AUDIO_EXTS = (".mp3", ".ogg", ".m4a", ".wav")


def music_dir() -> Path:
    """Folder z utworami: DZIECI_MUZYKA, na Androidzie files/muzyka aplikacji,
    na PC katalog muzyka obok kodu."""
    env = os.environ.get("DZIECI_MUZYKA")
    if env:
        return Path(env)
    if ANDROID:
        try:
            from jnius import autoclass
            ext = autoclass("org.kivy.android.PythonActivity").mActivity.getExternalFilesDir(None)
            if ext is not None:
                return Path(ext.getAbsolutePath()) / "muzyka"
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Muzyka: brak katalogu plików aplikacji: {e}")
    return HERE.parent.parent / "muzyka"


def _icon(code: str) -> str:
    path = ICONS / f"{code}.png"
    return str(path if path.exists() else ICONS / f"{DEFAULT_ICON}.png")


def load_songs(folder: Path) -> list:
    """Utwory z katalogu, które są w folderze (w kolejności albumów), potem pozostałe pliki."""
    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        catalog = {"albums": [], "songs": []}
    albums = {a["key"]: a for a in catalog.get("albums", [])}
    try:
        present = {p.name: p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in AUDIO_EXTS}
    except OSError:
        present = {}
    songs = []
    for s in catalog.get("songs", []):
        path = present.pop(s["file"], None)
        if path is None:
            continue
        album = albums.get(s.get("album"), {})
        songs.append({"path": str(path), "title": s["title"], "icon": _icon(s.get("icon", "")),
                      "album": album.get("title", "Inne"),
                      "color": album.get("color", DEFAULT_COLOR)})
    for name in sorted(present):
        songs.append({"path": str(present[name]), "title": Path(name).stem.replace("_", " "),
                      "icon": _icon(DEFAULT_ICON), "album": "Inne", "color": DEFAULT_COLOR})
    return songs


class MusicPlayer(EventDispatcher):
    """Jeden utwór naraz na osobnym MediaPlayerze (komunikaty mają swój w voice.Player)."""
    current_path = StringProperty("")
    title = StringProperty("")
    album = StringProperty("")
    icon = StringProperty("")
    playing = BooleanProperty(False)    # utwór wybrany (gra albo pauza)
    paused = BooleanProperty(False)
    progress = NumericProperty(0)       # 0..1
    status = StringProperty("Wybierz piosenkę")

    def __init__(self, voice_player=None, **kwargs):
        super().__init__(**kwargs)
        self.voice_player = voice_player
        self.songs = []
        self._index = -1
        self._player = None
        self._sound = None
        self._ducked = False
        Clock.schedule_interval(self._tick, TICK)

    # --- sterowanie ------------------------------------------------------------------
    def play(self, index: int):
        if not 0 <= index < len(self.songs):
            return
        song = self.songs[index]
        self._index = index
        self.current_path, self.title, self.album = song["path"], song["title"], song["album"]
        self.icon = song["icon"]
        self.progress = 0
        try:
            self._start(song["path"])
            self.playing, self.paused = True, False
            self.status = ""
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Muzyka: błąd odtwarzania {song['path']}: {e}")
            self.playing = False
            self.status = "Nie udało się odtworzyć piosenki"

    def play_path(self, path: str):
        for i, s in enumerate(self.songs):
            if s["path"] == path:
                self.play(i)
                return

    def toggle(self):
        """Pauza albo wznowienie; bez wybranego utworu - pierwszy z listy."""
        if not self.playing:
            self.play(max(self._index, 0))
            return
        try:
            if ANDROID:
                (self._player.start if self.paused else self._player.pause)()
            elif self._sound is not None:
                if self.paused:
                    self._sound.play()
                    self._sound.seek(self._paused_at)
                else:
                    self._paused_at = self._sound.get_pos()
                    self._sound.stop()
            self.paused = not self.paused
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Muzyka: pauza: {e}")

    def stop(self):
        self.playing = self.paused = False
        self.current_path = ""
        self.progress = 0
        self.status = "Wybierz piosenkę"
        try:
            if ANDROID and self._player is not None:
                self._player.reset()
            elif self._sound is not None:
                self._sound.stop()
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Muzyka: stop: {e}")

    def step(self, delta: int):
        """Przyciski Poprzednia / Następna: sąsiednia piosenka na całej liście (przez albumy);
        bez wybranej piosenki - pierwsza albo ostatnia."""
        if not self.songs:
            return
        if self._index < 0:
            self.play(0 if delta > 0 else len(self.songs) - 1)
        else:
            self.play((self._index + delta) % len(self.songs))
    def next(self):
        """Następny utwór z tego samego albumu (po ostatnim - pierwszy)."""
        if not self.songs:
            return
        if self._index < 0:
            self.play(0)
            return
        album = self.songs[self._index]["album"]
        same = [i for i, s in enumerate(self.songs) if s["album"] == album]
        pos = same.index(self._index) if self._index in same else -1
        self.play(same[(pos + 1) % len(same)])

    # --- odtwarzanie -----------------------------------------------------------------
    def _start(self, path: str):
        if ANDROID:
            if self._player is None:
                from jnius import autoclass
                self._player = autoclass("android.media.MediaPlayer")()
            p = self._player
            p.reset()
            p.setAudioStreamType(STREAM_MUSIC)
            p.setDataSource(path)
            p.prepare()
            self._ducked = False
            p.setVolume(1.0, 1.0)
            p.start()
            return
        from kivy.core.audio import SoundLoader
        if self._sound is not None:
            self._sound.stop()
        self._sound = SoundLoader.load(path)
        if self._sound is None:
            raise RuntimeError("brak dekodera audio")
        self._sound.play()

    def _is_running(self) -> bool:
        if ANDROID:
            return self._player is not None and bool(self._player.isPlaying())
        return self._sound is not None and self._sound.state == "play"

    def _announcing(self) -> bool:
        vp = self.voice_player
        if vp is None:
            return False
        try:
            return vp._next is not None or vp._still_playing()
        except Exception:               # noqa: BLE001
            return False

    def _tick(self, _dt):
        if not self.playing or self.paused:
            return
        try:
            if not self._is_running():  # utwór się skończył
                self.next()
                return
            if ANDROID:
                dur = self._player.getDuration()
                pos = self._player.getCurrentPosition()
                duck = self._announcing()
                if duck != self._ducked:
                    vol = DUCK if duck else 1.0
                    self._player.setVolume(vol, vol)
                    self._ducked = duck
            else:
                dur, pos = self._sound.length, self._sound.get_pos()
            self.progress = min(pos / dur, 1.0) if dur and dur > 0 else 0
        except Exception as e:          # noqa: BLE001
            Logger.warning(f"Muzyka: {e}")


class MusicTile(ButtonBehavior, BoxLayout):
    """Kafelek utworu: mała ikonka i tytuł; zaznaczony, gdy właśnie gra."""
    path = StringProperty("")
    title = StringProperty("")
    icon = StringProperty("")
    color = ListProperty(DEFAULT_COLOR)

    def on_release(self):
        App.get_running_app().music.play_path(self.path)


class AlbumHeader(Label):
    pass


class MusicList(BoxLayout):
    """Lista albumów z siatkami kafelków; odświeżana przy wejściu na ekran Muzyka
    (nowo wgrane pliki pojawiają się bez restartu aplikacji)."""
    cols = NumericProperty(7)
    empty = BooleanProperty(True)
    folder = StringProperty("")
    player = ObjectProperty(None, allownone=True)

    def refresh(self):
        player = App.get_running_app().music
        folder = music_dir()
        self.folder = str(folder)
        songs = load_songs(folder)
        if [s["path"] for s in songs] == [s["path"] for s in player.songs] and self.children:
            return
        player.songs = songs
        self.clear_widgets()
        self.empty = not songs
        grid, album = None, None
        for s in songs:
            if s["album"] != album:
                album = s["album"]
                self.add_widget(AlbumHeader(text=album))
                grid = GridLayout(cols=self.cols, spacing=12, size_hint_y=None)
                grid.bind(minimum_height=grid.setter("height"))
                self.add_widget(grid)
            grid.add_widget(MusicTile(path=s["path"], title=s["title"], icon=s["icon"],
                                      color=s["color"]))
