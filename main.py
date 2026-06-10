import tkinter as tk
import queue
import threading
import random
import os

from database      import init_db, get_setting, set_setting, get_active_topics, log_session
from scheduler     import Scheduler
from tray          import TrayManager
from popup         import open_settings, open_history, new_ping_popup
from ollama_client import generate_lesson, generate_quiz, is_available


class KnowledgePingApp:
    def __init__(self):
        init_db()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("KnowledgePing")
        self._queue: queue.Queue = queue.Queue()

        interval = int(get_setting("interval_minutes", "30"))
        self.scheduler = Scheduler(interval_minutes=interval, callback=self._post_ping)
        self.scheduler.start()

        self.tray = TrayManager(
            on_ping_now = self._post_ping,
            on_settings = lambda: self._queue.put(("settings", None)),
            on_history  = lambda: self._queue.put(("history",  None)),
            on_toggle   = lambda: self._queue.put(("toggle",   None)),
            on_quit     = lambda: self._queue.put(("quit",     None)),
            is_enabled  = lambda: get_setting("enabled", "1") == "1",
        )
        self.tray.start()
        self.root.after(50, self._poll)


    def _post_ping(self) -> None:
        self._queue.put(("ping", None))


    def _poll(self) -> None:
        try:
            while True:
                task, data = self._queue.get_nowait()

                if task == "ping":
                    self._handle_ping()

                elif task == "show_lesson":
                    topic, content = data
                    new_ping_popup(self.root, topic, "lesson", content=content)
                    log_session(topic, "lesson", content)

                elif task == "show_quiz":
                    topic, question, answer = data
                    new_ping_popup(self.root, topic, "quiz", question=question, answer=answer)
                    log_session(topic, "quiz", f"Q: {question}\nA: {answer}")

                elif task == "show_error":
                    topic, mode, msg = data
                    new_ping_popup(self.root, topic, mode, error=msg)

                elif task == "settings":
                    open_settings(self.root, on_save=self._on_settings_saved)

                elif task == "history":
                    open_history(self.root)

                elif task == "toggle":
                    self._toggle_enabled()

                elif task == "quit":
                    self._quit()
                    return

        except queue.Empty:
            pass

        self.root.after(50, self._poll)


    def _handle_ping(self) -> None:
        if get_setting("enabled", "1") != "1":
            return

        topics = get_active_topics()
        if not topics:
            return

        topic = random.choice(topics)
        mode  = random.choice(["lesson", "quiz"])
        model = get_setting("model", "qwen3.5:0.8b")

        self.scheduler.reset_timer()

        def _fetch():
            # Generate first; the popup is created only once we have content.
            if not is_available():
                self._queue.put(("show_error", (
                    topic, mode,
                    "⚠️  Ollama is not running.\n\n"
                    "Start it with:\n    ollama serve\n\n"
                    f"Then pull a model:\n    ollama pull {model}"
                )))
                return

            if mode == "quiz":
                result = generate_quiz(topic, model)
                if result:
                    q, a = result
                    self._queue.put(("show_quiz", (topic, q, a)))
                    return

            content = generate_lesson(topic, model)
            if content:
                self._queue.put(("show_lesson", (topic, content)))
            else:
                self._queue.put(("show_error", (
                    topic, mode,
                    f"⚠️  Model '{model}' did not respond.\n\n"
                    "Check that the model is available:\n"
                    f"    ollama pull {model}"
                )))

        threading.Thread(target=_fetch, name="KPFetch", daemon=True).start()


    def _toggle_enabled(self) -> None:
        current = get_setting("enabled", "1")
        new_val = "0" if current == "1" else "1"
        set_setting("enabled", new_val)
        self.tray.update_icon(enabled=(new_val == "1"))

    def _on_settings_saved(self) -> None:
        interval = int(get_setting("interval_minutes", "30"))
        self.scheduler.update_interval(interval)
        self.tray.update_icon(enabled=(get_setting("enabled", "1") == "1"))

    def _quit(self) -> None:
        self.scheduler.stop()
        self.tray.stop()
        self.root.destroy()


    def run(self) -> None:
        self.root.mainloop()


def main():
    app = KnowledgePingApp()
    app.run()


if __name__ == "__main__":
    main()
