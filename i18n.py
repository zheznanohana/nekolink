# i18n.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict

SUPPORTED = ["zh", "en", "ja"]

LANG_LABEL = {
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
}

DICT: Dict[str, Dict[str, str]] = {
    "app_title": {
        "zh": "NekoLink · iPhone 通知转发器（Windows）",
        "en": "NekoLink · iPhone Notification Bridge (Windows)",
        "ja": "NekoLink · iPhone 通知ブリッジ（Windows）",
    },
    "header_line": {
        "zh": "iPhone → Windows → Telegram / 钉钉 / Gotify / 邮件",
        "en": "iPhone → Windows → Telegram / DingTalk / Gotify / Email",
        "ja": "iPhone → Windows → Telegram / DingTalk / Gotify / メール",
    },
    "status_stopped": {"zh": "● 已停止", "en": "● Stopped", "ja": "● 停止中"},
    "status_running": {"zh": "● 运行中", "en": "● Running", "ja": "● 実行中"},
    "config_path": {"zh": "配置", "en": "Config", "ja": "設定"},

    "tab_main": {"zh": "主页", "en": "Main", "ja": "メイン"},
    "tab_devices": {"zh": "设备", "en": "Devices", "ja": "デバイス"},
    "tab_dest": {"zh": "转发目标", "en": "Destinations", "ja": "転送先"},
    "tab_filter": {"zh": "屏蔽关键词", "en": "Block Keywords", "ja": "ブロック"},
    "tab_misc": {"zh": "杂项", "en": "Misc", "ja": "その他"},
    "tab_history": {"zh": "历史", "en": "History", "ja": "履歴"},
    "tab_logs": {"zh": "日志", "en": "Logs", "ja": "ログ"},

    "save": {"zh": "保存", "en": "Save", "ja": "保存"},
    "save_all": {"zh": "保存（全部）", "en": "Save (All)", "ja": "保存（全て）"},
    "start": {"zh": "启动", "en": "Start", "ja": "開始"},
    "stop": {"zh": "停止", "en": "Stop", "ja": "停止"},
    "scan": {"zh": "扫描", "en": "Scan", "ja": "スキャン"},
    "add": {"zh": "添加", "en": "Add", "ja": "追加"},
    "remove_selected": {"zh": "删除所选", "en": "Remove selected", "ja": "選択削除"},
    "clear": {"zh": "清空", "en": "Clear", "ja": "クリア"},
    "copy_selected": {"zh": "复制所选", "en": "Copy selected", "ja": "選択コピー"},

    "tip_tray": {
        "zh": "提示：点击关闭按钮会最小化到托盘。退出请在托盘菜单中操作。",
        "en": "Tip: Close button will minimize to tray. Exit from tray menu.",
        "ja": "ヒント：閉じるとトレイに最小化されます。終了はトレイメニューから。",
    },

    "run_control": {"zh": "运行控制", "en": "Run Control", "ja": "実行制御"},
    "dedup_sec": {"zh": "去重（秒）", "en": "Dedup (sec)", "ja": "重複排除(秒)"},
    "enable_code_detect": {"zh": "启用验证码识别", "en": "Enable code detect", "ja": "コード検出を有効化"},
    "send_code_sep": {"zh": "验证码单独发送", "en": "Send code separately", "ja": "コードを別送信"},
    "history_limit": {"zh": "历史条数上限", "en": "History limit", "ja": "履歴上限"},
    "latest_preview": {"zh": "最新通知预览", "en": "Latest notification preview", "ja": "最新通知プレビュー"},

    "selected_ble": {"zh": "已选择的 BLE 地址", "en": "Selected BLE addresses", "ja": "選択されたBLEアドレス"},
    "scan_hint": {
        "zh": "扫描结果会显示在这里。双击一行可填入地址输入框。",
        "en": "Scan results will appear here. Double-click a line to fill the address input.",
        "ja": "スキャン結果がここに表示されます。行をダブルクリックすると入力欄に反映します。",
    },

    "block_intro": {
        "zh": "屏蔽关键词：通知文本包含任意关键词就会被忽略。",
        "en": "Block keywords: if notification contains any of these, it will be ignored.",
        "ja": "ブロック語句：通知に含まれる場合は無視されます。",
    },
    "case_insensitive": {"zh": "忽略大小写", "en": "Case-insensitive match", "ja": "大文字小文字を無視"},

    "misc_title": {"zh": "杂项设置", "en": "Misc Settings", "ja": "その他設定"},
    "misc_battery": {
        "zh": "每条消息附带电量",
        "en": "Include battery in every message",
        "ja": "各メッセージにバッテリーを付与",
    },
    "misc_toast": {
        "zh": "使用 Windows 通知通道（Toast）",
        "en": "Use Windows toast channel",
        "ja": "Windowsトースト通知を使用",
    },

    "history_title": {"zh": "通知历史", "en": "Notification History", "ja": "通知履歴"},
    "copied": {"zh": "已复制到剪贴板", "en": "Copied to clipboard", "ja": "クリップボードにコピーしました"},
    "saved_to": {"zh": "已保存到：", "en": "Saved to:", "ja": "保存先:"},
    "missing": {"zh": "缺少信息", "en": "Missing", "ja": "未入力"},
    "ok": {"zh": "成功", "en": "OK", "ja": "OK"},
    "fail": {"zh": "失败", "en": "Fail", "ja": "失敗"},
    "no_devices": {"zh": "没有设备", "en": "No devices", "ja": "デバイスなし"},
    "add_device_warn": {
        "zh": "请先在 Devices 里添加至少一个地址，或先 Scan 再添加。",
        "en": "Add at least one address in Devices tab or Scan to add.",
        "ja": "Devicesでアドレスを追加するか、Scanで見つけて追加してください。",
    },
}

_current_lang = "zh"


def set_lang(lang: str):
    global _current_lang
    lang = (lang or "").strip().lower()
    if lang not in SUPPORTED:
        lang = "zh"
    _current_lang = lang


def get_lang() -> str:
    return _current_lang


def lang_label(lang: str) -> str:
    return LANG_LABEL.get(lang, lang)


def t(key: str, fallback: str | None = None) -> str:
    key = key or ""
    row = DICT.get(key)
    if not row:
        return fallback if fallback is not None else key
    return row.get(_current_lang) or row.get("en") or fallback or key