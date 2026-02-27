import os
import json
import queue
import time
import threading
import tkinter as tk

import requests
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from ancs_bridge import BridgeConfig, BridgeManager
from tray_helper import TrayController
from i18n import t

# Always read/write config.json next to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def _bridge_field_set():
    try:
        from dataclasses import fields
        return {f.name for f in fields(BridgeConfig)}
    except Exception:
        return set()


BRIDGE_FIELDS = _bridge_field_set()


class App(tb.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.geometry("1100x680")

        self.log_q = queue.Queue()

        # UI-only
        self.ui_lang = "zh"
        self._dirty = False
        self._restore_state = "normal"  # remember normal/zoomed when minimizing

        self.cfg = self.load_config()
        self.manager = BridgeManager(self.cfg, self.log, self.on_notification)
        self.running = False

        # tray
        self.tray = TrayController(
            title="NekoLink",
            on_restore=self.restore_from_tray,
            on_exit=self.exit_app,
        )
        self.tray.start()

        self.history = []

        self._build_ui()
        self.apply_i18n()
        self.set_dirty(False)

        self._flush_logs()

        # Click X -> minimize (keeps taskbar workable)
        self.protocol("WM_DELETE_WINDOW", self.on_close_minimize)

    # ---------- i18n / dirty ----------
    def apply_i18n(self):
        title = t(self.ui_lang, "app_title")
        self.title(title + (" •" if self._dirty else ""))

        self.lbl_header_title.config(text=t(self.ui_lang, "header_title"))
        self.lbl_status.config(text=t(self.ui_lang, "running") if self.running else t(self.ui_lang, "stopped"))
        self.lbl_unsaved.config(text=t(self.ui_lang, "unsaved"))

        self.nb.tab(self.tab_main, text=t(self.ui_lang, "tab_main"))
        self.nb.tab(self.tab_devices, text=t(self.ui_lang, "tab_devices"))
        self.nb.tab(self.tab_dest, text=t(self.ui_lang, "tab_destinations"))
        self.nb.tab(self.tab_block, text=t(self.ui_lang, "tab_block"))
        self.nb.tab(self.tab_history, text=t(self.ui_lang, "tab_history"))
        self.nb.tab(self.tab_logs, text=t(self.ui_lang, "tab_logs"))

        self.lbl_lang.config(text=t(self.ui_lang, "lbl_language"))

        # Main
        self.btn_main_save.config(text=t(self.ui_lang, "btn_save"))
        self.btn_main_start.config(text=t(self.ui_lang, "btn_start"))
        self.btn_main_stop.config(text=t(self.ui_lang, "btn_stop"))
        self.lbl_dedup.config(text=t(self.ui_lang, "lbl_dedup"))
        self.chk_code_detect.config(text=t(self.ui_lang, "chk_code_detect"))
        self.chk_code_sep.config(text=t(self.ui_lang, "chk_code_separate"))
        self.lbl_history_limit.config(text=t(self.ui_lang, "lbl_history_limit"))
        self.lbl_preview_title.config(text=t(self.ui_lang, "lbl_latest_preview"))
        self.lbl_tip.config(text=t(self.ui_lang, "lbl_tip_tray"))
        self.lbl_cfg_path.config(text=f"{t(self.ui_lang, 'lbl_config_path')} {CONFIG_PATH}")

        # Devices
        self.lbl_devices_title.config(text=t(self.ui_lang, "devices_title"))
        self.btn_scan.config(text=t(self.ui_lang, "btn_scan"))
        self.btn_add_addr.config(text=t(self.ui_lang, "btn_add"))
        self.btn_remove_addr.config(text=t(self.ui_lang, "btn_remove_selected"))
        self.lbl_scan_hint.config(text=t(self.ui_lang, "devices_scan_hint"))
        self.btn_devices_save.config(text=t(self.ui_lang, "btn_save"))

        # Destinations
        self.chk_tg_enable.config(text=t(self.ui_lang, "dest_tg_enable"))
        self.lbl_tg_token.config(text=t(self.ui_lang, "dest_tg_token"))
        self.lbl_tg_chat.config(text=t(self.ui_lang, "dest_tg_chat"))
        self.btn_tg_showhide.config(text=t(self.ui_lang, "dest_show_hide"))
        self.btn_tg_test.config(text=t(self.ui_lang, "btn_test"))

        self.chk_mail_enable.config(text=t(self.ui_lang, "dest_email_enable"))
        self.lbl_mail_host.config(text=t(self.ui_lang, "dest_email_host"))
        self.lbl_mail_port.config(text=t(self.ui_lang, "dest_email_port"))
        self.lbl_mail_user.config(text=t(self.ui_lang, "dest_email_user"))
        self.lbl_mail_pass.config(text=t(self.ui_lang, "dest_email_pass"))
        self.lbl_mail_from.config(text=t(self.ui_lang, "dest_email_from"))
        self.lbl_mail_to.config(text=t(self.ui_lang, "dest_email_to"))
        self.btn_mail_test.config(text=t(self.ui_lang, "btn_test"))
        self.btn_dest_save.config(text=t(self.ui_lang, "btn_save"))

        # Block
        self.lbl_block_title.config(text=t(self.ui_lang, "block_title"))
        self.chk_block_ci.config(text=t(self.ui_lang, "block_case_insensitive"))
        self.btn_block_add.config(text=t(self.ui_lang, "btn_add"))
        self.btn_block_remove.config(text=t(self.ui_lang, "btn_remove_selected"))
        self.btn_block_save.config(text=t(self.ui_lang, "btn_save"))

        # History / Logs
        self.lbl_history_title.config(text=t(self.ui_lang, "history_title"))
        self.btn_hist_clear.config(text=t(self.ui_lang, "btn_clear"))
        self.btn_hist_copy.config(text=t(self.ui_lang, "btn_copy_selected"))

        self.lbl_logs_title.config(text=t(self.ui_lang, "logs_title"))
        self.btn_logs_clear.config(text=t(self.ui_lang, "btn_clear"))

    def set_dirty(self, dirty: bool):
        self._dirty = bool(dirty)
        self.lbl_unsaved.pack_forget()
        if self._dirty:
            self.lbl_unsaved.pack(side=RIGHT, padx=(8, 0))
        self.apply_i18n()

    def mark_dirty(self, *_args):
        if not self._dirty:
            self.set_dirty(True)

    # ---------- UI ----------
    def _build_ui(self):
        root = tb.Frame(self, padding=10)
        root.pack(fill=BOTH, expand=True)

        # Header
        header = tb.Frame(root)
        header.pack(fill=X)

        self.lbl_header_title = tb.Label(header, text="", font=("Segoe UI", 16, "bold"))
        self.lbl_header_title.pack(side=LEFT)

        right = tb.Frame(header)
        right.pack(side=RIGHT)

        self.lbl_unsaved = tb.Label(right, text="", bootstyle="warning")
        # packed only when dirty

        self.lbl_status = tb.Label(right, text="", bootstyle="danger")
        self.lbl_status.pack(side=RIGHT)

        tb.Separator(root).pack(fill=X, pady=(10, 8))

        # Language selector
        langbar = tb.Frame(root)
        langbar.pack(fill=X, pady=(0, 8))
        self.lbl_lang = tb.Label(langbar, text="")
        self.lbl_lang.pack(side=LEFT)

        self.var_lang = tk.StringVar(value=self.ui_lang)
        self.cmb_lang = tb.Combobox(langbar, textvariable=self.var_lang, values=["zh", "ja", "en"], width=6, state="readonly")
        self.cmb_lang.pack(side=LEFT, padx=(8, 0))
        self.cmb_lang.bind("<<ComboboxSelected>>", self.on_change_language)

        # Tabs
        self.nb = tb.Notebook(root)
        self.nb.pack(fill=BOTH, expand=True)

        self.tab_main = tb.Frame(self.nb)
        self.tab_devices = tb.Frame(self.nb)
        self.tab_dest = tb.Frame(self.nb)
        self.tab_block = tb.Frame(self.nb)
        self.tab_history = tb.Frame(self.nb)
        self.tab_logs = tb.Frame(self.nb)

        self.nb.add(self.tab_main, text="Main")
        self.nb.add(self.tab_devices, text="Devices")
        self.nb.add(self.tab_dest, text="Destinations")
        self.nb.add(self.tab_block, text="Block")
        self.nb.add(self.tab_history, text="History")
        self.nb.add(self.tab_logs, text="Logs")

        self._build_tab_main()
        self._build_tab_devices()
        self._build_tab_dest()
        self._build_tab_block()
        self._build_tab_history()
        self._build_tab_logs()

    # ---------- Savebar helper ----------
    def _tab_with_savebar(self, tab: tb.Frame, save_command, save_btn_attr: str):
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)

        content = tb.Frame(tab, padding=12)
        content.grid(row=0, column=0, sticky="nsew")

        savebar = tb.Frame(tab, padding=10)
        savebar.grid(row=1, column=0, sticky="ew")
        savebar.grid_columnconfigure(0, weight=1)
        tb.Frame(savebar).grid(row=0, column=0, sticky="ew")

        btn = tb.Button(savebar, text="Save", bootstyle="secondary", command=save_command)
        btn.grid(row=0, column=1, sticky="e")

        setattr(self, save_btn_attr, btn)
        return content

    # ---------- Main ----------
    def _build_tab_main(self):
        content = self._tab_with_savebar(self.tab_main, self.on_save, "btn_main_save")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)

        left = tb.Frame(content)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 16))

        right = tb.Frame(content)
        right.grid(row=0, column=1, sticky="nsew")

        runbar = tb.Frame(left)
        runbar.pack(anchor=W, pady=(0, 10))

        self.btn_main_start = tb.Button(runbar, text="Start", bootstyle="success", command=self.on_start)
        self.btn_main_start.pack(side=LEFT, padx=(0, 8))
        self.btn_main_stop = tb.Button(runbar, text="Stop", bootstyle="danger", command=self.on_stop)
        self.btn_main_stop.pack(side=LEFT)

        tb.Separator(left).pack(fill=X, pady=10)

        self.var_dedup = tk.StringVar(value=str(getattr(self.cfg, "dedup_seconds", 8)))
        self.lbl_dedup = tb.Label(left, text="")
        self.lbl_dedup.pack(anchor=W)
        tb.Entry(left, textvariable=self.var_dedup, width=10).pack(anchor=W, pady=(0, 10))

        self.var_code_on = tk.BooleanVar(value=getattr(self.cfg, "enable_code_highlight", True))
        self.var_code_sep = tk.BooleanVar(value=getattr(self.cfg, "code_send_separately", True))
        self.chk_code_detect = tb.Checkbutton(left, text="", variable=self.var_code_on, bootstyle="round-toggle")
        self.chk_code_detect.pack(anchor=W, pady=(0, 6))
        self.chk_code_sep = tb.Checkbutton(left, text="", variable=self.var_code_sep, bootstyle="round-toggle")
        self.chk_code_sep.pack(anchor=W)

        self.var_history_limit = tk.StringVar(value=str(getattr(self.cfg, "history_limit", 300)))
        self.lbl_history_limit = tb.Label(left, text="")
        self.lbl_history_limit.pack(anchor=W, pady=(10, 0))
        tb.Entry(left, textvariable=self.var_history_limit, width=10).pack(anchor=W)

        self.lbl_preview_title = tb.Label(right, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_preview_title.pack(anchor=W)
        self.preview = tk.Text(right, height=8, wrap="word")
        self.preview.pack(fill=X, pady=(8, 8))
        self.preview.insert("end", "（暂无）\n")

        self.lbl_tip = tb.Label(right, text="")
        self.lbl_tip.pack(anchor=W)

        self.lbl_cfg_path = tb.Label(right, text="")
        self.lbl_cfg_path.pack(anchor=W, pady=(6, 0))

        # dirty watchers
        self.var_dedup.trace_add("write", self.mark_dirty)
        self.var_code_on.trace_add("write", self.mark_dirty)
        self.var_code_sep.trace_add("write", self.mark_dirty)
        self.var_history_limit.trace_add("write", self.mark_dirty)

    # ---------- Devices ----------
    def _build_tab_devices(self):
        content = self._tab_with_savebar(self.tab_devices, self.on_save, "btn_devices_save")

        top = tb.Frame(content)
        top.pack(fill=X, pady=(0, 10))

        self.lbl_devices_title = tb.Label(top, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_devices_title.pack(side=LEFT)

        self.btn_scan = tb.Button(top, text="Scan", bootstyle="info", command=self.scan_devices)
        self.btn_scan.pack(side=RIGHT)

        self.lst_addr = tk.Listbox(content, height=10)
        self.lst_addr.pack(fill=X, pady=(0, 10))
        for a in (getattr(self.cfg, "ble_addresses", []) or []):
            self.lst_addr.insert("end", a)

        ctl = tb.Frame(content)
        ctl.pack(fill=X, pady=(0, 10))

        self.var_add_addr = tk.StringVar()
        tb.Entry(ctl, textvariable=self.var_add_addr, width=40).pack(side=LEFT, padx=(0, 8))

        self.btn_add_addr = tb.Button(ctl, text="Add", bootstyle="secondary", command=self.add_addr)
        self.btn_add_addr.pack(side=LEFT, padx=(0, 8))

        self.btn_remove_addr = tb.Button(ctl, text="Remove selected", bootstyle="warning", command=self.remove_selected_addr)
        self.btn_remove_addr.pack(side=LEFT)

        self.lbl_scan_hint = tb.Label(content, text="")
        self.lbl_scan_hint.pack(anchor=W, pady=(10, 4))

        self.scan_box = tk.Text(content, height=10, wrap="word")
        self.scan_box.pack(fill=BOTH, expand=True)
        self.scan_box.insert("end", "Scan results will appear here.\n")

        def on_dbl_click(_evt):
            try:
                sel = self.scan_box.get("insert linestart", "insert lineend").strip()
                if "addr=" in sel:
                    addr = sel.split("addr=")[1].split()[0].strip()
                    self.var_add_addr.set(addr)
            except Exception:
                pass

        self.scan_box.bind("<Double-Button-1>", on_dbl_click)

    # ---------- Destinations ----------
    def _build_tab_dest(self):
        content = self._tab_with_savebar(self.tab_dest, self.on_save, "btn_dest_save")

        tg = tb.Labelframe(content, text="Telegram", padding=10)
        tg.pack(fill=X, pady=(0, 12))

        self.var_tg_on = tk.BooleanVar(value=getattr(self.cfg, "enable_telegram", True))
        self.var_tg_token = tk.StringVar(value=getattr(self.cfg, "telegram_bot_token", ""))
        self.var_tg_chat = tk.StringVar(value=getattr(self.cfg, "telegram_chat_id", ""))

        self.chk_tg_enable = tb.Checkbutton(tg, text="", variable=self.var_tg_on, bootstyle="round-toggle")
        self.chk_tg_enable.grid(row=0, column=0, sticky=W, pady=(0, 6))

        self.lbl_tg_token = tb.Label(tg, text="")
        self.lbl_tg_token.grid(row=1, column=0, sticky=W)

        self.ent_token = tb.Entry(tg, textvariable=self.var_tg_token, width=70, show="•")
        self.ent_token.grid(row=1, column=1, sticky=W, pady=2)

        self._token_hidden = True
        self.btn_tg_showhide = tb.Button(tg, text="", bootstyle="secondary", command=self.toggle_token_visibility)
        self.btn_tg_showhide.grid(row=1, column=2, sticky=W, padx=(8, 0))

        self.lbl_tg_chat = tb.Label(tg, text="")
        self.lbl_tg_chat.grid(row=2, column=0, sticky=W)

        tb.Entry(tg, textvariable=self.var_tg_chat, width=30).grid(row=2, column=1, sticky=W, pady=2)

        self.btn_tg_test = tb.Button(tg, text="Test", bootstyle="success", command=self.test_telegram)
        self.btn_tg_test.grid(row=3, column=1, sticky=W, pady=(8, 0))

        mail = tb.Labelframe(content, text="Email (SMTP)", padding=10)
        mail.pack(fill=X)

        self.var_mail_on = tk.BooleanVar(value=getattr(self.cfg, "enable_email", False))
        self.var_smtp_host = tk.StringVar(value=getattr(self.cfg, "smtp_host", "smtp.gmail.com"))
        self.var_smtp_port = tk.StringVar(value=str(getattr(self.cfg, "smtp_port", 587)))
        self.var_smtp_user = tk.StringVar(value=getattr(self.cfg, "smtp_user", ""))
        self.var_smtp_pass = tk.StringVar(value=getattr(self.cfg, "smtp_pass", ""))
        self.var_email_from = tk.StringVar(value=getattr(self.cfg, "email_from", ""))
        self.var_email_to = tk.StringVar(value=getattr(self.cfg, "email_to", ""))

        self.chk_mail_enable = tb.Checkbutton(mail, text="", variable=self.var_mail_on, bootstyle="round-toggle")
        self.chk_mail_enable.grid(row=0, column=0, sticky=W, pady=(0, 6))

        self.lbl_mail_host = tb.Label(mail, text="")
        self.lbl_mail_host.grid(row=1, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_host, width=36).grid(row=1, column=1, sticky=W, pady=2)

        self.lbl_mail_port = tb.Label(mail, text="")
        self.lbl_mail_port.grid(row=1, column=2, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_port, width=8).grid(row=1, column=3, sticky=W, pady=2)

        self.lbl_mail_user = tb.Label(mail, text="")
        self.lbl_mail_user.grid(row=2, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_user, width=36).grid(row=2, column=1, sticky=W, pady=2)

        self.lbl_mail_pass = tb.Label(mail, text="")
        self.lbl_mail_pass.grid(row=3, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_pass, width=36, show="•").grid(row=3, column=1, sticky=W, pady=2)

        self.lbl_mail_from = tb.Label(mail, text="")
        self.lbl_mail_from.grid(row=4, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_email_from, width=36).grid(row=4, column=1, sticky=W, pady=2)

        self.lbl_mail_to = tb.Label(mail, text="")
        self.lbl_mail_to.grid(row=5, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_email_to, width=36).grid(row=5, column=1, sticky=W, pady=2)

        self.btn_mail_test = tb.Button(mail, text="Test", bootstyle="success", command=self.test_email)
        self.btn_mail_test.grid(row=6, column=1, sticky=W, pady=(8, 0))

        # dirty watchers
        for v in [
            self.var_tg_on, self.var_tg_token, self.var_tg_chat,
            self.var_mail_on, self.var_smtp_host, self.var_smtp_port,
            self.var_smtp_user, self.var_smtp_pass, self.var_email_from, self.var_email_to
        ]:
            v.trace_add("write", self.mark_dirty)

    # ---------- Block ----------
    def _build_tab_block(self):
        content = self._tab_with_savebar(self.tab_block, self.on_save, "btn_block_save")

        self.lbl_block_title = tb.Label(content, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_block_title.pack(anchor=W, pady=(0, 8))

        self.var_block_ci = tk.BooleanVar(value=getattr(self.cfg, "block_case_insensitive", True))
        self.chk_block_ci = tb.Checkbutton(content, text="", variable=self.var_block_ci, bootstyle="round-toggle")
        self.chk_block_ci.pack(anchor=W, pady=(0, 10))

        self.lst_block = tk.Listbox(content, height=10)
        self.lst_block.pack(fill=X, pady=(0, 10))
        for k in (getattr(self.cfg, "block_keywords", []) or []):
            self.lst_block.insert("end", k)

        ctl = tb.Frame(content)
        ctl.pack(fill=X)

        self.var_block_input = tk.StringVar()
        tb.Entry(ctl, textvariable=self.var_block_input, width=40).pack(side=LEFT, padx=(0, 8))

        self.btn_block_add = tb.Button(ctl, text="Add", bootstyle="secondary", command=self.add_block)
        self.btn_block_add.pack(side=LEFT, padx=(0, 8))

        self.btn_block_remove = tb.Button(ctl, text="Remove selected", bootstyle="warning", command=self.remove_block)
        self.btn_block_remove.pack(side=LEFT)

        self.var_block_ci.trace_add("write", self.mark_dirty)

    # ---------- History ----------
    def _build_tab_history(self):
        content = tb.Frame(self.tab_history, padding=12)
        content.pack(fill=BOTH, expand=True)

        top = tb.Frame(content)
        top.pack(fill=X, pady=(0, 8))

        self.lbl_history_title = tb.Label(top, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_history_title.pack(side=LEFT)

        self.btn_hist_clear = tb.Button(top, text="Clear", bootstyle="warning", command=self.clear_history)
        self.btn_hist_clear.pack(side=RIGHT, padx=(8, 0))

        self.btn_hist_copy = tb.Button(top, text="Copy selected", bootstyle="secondary", command=self.copy_selected_history)
        self.btn_hist_copy.pack(side=RIGHT)

        cols = ("time", "device", "app", "title", "msg", "codes")
        self.tree = tb.Treeview(content, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("time", width=130, anchor=W)
        self.tree.column("device", width=140, anchor=W)
        self.tree.column("app", width=180, anchor=W)
        self.tree.column("title", width=200, anchor=W)
        self.tree.column("msg", width=320, anchor=W)
        self.tree.column("codes", width=90, anchor=W)
        self.tree.pack(fill=BOTH, expand=True)

    # ---------- Logs ----------
    def _build_tab_logs(self):
        content = tb.Frame(self.tab_logs, padding=12)
        content.pack(fill=BOTH, expand=True)

        top = tb.Frame(content)
        top.pack(fill=X, pady=(0, 8))

        self.lbl_logs_title = tb.Label(top, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_logs_title.pack(side=LEFT)

        self.btn_logs_clear = tb.Button(top, text="Clear", bootstyle="warning", command=self.clear_logs)
        self.btn_logs_clear.pack(side=RIGHT)

        self.txt_logs = tk.Text(content, wrap="word", height=10)
        self.txt_logs.pack(fill=BOTH, expand=True)
        self.txt_logs.insert("end", "Ready.\n")

    # ---------- Language ----------
    def on_change_language(self, _evt=None):
        lang = (self.var_lang.get() or "en").lower()
        if lang not in ("zh", "ja", "en"):
            lang = "en"
        if lang != self.ui_lang:
            self.ui_lang = lang
            self.mark_dirty()
            self.apply_i18n()

    # ---------- Core ----------
    def log(self, s: str):
        self.log_q.put(s)

    def on_notification(self, payload: dict):
        preview_text = (
            f"Device: {payload.get('device')}\n"
            f"App: {payload.get('app')}\n"
            f"Title: {payload.get('title')}\n"
            f"Msg: {payload.get('msg')}\n"
            f"Codes: {' '.join(payload.get('codes') or [])}\n"
        )
        self.preview.delete("1.0", "end")
        self.preview.insert("end", preview_text)

        self.history.append(payload)
        limit = max(50, self.safe_int(self.var_history_limit.get(), getattr(self.cfg, "history_limit", 300)))
        if len(self.history) > limit:
            self.history = self.history[-limit:]

        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(payload["ts"]))
        codes = " ".join(payload.get("codes") or [])
        self.tree.insert("", "end", values=(ts, payload["device"], payload["app"], payload["title"], payload["msg"], codes))

        children = self.tree.get_children()
        if len(children) > limit:
            for iid in children[: len(children) - limit]:
                self.tree.delete(iid)

    def _validate_before_run(self, cfg: BridgeConfig) -> bool:
        if getattr(cfg, "enable_telegram", False):
            tok = (getattr(cfg, "telegram_bot_token", "") or "").strip()
            if not tok or tok.upper().startswith("PASTE_") or ":" not in tok:
                messagebox.showerror(
                    t(self.ui_lang, "msg_missing_title"),
                    t(self.ui_lang, "msg_tg_invalid").format(prefix=tok[:12], path=CONFIG_PATH),
                )
                return False
        return True

    def on_save(self):
        cfg = self.collect_config()
        self.save_config(cfg)
        self.set_dirty(False)

    def on_start(self):
        if self.running:
            return
        cfg = self.collect_config()
        if not self._validate_before_run(cfg):
            return

        # Start implies save
        self.save_config(cfg)
        self.set_dirty(False)

        self.cfg = cfg
        self.manager.cfg = cfg

        addrs = getattr(cfg, "ble_addresses", []) or []
        if not addrs:
            messagebox.showwarning(t(self.ui_lang, "msg_missing_title"), t(self.ui_lang, "msg_no_devices"))
            return

        self.running = True
        self.lbl_status.config(text=t(self.ui_lang, "running"), bootstyle="success")
        self.manager.start_all(addrs)
        self.log("[UI] started")

    def on_stop(self):
        if not self.running:
            return
        self.running = False
        self.lbl_status.config(text=t(self.ui_lang, "stopped"), bootstyle="danger")
        self.manager.stop_all()
        self.log("[UI] stopped")

    # ---------- Devices ----------
    def scan_devices(self):
        self.scan_box.delete("1.0", "end")
        self.scan_box.insert("end", "Scanning...\n")

        def _work():
            try:
                results = asyncio_run(self.manager.scan_heart_rate(timeout=8))
                if not results:
                    self.log("[SCAN] none")
                    self.scan_box.insert("end", t(self.ui_lang, "devices_no_found") + "\n")
                    return
                for name, addr, rssi in results:
                    self.scan_box.insert("end", f"{name} | addr={addr} | rssi={rssi}\n")
            except Exception as e:
                self.scan_box.insert("end", f"Scan error: {e}\n")

        threading.Thread(target=_work, daemon=True).start()

    def add_addr(self):
        addr = (self.var_add_addr.get() or "").strip()
        if not addr:
            return
        existing = [self.lst_addr.get(i) for i in range(self.lst_addr.size())]
        if addr not in existing:
            self.lst_addr.insert("end", addr)
            self.mark_dirty()
        self.var_add_addr.set("")

    def remove_selected_addr(self):
        sel = list(self.lst_addr.curselection())
        if not sel:
            return
        sel.reverse()
        for idx in sel:
            self.lst_addr.delete(idx)
        self.mark_dirty()

    # ---------- Block ----------
    def add_block(self):
        s = (self.var_block_input.get() or "").strip()
        if not s:
            return
        self.lst_block.insert("end", s)
        self.var_block_input.set("")
        self.mark_dirty()

    def remove_block(self):
        sel = list(self.lst_block.curselection())
        if not sel:
            return
        sel.reverse()
        for idx in sel:
            self.lst_block.delete(idx)
        self.mark_dirty()

    # ---------- History ----------
    def clear_history(self):
        self.history.clear()
        for iid in self.tree.get_children():
            self.tree.delete(iid)

    def copy_selected_history(self):
        sel = self.tree.selection()
        if not sel:
            return
        lines = []
        for iid in sel:
            vals = self.tree.item(iid, "values")
            lines.append(" | ".join(str(v) for v in vals))
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo(t(self.ui_lang, "msg_saved_title"), t(self.ui_lang, "msg_copied"))

    # ---------- Logs ----------
    def clear_logs(self):
        self.txt_logs.delete("1.0", "end")

    # ---------- Tests ----------
    def test_telegram(self):
        token = (self.var_tg_token.get() or "").strip()
        chat_id = (self.var_tg_chat.get() or "").strip()
        if not token or not chat_id:
            messagebox.showwarning(t(self.ui_lang, "msg_missing_title"), t(self.ui_lang, "msg_missing_tg"))
            return
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": "✅ Telegram Test: NekoLink OK", "disable_web_page_preview": True}
            r = requests.post(url, json=payload, timeout=10)
            r.raise_for_status()
            messagebox.showinfo("OK", t(self.ui_lang, "msg_tg_ok"))
        except Exception as e:
            messagebox.showerror("Fail", f"Telegram failed: {e}")

    def test_email(self):
        cfg = self.collect_config()
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText("✅ Email Test: NekoLink OK", _charset="utf-8")
            msg["Subject"] = "NekoLink Email Test"
            msg["From"] = getattr(cfg, "email_from", "")
            msg["To"] = getattr(cfg, "email_to", "")

            server = smtplib.SMTP(getattr(cfg, "smtp_host", ""), int(getattr(cfg, "smtp_port", 587)), timeout=10)
            server.ehlo()
            server.starttls()
            server.login(getattr(cfg, "smtp_user", ""), getattr(cfg, "smtp_pass", ""))
            server.send_message(msg)
            server.quit()
            messagebox.showinfo("OK", t(self.ui_lang, "msg_email_ok"))
        except Exception as e:
            messagebox.showerror("Fail", f"Email failed: {e}")

    # ---------- Token visibility ----------
    def toggle_token_visibility(self):
        self._token_hidden = not self._token_hidden
        self.ent_token.configure(show="•" if self._token_hidden else "")

    # ---------- Tray / window behavior ----------
    def on_close_minimize(self):
        # remember current state (normal/zoomed)
        try:
            st = self.state()
            if st in ("zoomed", "normal"):
                self._restore_state = st
        except Exception:
            self._restore_state = "normal"

        self.iconify()
        self.log("[UI] minimized")

    def restore_from_tray(self):
        # tray callback is not Tk main thread
        self.after(0, self._restore_ui)

    def _restore_ui(self):
        try:
            self.deiconify()

            st = getattr(self, "_restore_state", "normal")
            if st not in ("zoomed", "normal"):
                st = "normal"
            self.state(st)

            self.lift()
            self.attributes("-topmost", True)
            self.attributes("-topmost", False)
            self.focus_force()
        except Exception:
            pass

    def exit_app(self):
        try:
            self.on_stop()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        self.destroy()

    # ---------- Config IO ----------
    def load_config(self) -> BridgeConfig:
        self.ui_lang = "zh"
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)

            self.ui_lang = (d.get("ui_lang") or "zh").lower()
            if self.ui_lang not in ("zh", "ja", "en"):
                self.ui_lang = "en"
            self.var_lang = tk.StringVar(value=self.ui_lang)

            if BRIDGE_FIELDS:
                bd = {k: v for k, v in d.items() if k in BRIDGE_FIELDS}
            else:
                bd = d
            return BridgeConfig(**bd)
        except Exception:
            self.ui_lang = "zh"
            return BridgeConfig()

    def collect_config(self) -> BridgeConfig:
        addrs = [self.lst_addr.get(i).strip() for i in range(self.lst_addr.size()) if self.lst_addr.get(i).strip()]
        blocks = [self.lst_block.get(i).strip() for i in range(self.lst_block.size()) if self.lst_block.get(i).strip()]

        code_regex = getattr(self.cfg, "code_regex", r"\b\d{4,8}\b")
        code_prefix = getattr(self.cfg, "code_separate_prefix", "🔑 Code")

        return BridgeConfig(
            ble_addresses=addrs,
            auto_pick_heart_rate=False,

            enable_telegram=bool(self.var_tg_on.get()),
            telegram_bot_token=(self.var_tg_token.get() or "").strip(),
            telegram_chat_id=(self.var_tg_chat.get() or "").strip(),

            enable_email=bool(self.var_mail_on.get()),
            smtp_host=(self.var_smtp_host.get() or "").strip(),
            smtp_port=self.safe_int(self.var_smtp_port.get(), 587),
            smtp_user=(self.var_smtp_user.get() or "").strip(),
            smtp_pass=(self.var_smtp_pass.get() or "").strip(),
            email_to=(self.var_email_to.get() or "").strip(),
            email_from=(self.var_email_from.get() or "").strip(),

            dedup_seconds=self.safe_int(self.var_dedup.get(), 8),

            block_keywords=blocks,
            block_case_insensitive=bool(self.var_block_ci.get()),

            enable_code_highlight=bool(self.var_code_on.get()),
            code_send_separately=bool(self.var_code_sep.get()),
            code_regex=code_regex,
            code_separate_prefix=code_prefix,

            history_limit=self.safe_int(self.var_history_limit.get(), getattr(self.cfg, "history_limit", 300)),
            autostart_enabled=getattr(self.cfg, "autostart_enabled", False),
        )

    def save_config(self, cfg: BridgeConfig):
        data = dict(cfg.__dict__)
        data["ui_lang"] = self.ui_lang

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            back = json.load(f)

        tok = (back.get("telegram_bot_token") or "")
        messagebox.showinfo(
            t(self.ui_lang, "msg_saved_title"),
            t(self.ui_lang, "msg_saved_body").format(path=os.path.abspath(CONFIG_PATH), prefix=tok[:12]),
        )

    @staticmethod
    def safe_int(v, default=0):
        try:
            return int(str(v).strip())
        except Exception:
            return default

    # ---------- Log pump ----------
    def _flush_logs(self):
        try:
            while True:
                s = self.log_q.get_nowait()
                self.txt_logs.insert("end", s + "\n")
                self.txt_logs.see("end")
        except queue.Empty:
            pass
        self.after(120, self._flush_logs)


def asyncio_run(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return loop.run_until_complete(coro)
    except RuntimeError:
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()


if __name__ == "__main__":
    App().mainloop()