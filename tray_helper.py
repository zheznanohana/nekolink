import threading
import pystray
from PIL import Image, ImageDraw

def _make_icon_image(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # simple round icon
    d.ellipse((8, 8, size-8, size-8), fill=(60, 130, 255, 255))
    d.text((size//2-10, size//2-12), "N", fill=(255,255,255,255))
    return img

class TrayController:
    """
    - close window -> hide to tray
    - tray menu -> restore / exit
    """
    def __init__(self, title: str, on_restore, on_exit):
        self.title = title
        self.on_restore = on_restore
        self.on_exit = on_exit

        self.icon = None
        self._thread = None

    def start(self):
        if self.icon:
            return
        image = _make_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Restore", lambda: self.on_restore()),
            pystray.MenuItem("Exit", lambda: self.on_exit()),
        )
        self.icon = pystray.Icon(self.title, image, self.title, menu)

        def _run():
            self.icon.run()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None