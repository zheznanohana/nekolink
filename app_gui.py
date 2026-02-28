# app_gui.py
# -*- coding: utf-8 -*-
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as tb
from ttkbootstrap.constants import *

from ancs_bridge import (
    BridgeConfig,
    BridgeManager,
    get_config_path,
    load_config,
    save_config,
    send_dingtalk_text,
    send_email,
    send_telegram,
)
from tray_helper import TrayController
from i18n import I18n

CONFIG_PATH = get_config_path()
ICON_PATH = "icon.ico"


class App(tb.Window):
    def __init__(self):
        super().__init__(themename="flatly")
        self.i18n = I18n("zh")

        self.title(self.i18n.t("app_title"))
        self.geometry("1100x720")
        self.minsize(980, 620)

        self.log_q = queue.Queue()
        self.cfg: BridgeConfig = load_config(CONFIG_PATH)

        self.manager = BridgeManager(self.cfg, self.log, self.on_notification)
        self.running = False
        self.history = []

        # per-tab dirty
        self.dirty = {"devices": False, "filter": False, "dest": False, "misc": False}
        self._dirty_widgets = {}  # tab_key -> (dot_label, save_btn)

        # tray
        icon_path = ICON_PATH if os.path.exists(ICON_PATH) else None
        self.tray = TrayController(
            title="NekoLink",
            on_restore=self.restore_from_tray,
            on_exit=self.exit_app,
            icon_path=icon_path,
        )
        self.tray.start()

        self._build_ui()
        self._flush_logs()
        self.protocol("WM_DELETE_WINDOW", self.on_close_to_tray)

    # ---------- Dirty helpers ----------
    def mark_dirty(self, tab_key: str):
        if tab_key not in self.dirty:
            return
        self.dirty[tab_key] = True
        w = self._dirty_widgets.get(tab_key)
        if w:
            dot, _btn = w
            dot.configure(text="●", bootstyle="danger")
            dot.lift()

    def clear_dirty(self, tab_key: str):
        if tab_key not in self.dirty:
            return
        self.dirty[tab_key] = False
        w = self._dirty_widgets.get(tab_key)
        if w:
            dot, _btn = w
            dot.configure(text="", bootstyle="secondary")

    def add_tab_save_bar(self, parent, tab_key: str, save_func):
        bar = tb.Frame(parent)
        bar.place(relx=1.0, rely=1.0, anchor="se", x=-12, y=-12)

        dot = tb.Label(bar, text="", bootstyle="secondary", font=("Segoe UI", 14, "bold"))
        dot.pack(side=LEFT, padx=(0, 8))

        btn = tb.Button(bar, text=self.i18n.t("save"), bootstyle="primary", command=save_func)
        btn.pack(side=LEFT)

        self._dirty_widgets[tab_key] = (dot, btn)

    # ---------- Page save ----------
    def _save_any(self, tab_key: str):
        cfg = self.collect_config()
        save_config(CONFIG_PATH, cfg)
        self.cfg = cfg
        self.manager.cfg = cfg
        self.clear_dirty(tab_key)
        messagebox.showinfo(self.i18n.t("ok"), f"{self.i18n.t('saved_to')}\n{CONFIG_PATH}")

    def save_devices_tab(self):
        self._save_any("devices")

    def save_filter_tab(self):
        self._save_any("filter")

    def save_dest_tab(self):
        self._save_any("dest")

    def save_misc_tab(self):
        self._save_any("misc")

    # ---------- UI ----------
    def _build_ui(self):
        root = tb.Frame(self, padding=10)
        root.pack(fill=BOTH, expand=True)

        header = tb.Frame(root)
        header.pack(fill=X)

        self.lbl_title = tb.Label(header, text="iPhone → Windows → Telegram / DingTalk / Email", font=("Segoe UI", 16, "bold"))
        self.lbl_title.pack(side=LEFT)

        # language selector
        self.var_lang = tk.StringVar(value=self.i18n.lang)
        lang_box = tb.Combobox(header, textvariable=self.var_lang, values=["zh", "en", "ja"], width=6, state="readonly")
        lang_box.pack(side=RIGHT, padx=(8, 0))
        lang_box.bind("<<ComboboxSelected>>", lambda _e: self.on_change_lang())

        self.lbl_status = tb.Label(header, text=self.i18n.t("stopped"), bootstyle="danger")
        self.lbl_status.pack(side=RIGHT, padx=(8, 0))

        self.lbl_cfg = tb.Label(header, text=f"{self.i18n.t('config_path')}: {CONFIG_PATH}", bootstyle="secondary")
        self.lbl_cfg.pack(side=RIGHT)

        self.nb = tb.Notebook(root)
        self.nb.pack(fill=BOTH, expand=True, pady=(10, 0))

        self.tab_main = tb.Frame(self.nb)
        self.tab_devices = tb.Frame(self.nb)
        self.tab_dest = tb.Frame(self.nb)
        self.tab_filter = tb.Frame(self.nb)
        self.tab_misc = tb.Frame(self.nb)
        self.tab_history = tb.Frame(self.nb)
        self.tab_logs = tb.Frame(self.nb)

        self.nb.add(self.tab_main, text=self.i18n.t("main"))
        self.nb.add(self.tab_devices, text=self.i18n.t("devices"))
        self.nb.add(self.tab_dest, text=self.i18n.t("dest"))
        self.nb.add(self.tab_filter, text=self.i18n.t("filter"))
        self.nb.add(self.tab_misc, text=self.i18n.t("misc"))
        self.nb.add(self.tab_history, text=self.i18n.t("history"))
        self.nb.add(self.tab_logs, text=self.i18n.t("logs"))

        self._build_main()
        self._build_devices()
        self._build_dest()
        self._build_filter()
        self._build_misc()
        self._build_history()
        self._build_logs()

    def _build_main(self):
        frm = tb.Frame(self.tab_main, padding=12)
        frm.pack(fill=BOTH, expand=True)

        left = tb.Frame(frm)
        left.pack(side=LEFT, fill=Y, padx=(0, 16))

        tb.Label(left, text="Run Control", font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0, 8))

        btns = tb.Frame(left)
        btns.pack(anchor=W, pady=(0, 8))
        tb.Button(btns, text=self.i18n.t("save"), bootstyle="secondary", command=self.on_save).pack(side=LEFT, padx=(0, 8))
        tb.Button(btns, text=self.i18n.t("start"), bootstyle="success", command=self.on_start).pack(side=LEFT, padx=(0, 8))
        tb.Button(btns, text=self.i18n.t("stop"), bootstyle="danger", command=self.on_stop).pack(side=LEFT)

        tb.Separator(left).pack(fill=X, pady=10)

        self.var_dedup = tk.StringVar(value=str(getattr(self.cfg, "dedup_seconds", 8)))
        tb.Label(left, text=self.i18n.t("dedup")).pack(anchor=W)
        e = tb.Entry(left, textvariable=self.var_dedup, width=10)
        e.pack(anchor=W, pady=(0, 10))
        self.var_dedup.trace_add("write", lambda *_: None)

        self.var_code_on = tk.BooleanVar(value=self.cfg.enable_code_highlight)
        self.var_code_sep = tk.BooleanVar(value=self.cfg.code_send_separately)
        tb.Checkbutton(left, text=self.i18n.t("enable_code"), variable=self.var_code_on, bootstyle="round-toggle").pack(anchor=W, pady=(0, 6))
        tb.Checkbutton(left, text=self.i18n.t("send_code_sep"), variable=self.var_code_sep, bootstyle="round-toggle").pack(anchor=W)

        self.var_history_limit = tk.StringVar(value=str(self.cfg.history_limit))
        tb.Label(left, text=self.i18n.t("history_limit")).pack(anchor=W, pady=(10, 0))
        tb.Entry(left, textvariable=self.var_history_limit, width=10).pack(anchor=W)

        right = tb.Frame(frm)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        tb.Label(right, text=self.i18n.t("preview"), font=("Segoe UI", 12, "bold")).pack(anchor=W)
        self.preview = tk.Text(right, height=9, wrap="word")
        self.preview.pack(fill=X, pady=(8, 8))
        self.preview.insert("end", "（暂无）\n")

        tb.Label(right, text=self.i18n.t("tip_tray")).pack(anchor=W)

    def _build_devices(self):
        frm = tb.Frame(self.tab_devices, padding=12)
        frm.pack(fill=BOTH, expand=True)

        top = tb.Frame(frm)
        top.pack(fill=X, pady=(0, 10))

        tb.Label(top, text="Selected BLE addresses (Heart Rate devices)", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        tb.Button(top, text=self.i18n.t("scan"), bootstyle="info", command=self.scan_devices).pack(side=RIGHT)

        self.lst_addr = tk.Listbox(frm, height=10)
        self.lst_addr.pack(fill=X, pady=(0, 10))
        for a in (self.cfg.ble_addresses or []):
            self.lst_addr.insert("end", a)

        ctl = tb.Frame(frm)
        ctl.pack(fill=X)

        self.var_add_addr = tk.StringVar()
        tb.Entry(ctl, textvariable=self.var_add_addr, width=40).pack(side=LEFT, padx=(0, 8))
        tb.Button(ctl, text=self.i18n.t("add"), bootstyle="secondary", command=self.add_addr).pack(side=LEFT, padx=(0, 8))
        tb.Button(ctl, text=self.i18n.t("remove_selected"), bootstyle="warning", command=self.remove_selected_addr).pack(side=LEFT)

        tb.Separator(frm).pack(fill=X, pady=12)

        self.scan_box = tk.Text(frm, height=10, wrap="word")
        self.scan_box.pack(fill=BOTH, expand=True)
        self.scan_box.insert("end", "Scan results will appear here. Double-click an address to add.\n")

        def on_dbl_click(_evt):
            try:
                sel = self.scan_box.get("insert linestart", "insert lineend").strip()
                if "addr=" in sel:
                    addr = sel.split("addr=")[1].split()[0].strip()
                    self.var_add_addr.set(addr)
            except Exception:
                pass

        self.scan_box.bind("<Double-Button-1>", on_dbl_click)

        # per-page save
        self.add_tab_save_bar(frm, "devices", self.save_devices_tab)

    def _build_dest(self):
        frm = tb.Frame(self.tab_dest, padding=12)
        frm.pack(fill=BOTH, expand=True)

        # Telegram
        tg = tb.Labelframe(frm, text="Telegram", padding=10)
        tg.pack(fill=X, pady=(0, 12))

        self.var_tg_on = tk.BooleanVar(value=self.cfg.enable_telegram)
        self.var_tg_token = tk.StringVar(value=self.cfg.telegram_bot_token)
        self.var_tg_chat = tk.StringVar(value=self.cfg.telegram_chat_id)

        tb.Checkbutton(tg, text=self.i18n.t("tg_enable"), variable=self.var_tg_on, bootstyle="round-toggle").grid(row=0, column=0, sticky=W, pady=(0, 6))

        tb.Label(tg, text=self.i18n.t("tg_token")).grid(row=1, column=0, sticky=W)
        self.ent_tg_token = tb.Entry(tg, textvariable=self.var_tg_token, width=64, show="•")
        self.ent_tg_token.grid(row=1, column=1, sticky=W, pady=2)
        self._tg_token_hidden = True

        def toggle_tg_token():
            self._tg_token_hidden = not self._tg_token_hidden
            self.ent_tg_token.config(show=("•" if self._tg_token_hidden else ""))

        tb.Button(tg, text="👁", width=3, bootstyle="secondary", command=toggle_tg_token).grid(row=1, column=2, sticky=W, padx=(6, 0))

        tb.Label(tg, text=self.i18n.t("tg_chat")).grid(row=2, column=0, sticky=W)
        tb.Entry(tg, textvariable=self.var_tg_chat, width=30).grid(row=2, column=1, sticky=W, pady=2)
        tb.Button(tg, text=self.i18n.t("tg_test"), bootstyle="success", command=self.test_telegram).grid(row=3, column=1, sticky=W, pady=(8, 0))

        # DingTalk
        dt = tb.Labelframe(frm, text="DingTalk", padding=10)
        dt.pack(fill=X, pady=(0, 12))

        self.var_dt_on = tk.BooleanVar(value=getattr(self.cfg, "enable_dingtalk", False))
        self.var_dt_webhook = tk.StringVar(value=getattr(self.cfg, "dingtalk_webhook", ""))
        self.var_dt_secret = tk.StringVar(value=getattr(self.cfg, "dingtalk_secret", ""))

        tb.Checkbutton(dt, text=self.i18n.t("dt_enable"), variable=self.var_dt_on, bootstyle="round-toggle").grid(row=0, column=0, sticky=W, pady=(0, 6))
        tb.Label(dt, text=self.i18n.t("dt_webhook")).grid(row=1, column=0, sticky=W)
        tb.Entry(dt, textvariable=self.var_dt_webhook, width=78).grid(row=1, column=1, sticky=W, pady=2)

        tb.Label(dt, text=self.i18n.t("dt_secret")).grid(row=2, column=0, sticky=W)
        self.ent_dt_secret = tb.Entry(dt, textvariable=self.var_dt_secret, width=36, show="•")
        self.ent_dt_secret.grid(row=2, column=1, sticky=W, pady=2)
        self._dt_secret_hidden = True

        def toggle_dt_secret():
            self._dt_secret_hidden = not self._dt_secret_hidden
            self.ent_dt_secret.config(show=("•" if self._dt_secret_hidden else ""))

        tb.Button(dt, text="👁", width=3, bootstyle="secondary", command=toggle_dt_secret).grid(row=2, column=2, sticky=W, padx=(6, 0))
        tb.Button(dt, text=self.i18n.t("dt_test"), bootstyle="success", command=self.test_dingtalk).grid(row=3, column=1, sticky=W, pady=(8, 0))

        # Email
        mail = tb.Labelframe(frm, text="Email (SMTP)", padding=10)
        mail.pack(fill=X)

        self.var_mail_on = tk.BooleanVar(value=self.cfg.enable_email)
        self.var_smtp_host = tk.StringVar(value=self.cfg.smtp_host)
        self.var_smtp_port = tk.StringVar(value=str(self.cfg.smtp_port))
        self.var_smtp_user = tk.StringVar(value=self.cfg.smtp_user)
        self.var_smtp_pass = tk.StringVar(value=self.cfg.smtp_pass)
        self.var_email_from = tk.StringVar(value=self.cfg.email_from)
        self.var_email_to = tk.StringVar(value=self.cfg.email_to)

        tb.Checkbutton(mail, text=self.i18n.t("mail_enable"), variable=self.var_mail_on, bootstyle="round-toggle").grid(row=0, column=0, sticky=W, pady=(0, 6))
        tb.Label(mail, text="Host").grid(row=1, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_host, width=36).grid(row=1, column=1, sticky=W, pady=2)
        tb.Label(mail, text="Port").grid(row=1, column=2, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_port, width=8).grid(row=1, column=3, sticky=W, pady=2)

        tb.Label(mail, text="User").grid(row=2, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_smtp_user, width=36).grid(row=2, column=1, sticky=W, pady=2)

        tb.Label(mail, text="Pass").grid(row=3, column=0, sticky=W)
        self.ent_smtp_pass = tb.Entry(mail, textvariable=self.var_smtp_pass, width=32, show="•")
        self.ent_smtp_pass.grid(row=3, column=1, sticky=W, pady=2)
        self._smtp_pass_hidden = True

        def toggle_smtp_pass():
            self._smtp_pass_hidden = not self._smtp_pass_hidden
            self.ent_smtp_pass.config(show=("•" if self._smtp_pass_hidden else ""))

        tb.Button(mail, text="👁", width=3, bootstyle="secondary", command=toggle_smtp_pass).grid(row=3, column=2, sticky=W, padx=(6, 0))

        tb.Label(mail, text="From").grid(row=4, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_email_from, width=36).grid(row=4, column=1, sticky=W, pady=2)
        tb.Label(mail, text="To").grid(row=5, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_email_to, width=36).grid(row=5, column=1, sticky=W, pady=2)

        tb.Button(mail, text=self.i18n.t("mail_test"), bootstyle="success", command=self.test_email).grid(row=6, column=1, sticky=W, pady=(8, 0))

        # mark dirty on edits
        def _bind_dirty(var):
            try:
                var.trace_add("write", lambda *_: self.mark_dirty("dest"))
            except Exception:
                pass

        for v in [
            self.var_tg_on, self.var_tg_token, self.var_tg_chat,
            self.var_dt_on, self.var_dt_webhook, self.var_dt_secret,
            self.var_mail_on, self.var_smtp_host, self.var_smtp_port,
            self.var_smtp_user, self.var_smtp_pass, self.var_email_from, self.var_email_to
        ]:
            _bind_dirty(v)

        # per-page save
        self.add_tab_save_bar(frm, "dest", self.save_dest_tab)

    def _build_filter(self):
        frm = tb.Frame(self.tab_filter, padding=12)
        frm.pack(fill=BOTH, expand=True)

        tb.Label(
            frm,
            text="Block keywords: if notification contains any of these, it will be ignored.",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=W, pady=(0, 8))

        self.var_block_ci = tk.BooleanVar(value=self.cfg.block_case_insensitive)
        tb.Checkbutton(frm, text="Case-insensitive match", variable=self.var_block_ci, bootstyle="round-toggle").pack(anchor=W, pady=(0, 10))
        self.var_block_ci.trace_add("write", lambda *_: self.mark_dirty("filter"))

        self.lst_block = tk.Listbox(frm, height=10)
        self.lst_block.pack(fill=X, pady=(0, 10))
        for k in (self.cfg.block_keywords or []):
            self.lst_block.insert("end", k)

        ctl = tb.Frame(frm)
        ctl.pack(fill=X)

        self.var_block_input = tk.StringVar()
        tb.Entry(ctl, textvariable=self.var_block_input, width=40).pack(side=LEFT, padx=(0, 8))
        tb.Button(ctl, text=self.i18n.t("add"), bootstyle="secondary", command=self.add_block).pack(side=LEFT, padx=(0, 8))
        tb.Button(ctl, text=self.i18n.t("remove_selected"), bootstyle="warning", command=self.remove_block).pack(side=LEFT)

        # per-page save
        self.add_tab_save_bar(frm, "filter", self.save_filter_tab)

    def _build_misc(self):
        frm = tb.Frame(self.tab_misc, padding=12)
        frm.pack(fill=BOTH, expand=True)

        tb.Label(frm, text=self.i18n.t("misc_title"), font=("Segoe UI", 12, "bold")).pack(anchor=W, pady=(0, 10))

        self.var_show_battery = tk.BooleanVar(value=getattr(self.cfg, "show_battery_in_message", True))
        self.var_win_toast = tk.BooleanVar(value=getattr(self.cfg, "enable_windows_toast", True))

        tb.Checkbutton(frm, text=self.i18n.t("show_battery_in_msg"), variable=self.var_show_battery, bootstyle="round-toggle").pack(anchor=W, pady=(0, 10))
        tb.Checkbutton(frm, text=self.i18n.t("enable_windows_toast"), variable=self.var_win_toast, bootstyle="round-toggle").pack(anchor=W, pady=(0, 10))
        tb.Label(frm, text=self.i18n.t("toast_note")).pack(anchor=W, pady=(10, 0))

        self.var_show_battery.trace_add("write", lambda *_: self.mark_dirty("misc"))
        self.var_win_toast.trace_add("write", lambda *_: self.mark_dirty("misc"))

        # per-page save
        self.add_tab_save_bar(frm, "misc", self.save_misc_tab)

    def _build_history(self):
        frm = tb.Frame(self.tab_history, padding=12)
        frm.pack(fill=BOTH, expand=True)

        top = tb.Frame(frm)
        top.pack(fill=X, pady=(0, 8))
        tb.Label(top, text="Notification History", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        tb.Button(top, text=self.i18n.t("clear"), bootstyle="warning", command=self.clear_history).pack(side=RIGHT, padx=(8, 0))
        tb.Button(top, text=self.i18n.t("copy_selected"), bootstyle="secondary", command=self.copy_selected_history).pack(side=RIGHT)

        cols = ("time", "device", "battery", "app", "title", "msg", "codes")
        self.tree = tb.Treeview(frm, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c)
        self.tree.column("time", width=150, anchor=W)
        self.tree.column("device", width=150, anchor=W)
        self.tree.column("battery", width=80, anchor=W)
        self.tree.column("app", width=220, anchor=W)
        self.tree.column("title", width=220, anchor=W)
        self.tree.column("msg", width=320, anchor=W)
        self.tree.column("codes", width=140, anchor=W)
        self.tree.pack(fill=BOTH, expand=True)

    def _build_logs(self):
        frm = tb.Frame(self.tab_logs, padding=12)
        frm.pack(fill=BOTH, expand=True)

        top = tb.Frame(frm)
        top.pack(fill=X, pady=(0, 8))
        tb.Label(top, text="Compact logs (debug)", font=("Segoe UI", 12, "bold")).pack(side=LEFT)
        tb.Button(top, text=self.i18n.t("clear"), bootstyle="warning", command=self.clear_logs).pack(side=RIGHT)

        self.txt_logs = tk.Text(frm, wrap="word", height=10)
        self.txt_logs.pack(fill=BOTH, expand=True)
        self.txt_logs.insert("end", "Ready.\n")

    # ---------- Actions ----------
    def log(self, s: str):
        self.log_q.put(s)

    def on_notification(self, payload: dict):
        bat = payload.get("battery")
        bat_text = f"{bat}%" if isinstance(bat, int) else "--"

        preview_lines = [
            f"Device: {payload.get('device')}",
            f"{self.i18n.t('battery')}: {bat_text}",
            f"App: {payload.get('app')}",
            f"Title: {payload.get('title')}",
            f"Msg: {payload.get('msg')}",
            f"Codes: {' '.join(payload.get('codes') or [])}",
        ]
        self.preview.delete("1.0", "end")
        self.preview.insert("end", "\n".join(preview_lines))

        self.history.append(payload)
        limit = int(self.safe_int(self.var_history_limit.get(), default=self.cfg.history_limit))
        if len(self.history) > max(50, limit):
            self.history = self.history[-limit:]

        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(payload["ts"]))
        codes = " ".join(payload.get("codes") or [])
        self.tree.insert("", "end", values=(
            t,
            payload.get("device", ""),
            bat_text,
            payload.get("app", ""),
            payload.get("title", ""),
            payload.get("msg", ""),
            codes
        ))

        children = self.tree.get_children()
        if len(children) > max(50, limit):
            for iid in children[: len(children) - limit]:
                self.tree.delete(iid)

    def on_save(self):
        cfg = self.collect_config()
        save_config(CONFIG_PATH, cfg)
        self.cfg = cfg
        self.manager.cfg = cfg
        # 主保存：顺带清所有页面 dirty
        for k in list(self.dirty.keys()):
            self.clear_dirty(k)
        messagebox.showinfo(self.i18n.t("ok"), f"{self.i18n.t('saved_to')}\n{CONFIG_PATH}")

    def on_start(self):
        if self.running:
            return
        cfg = self.collect_config()
        save_config(CONFIG_PATH, cfg)
        self.cfg = cfg
        self.manager.cfg = cfg

        addrs = cfg.ble_addresses or []
        if not addrs:
            messagebox.showwarning(self.i18n.t("missing"), "Add at least one address in Devices tab.")
            return

        self.running = True
        self.lbl_status.config(text=self.i18n.t("running"), bootstyle="success")
        self.manager.start_all(addrs)
        self.log("[UI] started")

    def on_stop(self):
        if not self.running:
            return
        self.running = False
        self.lbl_status.config(text=self.i18n.t("stopped"), bootstyle="danger")
        self.manager.stop_all()
        self.log("[UI] stopped")

    def scan_devices(self):
        self.scan_box.delete("1.0", "end")
        self.scan_box.insert("end", "Scanning...\n")

        def _work():
            try:
                results = asyncio_run(self.manager.scan_heart_rate(timeout=8))
                if not results:
                    self.scan_box.insert("end", "No Heart Rate devices found.\n")
                    return
                for name, addr, rssi in results:
                    self.scan_box.insert("end", f"{name} | addr={addr} | rssi={rssi}\n")
            except Exception as e:
                self.scan_box.insert("end", f"Scan error: {e}\n")

        threading.Thread(target=_work, daemon=True).start()

    def add_addr(self):
        addr = self.var_add_addr.get().strip()
        if not addr:
            return
        existing = [self.lst_addr.get(i) for i in range(self.lst_addr.size())]
        if addr not in existing:
            self.lst_addr.insert("end", addr)
            self.mark_dirty("devices")
        self.var_add_addr.set("")

    def remove_selected_addr(self):
        sel = list(self.lst_addr.curselection())
        sel.reverse()
        if not sel:
            return
        for idx in sel:
            self.lst_addr.delete(idx)
        self.mark_dirty("devices")

    def add_block(self):
        s = self.var_block_input.get().strip()
        if not s:
            return
        self.lst_block.insert("end", s)
        self.var_block_input.set("")
        self.mark_dirty("filter")

    def remove_block(self):
        sel = list(self.lst_block.curselection())
        sel.reverse()
        if not sel:
            return
        for idx in sel:
            self.lst_block.delete(idx)
        self.mark_dirty("filter")

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
        messagebox.showinfo(self.i18n.t("ok"), "Copied")

    def clear_logs(self):
        self.txt_logs.delete("1.0", "end")

    # ---------- Tests ----------
    def test_telegram(self):
        token = self.var_tg_token.get().strip()
        chat_id = self.var_tg_chat.get().strip()
        if not token or not chat_id:
            messagebox.showwarning(self.i18n.t("missing"), "Fill Telegram token & chat_id")
            return
        try:
            send_telegram(token, chat_id, "✅ Telegram Test: NekoLink OK")
            messagebox.showinfo(self.i18n.t("ok"), "Telegram test sent")
        except Exception as e:
            messagebox.showerror(self.i18n.t("fail"), f"Telegram failed: {e}")

    def test_dingtalk(self):
        webhook = self.var_dt_webhook.get().strip()
        secret = self.var_dt_secret.get().strip()
        if not webhook:
            messagebox.showwarning(self.i18n.t("missing"), "Fill DingTalk webhook")
            return
        try:
            send_dingtalk_text(webhook, secret, "✅ DingTalk Test: NekoLink OK")
            messagebox.showinfo(self.i18n.t("ok"), "DingTalk test sent")
        except Exception as e:
            messagebox.showerror(self.i18n.t("fail"), f"DingTalk failed: {e}")

    def test_email(self):
        cfg = self.collect_config()
        try:
            send_email(cfg, "NekoLink Email Test", "✅ Email Test: NekoLink OK")
            messagebox.showinfo(self.i18n.t("ok"), "Email test sent")
        except Exception as e:
            messagebox.showerror(self.i18n.t("fail"), f"Email failed: {e}")

    # ---------- Tray behavior ----------
    def on_close_to_tray(self):
        self.withdraw()
        self.log("[UI] minimized to tray")

    def restore_from_tray(self):
        try:
            self.deiconify()
            # 防止“最大化弹回/状态异常”
            try:
                self.state("normal")
            except Exception:
                pass
            self.lift()
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

    # ---------- Config ----------
    def collect_config(self) -> BridgeConfig:
        addrs = [self.lst_addr.get(i).strip() for i in range(self.lst_addr.size()) if self.lst_addr.get(i).strip()]
        blocks = [self.lst_block.get(i).strip() for i in range(self.lst_block.size()) if self.lst_block.get(i).strip()]

        return BridgeConfig(
            ble_addresses=addrs,
            auto_pick_heart_rate=False,

            enable_telegram=bool(self.var_tg_on.get()),
            telegram_bot_token=self.var_tg_token.get().strip(),
            telegram_chat_id=self.var_tg_chat.get().strip(),

            enable_dingtalk=bool(self.var_dt_on.get()),
            dingtalk_webhook=self.var_dt_webhook.get().strip(),
            dingtalk_secret=self.var_dt_secret.get().strip(),

            enable_email=bool(self.var_mail_on.get()),
            smtp_host=self.var_smtp_host.get().strip(),
            smtp_port=self.safe_int(self.var_smtp_port.get(), 587),
            smtp_user=self.var_smtp_user.get().strip(),
            smtp_pass=self.var_smtp_pass.get().strip(),
            email_to=self.var_email_to.get().strip(),
            email_from=self.var_email_from.get().strip(),

            dedup_seconds=self.safe_int(self.var_dedup.get(), 8),

            block_keywords=blocks,
            block_case_insensitive=bool(self.var_block_ci.get()),

            enable_code_highlight=bool(self.var_code_on.get()),
            code_send_separately=bool(self.var_code_sep.get()),
            code_regex=self.cfg.code_regex,
            code_separate_prefix=self.cfg.code_separate_prefix,

            history_limit=self.safe_int(self.var_history_limit.get(), self.cfg.history_limit),
            autostart_enabled=self.cfg.autostart_enabled,

            show_battery_in_message=bool(self.var_show_battery.get()),
            enable_windows_toast=bool(self.var_win_toast.get()),
        )

    @staticmethod
    def safe_int(v, default=0):
        try:
            return int(str(v).strip())
        except Exception:
            return default

    # ---------- i18n ----------
    def on_change_lang(self):
        lang = self.var_lang.get().strip()
        self.i18n.set_lang(lang)
        self.title(self.i18n.t("app_title"))

        self.nb.tab(self.tab_main, text=self.i18n.t("main"))
        self.nb.tab(self.tab_devices, text=self.i18n.t("devices"))
        self.nb.tab(self.tab_dest, text=self.i18n.t("dest"))
        self.nb.tab(self.tab_filter, text=self.i18n.t("filter"))
        self.nb.tab(self.tab_misc, text=self.i18n.t("misc"))
        self.nb.tab(self.tab_history, text=self.i18n.t("history"))
        self.nb.tab(self.tab_logs, text=self.i18n.t("logs"))

        self.lbl_cfg.config(text=f"{self.i18n.t('config_path')}: {CONFIG_PATH}")
        self.lbl_status.config(text=self.i18n.t("running") if self.running else self.i18n.t("stopped"))

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