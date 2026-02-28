# win_toast.py
# -*- coding: utf-8 -*-
from __future__ import annotations


def show_toast(title: str, body: str, app_id: str = "NekoLink"):
    """
    Windows 10/11 Toast notification (WinRT).
    Note: If you want a perfect "App name + icon" source in Windows notification center,
    you will later bind an AUMID via a Start Menu shortcut / installer.
    For now, this is enough for functional toasts.
    """
    try:
        from winsdk.windows.ui.notifications import ToastNotificationManager, ToastNotification
        from winsdk.windows.data.xml.dom import XmlDocument
    except Exception:
        return

    toast_xml = f"""
    <toast>
      <visual>
        <binding template="ToastGeneric">
          <text>{_xml_escape(title)}</text>
          <text>{_xml_escape(body)}</text>
        </binding>
      </visual>
    </toast>
    """.strip()

    try:
        xml = XmlDocument()
        xml.load_xml(toast_xml)
        toast = ToastNotification(xml)
        notifier = ToastNotificationManager.create_toast_notifier(app_id)
        notifier.show(toast)
    except Exception:
        # never crash main app due to notification
        return


def _xml_escape(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )