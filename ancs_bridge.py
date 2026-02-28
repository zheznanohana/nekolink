# ancs_bridge.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import base64
import dataclasses
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import requests
from bleak import BleakClient, BleakScanner

try:
    from win_toast import show_toast
except Exception:
    show_toast = None  # type: ignore


# -----------------------------
# UUIDs
# -----------------------------
# ANCS UUIDs
ANCS_SERVICE = "7905f431-b5ce-4e99-a40f-4b1e122d00d0"
NOTIF_SRC = "9fbf120d-6301-42d9-8c58-25e699a21dbd"
CTRL_PT = "69d1d8f3-45e1-49a8-9821-9bbdfdaad9d9"
DATA_SRC = "22eac6e9-24d6-4bb5-be44-b36ace7c7bfb"

# Battery Level characteristic
BATTERY_LEVEL_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"

# ANCS Attribute IDs
ATTR_APP_IDENTIFIER = 0
ATTR_TITLE = 1
ATTR_SUBTITLE = 2
ATTR_MESSAGE = 3
ATTR_DATE = 5


# -----------------------------
# Config location (portable-first, AppData fallback)
# -----------------------------
def _base_dir() -> Path:
    # script dir (py) or exe dir (pyinstaller)
    try:
        import sys

        if getattr(sys, "frozen", False):
            return Path(os.path.dirname(sys.executable)).resolve()
    except Exception:
        pass
    return Path(os.path.dirname(__file__)).resolve()


def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_config_path() -> str:
    """
    Rules:
      1) If config.json exists next to exe/script -> use it (portable, easy to view/edit)
      2) If dir not writable -> fallback to %APPDATA%\\NekoLink\\config.json (stable)
      3) You can set env NEKOLINK_PORTABLE=1 to force portable mode
    """
    base = _base_dir()
    portable = base / "config.json"
    force_portable = os.getenv("NEKOLINK_PORTABLE", "0").strip() == "1"

    if force_portable or portable.exists():
        if _is_writable_dir(base):
            return str(portable)

    appdata = Path(os.getenv("APPDATA", str(Path.home())))
    cfg_dir = appdata / "NekoLink"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return str(cfg_dir / "config.json")


def load_config(path: str) -> "BridgeConfig":
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return BridgeConfig(**d)
    except Exception:
        return BridgeConfig()


def save_config(path: str, cfg: "BridgeConfig"):
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p), "w", encoding="utf-8") as f:
        json.dump(dataclasses.asdict(cfg), f, ensure_ascii=False, indent=2)


# -----------------------------
# Config
# -----------------------------
@dataclass
class BridgeConfig:
    # devices
    ble_addresses: List[str] = field(default_factory=list)
    auto_pick_heart_rate: bool = False

    # telegram
    enable_telegram: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # email
    enable_email: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    email_to: str = ""
    email_from: str = ""

    # dingtalk
    enable_dingtalk: bool = False
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""  # optional

    # behavior
    dedup_seconds: int = 8

    # filter
    block_keywords: List[str] = field(default_factory=list)
    block_case_insensitive: bool = True

    # code
    enable_code_highlight: bool = True
    code_regex: str = r"\b\d{4,8}\b"
    code_send_separately: bool = True
    code_separate_prefix: str = "🔑 Code"

    # history
    history_limit: int = 300

    # autostart
    autostart_enabled: bool = False

    # --- Misc (NEW) ---
    show_battery_in_message: bool = True
    enable_windows_toast: bool = True


# -----------------------------
# Destinations
# -----------------------------
def send_telegram(token: str, chat_id: str, text: str, timeout: int = 10):
    if not token or not chat_id:
        raise ValueError("Missing Telegram token/chat_id")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if not j.get("ok", False):
        raise RuntimeError(str(j))


def send_email(cfg: BridgeConfig, subject: str, body: str):
    import smtplib
    from email.mime.text import MIMEText

    if not cfg.smtp_host or not cfg.smtp_user or not cfg.smtp_pass:
        raise ValueError("Missing SMTP settings")
    if not cfg.email_to or not cfg.email_from:
        raise ValueError("Missing email to/from")

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg.email_from
    msg["To"] = cfg.email_to

    server = smtplib.SMTP(cfg.smtp_host, int(cfg.smtp_port), timeout=12)
    server.ehlo()
    server.starttls()
    server.login(cfg.smtp_user, cfg.smtp_pass)
    server.send_message(msg)
    server.quit()


