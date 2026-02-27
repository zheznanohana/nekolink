import asyncio
import time
import threading
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Dict, Tuple, List

import requests
from bleak import BleakClient, BleakScanner

# ANCS UUIDs
NOTIF_SRC = "9fbf120d-6301-42d9-8c58-25e699a21dbd"
CTRL_PT   = "69d1d8f3-45e1-49a8-9821-9bbdfdaad9d9"
DATA_SRC  = "22eac6e9-24d6-4bb5-be44-b36ace7c7bfb"

# ANCS Attribute IDs
ATTR_APP_IDENTIFIER = 0
ATTR_TITLE          = 1
ATTR_MESSAGE        = 3
ATTR_DATE           = 5


@dataclass
class BridgeConfig:
    ble_addresses: List[str] = field(default_factory=list)
    auto_pick_heart_rate: bool = False

    enable_telegram: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    enable_email: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    email_to: str = ""
    email_from: str = ""

    dedup_seconds: int = 8

    block_keywords: List[str] = field(default_factory=list)
    block_case_insensitive: bool = True

    enable_code_highlight: bool = True
    code_regex: str = r"\b\d{4,8}\b"
    code_send_separately: bool = True
    code_separate_prefix: str = "🔑 Code"

    history_limit: int = 300
    autostart_enabled: bool = False


def build_get_notification_attributes(uid: int) -> bytes:
    b = bytearray()
    b += b"\x00"
    b += uid.to_bytes(4, "little")

    b += bytes([ATTR_APP_IDENTIFIER])

    b += bytes([ATTR_TITLE])
    b += (64).to_bytes(2, "little")

    b += bytes([ATTR_MESSAGE])
    b += (300).to_bytes(2, "little")

    b += bytes([ATTR_DATE])
    return bytes(b)


def try_parse_ds(buffer: bytearray):
    if len(buffer) < 5:
        return None
    cmd_id = buffer[0]
    uid = int.from_bytes(buffer[1:5], "little")
    i = 5
    attrs: Dict[int, str] = {}
    while True:
        if i == len(buffer):
            return cmd_id, uid, attrs, i
        if i + 3 > len(buffer):
            return None
        attr_id = buffer[i]
        attr_len = int.from_bytes(buffer[i+1:i+3], "little")
        i += 3
        if i + attr_len > len(buffer):
            return None
        raw = bytes(buffer[i:i+attr_len])
        i += attr_len
        attrs[attr_id] = raw.decode("utf-8", errors="replace")


