# i18n.py
# Minimal i18n dictionary for zh / ja / en
# If a key is missing, it will fallback to English, then to the key itself.

STRINGS = {
    "zh": {
        "app_title": "NekoLink · iPhone 通知转发器（Windows）",
        "header_title": "iPhone → Windows → Telegram / Email",

        "running": "● 运行中",
        "stopped": "● 已停止",
        "unsaved": "● 未保存",

        "tab_main": "主页",
        "tab_devices": "设备",
        "tab_destinations": "转发",
        "tab_block": "屏蔽",
        "tab_history": "历史",
        "tab_logs": "日志",

        "btn_save": "保存",
        "btn_start": "开始",
        "btn_stop": "停止",
        "btn_scan": "扫描",
        "btn_add": "添加",
        "btn_remove_selected": "删除选中",
        "btn_test": "测试",
        "btn_clear": "清空",
        "btn_copy_selected": "复制选中",

        "lbl_language": "语言",
        "lbl_dedup": "去重(秒)",
        "lbl_history_limit": "历史条数上限",

        "chk_code_detect": "开启验证码识别",
        "chk_code_separate": "验证码单独推送",

        "lbl_latest_preview": "最新通知预览",
        "lbl_tip_tray": "提示：点 X 最小化；托盘右键 Exit 才退出。",
        "lbl_config_path": "配置文件：",

        "devices_title": "已选择设备地址（Heart Rate）",
        "devices_scan_hint": "扫描结果会显示在下面；双击一行可把地址填到输入框。",
        "devices_no_found": "未找到 Heart Rate 设备。",

        "dest_tg_enable": "启用 Telegram",
        "dest_tg_token": "Bot Token",
        "dest_tg_chat": "Chat ID",
        "dest_show_hide": "显示/隐藏",

        "dest_email_enable": "启用 Email",
        "dest_email_host": "Host",
        "dest_email_port": "Port",
        "dest_email_user": "User",
        "dest_email_pass": "Pass",
        "dest_email_from": "From",
        "dest_email_to": "To",

        "block_title": "屏蔽关键词：通知包含任意关键词就会被忽略",
        "block_case_insensitive": "忽略大小写",

        "history_title": "通知历史",
        "logs_title": "调试日志(精简)",

        "msg_saved_title": "已保存",
        "msg_saved_body": "已保存到：\n{path}\n\nToken 前缀：{prefix}",
        "msg_missing_title": "缺少配置",
        "msg_missing_tg": "请填写 Telegram Token 和 Chat ID",
        "msg_tg_ok": "Telegram 测试消息已发送",
        "msg_email_ok": "Email 测试消息已发送",
        "msg_no_devices": "请在 Devices 页添加至少一个设备地址，或先 Scan 再添加。",
        "msg_tg_invalid": "Telegram 已启用，但 Token 为空或仍是占位符。\n请在 Destinations 页填写后保存。\n\n当前前缀：{prefix}\n配置文件：{path}",
        "msg_copied": "已复制到剪贴板",
    },
    "ja": {
        "app_title": "NekoLink · iPhone通知転送（Windows）",
        "header_title": "iPhone → Windows → Telegram / Email",

        "running": "● 実行中",
        "stopped": "● 停止中",
        "unsaved": "● 未保存",

        "tab_main": "メイン",
        "tab_devices": "デバイス",
        "tab_destinations": "転送先",
        "tab_block": "除外",
        "tab_history": "履歴",
        "tab_logs": "ログ",

        "btn_save": "保存",
        "btn_start": "開始",
        "btn_stop": "停止",
        "btn_scan": "スキャン",
        "btn_add": "追加",
        "btn_remove_selected": "選択削除",
        "btn_test": "テスト",
        "btn_clear": "クリア",
        "btn_copy_selected": "選択コピー",

        "lbl_language": "言語",
        "lbl_dedup": "重複除外(秒)",
        "lbl_history_limit": "履歴上限",

        "chk_code_detect": "認証コード検出",
        "chk_code_separate": "コードを別送信",

        "lbl_latest_preview": "最新通知プレビュー",
        "lbl_tip_tray": "ヒント：Xで最小化。終了はトレイのExitから。",
        "lbl_config_path": "設定ファイル：",

        "devices_title": "選択済みアドレス（Heart Rate）",
        "devices_scan_hint": "結果は下に表示。行をダブルクリックでアドレスを入力欄へ。",
        "devices_no_found": "Heart Rate デバイスが見つかりません。",

        "dest_tg_enable": "Telegram を有効化",
        "dest_tg_token": "Botトークン",
        "dest_tg_chat": "Chat ID",
        "dest_show_hide": "表示/非表示",

        "dest_email_enable": "Email を有効化",
        "dest_email_host": "Host",
        "dest_email_port": "Port",
        "dest_email_user": "User",
        "dest_email_pass": "Pass",
        "dest_email_from": "From",
        "dest_email_to": "To",

        "block_title": "キーワード除外：含まれる通知は無視します",
        "block_case_insensitive": "大文字小文字を区別しない",

        "history_title": "通知履歴",
        "logs_title": "デバッグログ(簡易)",

        "msg_saved_title": "保存完了",
        "msg_saved_body": "保存先：\n{path}\n\nToken prefix：{prefix}",
        "msg_missing_title": "設定不足",
        "msg_missing_tg": "Telegram Token と Chat ID を入力してください",
        "msg_tg_ok": "Telegram テスト送信OK",
        "msg_email_ok": "Email テスト送信OK",
        "msg_no_devices": "Devices でアドレスを追加するか、Scan してから追加してください。",
        "msg_tg_invalid": "Telegram が有効ですが、Token が空または占位です。\nDestinationsで入力して保存してください。\n\nprefix：{prefix}\n設定：{path}",
        "msg_copied": "クリップボードにコピーしました",
    },
    "en": {
        "app_title": "NekoLink · iPhone Notification Forwarder (Windows)",
        "header_title": "iPhone → Windows → Telegram / Email",

        "running": "● Running",
        "stopped": "● Stopped",
        "unsaved": "● Unsaved",

        "tab_main": "Main",
        "tab_devices": "Devices",
        "tab_destinations": "Destinations",
        "tab_block": "Block",
        "tab_history": "History",
        "tab_logs": "Logs",

        "btn_save": "Save",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "btn_scan": "Scan",
        "btn_add": "Add",
        "btn_remove_selected": "Remove selected",
        "btn_test": "Test",
        "btn_clear": "Clear",
        "btn_copy_selected": "Copy selected",

        "lbl_language": "Language",
        "lbl_dedup": "Dedup (sec)",
        "lbl_history_limit": "History limit",

        "chk_code_detect": "Enable code detection",
        "chk_code_separate": "Send code separately",

        "lbl_latest_preview": "Latest notification preview",
        "lbl_tip_tray": "Tip: Click X to minimize. Exit only from tray menu.",
        "lbl_config_path": "Config file:",

        "devices_title": "Selected BLE addresses (Heart Rate)",
        "devices_scan_hint": "Scan results appear below. Double-click a line to fill the address input.",
        "devices_no_found": "No Heart Rate devices found.",

        "dest_tg_enable": "Enable Telegram",
        "dest_tg_token": "Bot Token",
        "dest_tg_chat": "Chat ID",
        "dest_show_hide": "Show/Hide",

        "dest_email_enable": "Enable Email",
        "dest_email_host": "Host",
        "dest_email_port": "Port",
        "dest_email_user": "User",
        "dest_email_pass": "Pass",
        "dest_email_from": "From",
        "dest_email_to": "To",

        "block_title": "Block keywords: notifications containing any keyword will be ignored",
        "block_case_insensitive": "Case-insensitive",

        "history_title": "Notification History",
        "logs_title": "Compact logs (debug)",

        "msg_saved_title": "Saved",
        "msg_saved_body": "Saved to:\n{path}\n\nToken prefix: {prefix}",
        "msg_missing_title": "Missing",
        "msg_missing_tg": "Fill Telegram token & chat_id",
        "msg_tg_ok": "Telegram test sent",
        "msg_email_ok": "Email test sent",
        "msg_no_devices": "Add at least one address in Devices tab, or Scan then Add.",
        "msg_tg_invalid": "Telegram is enabled but token is empty or placeholder.\nFill it in Destinations and save.\n\nprefix: {prefix}\nconfig: {path}",
        "msg_copied": "Copied to clipboard",
    }
}


def t(lang: str, key: str) -> str:
    lang = (lang or "en").lower()
    if lang not in STRINGS:
        lang = "en"
    return STRINGS[lang].get(key, STRINGS["en"].get(key, key))