def _dingtalk_signed_url(webhook: str, secret: str) -> str:
    ts = str(round(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(digest))
    joiner = "&" if ("?" in webhook) else "?"
    return f"{webhook}{joiner}timestamp={ts}&sign={sign}"


def send_dingtalk_text(webhook: str, secret: str, text: str, timeout: int = 10):
    if not webhook:
        raise ValueError("Missing DingTalk webhook")
    url = _dingtalk_signed_url(webhook, secret) if secret else webhook
    payload = {"msgtype": "text", "text": {"content": text}}
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict) and j.get("errcode", 0) != 0:
        raise RuntimeError(f"DingTalk error: {j}")


# -----------------------------
# ANCS helpers
# -----------------------------
def build_get_notification_attributes(uid: int) -> bytes:
    """
    CommandID(0x00) + UID(LE 4)
    Attributes: AppId, Title(64), Subtitle(64), Message(256), Date
    """
    b = bytearray()
    b += b"\x00"
    b += uid.to_bytes(4, "little")

    b += bytes([ATTR_APP_IDENTIFIER])

    b += bytes([ATTR_TITLE])
    b += (64).to_bytes(2, "little")

    b += bytes([ATTR_SUBTITLE])
    b += (64).to_bytes(2, "little")

    b += bytes([ATTR_MESSAGE])
    b += (256).to_bytes(2, "little")

    b += bytes([ATTR_DATE])
    return bytes(b)


def _try_parse_ds(buffer: bytearray):
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
        attr_len = int.from_bytes(buffer[i + 1 : i + 3], "little")
        i += 3
        if i + attr_len > len(buffer):
            return None
        raw = bytes(buffer[i : i + attr_len])
        i += attr_len
        attrs[attr_id] = raw.decode("utf-8", errors="replace")


def _contains_block(hay: str, keywords: List[str], ci: bool) -> bool:
    kws = [k for k in (keywords or []) if k.strip()]
    if not kws:
        return False
    if ci:
        hay = (hay or "").lower()
        kws = [k.lower() for k in kws]
    return any(k in hay for k in kws)


