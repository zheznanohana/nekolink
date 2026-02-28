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
ANCS_SERVICE = "7905f431-b5ce-4e99-a40f-4b1e122d00d0"
NOTIF_SRC = "9fbf120d-6301-42d9-8c58-25e699a21dbd"
CTRL_PT = "69d1d8f3-45e1-49a8-9821-9bbdfdaad9d9"
DATA_SRC = "22eac6e9-24d6-4bb5-be44-b36ace7c7bfb"

BATTERY_LEVEL_CHAR = "00002a19-0000-1000-8000-00805f9b34fb"

ATTR_APP_IDENTIFIER = 0
ATTR_TITLE = 1
ATTR_SUBTITLE = 2
ATTR_MESSAGE = 3
ATTR_DATE = 5


# -----------------------------
# Config location (portable-first, AppData fallback)
# -----------------------------
def _base_dir() -> Path:
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
      1) If config.json exists next to exe/script -> use it (portable)
      2) If dir not writable -> fallback to %APPDATA%\\NekoLink\\config.json
      3) Env NEKOLINK_PORTABLE=1 forces portable mode
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
    # UI (NEW) - persisted language: "zh" | "en" | "ja"
    ui_lang: str = "zh"

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
    dingtalk_secret: str = ""

    # gotify
    enable_gotify: bool = False
    gotify_url: str = ""
    gotify_token: str = ""
    gotify_priority: int = 5

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

    # misc
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
        raise ValueError("Missing email_to/email_from")

    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg.email_from
    msg["To"] = cfg.email_to

    server = smtplib.SMTP(cfg.smtp_host, int(cfg.smtp_port), timeout=10)
    server.ehlo()
    server.starttls()
    server.login(cfg.smtp_user, cfg.smtp_pass)
    server.send_message(msg)
    server.quit()


