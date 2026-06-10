from datetime import datetime
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger


class Scheduler:
    _JOB_ID = "kp_ping"

    def __init__(self, interval_minutes: int, callback: Callable[[], None]):
        self.interval_minutes = interval_minutes
        self.callback = callback

        self._scheduler = BackgroundScheduler(daemon=True)
        self._started = False


    def start(self) -> None:
        if self._started:
            return
        self._scheduler.start()
        self._scheduler.add_job(
            self._safe_callback,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id=self._JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(),
        )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        try:
            if self._scheduler.get_job(self._JOB_ID):
                self._scheduler.remove_job(self._JOB_ID)
        except Exception:
            pass
        try:
            self._scheduler.shutdown(wait=False)
        except Exception:
            pass

    def reset_timer(self) -> None:
        if not self._started:
            return
        self._scheduler.reschedule_job(
            self._JOB_ID,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
        )

    def update_interval(self, interval_minutes: int) -> None:
        self.interval_minutes = interval_minutes
        self.reset_timer()

    def seconds_until_next(self) -> int:
        if not self._started:
            return self.interval_minutes * 60
        job = self._scheduler.get_job(self._JOB_ID)
        if job is None or job.next_run_time is None:
            return self.interval_minutes * 60
        next_run = job.next_run_time
        now = datetime.now(next_run.tzinfo) if next_run.tzinfo else datetime.now()
        return max(0, int((next_run - now).total_seconds()))

    def _safe_callback(self) -> None:
        try:
            self.callback()
        except Exception:
            pass 
