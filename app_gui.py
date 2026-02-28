# app_gui.py
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox
from ttkbootstrap.scrolled import ScrolledFrame
import ttkbootstrap as tb
from ttkbootstrap.constants import *

import i18n
from ancs_bridge import (
    BridgeConfig,
    BridgeManager,
    get_config_path,
    load_config,
    save_config,
    send_dingtalk_text,
    send_email,
    send_telegram,
    send_gotify,
)
from tray_helper import TrayController

CONFIG_PATH = get_config_path()
ICON_PATH = "icon.ico"


class App(tb.Window):
    def __init__(self):
        super().__init__(themename="flatly")

        self.log_q = queue.Queue()
        self.cfg = load_config(CONFIG_PATH)

        # i18n
        i18n.set_lang(getattr(self.cfg, "ui_lang", "zh"))

        self.title(i18n.t("app_title"))
        self.geometry("1100x720")
        self.minsize(980, 620)

        self.manager = BridgeManager(self.cfg, self.log, self.on_notification)
        self.running = False
        self.history = []  # list of payload dict

        icon_path = ICON_PATH if os.path.exists(ICON_PATH) else None
        self.tray = TrayController(
            title="NekoLink",
            on_restore=self.restore_from_tray,
            on_exit=self.exit_app,
            icon_path=icon_path,
        )
        self.tray.start()

        self.ui = {}  # widgets needing i18n refresh

        self._build_ui()
        self.apply_i18n()

        self._flush_logs()

        # close -> tray
        self.protocol("WM_DELETE_WINDOW", self.on_close_to_tray)

    # ---------- UI ----------
    def _build_ui(self):
        root = tb.Frame(self, padding=10)
        root.pack(fill=BOTH, expand=True)

        header = tb.Frame(root)
        header.pack(fill=X)

        self.ui["lbl_header"] = tb.Label(header, text="", font=("Segoe UI", 16, "bold"))
        self.ui["lbl_header"].pack(side=LEFT)

        # language selector (right)
        lang_frame = tb.Frame(header)
        lang_frame.pack(side=RIGHT, padx=(10, 0))

        self.ui["lbl_lang"] = tb.Label(lang_frame, text="Lang")
        self.ui["lbl_lang"].pack(side=LEFT, padx=(0, 6))

        self.var_lang = tk.StringVar(value=i18n.lang_label(i18n.get_lang()))
        self.cmb_lang = tb.Combobox(
            lang_frame,
            width=10,
            textvariable=self.var_lang,
            values=[i18n.lang_label("zh"), i18n.lang_label("en"), i18n.lang_label("ja")],
            state="readonly",
        )
        self.cmb_lang.pack(side=LEFT)

        def on_lang_change(_evt=None):
            label = self.var_lang.get().strip()
            code = "zh"
            for k, v in i18n.LANG_LABEL.items():
                if v == label:
                    code = k
                    break
            i18n.set_lang(code)
            self.cfg.ui_lang = code
            save_config(CONFIG_PATH, self.cfg)
            self.apply_i18n()

        self.cmb_lang.bind("<<ComboboxSelected>>", on_lang_change)

        # status + config path
        self.ui["lbl_status"] = tb.Label(header, text="", bootstyle="danger")
        self.ui["lbl_status"].pack(side=RIGHT)

        self.ui["lbl_cfg"] = tb.Label(header, text="", bootstyle="secondary")
        self.ui["lbl_cfg"].pack(side=RIGHT, padx=(0, 12))

        # notebook
        self.nb = tb.Notebook(root)
        self.nb.pack(fill=BOTH, expand=True, pady=(10, 0))

        self.tab_main = tb.Frame(self.nb)
        self.tab_devices = tb.Frame(self.nb)
        self.tab_dest = tb.Frame(self.nb)
        self.tab_filter = tb.Frame(self.nb)
        self.tab_misc = tb.Frame(self.nb)
        self.tab_history = tb.Frame(self.nb)
        self.tab_logs = tb.Frame(self.nb)

        self.nb.add(self.tab_main, text="Main")
        self.nb.add(self.tab_devices, text="Devices")
        self.nb.add(self.tab_dest, text="Destinations")
        self.nb.add(self.tab_filter, text="Block Keywords")
        self.nb.add(self.tab_misc, text="Misc")
        self.nb.add(self.tab_history, text="History")
        self.nb.add(self.tab_logs, text="Logs")

        self._build_main()
        self._build_devices()
        self._build_dest()     # ✅ scroll + bottom save
        self._build_filter()
        self._build_misc()
        self._build_history()
        self._build_logs()

    def apply_i18n(self):
        self.title(i18n.t("app_title"))
        self.ui["lbl_header"].config(text=i18n.t("header_line"))
        self.ui["lbl_cfg"].config(text=f"{i18n.t('config_path')}: {CONFIG_PATH}")

        if self.running:
            self.ui["lbl_status"].config(text=i18n.t("status_running"), bootstyle="success")
        else:
            self.ui["lbl_status"].config(text=i18n.t("status_stopped"), bootstyle="danger")

        self.nb.tab(self.tab_main, text=i18n.t("tab_main"))
        self.nb.tab(self.tab_devices, text=i18n.t("tab_devices"))
        self.nb.tab(self.tab_dest, text=i18n.t("tab_dest"))
        self.nb.tab(self.tab_filter, text=i18n.t("tab_filter"))
        self.nb.tab(self.tab_misc, text=i18n.t("tab_misc"))
        self.nb.tab(self.tab_history, text=i18n.t("tab_history"))
        self.nb.tab(self.tab_logs, text=i18n.t("tab_logs"))

        # main
        self.ui["lbl_run_control"].config(text=i18n.t("run_control"))
        self.ui["btn_save_all"].config(text=i18n.t("save_all"))
        self.ui["btn_start"].config(text=i18n.t("start"))
        self.ui["btn_stop"].config(text=i18n.t("stop"))
        self.ui["lbl_dedup"].config(text=i18n.t("dedup_sec"))
        self.ui["chk_code_on"].config(text=i18n.t("enable_code_detect"))
        self.ui["chk_code_sep"].config(text=i18n.t("send_code_sep"))
        self.ui["lbl_history_limit"].config(text=i18n.t("history_limit"))
        self.ui["lbl_preview"].config(text=i18n.t("latest_preview"))
        self.ui["lbl_tip_tray"].config(text=i18n.t("tip_tray"))

        # devices
        self.ui["lbl_devices_title"].config(text=i18n.t("selected_ble"))
        self.ui["btn_scan"].config(text=i18n.t("scan"))
        self.ui["btn_add_addr"].config(text=i18n.t("add"))
        self.ui["btn_remove_addr"].config(text=i18n.t("remove_selected"))
        self.ui["txt_scan_hint"].config(text=i18n.t("scan_hint"))
        self.ui["btn_save_devices"].config(text=i18n.t("save"))

        # filter
        self.ui["lbl_block_intro"].config(text=i18n.t("block_intro"))
        self.ui["chk_block_ci"].config(text=i18n.t("case_insensitive"))
        self.ui["btn_add_block"].config(text=i18n.t("add"))
        self.ui["btn_remove_block"].config(text=i18n.t("remove_selected"))
        self.ui["btn_save_filter"].config(text=i18n.t("save"))

        # misc
        self.ui["lbl_misc_title"].config(text=i18n.t("misc_title"))
        self.ui["chk_battery"].config(text=i18n.t("misc_battery"))
        self.ui["chk_toast"].config(text=i18n.t("misc_toast"))
        self.ui["btn_save_misc"].config(text=i18n.t("save"))

        # history/logs
        self.ui["lbl_history_title"].config(text=i18n.t("history_title"))
        self.ui["btn_clear_history"].config(text=i18n.t("clear"))
        self.ui["btn_copy_history"].config(text=i18n.t("copy_selected"))
        self.ui["lbl_logs_title"].config(text=i18n.t("tab_logs"))
        self.ui["btn_clear_logs"].config(text=i18n.t("clear"))

        # destinations bottom save
        if "btn_save_dest" in self.ui:
            self.ui["btn_save_dest"].config(text=i18n.t("save"))

    # ---------- Tabs ----------
    def _build_main(self):
        frm = tb.Frame(self.tab_main, padding=12)
        frm.pack(fill=BOTH, expand=True)

        left = tb.Frame(frm)
        left.pack(side=LEFT, fill=Y, padx=(0, 16))

        self.ui["lbl_run_control"] = tb.Label(left, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_run_control"].pack(anchor=W, pady=(0, 8))

        btns = tb.Frame(left)
        btns.pack(anchor=W, pady=(0, 8))

        self.ui["btn_save_all"] = tb.Button(btns, text="", bootstyle="secondary", command=self.on_save)
        self.ui["btn_save_all"].pack(side=LEFT, padx=(0, 8))
        self.ui["btn_start"] = tb.Button(btns, text="", bootstyle="success", command=self.on_start)
        self.ui["btn_start"].pack(side=LEFT, padx=(0, 8))
        self.ui["btn_stop"] = tb.Button(btns, text="", bootstyle="danger", command=self.on_stop)
        self.ui["btn_stop"].pack(side=LEFT)

        tb.Separator(left).pack(fill=X, pady=10)

        self.var_dedup = tk.StringVar(value=str(getattr(self.cfg, "dedup_seconds", 8)))
        self.ui["lbl_dedup"] = tb.Label(left, text="")
        self.ui["lbl_dedup"].pack(anchor=W)
        tb.Entry(left, textvariable=self.var_dedup, width=10).pack(anchor=W, pady=(0, 10))

        self.var_code_on = tk.BooleanVar(value=self.cfg.enable_code_highlight)
        self.var_code_sep = tk.BooleanVar(value=self.cfg.code_send_separately)
        self.ui["chk_code_on"] = tb.Checkbutton(left, text="", variable=self.var_code_on, bootstyle="round-toggle")
        self.ui["chk_code_on"].pack(anchor=W, pady=(0, 6))
        self.ui["chk_code_sep"] = tb.Checkbutton(left, text="", variable=self.var_code_sep, bootstyle="round-toggle")
        self.ui["chk_code_sep"].pack(anchor=W)

        self.var_history_limit = tk.StringVar(value=str(self.cfg.history_limit))
        self.ui["lbl_history_limit"] = tb.Label(left, text="")
        self.ui["lbl_history_limit"].pack(anchor=W, pady=(10, 0))
        tb.Entry(left, textvariable=self.var_history_limit, width=10).pack(anchor=W)

        right = tb.Frame(frm)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        self.ui["lbl_preview"] = tb.Label(right, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_preview"].pack(anchor=W)

        self.preview = tk.Text(right, height=9, wrap="word")
        self.preview.pack(fill=X, pady=(8, 8))
        self.preview.insert("end", "（暂无）\n")

        self.ui["lbl_tip_tray"] = tb.Label(right, text="")
        self.ui["lbl_tip_tray"].pack(anchor=W)

    def _build_devices(self):
        frm = tb.Frame(self.tab_devices, padding=12)
        frm.pack(fill=BOTH, expand=True)

        top = tb.Frame(frm)
        top.pack(fill=X, pady=(0, 10))

        self.ui["lbl_devices_title"] = tb.Label(top, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_devices_title"].pack(side=LEFT)

        self.ui["btn_scan"] = tb.Button(top, text="", bootstyle="info", command=self.scan_devices)
        self.ui["btn_scan"].pack(side=RIGHT)

        self.lst_addr = tk.Listbox(frm, height=10)
        self.lst_addr.pack(fill=X, pady=(0, 10))
        for a in (self.cfg.ble_addresses or []):
            self.lst_addr.insert("end", a)

        ctl = tb.Frame(frm)
        ctl.pack(fill=X)

        self.var_add_addr = tk.StringVar()
        tb.Entry(ctl, textvariable=self.var_add_addr, width=40).pack(side=LEFT, padx=(0, 8))
        self.ui["btn_add_addr"] = tb.Button(ctl, text="", bootstyle="secondary", command=self.add_addr)
        self.ui["btn_add_addr"].pack(side=LEFT, padx=(0, 8))
        self.ui["btn_remove_addr"] = tb.Button(ctl, text="", bootstyle="warning", command=self.remove_selected_addr)
        self.ui["btn_remove_addr"].pack(side=LEFT)

        tb.Separator(frm).pack(fill=X, pady=12)

        self.ui["txt_scan_hint"] = tb.Label(frm, text="", bootstyle="secondary")
        self.ui["txt_scan_hint"].pack(anchor=W, pady=(0, 6))

        self.scan_box = tk.Text(frm, height=10, wrap="word")
        self.scan_box.pack(fill=BOTH, expand=True)
        self.scan_box.insert("end", "")

        def on_dbl_click(_evt):
            try:
                sel = self.scan_box.get("insert linestart", "insert lineend").strip()
                if "addr=" in sel:
                    addr = sel.split("addr=")[1].split()[0].strip()
                    self.var_add_addr.set(addr)
            except Exception:
                pass

        self.scan_box.bind("<Double-Button-1>", on_dbl_click)

        self.ui["btn_save_devices"] = tb.Button(frm, text="", bootstyle="primary", command=self.on_save)
        self.ui["btn_save_devices"].pack(anchor=SE, pady=(10, 0))

    # ✅ Destinations: scrollable + fixed bottom Save
    def _build_dest(self):
        outer = tb.Frame(self.tab_dest, padding=12)
        outer.pack(fill=BOTH, expand=True)

        # scroll area
        sc = ScrolledFrame(outer, autohide=True)
        sc.pack(fill=BOTH, expand=True)

        frm = sc

        # Telegram
        tg = tb.Labelframe(frm, text="Telegram", padding=10)
        tg.pack(fill=X, pady=(0, 12))

        self.var_tg_on = tk.BooleanVar(value=self.cfg.enable_telegram)
        self.var_tg_token = tk.StringVar(value=self.cfg.telegram_bot_token)
        self.var_tg_chat = tk.StringVar(value=self.cfg.telegram_chat_id)

        tb.Checkbutton(tg, text="Enable Telegram", variable=self.var_tg_on, bootstyle="round-toggle").grid(
            row=0, column=0, sticky=W, pady=(0, 6)
        )
        tb.Label(tg, text="Bot Token").grid(row=1, column=0, sticky=W)
        self.ent_tg_token = tb.Entry(tg, textvariable=self.var_tg_token, width=70, show="•")
        self.ent_tg_token.grid(row=1, column=1, sticky=W, pady=2)
        self._tg_token_hidden = True

        def toggle_tg_token():
            self._tg_token_hidden = not self._tg_token_hidden
            self.ent_tg_token.config(show=("•" if self._tg_token_hidden else ""))

        tb.Button(tg, text="👁", width=3, bootstyle="secondary", command=toggle_tg_token).grid(
            row=1, column=2, sticky=W, padx=(6, 0)
        )

        tb.Label(tg, text="Chat ID").grid(row=2, column=0, sticky=W)
        tb.Entry(tg, textvariable=self.var_tg_chat, width=30).grid(row=2, column=1, sticky=W, pady=2)
        tb.Button(tg, text="Test", bootstyle="success", command=self.test_telegram).grid(
            row=3, column=1, sticky=W, pady=(8, 0)
        )

        # DingTalk
        dt = tb.Labelframe(frm, text="DingTalk (Robot)", padding=10)
        dt.pack(fill=X, pady=(0, 12))

        self.var_dt_on = tk.BooleanVar(value=getattr(self.cfg, "enable_dingtalk", False))
        self.var_dt_webhook = tk.StringVar(value=getattr(self.cfg, "dingtalk_webhook", ""))
        self.var_dt_secret = tk.StringVar(value=getattr(self.cfg, "dingtalk_secret", ""))

        tb.Checkbutton(dt, text="Enable DingTalk", variable=self.var_dt_on, bootstyle="round-toggle").grid(
            row=0, column=0, sticky=W, pady=(0, 6)
        )
        tb.Label(dt, text="Webhook").grid(row=1, column=0, sticky=W)
        tb.Entry(dt, textvariable=self.var_dt_webhook, width=78).grid(row=1, column=1, sticky=W, pady=2)

        tb.Label(dt, text="Secret (sign)").grid(row=2, column=0, sticky=W)
        self.ent_dt_secret = tb.Entry(dt, textvariable=self.var_dt_secret, width=36, show="•")
        self.ent_dt_secret.grid(row=2, column=1, sticky=W, pady=2)
        self._dt_secret_hidden = True

        def toggle_dt_secret():
            self._dt_secret_hidden = not self._dt_secret_hidden
            self.ent_dt_secret.config(show=("•" if self._dt_secret_hidden else ""))

        tb.Button(dt, text="👁", width=3, bootstyle="secondary", command=toggle_dt_secret).grid(
            row=2, column=2, sticky=W, padx=(6, 0)
        )
        tb.Button(dt, text="Test", bootstyle="success", command=self.test_dingtalk).grid(
            row=3, column=1, sticky=W, pady=(8, 0)
        )

        # Gotify
        gf = tb.Labelframe(frm, text="Gotify", padding=10)
        gf.pack(fill=X, pady=(0, 12))

        self.var_gotify_on = tk.BooleanVar(value=getattr(self.cfg, "enable_gotify", False))
        self.var_gotify_url = tk.StringVar(value=getattr(self.cfg, "gotify_url", ""))
        self.var_gotify_token = tk.StringVar(value=getattr(self.cfg, "gotify_token", ""))
        self.var_gotify_prio = tk.StringVar(value=str(getattr(self.cfg, "gotify_priority", 5)))

        tb.Checkbutton(gf, text="Enable Gotify", variable=self.var_gotify_on, bootstyle="round-toggle").grid(
            row=0, column=0, sticky=W, pady=(0, 6)
        )
        tb.Label(gf, text="Server URL").grid(row=1, column=0, sticky=W)
        tb.Entry(gf, textvariable=self.var_gotify_url, width=60).grid(row=1, column=1, sticky=W, pady=2)

        tb.Label(gf, text="App Token").grid(row=2, column=0, sticky=W)
        self.ent_gotify_token = tb.Entry(gf, textvariable=self.var_gotify_token, width=36, show="•")
        self.ent_gotify_token.grid(row=2, column=1, sticky=W, pady=2)
        self._gotify_token_hidden = True

        def toggle_gotify_token():
            self._gotify_token_hidden = not self._gotify_token_hidden
            self.ent_gotify_token.config(show=("•" if self._gotify_token_hidden else ""))

        tb.Button(gf, text="👁", width=3, bootstyle="secondary", command=toggle_gotify_token).grid(
            row=2, column=2, sticky=W, padx=(6, 0)
        )

        tb.Label(gf, text="Priority").grid(row=3, column=0, sticky=W)
        tb.Entry(gf, textvariable=self.var_gotify_prio, width=8).grid(row=3, column=1, sticky=W, pady=2)
        tb.Button(gf, text="Test", bootstyle="success", command=self.test_gotify).grid(
            row=4, column=1, sticky=W, pady=(8, 0)
        )

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

        tb.Checkbutton(mail, text="Enable Email", variable=self.var_mail_on, bootstyle="round-toggle").grid(
            row=0, column=0, sticky=W, pady=(0, 6)
        )
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

        tb.Button(mail, text="👁", width=3, bootstyle="secondary", command=toggle_smtp_pass).grid(
            row=3, column=2, sticky=W, padx=(6, 0)
        )

        tb.Label(mail, text="From").grid(row=4, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_email_from, width=36).grid(row=4, column=1, sticky=W, pady=2)
        tb.Label(mail, text="To").grid(row=5, column=0, sticky=W)
        tb.Entry(mail, textvariable=self.var_email_to, width=36).grid(row=5, column=1, sticky=W, pady=2)
        tb.Button(mail, text="Test", bootstyle="success", command=self.test_email).grid(
            row=6, column=1, sticky=W, pady=(8, 0)
        )

        # bottom fixed bar
        bottom = tb.Frame(outer)
        bottom.pack(fill=X, pady=(10, 0))
        tb.Separator(bottom).pack(fill=X, pady=(0, 8))

        self.ui["btn_save_dest"] = tb.Button(bottom, text="", bootstyle="primary", command=self.on_save)
        self.ui["btn_save_dest"].pack(side=RIGHT)

    def _build_filter(self):
        frm = tb.Frame(self.tab_filter, padding=12)
        frm.pack(fill=BOTH, expand=True)

        self.ui["lbl_block_intro"] = tb.Label(frm, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_block_intro"].pack(anchor=W, pady=(0, 8))

        self.var_block_ci = tk.BooleanVar(value=self.cfg.block_case_insensitive)
        self.ui["chk_block_ci"] = tb.Checkbutton(frm, text="", variable=self.var_block_ci, bootstyle="round-toggle")
        self.ui["chk_block_ci"].pack(anchor=W, pady=(0, 10))

        self.lst_block = tk.Listbox(frm, height=10)
        self.lst_block.pack(fill=X, pady=(0, 10))
        for k in (self.cfg.block_keywords or []):
            self.lst_block.insert("end", k)

        ctl = tb.Frame(frm)
        ctl.pack(fill=X)

        self.var_block_input = tk.StringVar()
        tb.Entry(ctl, textvariable=self.var_block_input, width=40).pack(side=LEFT, padx=(0, 8))
        self.ui["btn_add_block"] = tb.Button(ctl, text="", bootstyle="secondary", command=self.add_block)
        self.ui["btn_add_block"].pack(side=LEFT, padx=(0, 8))
        self.ui["btn_remove_block"] = tb.Button(ctl, text="", bootstyle="warning", command=self.remove_block)
        self.ui["btn_remove_block"].pack(side=LEFT)

        self.ui["btn_save_filter"] = tb.Button(frm, text="", bootstyle="primary", command=self.on_save)
        self.ui["btn_save_filter"].pack(anchor=SE, pady=(10, 0))

    def _build_misc(self):
        frm = tb.Frame(self.tab_misc, padding=12)
        frm.pack(fill=BOTH, expand=True)

        self.ui["lbl_misc_title"] = tb.Label(frm, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_misc_title"].pack(anchor=W, pady=(0, 10))

        self.var_show_battery = tk.BooleanVar(value=getattr(self.cfg, "show_battery_in_message", True))
        self.var_win_toast = tk.BooleanVar(value=getattr(self.cfg, "enable_windows_toast", True))

        self.ui["chk_battery"] = tb.Checkbutton(frm, text="", variable=self.var_show_battery, bootstyle="round-toggle")
        self.ui["chk_battery"].pack(anchor=W, pady=(0, 10))
        self.ui["chk_toast"] = tb.Checkbutton(frm, text="", variable=self.var_win_toast, bootstyle="round-toggle")
        self.ui["chk_toast"].pack(anchor=W, pady=(0, 10))

        self.ui["btn_save_misc"] = tb.Button(frm, text="", bootstyle="primary", command=self.on_save)
        self.ui["btn_save_misc"].pack(anchor=SE, pady=(10, 0))

    def _build_history(self):
        frm = tb.Frame(self.tab_history, padding=12)
        frm.pack(fill=BOTH, expand=True)

        top = tb.Frame(frm)
        top.pack(fill=X, pady=(0, 8))

        self.ui["lbl_history_title"] = tb.Label(top, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_history_title"].pack(side=LEFT)

        self.ui["btn_clear_history"] = tb.Button(top, text="", bootstyle="warning", command=self.clear_history)
        self.ui["btn_clear_history"].pack(side=RIGHT, padx=(8, 0))
        self.ui["btn_copy_history"] = tb.Button(top, text="", bootstyle="secondary", command=self.copy_selected_history)
        self.ui["btn_copy_history"].pack(side=RIGHT)

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

        self.ui["lbl_logs_title"] = tb.Label(top, text="", font=("Segoe UI", 12, "bold"))
        self.ui["lbl_logs_title"].pack(side=LEFT)

        self.ui["btn_clear_logs"] = tb.Button(top, text="", bootstyle="warning", command=self.clear_logs)
        self.ui["btn_clear_logs"].pack(side=RIGHT)

        self.txt_logs = tk.Text(frm, wrap="word", height=10)
        self.txt_logs.pack(fill=BOTH, expand=True)
        self.txt_logs.insert("end", "Ready.\n")

    # ---------- Actions ----------
    def log(self, s: str):
        self.log_q.put(s)

    def on_notification(self, payload: dict):
        bat = payload.get("battery")
        bat_text = f"{bat}%" if isinstance(bat, int) else "--"

        preview_text = (
            f"Device: {payload.get('device')}\n"
            f"Battery: {bat_text}\n"
            f"App: {payload.get('app')}\n"
            f"Title: {payload.get('title')}\n"
            f"Msg: {payload.get('msg')}\n"
            f"Codes: {' '.join(payload.get('codes') or [])}\n"
            f"Date: {payload.get('date')}\n"
        )
        self.preview.delete("1.0", "end")
        self.preview.insert("end", preview_text)

        # history table
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(payload["ts"]))
        codes = " ".join(payload.get("codes") or [])
        self.tree.insert(
            "", "end",
            values=(t, payload.get("device", ""), bat_text, payload.get("app", ""),
                    payload.get("title", ""), payload.get("msg", ""), codes)
        )

        # prune
        limit = int(self.safe_int(self.var_history_limit.get(), default=self.cfg.history_limit))
        children = self.tree.get_children()
        if len(children) > max(50, limit):
            for iid in children[: len(children) - limit]:
                self.tree.delete(iid)

    def on_save(self):
        cfg = self.collect_config()
        save_config(CONFIG_PATH, cfg)
        self.cfg = cfg
        self.manager.cfg = cfg
        messagebox.showinfo(i18n.t("ok"), f"{i18n.t('saved_to')}\n{CONFIG_PATH}")

    def on_start(self):
        if self.running:
            return

        cfg = self.collect_config()
        save_config(CONFIG_PATH, cfg)
        self.cfg = cfg
        self.manager.cfg = cfg

        addrs = cfg.ble_addresses or []
        if not addrs:
            messagebox.showwarning(i18n.t("no_devices"), i18n.t("add_device_warn"))
            return

        self.running = True
        self.apply_i18n()
        self.manager.start_all(addrs)
        self.log("[UI] started")

    def on_stop(self):
        if not self.running:
            return
        self.running = False
        self.apply_i18n()
        self.manager.stop_all()
        self.log("[UI] stopped")

    def scan_devices(self):
        self.scan_box.delete("1.0", "end")
        self.scan_box.insert("end", "Scanning...\n")

        def _work():
            try:
                results = asyncio_run(self.manager.scan_heart_rate(timeout=8))
                if not results:
                    self.log("[SCAN] none")
                    self.scan_box.insert("end", "No devices found.\n")
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
        self.var_add_addr.set("")

    def remove_selected_addr(self):
        sel = list(self.lst_addr.curselection())
        sel.reverse()
        for idx in sel:
            self.lst_addr.delete(idx)

    def add_block(self):
        s = self.var_block_input.get().strip()
        if not s:
            return
        self.lst_block.insert("end", s)
        self.var_block_input.set("")

    def remove_block(self):
        sel = list(self.lst_block.curselection())
        sel.reverse()
        for idx in sel:
            self.lst_block.delete(idx)

    def clear_history(self):
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
        messagebox.showinfo(i18n.t("ok"), i18n.t("copied"))

    def clear_logs(self):
        self.txt_logs.delete("1.0", "end")

    # ---------- Tests ----------
    def test_telegram(self):
        token = self.var_tg_token.get().strip()
        chat_id = self.var_tg_chat.get().strip()
        if not token or not chat_id:
            messagebox.showwarning(i18n.t("missing"), "Fill Telegram token & chat_id")
            return
        try:
            send_telegram(token, chat_id, "✅ Telegram Test: NekoLink OK")
            messagebox.showinfo(i18n.t("ok"), "Telegram test sent")
        except Exception as e:
            messagebox.showerror(i18n.t("fail"), f"Telegram failed: {e}")

    def test_dingtalk(self):
        webhook = self.var_dt_webhook.get().strip()
        secret = self.var_dt_secret.get().strip()
        if not webhook:
            messagebox.showwarning(i18n.t("missing"), "Fill DingTalk webhook")
            return
        try:
            send_dingtalk_text(webhook, secret, "✅ DingTalk Test: NekoLink OK")
            messagebox.showinfo(i18n.t("ok"), "DingTalk test sent")
        except Exception as e:
            messagebox.showerror(i18n.t("fail"), f"DingTalk failed: {e}")

    def test_gotify(self):
        url = self.var_gotify_url.get().strip()
        token = self.var_gotify_token.get().strip()
        prio = self.safe_int(self.var_gotify_prio.get(), 5)
        if not url or not token:
            messagebox.showwarning(i18n.t("missing"), "Fill Gotify Server URL & App Token")
            return
        try:
            send_gotify(url, token, "NekoLink", "✅ Gotify Test: NekoLink OK", priority=prio)
            messagebox.showinfo(i18n.t("ok"), "Gotify test sent")
        except Exception as e:
            messagebox.showerror(i18n.t("fail"), f"Gotify failed: {e}")

    def test_email(self):
        cfg = self.collect_config()
        try:
            send_email(cfg, "NekoLink Email Test", "✅ Email Test: NekoLink OK")
            messagebox.showinfo(i18n.t("ok"), "Email test sent")
        except Exception as e:
            messagebox.showerror(i18n.t("fail"), f"Email failed: {e}")

    # ---------- Tray behavior ----------
    def on_close_to_tray(self):
        self.withdraw()
        self.log("[UI] minimized to tray")

    def restore_from_tray(self):
        try:
            self.deiconify()
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

        # ui lang
        label = self.var_lang.get().strip()
        ui_lang = "zh"
        for k, v in i18n.LANG_LABEL.items():
            if v == label:
                ui_lang = k
                break

        return BridgeConfig(
            ui_lang=ui_lang,

            ble_addresses=addrs,
            auto_pick_heart_rate=False,

            enable_telegram=bool(self.var_tg_on.get()),
            telegram_bot_token=self.var_tg_token.get().strip(),
            telegram_chat_id=self.var_tg_chat.get().strip(),

            enable_dingtalk=bool(self.var_dt_on.get()),
            dingtalk_webhook=self.var_dt_webhook.get().strip(),
            dingtalk_secret=self.var_dt_secret.get().strip(),

            enable_gotify=bool(self.var_gotify_on.get()),
            gotify_url=self.var_gotify_url.get().strip(),
            gotify_token=self.var_gotify_token.get().strip(),
            gotify_priority=self.safe_int(self.var_gotify_prio.get(), 5),

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