"""Mowa z zegara przez systemowy syntezator mowy Androida."""
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.utils import platform


class ClockSpeech:
    def __init__(self):
        self._tts = None
        self._listener = None
        self._pending = ""
        self._ready = False

    def say(self, text: str):
        if platform != "android":
            Logger.warning("Zegar: odczyt głosowy jest dostępny na tablecie Android")
            return
        self._pending = text
        if self._tts is not None:
            if self._ready:
                self._speak()
            return
        try:
            from jnius import PythonJavaClass, autoclass, java_method

            owner = self

            class InitListener(PythonJavaClass):
                __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__ = "app"

                def __init__(self):
                    super().__init__()

                @java_method("(I)V")
                def onInit(self, status):
                    Clock.schedule_once(lambda _dt: owner._on_init(status))

            self._listener = InitListener()
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            tts_class = autoclass("android.speech.tts.TextToSpeech")
            self._tts_class = tts_class
            self._tts = tts_class(activity, self._listener)
        except Exception as exc:
            self._tts = None
            Logger.error(f"Zegar: nie udało się uruchomić syntezatora mowy: {exc}")

    def _on_init(self, status):
        if status != self._tts_class.SUCCESS:
            Logger.error(f"Zegar: inicjalizacja syntezatora mowy nie powiodła się ({status})")
            self._tts = None
            return
        try:
            from jnius import autoclass
            result = self._tts.setLanguage(autoclass("java.util.Locale")("pl", "PL"))
            if result < 0:
                Logger.error("Zegar: brak polskiego głosu w syntezatorze Androida")
                self._tts = None
                return
        except Exception as exc:
            Logger.error(f"Zegar: nie udało się ustawić polskiego głosu: {exc}")
            self._tts = None
            return
        self._ready = True
        self._speak()

    def _speak(self):
        text, self._pending = self._pending, ""
        if not text:
            return
        try:
            from jnius import autoclass
            bundle = autoclass("android.os.Bundle")()
            self._tts.speak(text, self._tts_class.QUEUE_FLUSH, bundle, "clock-readout")
        except Exception as exc:
            Logger.error(f"Zegar: nie udało się odczytać godziny: {exc}")
