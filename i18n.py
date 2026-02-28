# i18n.py
# -*- coding: utf-8 -*-

LANG_DATA = {
    "zh": {
        "app_title": "NekoLink · iPhone 通知转发器（Windows）",
        "main": "主页",
        "devices": "设备",
        "dest": "转发目标",
        "filter": "屏蔽关键词",
        "misc": "杂项",
        "history": "历史",
        "logs": "日志",

        "save": "保存",
        "start": "开始",
        "stop": "停止",
        "running": "● 运行中",
        "stopped": "● 已停止",
        "ok": "成功",
        "fail": "失败",
        "missing": "缺少信息",
        "saved_to": "已保存到",
        "config_path": "配置路径",

        "scan": "扫描",
        "add": "添加",
        "remove_selected": "删除选中",
        "clear": "清空",
        "copy_selected": "复制选中",

        "tg_enable": "启用 Telegram",
        "tg_token": "Bot Token",
        "tg_chat": "Chat ID",
        "tg_test": "测试 Telegram",

        "dt_enable": "启用钉钉",
        "dt_webhook": "Webhook",
        "dt_secret": "Secret（加签）",
        "dt_test": "测试钉钉",

        "mail_enable": "启用邮件",
        "mail_test": "测试邮件",

        "misc_title": "杂项设置",
        "show_battery_in_msg": "每条消息带电量",
        "enable_windows_toast": "使用 Windows 通知通道",
        "toast_note": "提示：开启后，转发时会在右下角弹出系统通知。",

        "battery": "电量",
        "dedup": "去重（秒）",
        "enable_code": "启用验证码识别",
        "send_code_sep": "验证码单独推送",
        "history_limit": "历史条数",
        "preview": "最新通知预览",
        "tip_tray": "提示：点右上角关闭会最小化到托盘，退出请在托盘菜单中选择 Exit。",
    },
    "en": {
        "app_title": "NekoLink · iPhone Notification Forwarder (Windows)",
        "main": "Main",
        "devices": "Devices",
        "dest": "Destinations",
        "filter": "Filters",
        "misc": "Misc",
        "history": "History",
        "logs": "Logs",

        "save": "Save",
        "start": "Start",
        "stop": "Stop",
        "running": "● Running",
        "stopped": "● Stopped",
        "ok": "OK",
        "fail": "Fail",
        "missing": "Missing",
        "saved_to": "Saved to",
        "config_path": "Config Path",

        "scan": "Scan",
        "add": "Add",
        "remove_selected": "Remove selected",
        "clear": "Clear",
        "copy_selected": "Copy selected",

        "tg_enable": "Enable Telegram",
        "tg_token": "Bot Token",
        "tg_chat": "Chat ID",
        "tg_test": "Test Telegram",

        "dt_enable": "Enable DingTalk",
        "dt_webhook": "Webhook",
        "dt_secret": "Secret (signing)",
        "dt_test": "Test DingTalk",

        "mail_enable": "Enable Email",
        "mail_test": "Test Email",

        "misc_title": "Misc Settings",
        "show_battery_in_msg": "Include battery in every message",
        "enable_windows_toast": "Use Windows toast channel",
        "toast_note": "Note: When enabled, Windows toast will pop up on forwarding.",

        "battery": "Battery",
        "dedup": "Dedup (sec)",
        "enable_code": "Enable code detection",
        "send_code_sep": "Send code separately",
        "history_limit": "History limit",
        "preview": "Latest notification preview",
        "tip_tray": "Tip: Close button minimizes to tray. Exit from tray menu.",
    },
    "ja": {
        "app_title": "NekoLink · iPhone 通知転送（Windows）",
        "main": "メイン",
        "devices": "デバイス",
        "dest": "転送先",
        "filter": "フィルター",
        "misc": "その他",
        "history": "履歴",
        "logs": "ログ",

        "save": "保存",
        "start": "開始",
        "stop": "停止",
        "running": "● 実行中",
        "stopped": "● 停止中",
        "ok": "OK",
        "fail": "失敗",
        "missing": "未入力",
        "saved_to": "保存先",
        "config_path": "設定ファイル",

        "scan": "スキャン",
        "add": "追加",
        "remove_selected": "選択を削除",
        "clear": "クリア",
        "copy_selected": "選択をコピー",

        "tg_enable": "Telegram を有効化",
        "tg_token": "Bot Token",
        "tg_chat": "Chat ID",
        "tg_test": "Telegram テスト",

        "dt_enable": "DingTalk を有効化",
        "dt_webhook": "Webhook",
        "dt_secret": "Secret（署名）",
        "dt_test": "DingTalk テスト",

        "mail_enable": "メールを有効化",
        "mail_test": "メールテスト",

        "misc_title": "その他の設定",
        "show_battery_in_msg": "毎回メッセージに電池残量を付ける",
        "enable_windows_toast": "Windows 通知を使う",
        "toast_note": "有効にすると、転送時にWindows通知が表示されます。",

        "battery": "バッテリー",
        "dedup": "重複除外（秒）",
        "enable_code": "コード検出を有効化",
        "send_code_sep": "コードを別送",
        "history_limit": "履歴の上限",
        "preview": "最新通知プレビュー",
        "tip_tray": "ヒント：閉じるとトレイに最小化。終了はトレイメニューから。",
    },
}


class I18n:
    def __init__(self, lang: str = "zh"):
        self.lang = lang if lang in LANG_DATA else "zh"

    def set_lang(self, lang: str):
        self.lang = lang if lang in LANG_DATA else "zh"

    def t(self, key: str) -> str:
        # fallback: zh -> key
        return LANG_DATA.get(self.lang, {}).get(key) or LANG_DATA["zh"].get(key) or key