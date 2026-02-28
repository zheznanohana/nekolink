# tray_helper.py
# -*- coding: utf-8 -*-
import threading
import os
from PIL import Image
import pystray


class TrayController:
    def __init__(self, title, on_restore, on_exit, icon_path=None):
        self.title = title
        self.on_restore = on_restore
        self.on_exit = on_exit
        self.icon_path = icon_path

        self.icon = None
        self.thread = None

    # ----------------------------
    # Public API
    # ----------------------------

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass

    # ----------------------------
    # Internal
    # ----------------------------

    def _run(self):
        image = self._load_icon()

        menu = pystray.Menu(
            pystray.MenuItem("Restore", self._restore),
            pystray.MenuItem("Exit", self._exit)
        )

        self.icon = pystray.Icon(
            self.title,
            image,
            self.title,
            menu
        )

        # 关键：用默认 run，不搞私有 listener
        self.icon.run()

    def _restore(self, icon, item):
        try:
            self.on_restore()
        except Exception:
            pass

    def _exit(self, icon, item):
        try:
            self.on_exit()
        finally:
            icon.stop()

    def _load_icon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            try:
                return Image.open(self.icon_path)
            except Exception:
                pass

        # fallback 简单图标
        from PIL import ImageDraw
        img = Image.new("RGB", (64, 64), color=(40, 120, 200))
        draw = ImageDraw.Draw(img)
        draw.text((20, 18), "N", fill="white")
        return img