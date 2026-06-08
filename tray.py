import threading
from typing import Callable
from PIL import Image
import pystray
from pystray import MenuItem as Item, Menu


class TrayManager:
    def __init__(
        self,
        on_ping_now: Callable,
        on_settings: Callable,
        on_history:  Callable,
        on_toggle:   Callable,
        on_quit:     Callable,
        is_enabled:  Callable[[], bool],
    ):
        self._on_ping_now = on_ping_now
        self._on_settings = on_settings
        self._on_history  = on_history
        self._on_toggle   = on_toggle
        self._on_quit     = on_quit
        self._is_enabled  = is_enabled

        self._icon_active   = Image.open("./assets/icon.png").convert('RGB')
        self._icon_inactive = Image.open("./assets/icon-disabled.png").convert('RGB')

        self._icon: pystray.Icon = pystray.Icon(
            "KnowledgePing",
            self._icon_active,
            "KnowledgePing",
            menu=self._build_menu(),
        )


    def start(self) -> None:
        t = threading.Thread(target=self._icon.run, name="KPTray", daemon=True)
        t.start()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    def update_icon(self, enabled: bool) -> None:
        try:
            self._icon.icon  = self._icon_active if enabled else self._icon_inactive
            self._icon.title = "KnowledgePing" if enabled else "KnowledgePing (paused)"
        except Exception:
            pass


    def _build_menu(self) -> Menu:
        return Menu(
            Item("⚡  Ping Now",    lambda: self._on_ping_now()),
            Menu.SEPARATOR,
            Item(
                lambda _: "⏸  Pause Pings" if self._is_enabled() else "▶  Resume Pings",
                lambda: self._on_toggle(),
            ),
            Item("⚙️  Settings",    lambda: self._on_settings()),
            Item("📜  History",     lambda: self._on_history()),
            Menu.SEPARATOR,
            Item("✕  Quit",         lambda: self._on_quit()),
        )