# -----------------------------
# Single device bridge
# -----------------------------
class SingleDeviceBridge:
    """
    One BLE connection -> ANCS -> callbacks
    Additionally subscribes Battery Level and caches latest percentage.
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
        self.latest_battery: Optional[int] = None  # cached battery %

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
        backoff = 2
        while not self._stop_evt.is_set():
            try:
                await self._connect_and_run()
                backoff = 2
            except Exception as e:
                self.log(f"[{self.address}] [RETRY] {e}")
            await self._disconnect()
            if self._stop_evt.is_set():
                break
            self.log(f"[{self.address}] reconnect in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(30, backoff * 2)

    async def _connect_and_run(self):
        self._pending_uid = None
        self._ds_buffer = bytearray()

        self.log(f"[{self.address}] connecting ...")
        self._client = BleakClient(
            self.address,
            timeout=30,
            winrt={"use_cached_services": False},
            disconnected_callback=lambda _c: self.log(f"[{self.address}] disconnected"),
        )
        await self._client.connect()
        self.log(f"[{self.address}] connected")

        # ANCS
        await self._client.start_notify(DATA_SRC, self._on_data_src)
        await self._client.start_notify(NOTIF_SRC, self._on_notif_src)
        self.log(f"[{self.address}] subscribed ANCS")

        # Battery (read once + subscribe)
        await self._setup_battery()

        while not self._stop_evt.is_set() and self._client.is_connected:
            await asyncio.sleep(0.2)

    async def _setup_battery(self):
        if not self._client:
            return
        # read once
        try:
            raw = await self._client.read_gatt_char(BATTERY_LEVEL_CHAR)
            if raw and len(raw) >= 1:
                self.latest_battery = int(raw[0])
                self.log(f"[{self.address}] battery={self.latest_battery}% (read)")
        except Exception as e:
            self.log(f"[{self.address}] battery read fail: {e}")

        # notify
        try:
            await self._client.start_notify(BATTERY_LEVEL_CHAR, self._on_battery)
            self.log(f"[{self.address}] battery notify on")
        except Exception as e:
            self.log(f"[{self.address}] battery notify fail: {e}")

    def _on_battery(self, _sender: str, data: bytearray):
        try:
            if data and len(data) >= 1:
                self.latest_battery = int(data[0])
        except Exception:
            pass

    def _extract_codes(self, msg: str) -> List[str]:
        if not self.cfg.enable_code_highlight:
            return []
        if not msg:
            return []
        return list(dict.fromkeys(self._code_re.findall(msg)))

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
        parsed = _try_parse_ds(self._ds_buffer)
        if not parsed:
            return
        _cmd_id, uid, attrs, used = parsed
        self._ds_buffer = self._ds_buffer[used:]

        if self._pending_uid is not None and uid != self._pending_uid:
            return

        app_id = attrs.get(ATTR_APP_IDENTIFIER, "") or ""
        title = attrs.get(ATTR_TITLE, "") or ""
        subtitle = attrs.get(ATTR_SUBTITLE, "") or ""
        msg = attrs.get(ATTR_MESSAGE, "") or ""
        date = attrs.get(ATTR_DATE, "") or ""

        # dedup
        key = (app_id, title, msg)
        now = time.time()
        last = self._last_sent.get(key, 0.0)
        if now - last < max(1, int(self.cfg.dedup_seconds)):
            return
        self._last_sent[key] = now

        # filter
        hay = f"{app_id}\n{title}\n{subtitle}\n{msg}\n{date}"
        if _contains_block(hay, self.cfg.block_keywords, self.cfg.block_case_insensitive):
            return

        codes = self._extract_codes(f"{title}\n{subtitle}\n{msg}")
        battery = self.latest_battery

        payload = {
            "ts": now,
            "device": self.address,
            "app": app_id,
            "title": title,
            "subtitle": subtitle,
            "msg": msg,
            "date": date,
            "codes": codes,
            "battery": battery,
        }
        self.on_notification(payload)

        bat_text = f"{battery}%" if isinstance(battery, int) else "--"

        # --- Windows toast (NEW, optional) ---
        if self.cfg.enable_windows_toast and show_toast is not None:
            try:
                toast_title = app_id or "iPhone"
                toast_body_lines = []
                if title:
                    toast_body_lines.append(title)
                if msg:
                    toast_body_lines.append(msg)
                if self.cfg.show_battery_in_message:
                    toast_body_lines.append(f"🔋 {bat_text}")
                toast_body = "\n".join(toast_body_lines[:3]).strip()
                if toast_body:
                    show_toast(toast_title, toast_body, app_id="NekoLink")
            except Exception:
                pass

        # Build unified forwarded text (battery optional)
        parts = []
        parts.append(f"🔔 {app_id}".strip())
        if title:
            parts.append(title)
        if msg:
            parts.append(msg)

        # codes line (optional)
        codes_line = ""
        if self.cfg.enable_code_highlight and codes:
            codes_line = "🔑 " + " ".join(codes)

        tail = []
        if codes_line:
            tail.append(codes_line)
        if self.cfg.show_battery_in_message:
            tail.append(f"🔋 {bat_text}")
        tail.append(f"📱 {self.address}")
        if date:
            tail.append(f"🕒 {date}")

        final_text = "\n".join([*parts, "", *tail]).strip()

        self._forward_all(final_text, app_id=app_id)

        # Code separately (optional)
        if self.cfg.enable_code_highlight and self.cfg.code_send_separately and codes:
            code_text_parts = [f"{self.cfg.code_separate_prefix}: " + " ".join(codes)]
            if self.cfg.show_battery_in_message:
                code_text_parts.append(f"🔋 {bat_text}")
            code_text_parts.append(f"📱 {self.address}")
            code_text = "\n".join(code_text_parts).strip()
            self._forward_all(code_text, app_id=app_id)

        self._pending_uid = None

    def _forward_all(self, text: str, app_id: str = ""):
        def _work():
            if self.cfg.enable_telegram:
                try:
                    send_telegram(self.cfg.telegram_bot_token.strip(), self.cfg.telegram_chat_id.strip(), text)
                    self.log(f"[TG] ok ({app_id})")
                except Exception as e:
                    self.log(f"[TG] failed: {e}")

            if self.cfg.enable_dingtalk:
                try:
                    send_dingtalk_text(self.cfg.dingtalk_webhook.strip(), self.cfg.dingtalk_secret.strip(), text)
                    self.log(f"[DT] ok ({app_id})")
                except Exception as e:
                    self.log(f"[DT] failed: {e}")

            if self.cfg.enable_email:
                try:
                    send_email(self.cfg, f"NekoLink: {app_id}", text)
                    self.log(f"[MAIL] ok ({app_id})")
                except Exception as e:
                    self.log(f"[MAIL] failed: {e}")

        threading.Thread(target=_work, daemon=True).start()


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
        devices = await BleakScanner.discover(timeout=timeout)
        out: List[Tuple[str, str, int]] = []
        for d in devices:
            name = (d.name or "").strip()
            if not name:
                continue
            # Your LightBlue "Heart Rate" is usually named exactly like this
            if "heart rate" in name.lower():
                rssi = getattr(d, "rssi", None)
                if rssi is None:
                    try:
                        rssi = d.metadata.get("rssi")  # type: ignore
                    except Exception:
                        rssi = -999
                out.append((name, d.address, int(rssi) if rssi is not None else -999))
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