class SingleDeviceBridge:
    """
    One BLE connection -> ANCS -> callbacks
    """
    def __init__(
        self,
        cfg: BridgeConfig,
        address: str,
        log: Callable[[str], None],
        on_notification: Callable[[dict], None],
    ):
        self.cfg = cfg
        self.address = address
        self.log = log
        self.on_notification = on_notification

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional[BleakClient] = None

        self._pending_uid: Optional[int] = None
        self._ds_buffer = bytearray()
        self._last_sent: Dict[Tuple[str, str, str], float] = {}

        self._code_re = re.compile(self.cfg.code_regex)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_evt.set()
        if self._loop:
            try:
                asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)
            except Exception:
                pass

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_reconnect_loop())
        except Exception as e:
            self.log(f"[{self.address}] [FATAL] {e}")
        finally:
            try:
                self._loop.stop()
                self._loop.close()
            except Exception:
                pass
            self.log(f"[{self.address}] stopped")

    async def _disconnect(self):
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass

    async def _main_reconnect_loop(self):
        while not self._stop_evt.is_set():
            try:
                await self._connect_and_run()
            except Exception as e:
                self.log(f"[{self.address}] [RETRY] {e}")

            # backoff
            for _ in range(10):
                if self._stop_evt.is_set():
                    break
                await asyncio.sleep(0.5)

    async def _connect_and_run(self):
        self._pending_uid = None
        self._ds_buffer = bytearray()

        self.log(f"[{self.address}] connecting ...")
        self._client = BleakClient(
            self.address,
            timeout=30,
            disconnected_callback=lambda _c: self.log(f"[{self.address}] disconnected"),
            winrt={"use_cached_services": False},
        )
        await self._client.connect()
        self.log(f"[{self.address}] connected")

        await self._client.start_notify(DATA_SRC, self._on_data_src)
        await self._client.start_notify(NOTIF_SRC, self._on_notif_src)
        self.log(f"[{self.address}] subscribed ANCS")

        while not self._stop_evt.is_set() and self._client.is_connected:
            await asyncio.sleep(0.2)

        await self._disconnect()

    def _blocked(self, app_id: str, title: str, msg: str) -> bool:
        kws = [k for k in (self.cfg.block_keywords or []) if k.strip()]
        if not kws:
            return False
        hay = f"{app_id}\n{title}\n{msg}"
        if self.cfg.block_case_insensitive:
            hay = hay.lower()
            kws = [k.lower() for k in kws]
        return any(k in hay for k in kws)

    def _extract_codes(self, msg: str) -> List[str]:
        if not self.cfg.enable_code_highlight:
            return []
        return self._code_re.findall(msg or "")

    def _on_notif_src(self, _sender: str, data: bytearray):
        if len(data) < 8:
            return
        event_id = data[0]
        uid = int.from_bytes(data[4:8], "little")
        if event_id != 0:
            return
        if self._loop and self._client:
            asyncio.run_coroutine_threadsafe(self._request_details(uid), self._loop)

    async def _request_details(self, uid: int):
        if not self._client:
            return
        self._pending_uid = uid
        cmd = build_get_notification_attributes(uid)
        try:
            await self._client.write_gatt_char(CTRL_PT, cmd, response=True)
        except Exception as e:
            self.log(f"[{self.address}] [CP] failed: {e}")

    def _on_data_src(self, _sender: str, data: bytearray):
        self._ds_buffer.extend(data)
        parsed = try_parse_ds(self._ds_buffer)
        if not parsed:
            return

        _cmd_id, uid, attrs, used = parsed
        self._ds_buffer = self._ds_buffer[used:]

        if self._pending_uid is not None and uid != self._pending_uid:
            return

        app_id = attrs.get(ATTR_APP_IDENTIFIER, "")
        title  = attrs.get(ATTR_TITLE, "")
        msg    = attrs.get(ATTR_MESSAGE, "")
        date   = attrs.get(ATTR_DATE, "")

        # dedup
        key = (app_id, title, msg)
        now = time.time()
        last = self._last_sent.get(key, 0)
        if now - last < max(1, int(self.cfg.dedup_seconds)):
            return
        self._last_sent[key] = now

        if self._blocked(app_id, title, msg):
            return

        codes = self._extract_codes(msg)

        payload = {
            "ts": time.time(),
            "device": self.address,
            "app": app_id,
            "title": title,
            "msg": msg,
            "date": date,
            "codes": codes,
        }
        self.on_notification(payload)

        # push normal full message
        text = (
            f"📲 iPhone 通知\n"
            f"Device: {self.address}\n"
            f"App: {app_id}\n"
            f"Title: {title}\n"
            f"Msg: {msg}\n"
            f"Date: {date}"
        )

        if self.cfg.enable_telegram:
            self._send_telegram(text)

        if self.cfg.enable_email:
            self._send_email(text)

        # push code separately (optional)
        if self.cfg.code_send_separately and codes:
            code_text = f"{self.cfg.code_separate_prefix}: " + " ".join(codes) + f"\nApp: {app_id}\nTitle: {title}"
            if self.cfg.enable_telegram:
                self._send_telegram(code_text)
            if self.cfg.enable_email:
                self._send_email(code_text)

        self._pending_uid = None

    def _send_telegram(self, text: str):
        token = (self.cfg.telegram_bot_token or "").strip()
        chat_id = (self.cfg.telegram_chat_id or "").strip()
        if not token or not chat_id:
            self.log(f"[{self.address}] [TG] skipped (missing token/chat_id)")
            return
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
            r = requests.post(url, json=payload, timeout=10)
            r.raise_for_status()
        except Exception as e:
            self.log(f"[{self.address}] [TG] failed: {e}")

    def _send_email(self, text: str):
        if not self.cfg.smtp_host or not self.cfg.smtp_user or not self.cfg.smtp_pass:
            self.log(f"[{self.address}] [MAIL] skipped (missing smtp settings)")
            return
        if not self.cfg.email_to or not self.cfg.email_from:
            self.log(f"[{self.address}] [MAIL] skipped (missing to/from)")
            return
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(text, _charset="utf-8")
            msg["Subject"] = "iPhone 通知转发"
            msg["From"] = self.cfg.email_from
            msg["To"] = self.cfg.email_to

            server = smtplib.SMTP(self.cfg.smtp_host, int(self.cfg.smtp_port), timeout=10)
            server.ehlo()
            server.starttls()
            server.login(self.cfg.smtp_user, self.cfg.smtp_pass)
            server.send_message(msg)
            server.quit()
        except Exception as e:
            self.log(f"[{self.address}] [MAIL] failed: {e}")


class BridgeManager:
    """
    Multiple devices manager
    """
    def __init__(self, cfg: BridgeConfig, log: Callable[[str], None], on_notification: Callable[[dict], None]):
        self.cfg = cfg
        self.log = log
        self.on_notification = on_notification
        self.bridges: Dict[str, SingleDeviceBridge] = {}

    async def scan_heart_rate(self, timeout=8) -> List[Tuple[str, str, int]]:
        found = await BleakScanner.discover(timeout=timeout, return_adv=True)
        out = []
        for addr, (dev, adv) in found.items():
            name = dev.name or ""
            if "Heart Rate" in name:
                rssi = adv.rssi if adv else -999
                out.append((name, addr, rssi))
        out.sort(key=lambda x: x[2], reverse=True)
        return out

    def start_all(self, addresses: List[str]):
        for addr in addresses:
            if addr in self.bridges:
                continue
            b = SingleDeviceBridge(self.cfg, addr, self.log, self.on_notification)
            self.bridges[addr] = b
            b.start()
            self.log(f"[MANAGER] started {addr}")

    def stop_all(self):
        for addr, b in list(self.bridges.items()):
            b.stop()
            self.log(f"[MANAGER] stopping {addr}")
        self.bridges.clear()