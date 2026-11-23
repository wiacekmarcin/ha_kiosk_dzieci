"""Gra przez sieć między tabletami - przez Home Assistant, jak wiadomości głosowe.

Każdy komunikat to nowy stan encji ENTITY (unikalne id) z atrybutami:
    type    - invite (zaproszenie do wszystkich), accept, decline, move, leave
    game    - tictactoe, checkers albo chess
    session - id partii (nadaje zapraszający)
    from    - nazwa tabletu nadawcy, to - nazwa tabletu odbiorcy (poza invite)
    move    - ruch (lista liczb), seq - numer ruchu w partii
    time    - czas nadania (UTC); starsze niż MAX_AGE s komunikaty są pomijane.
Każdy tablet czyta encję co POLL_SECONDS s w osobnym wątku; nowe komunikaty od innych
tabletów trafiają do on_event(atrybuty) w wątku interfejsu (Clock).
Ruchy są na zmianę, więc jeden stan encji naraz wystarcza (nadawca zawsze czeka na
odpowiedź drugiej strony).
"""
import threading
import uuid
from datetime import datetime, timezone

import requests
from kivy.clock import Clock
from kivy.logger import Logger

ENTITY = "sensor.kiosk_gra"
POLL_SECONDS = 1.0
MAX_AGE = 90


class GameNet:
    def __init__(self, settings: dict, name: str, on_event):
        self.base = settings["url"].rstrip("/")
        self.headers = {"Authorization": f"Bearer {settings['token']}"}
        self.name = name
        self.on_event = on_event
        self.session = None             # id bieżącej partii sieciowej
        self.peer = None                # nazwa tabletu przeciwnika
        self.seq = 0
        self._seen = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        threading.Thread(target=self._run, name="ha-game", daemon=True).start()

    # --- wysyłanie ----------------------------------------------------------------------
    def _post(self, payload: dict):
        state = uuid.uuid4().hex[:12]
        self._seen = state              # własnego komunikatu nie przetwarzamy
        attrs = {"friendly_name": "Gra między tabletami", "icon": "mdi:gamepad-variant",
                 "from": self.name, "time": datetime.now(timezone.utc).isoformat(), **payload}

        def work():
            with self._lock:            # komunikaty jeden po drugim, w kolejności
                try:
                    requests.post(f"{self.base}/api/states/{ENTITY}", headers=self.headers,
                                  json={"state": state, "attributes": attrs},
                                  timeout=10).raise_for_status()
                except Exception as e:  # noqa: BLE001
                    Logger.warning(f"Gra: błąd wysyłania {payload.get('type')}: {e}")
        threading.Thread(target=work, daemon=True).start()

    def invite(self, game: str):
        self.session, self.peer, self.seq = uuid.uuid4().hex[:8], None, 0
        self._post({"type": "invite", "game": game, "session": self.session})

    def accept(self, msg: dict):
        self.session, self.peer, self.seq = msg["session"], msg["from"], 0
        self._post({"type": "accept", "game": msg["game"], "session": self.session,
                    "to": self.peer})

    def decline(self, msg: dict):
        self._post({"type": "decline", "game": msg.get("game"), "session": msg["session"],
                    "to": msg["from"]})

    def send_move(self, game: str, move):
        if not self.session:
            return
        self.seq += 1
        self._post({"type": "move", "game": game, "session": self.session, "to": self.peer,
                    "seq": self.seq, "move": list(move)})

    def leave(self, game: str):
        if self.session:
            self._post({"type": "leave", "game": game, "session": self.session,
                        "to": self.peer})
        self.session = self.peer = None

    def mine(self, msg: dict) -> bool:
        """Komunikat dotyczy mojej bieżącej partii i jest do mnie."""
        return bool(self.session) and msg.get("session") == self.session \
            and msg.get("to") == self.name

    # --- odbiór -------------------------------------------------------------------------
    def _run(self):
        while not self._stop.is_set():
            try:
                self._poll()
            except Exception as e:      # noqa: BLE001
                Logger.debug(f"Gra: odczyt: {e}")
            self._stop.wait(POLL_SECONDS)

    def _poll(self):
        r = requests.get(f"{self.base}/api/states/{ENTITY}", headers=self.headers, timeout=10)
        if r.status_code == 404:
            return
        r.raise_for_status()
        data = r.json()
        state, attrs = data.get("state"), data.get("attributes", {})
        if state == self._seen:
            return
        self._seen = state
        if attrs.get("from") == self.name or not attrs.get("type"):
            return
        try:
            sent = datetime.fromisoformat(attrs.get("time", ""))
            if (datetime.now(timezone.utc) - sent).total_seconds() > MAX_AGE:
                return
        except ValueError:
            return
        Clock.schedule_once(lambda _dt, a=dict(attrs): self.on_event(a))

    def stop(self):
        self._stop.set()

