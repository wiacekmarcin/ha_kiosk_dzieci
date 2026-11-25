"""Gra bezpośrednio między tabletami (tryb "Internet"), bez Home Assistanta.

Tablet, który zaprasza, staje się serwerem: nasłuchuje na porcie TCP_PORT i co
ANNOUNCE_SECONDS s rozgłasza w sieci (UDP, port UDP_PORT) zaproszenie z nazwą gry,
id partii i portem. Każdy tablet stale słucha rozgłoszeń; po przyjęciu zaproszenia łączy
się z serwerem przez TCP i od tej chwili oba tablety wymieniają komunikaty bezpośrednio
(jeden JSON w linii). Komunikaty mają te same pola co w net.GameNet (type, game, session,
from, to, move, seq) i trafiają do tego samego on_event - plansze działają bez zmian.
Zerwane połączenie to dla drugiej strony "leave" (gra zakończona).

Interfejs jak GameNet: invite, accept, decline, send_move, leave, mine, session, peer, game.
"""
import json
import socket
import threading
import time
import uuid

from kivy.clock import Clock
from kivy.logger import Logger

TCP_PORT = 47600
UDP_PORT = 47601
ANNOUNCE_SECONDS = 1.0
INVITE_SECONDS = 90                     # tyle trwa rozgłaszanie zaproszenia
MAGIC = "ha-kiosk-gry"


