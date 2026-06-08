import threading
import time
from typing import Callable


class Scheduler:
    def __init__(self, interval_minutes: int, callback: Callable[[], None]):
        self.interval_minutes = interval_minutes
        self.callback = callback

        self._stop_event  = threading.Event()
        self._reset_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._reset_event.clear()
        self._thread = threading.Thread(target=self._run, name="KPScheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def reset_timer(self) -> None:
        self._reset_event.set()

    def update_interval(self, interval_minutes: int) -> None:
        self.interval_minutes = interval_minutes
        self._reset_event.set()

    def seconds_until_next(self) -> int:
        return getattr(self, "_remaining", self.interval_minutes * 60)

    def _run(self) -> None:
        elapsed = 0
        while not self._stop_event.is_set():
            time.sleep(1)

            if self._reset_event.is_set():
                elapsed = 0
                self._reset_event.clear()
                continue

            elapsed += 1
            self._remaining = max(0, self.interval_minutes * 60 - elapsed)

            if elapsed >= self.interval_minutes * 60:
                elapsed = 0
                if not self._stop_event.is_set():
                    try:
                        self.callback()
                    except Exception:
                        pass 