def _dingtalk_signed_url(webhook: str, secret: str) -> str:
    webhook = (webhook or "").strip()
    if not webhook:
        raise ValueError("Missing DingTalk webhook")

    secret = (secret or "").strip()
    if not secret:
        return webhook

    timestamp = str(int(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"

    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"{webhook}&timestamp={timestamp}&sign={sign}"


def send_dingtalk_text(webhook: str, secret: str, text: str, timeout: int = 10):
    url = _dingtalk_signed_url(webhook, secret)
    data = {"msgtype": "text", "text": {"content": text}}
    r = requests.post(url, json=data, timeout=timeout)

    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")

    try:
        j = r.json()
    except Exception:
        raise RuntimeError(f"Bad response: {r.text}")

    if j.get("errcode", 0) != 0:
        raise RuntimeError(str(j))


def send_gotify(gotify_url: str, token: str, title: str, message: str, priority: int = 5, timeout: int = 10):
    """
    FIX: Use JSON payload (more compatible). Also surface response body when failed.
    """
    gotify_url = (gotify_url or "").strip()
    token = (token or "").strip()
    if not gotify_url or not token:
        raise ValueError("Missing Gotify url/token")

    base = gotify_url.rstrip("/")
    url = f"{base}/message?token={token}"
    payload = {"title": title, "message": message, "priority": int(priority)}

    r = requests.post(url, json=payload, timeout=timeout)
    if r.status_code >= 400:
        # raise but keep body for debugging
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
    # gotify normally returns JSON; ignore content here


# -----------------------------
# Helpers
# -----------------------------
def _now_ts() -> float:
    return time.time()


def _contains_block_keyword(text: str, keywords: List[str], case_insensitive: bool) -> bool:
    if not keywords:
        return False
    hay = text or ""
    if case_insensitive:
        hay = hay.lower()
        kws = [k.lower() for k in keywords if k]
    else:
        kws = [k for k in keywords if k]
    for k in kws:
        if k and k in hay:
            return True
    return False


def _extract_codes(text: str, regex: str) -> List[str]:
    try:
        return re.findall(regex, text or "")
    except Exception:
        return []


def _format_message(payload: dict, cfg: BridgeConfig) -> str:
    lines = []
    lines.append("📲 iPhone 通知")
    if payload.get("device"):
        lines.append(f"Device: {payload.get('device')}")
    if cfg.show_battery_in_message:
        bat = payload.get("battery")
        if isinstance(bat, int):
            lines.append(f"Battery: {bat}%")
    if payload.get("app"):
        lines.append(f"App: {payload.get('app')}")
    if payload.get("title"):
        lines.append(f"Title: {payload.get('title')}")
    if payload.get("msg"):
        lines.append(f"Msg: {payload.get('msg')}")
    if payload.get("date"):
        lines.append(f"Date: {payload.get('date')}")
    return "\n".join(lines)


# -----------------------------
# ANCS Session
# -----------------------------
class _ANCSSession:
    def __init__(
        self,
        addr: str,
        cfg: BridgeConfig,
        log: Callable[[str], None],
        on_payload: Callable[[dict], None],
    ):
        self.addr = addr
        self.cfg = cfg
        self.log = log
        self.on_payload = on_payload

        self.client: Optional[BleakClient] = None
        self._stop = asyncio.Event()

        self._ds_buf: bytearray = bytearray()
        self._await_uid: Optional[int] = None
        self._last_battery_read: float = 0.0
        self._battery_cache: Optional[int] = None

    async def stop(self):
        self._stop.set()
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
        except Exception:
            pass

    async def run(self):
        while not self._stop.is_set():
            try:
                await self._connect_and_listen()
            except Exception as e:
                self.log(f"[{self.addr}] session error: {e}")
            await asyncio.sleep(1.5)

    async def _connect_and_listen(self):
        self.log(f"[{self.addr}] connecting...")
        async with BleakClient(self.addr) as client:
            self.client = client
            self.log(f"[{self.addr}] connected={client.is_connected}")

            await client.start_notify(NOTIF_SRC, self._on_notif_src)
            await client.start_notify(DATA_SRC, self._on_data_src)

            while client.is_connected and not self._stop.is_set():
                await asyncio.sleep(0.25)

            try:
                await client.stop_notify(NOTIF_SRC)
            except Exception:
                pass
            try:
                await client.stop_notify(DATA_SRC)
            except Exception:
                pass

    async def _read_battery(self) -> Optional[int]:
        if self._battery_cache is not None and (_now_ts() - self._last_battery_read) < 5.0:
            return self._battery_cache
        if not self.client or not self.client.is_connected:
            return self._battery_cache
        try:
            val = await self.client.read_gatt_char(BATTERY_LEVEL_CHAR)
            if val and len(val) >= 1:
                b = int(val[0])
                if 0 <= b <= 100:
                    self._battery_cache = b
                    self._last_battery_read = _now_ts()
                    return b
        except Exception:
            return self._battery_cache
        return self._battery_cache

    def _on_notif_src(self, _sender: int, data: bytearray):
        if not data or len(data) < 8:
            return
        event_id = data[0]
        uid = int.from_bytes(data[4:8], byteorder="little", signed=False)
        if event_id != 0:
            return
        self._await_uid = uid
        self._ds_buf = bytearray()
        asyncio.create_task(self._request_attributes(uid))

    async def _request_attributes(self, uid: int):
        if not self.client or not self.client.is_connected:
            return
        try:
            title_len = 64
            msg_len = 256

            payload = bytearray()
            payload.append(0x00)
            payload += uid.to_bytes(4, "little")

            payload.append(ATTR_APP_IDENTIFIER)

            payload.append(ATTR_TITLE)
            payload += int(title_len).to_bytes(2, "little")

            payload.append(ATTR_MESSAGE)
            payload += int(msg_len).to_bytes(2, "little")

            payload.append(ATTR_DATE)

            await self.client.write_gatt_char(CTRL_PT, payload, response=True)
            self.log(f"[{self.addr}] [CP] requested attributes for uid={uid}")
        except Exception as e:
            self.log(f"[{self.addr}] [CP] error: {e}")

    def _on_data_src(self, _sender: int, chunk: bytearray):
        if not chunk:
            return
        self._ds_buf += chunk
        self._try_parse_ds()

    def _try_parse_ds(self):
        while True:
            if len(self._ds_buf) < 5:
                return

            cmd_id = self._ds_buf[0]
            uid = int.from_bytes(self._ds_buf[1:5], "little", signed=False)
            if cmd_id != 0x00:
                self._ds_buf = bytearray()
                return

            pos = 5
            attrs: Dict[int, str] = {}
            while True:
                if len(self._ds_buf) < pos + 3:
                    return
                attr_id = self._ds_buf[pos]
                attr_len = int.from_bytes(self._ds_buf[pos + 1: pos + 3], "little", signed=False)
                pos += 3
                if len(self._ds_buf) < pos + attr_len:
                    return
                raw = bytes(self._ds_buf[pos: pos + attr_len])
                pos += attr_len
                try:
                    attrs[attr_id] = raw.decode("utf-8", errors="ignore")
                except Exception:
                    attrs[attr_id] = ""

                if pos >= len(self._ds_buf):
                    break

            self._ds_buf = bytearray()
            asyncio.create_task(self._emit_notification(uid, attrs))
            return

    async def _emit_notification(self, uid: int, attrs: Dict[int, str]):
        try:
            app = attrs.get(ATTR_APP_IDENTIFIER, "") or ""
            title = attrs.get(ATTR_TITLE, "") or ""
            msg = attrs.get(ATTR_MESSAGE, "") or ""
            date = attrs.get(ATTR_DATE, "") or ""

            merged_text = "\n".join([app, title, msg, date]).strip()
            if _contains_block_keyword(merged_text, self.cfg.block_keywords, self.cfg.block_case_insensitive):
                self.log(f"[{self.addr}] [FILTER] blocked")
                return

            bat = await self._read_battery()

            codes: List[str] = []
            if self.cfg.enable_code_highlight:
                codes = _extract_codes(merged_text, self.cfg.code_regex)

            payload = {
                "ts": _now_ts(),
                "uid": uid,
                "device": self.addr,
                "battery": bat,
                "app": app,
                "title": title,
                "msg": msg,
                "date": date,
                "codes": codes,
            }
            self.on_payload(payload)

        except Exception as e:
            self.log(f"[{self.addr}] emit error: {e}")


# -----------------------------
# BridgeManager
# -----------------------------
class BridgeManager:
    def __init__(
        self,
        cfg: BridgeConfig,
        log_func: Callable[[str], None],
        on_notification: Callable[[dict], None],
    ):
        self.cfg = cfg
        self.log = log_func
        self.on_notification = on_notification

        self._threads: Dict[str, threading.Thread] = {}
        self._loops: Dict[str, asyncio.AbstractEventLoop] = {}
        self._sessions: Dict[str, _ANCSSession] = {}

        self._dedup: Dict[str, float] = {}
        self._lock = threading.Lock()

    async def scan_heart_rate(self, timeout: int = 8) -> List[Tuple[str, str, int]]:
        devices = await BleakScanner.discover(timeout=timeout)
        out: List[Tuple[str, str, int]] = []
        for d in devices:
            name = (d.name or "").strip() or "(no name)"
            addr = d.address
            rssi = getattr(d, "rssi", None)
            if rssi is None:
                rssi = -999
            if "heart" in name.lower() or "rate" in name.lower():
                out.append((name, addr, int(rssi)))
        if not out:
            for d in devices:
                name = (d.name or "").strip() or "(no name)"
                addr = d.address
                rssi = getattr(d, "rssi", None)
                if rssi is None:
                    rssi = -999
                out.append((name, addr, int(rssi)))
        out.sort(key=lambda x: x[2], reverse=True)
        return out

    def start_all(self, addrs: List[str]):
        addrs = [a.strip() for a in (addrs or []) if a.strip()]
        if not addrs:
            return
        for addr in addrs:
            if addr in self._threads and self._threads[addr].is_alive():
                continue
            self._start_one(addr)

    def stop_all(self):
        for addr in list(self._threads.keys()):
            self._stop_one(addr)

    def _start_one(self, addr: str):
        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loops[addr] = loop

            session = _ANCSSession(addr, self.cfg, self.log, self._on_payload_internal)
            self._sessions[addr] = session

            async def _main():
                await session.run()

            try:
                loop.run_until_complete(_main())
            except Exception as e:
                self.log(f"[{addr}] loop error: {e}")
            finally:
                try:
                    loop.stop()
                except Exception:
                    pass
                try:
                    loop.close()
                except Exception:
                    pass

        t = threading.Thread(target=_runner, daemon=True)
        self._threads[addr] = t
        t.start()
        self.log(f"[MANAGER] started {addr}")

    def _stop_one(self, addr: str):
        try:
            loop = self._loops.get(addr)
            session = self._sessions.get(addr)
            if loop and session:
                asyncio.run_coroutine_threadsafe(session.stop(), loop)
        except Exception:
            pass
        self.log(f"[MANAGER] stopping {addr}")

    def _dedup_ok(self, payload: dict) -> bool:
        window = int(getattr(self.cfg, "dedup_seconds", 8) or 8)
        key = f"{payload.get('device')}|{payload.get('app')}|{payload.get('title')}|{payload.get('msg')}|{payload.get('date')}"
        now = _now_ts()
        with self._lock:
            last = self._dedup.get(key)
            if last is not None and (now - last) < window:
                return False
            self._dedup[key] = now
        return True

    def _on_payload_internal(self, payload: dict):
        if not self._dedup_ok(payload):
            return

        try:
            self._forward(payload)
        except Exception as e:
            self.log(f"[FORWARD] error: {e}")

        try:
            self.on_notification(payload)
        except Exception:
            pass

    def _forward(self, payload: dict):
        cfg = self.cfg
        text = _format_message(payload, cfg)

        if cfg.enable_windows_toast and show_toast is not None:
            try:
                show_toast("NekoLink", text)
            except Exception as e:
                self.log(f"[TOAST] failed: {e}")

        if cfg.enable_telegram:
            try:
                send_telegram(cfg.telegram_bot_token, cfg.telegram_chat_id, text)
            except Exception as e:
                self.log(f"[TG] failed: {e}")

        if cfg.enable_dingtalk:
            try:
                send_dingtalk_text(cfg.dingtalk_webhook, cfg.dingtalk_secret, text)
            except Exception as e:
                self.log(f"[DT] failed: {e}")

        if cfg.enable_gotify:
            try:
                send_gotify(cfg.gotify_url, cfg.gotify_token, "NekoLink", text, priority=cfg.gotify_priority)
            except Exception as e:
                self.log(f"[GOTIFY] failed: {e}")

        if cfg.enable_email:
            try:
                send_email(cfg, "NekoLink Notification", text)
            except Exception as e:
                self.log(f"[MAIL] failed: {e}")

        if cfg.enable_code_highlight and cfg.code_send_separately:
            codes = payload.get("codes") or []
            if codes:
                code_text = f"{cfg.code_separate_prefix}: " + " ".join(codes)

                if cfg.enable_telegram:
                    try:
                        send_telegram(cfg.telegram_bot_token, cfg.telegram_chat_id, code_text)
                    except Exception as e:
                        self.log(f"[TG-code] failed: {e}")

                if cfg.enable_dingtalk:
                    try:
                        send_dingtalk_text(cfg.dingtalk_webhook, cfg.dingtalk_secret, code_text)
                    except Exception as e:
                        self.log(f"[DT-code] failed: {e}")

                if cfg.enable_gotify:
                    try:
                        send_gotify(
                            cfg.gotify_url,
                            cfg.gotify_token,
                            "NekoLink Code",
                            code_text,
                            priority=max(7, int(cfg.gotify_priority)),
                        )
                    except Exception as e:
                        self.log(f"[GOTIFY-code] failed: {e}")

                if cfg.enable_email:
                    try:
                        send_email(cfg, "NekoLink Code", code_text)
                    except Exception as e:
                        self.log(f"[MAIL-code] failed: {e}")