def local_ip() -> str:
    """Adres tabletu w sieci lokalnej (bez wysyłania czegokolwiek)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def multicast_lock():
    """Android: bez blokady Wi-Fi część tabletów odrzuca pakiety rozgłoszeniowe."""
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        wifi = activity.getApplicationContext().getSystemService("wifi")
        lock = wifi.createMulticastLock("ha-kiosk-gry")
        lock.setReferenceCounted(False)
        lock.acquire()
        return lock
    except Exception as e:              # noqa: BLE001 - nie Android albo brak uprawnienia
        Logger.debug(f"Gra bezpośrednia: bez blokady multicast: {e}")
        return None


class DirectNet:
    def __init__(self, name: str, on_event):
        self.name = name
        self.on_event = on_event
        self.session = self.peer = self.game = None
        self.seq = 0
        self._server = None             # gniazdo serwera (tablet zapraszający)
        self._conn = None               # połączenie z drugim tabletem
        self._announcing = threading.Event()
        self._lock = threading.Lock()
        self._seen = set()              # zaproszenia już pokazane
        self._mlock = multicast_lock()
        threading.Thread(target=self._listen_udp, name="gra-udp", daemon=True).start()

    # --- wysyłanie ----------------------------------------------------------------------
    def _send(self, payload: dict, conn=None) -> bool:
        conn = conn or self._conn
        if conn is None:
            return False
        data = (json.dumps({"from": self.name, **payload}, ensure_ascii=False) + "\n").encode()
        try:
            with self._lock:
                conn.sendall(data)
            return True
        except OSError as e:
            Logger.warning(f"Gra bezpośrednia: wysyłanie {payload.get('type')}: {e}")
            return False

    def invite(self, game: str, side: int = 0):
        """Ten tablet staje się serwerem i rozgłasza zaproszenie."""
        self._close()
        self.session, self.peer, self.game, self.seq = uuid.uuid4().hex[:8], None, game, 0
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("", TCP_PORT))
        except OSError:
            srv.bind(("", 0))           # port zajęty - dowolny wolny
        srv.listen(2)
        self._server = srv
        port = srv.getsockname()[1]
        threading.Thread(target=self._serve, args=(srv, self.session), daemon=True).start()
        self._announcing.set()
        msg = {"magic": MAGIC, "type": "invite", "game": game, "session": self.session,
               "from": self.name, "port": port, "side": side}
        threading.Thread(target=self._announce, args=(msg,), daemon=True).start()

    def accept(self, msg: dict) -> bool:
        """Przyjęcie zaproszenia: połączenie z serwerem drugiego tabletu."""
        self._close()
        self.session, self.peer, self.game, self.seq = msg["session"], msg["from"], msg["game"], 0
        try:
            conn = socket.create_connection((msg["_addr"], msg["port"]), timeout=5)
            conn.settimeout(None)
        except OSError as e:
            Logger.warning(f"Gra bezpośrednia: brak połączenia z {msg.get('_addr')}: {e}")
            self.session = self.peer = self.game = None
            return False
        self._conn = conn
        threading.Thread(target=self._read, args=(conn, self.session), daemon=True).start()
        if not self._send({"type": "accept", "game": msg["game"], "session": self.session,
                           "to": self.peer}):
            self._close()
            self.session = self.peer = self.game = None
            return False
        return True

    def ready(self, game: str):
        if self.session:
            self._send({"type": "ready", "game": game, "session": self.session, "to": self.peer})

    def ready_ack(self, game: str):
        if self.session:
            self._send({"type": "ready_ack", "game": game, "session": self.session,
                        "to": self.peer})

    def decline(self, msg: dict):
        def work():
            try:
                with socket.create_connection((msg["_addr"], msg["port"]), timeout=5) as c:
                    c.sendall((json.dumps({"type": "decline", "game": msg.get("game"),
                                           "session": msg["session"], "from": self.name,
                                           "to": msg["from"]}) + "\n").encode())
            except OSError:
                pass
        threading.Thread(target=work, daemon=True).start()

    def send_move(self, game: str, move):
        if not self.session:
            return
        self.seq += 1
        self._send({"type": "move", "game": game, "session": self.session, "to": self.peer,
                    "seq": self.seq, "move": list(move)})

    def leave(self, game: str):
        if self.session:
            self._send({"type": "leave", "game": game, "session": self.session, "to": self.peer})
        self._close()
        self.session = self.peer = self.game = None

    def mine(self, msg: dict) -> bool:
        return bool(self.session) and msg.get("session") == self.session \
            and msg.get("to") == self.name

    # --- wątki ----------------------------------------------------------------------------
    def _close(self):
        self._announcing.clear()
        for s in (self._conn, self._server):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
        self._conn = self._server = None

    def _emit(self, msg: dict):
        msg["_via"] = "direct"
        Clock.schedule_once(lambda _dt: self.on_event(msg))

    def _announce(self, msg: dict):
        data = json.dumps(msg, ensure_ascii=False).encode()
        ip = local_ip()
        targets = {"255.255.255.255", ip.rsplit(".", 1)[0] + ".255"}
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            for _ in range(int(INVITE_SECONDS / ANNOUNCE_SECONDS)):
                if not self._announcing.is_set() or self.session != msg["session"]:
                    break
                for t in targets:
                    try:
                        s.sendto(data, (t, UDP_PORT))
                    except OSError:
                        pass
                time.sleep(ANNOUNCE_SECONDS)
        finally:
            s.close()

    def _listen_udp(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            s.bind(("", UDP_PORT))
        except OSError as e:
            Logger.warning(f"Gra bezpośrednia: port {UDP_PORT} zajęty: {e}")
            return
        while True:
            try:
                data, (addr, _port) = s.recvfrom(4096)
                msg = json.loads(data.decode())
            except (OSError, ValueError):
                continue
            if msg.get("magic") != MAGIC or msg.get("from") == self.name \
                    or msg.get("session") in self._seen:
                continue
            self._seen.add(msg["session"])
            msg["_addr"] = addr
            self._emit(msg)

    def _serve(self, srv, session):
        """Serwer: pierwszy tablet z poprawnym "accept" zostaje przeciwnikiem."""
        while self.session == session and self._server is srv:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            if self._conn is not None:
                conn.close()
                continue
            threading.Thread(target=self._read, args=(conn, session, True), daemon=True).start()

    def _read(self, conn, session, incoming=False):
        buf = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode())
                    except ValueError:
                        continue
                    if msg.get("session") != session:
                        continue
                    if incoming and msg.get("type") == "accept" and self._conn is None:
                        self._conn = conn       # przeciwnik połączony - koniec zaproszeń
                        self._announcing.clear()
                    elif incoming and self._conn is not conn and msg.get("type") != "decline":
                        continue
                    self._emit(msg)
        except OSError:
            pass
        if self._conn is conn and self.session == session:
            # zerwane połączenie: dla tego tabletu przeciwnik wyszedł z gry
            self._emit({"type": "leave", "game": self.game, "session": session,
                        "from": self.peer or "Drugi tablet", "to": self.name})
            self._conn = None
