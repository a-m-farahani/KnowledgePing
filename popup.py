import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional
import threading

from database import (
    get_setting, set_setting,
    get_all_topics, add_topic, delete_topic, set_topic_active,
    get_history, clear_history,
)
from ollama_client import list_models


C = {
    "bg":           "#0f172a",
    "surface":      "#1e293b",
    "surface2":     "#263248",
    "border":       "#334155",
    "accent":       "#7c3aed",
    "accent_hover": "#6d28d9",
    "accent_dim":   "#4c1d95",
    "success":      "#10b981",
    "warning":      "#f59e0b",
    "danger":       "#ef4444",
    "text":         "#f1f5f9",
    "text_dim":     "#94a3b8",
    "text_muted":   "#475569",
}

FONT_FAMILY = "Segoe UI"


def _btn(parent, text, cmd, style="primary", **kwargs):
    colors = {
        "primary":   (C["accent"],   C["accent_hover"], "white"),
        "secondary": (C["surface"],  C["surface2"],     C["text_dim"]),
        "danger":    (C["danger"],   "#dc2626",          "white"),
        "ghost":     (C["bg"],       C["surface"],       C["text_dim"]),
    }
    bg, abg, fg = colors.get(style, colors["primary"])
    
    return tk.Button(
        parent, text=text, command=cmd,
        font = kwargs.pop("font", (FONT_FAMILY, 10)),
        fg=fg, bg=bg,
        activebackground=abg, activeforeground=fg,
        relief="flat", bd=0,
        padx=kwargs.pop("padx", 18), pady=kwargs.pop("pady", 7),
        cursor="hand2",
        **kwargs,
    )


def _label(parent, text, size=10, bold=False, dim=False, **kwargs):
    return tk.Label(
        parent, text=text,
        font=(FONT_FAMILY, size),
        fg=C["text_dim"] if dim else C["text"],
        bg=kwargs.pop("bg", C["bg"]),
        **kwargs,
    )


def _center(win, w, h):
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


class PingPopup:
    def __init__(
        self,
        root: tk.Tk,
        topic: str,
        mode: str,
        content:  Optional[str] = None,
        question: Optional[str] = None,
        answer:   Optional[str] = None,
        error:    Optional[str] = None,
    ):
        self.root   = root
        self.topic  = topic
        self.mode   = mode       # 'lesson' | 'quiz'
        self._answer = answer or ""
        self._answer_shown = False

        self._build()

        # Decide initial state.  Generate-first flow: we only ever construct
        # the popup once we have the content ready, so the loading state is
        # never shown in the normal path.
        if error is not None:
            self.show_error(error)
        elif mode == "lesson" and content is not None:
            self.show_lesson(content)
        elif mode == "quiz" and question is not None and answer is not None:
            self.show_quiz(question, answer)
        else:
            self._set_loading()


    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("KnowledgePing")
        self.win.configure(bg=C["bg"])
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        _center(self.win, 500, 360)

        # Accent bar
        tk.Frame(self.win, bg=C["accent"], height=4).pack(fill="x")

        # Header row
        hdr = tk.Frame(self.win, bg=C["bg"])
        hdr.pack(fill="x", padx=18, pady=(12, 4))

        icon = "📚" if self.mode == "lesson" else "🧠"
        _label(hdr, f"{icon}  KnowledgePing", size=13, bold=True, bg=C["bg"]).pack(side="left")

        close = tk.Label(hdr, text="✕", font=(FONT_FAMILY, 12),
                         fg=C["text_muted"], bg=C["bg"], cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda _: self._close())

        # Badges
        badge_row = tk.Frame(self.win, bg=C["bg"])
        badge_row.pack(fill="x", padx=18, pady=(0, 8))

        for text, color in [
            (self.topic, C["accent_dim"]),
            ("LESSON" if self.mode == "lesson" else "QUIZ", C["surface"]),
        ]:
            tk.Label(
                badge_row, text=f"  {text}  ",
                font=(FONT_FAMILY, 8, "bold"),
                fg=C["text_dim"], bg=color,
                padx=4, pady=2,
            ).pack(side="left", padx=(0, 6))

        # Content text
        content_frame = tk.Frame(self.win, bg=C["bg"])
        content_frame.pack(fill="both", expand=True, padx=18, pady=(0, 6))

        self.content_txt = tk.Text(
            content_frame,
            font=(FONT_FAMILY, 10), fg=C["text"], bg=C["surface"],
            wrap="word", relief="flat", bd=0,
            padx=14, pady=12,
            height=7, state="disabled",
            selectbackground=C["accent"],
            cursor="arrow",
        )
        self.content_txt.pack(fill="both", expand=True)

        # Answer area (quiz)
        self.answer_outer = tk.Frame(self.win, bg=C["bg"])

        self.answer_inner = tk.Frame(self.answer_outer, bg=C["surface"], padx=12, pady=8)
        self.answer_inner.pack(fill="x", padx=18)

        tk.Label(self.answer_inner, text="✅  Answer",
                 font=(FONT_FAMILY, 8, "bold"),
                 fg=C["success"], bg=C["surface"]).pack(anchor="w")
        self.answer_lbl = tk.Label(
            self.answer_inner, text="",
            font=(FONT_FAMILY, 10), fg=C["text"], bg=C["surface"],
            wraplength=420, justify="left",
        )
        self.answer_lbl.pack(anchor="w", pady=(4, 0))

        # Button row
        btn_row = tk.Frame(self.win, bg=C["bg"])
        btn_row.pack(fill="x", padx=18, pady=(4, 14))

        self.skip_btn = _btn(btn_row, "Skip", self._close, style="ghost")
        self.skip_btn.pack(side="right", padx=(0, 0))

        self.primary_btn = _btn(btn_row, "Loading…", self._close, state="disabled")
        self.primary_btn.pack(side="right", padx=(0, 8))

    def _set_loading(self):
        self._write("⏳  Generating your content, please wait…")
        self.primary_btn.config(text="Loading…", state="disabled")

    def show_lesson(self, content: str):
        self._write(content)
        self.primary_btn.config(text="Got it ✓", state="normal", command=self._close)

    def show_quiz(self, question: str, answer: str):
        self._answer = answer
        self._write(f"❓  {question}")
        self.primary_btn.config(
            text="Reveal Answer",
            state="normal",
            command=self._reveal_answer,
        )

    def show_error(self, msg: str = ""):
        msg = msg or (
            "⚠️  Could not reach Ollama.\n\n"
            "Make sure Ollama is running:\n"
            "    ollama serve\n\n"
            "And that your model is pulled:\n"
            "    ollama pull qwen3.5:0.8b"
        )
        self._write(msg)
        self.primary_btn.config(text="Close", state="normal", command=self._close)

    def _reveal_answer(self):
        if self._answer_shown:
            return
        self._answer_shown = True
        self.answer_lbl.config(text=self._answer)
        # Make sure the answer panel sits *above* the button row.
        self.answer_outer.pack(fill="x", padx=0, pady=(0, 4),
                               before=self.primary_btn.master)
        self.primary_btn.config(text="Got it ✓", command=self._close)


    def _write(self, text: str):
        self.content_txt.config(state="normal")
        self.content_txt.delete("1.0", "end")
        self.content_txt.insert("1.0", text)
        self.content_txt.config(state="disabled")

    def _close(self):
        try:
            self.win.destroy()
        except Exception:
            pass

    @property
    def alive(self) -> bool:
        try:
            return self.win.winfo_exists()
        except Exception:
            return False


class SettingsWindow:
    def __init__(self, root: tk.Tk, on_save: Optional[Callable] = None):
        self.root    = root
        self.on_save = on_save

        self.win = tk.Toplevel(root)
        self.win.title("KnowledgePing – Settings")
        self.win.configure(bg=C["bg"])
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.grab_set()    # modal
        _center(self.win, 520, 560)

        tk.Frame(self.win, bg=C["accent"], height=4).pack(fill="x")

        _label(self.win, "⚙️  Settings", size=14, bold=True,
               bg=C["bg"]).pack(anchor="w", padx=20, pady=(14, 10))

        self._build_general()
        self._build_topics()
        self._build_buttons()


    def _section(self, title: str) -> tk.Frame:
        tk.Label(self.win, text=title,
                 font=(FONT_FAMILY, 9, "bold"),
                 fg=C["accent"], bg=C["bg"]).pack(anchor="w", padx=20, pady=(10, 4))
        sep = tk.Frame(self.win, bg=C["border"], height=1)
        sep.pack(fill="x", padx=20, pady=(0, 8))
        f = tk.Frame(self.win, bg=C["bg"])
        f.pack(fill="x", padx=20, pady=(0, 4))
        return f

    def _row(self, parent, label_text: str, widget_factory):
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label_text, width=16,
                 font=(FONT_FAMILY, 10), fg=C["text_dim"], bg=C["bg"],
                 anchor="w").pack(side="left")
        widget_factory(row)
        return row

    def _build_general(self):
        f = self._section("GENERAL")

        # Enabled toggle
        self._enabled_var = tk.BooleanVar(value=get_setting("enabled", "1") == "1")
        self._row(f, "Pings enabled", lambda p: tk.Checkbutton(
            p, variable=self._enabled_var,
            text="Active", font=(FONT_FAMILY, 10),
            fg=C["text"], bg=C["bg"],
            activebackground=C["bg"], activeforeground=C["text"],
            selectcolor=C["surface"],
        ).pack(side="left"))

        # Interval
        self._interval_var = tk.StringVar(value=get_setting("interval_minutes", "30"))
        def _interval_widget(p):
            tk.Spinbox(
                p, from_=1, to=240, textvariable=self._interval_var,
                width=5, font=(FONT_FAMILY, 10),
                fg=C["text"], bg=C["surface"],
                relief="flat", bd=0, buttonbackground=C["surface2"],
            ).pack(side="left")
            tk.Label(p, text=" minutes", font=(FONT_FAMILY, 10),
                     fg=C["text_dim"], bg=C["bg"]).pack(side="left")
        self._row(f, "Ping interval", _interval_widget)

        # Model
        self._model_var = tk.StringVar(value=get_setting("model", "gemma3:1b"))
        def _model_widget(p):
            entry = tk.Entry(p, textvariable=self._model_var, width=22,
                             font=(FONT_FAMILY, 10), fg=C["text"],
                             bg=C["surface"], relief="flat", bd=4,
                             insertbackground=C["text"])
            entry.pack(side="left")
            _btn(p, "↻ Refresh", self._refresh_models,
                 style="secondary", padx=10, pady=4).pack(side="left", padx=(8, 0))
        self._row(f, "Ollama model", _model_widget)

        # Model dropdown
        self._model_listbox_frame = tk.Frame(f, bg=C["bg"])
        self._model_listbox_frame.pack(fill="x", pady=(0, 4))

    def _refresh_models(self):
        def _fetch():
            models = list_models()
            self.win.after(0, lambda: self._populate_models(models))
        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_models(self, models: list[str]):
        for w in self._model_listbox_frame.winfo_children():
            w.destroy()
        if not models:
            tk.Label(self._model_listbox_frame,
                     text="  No models found – is Ollama running?",
                     font=(FONT_FAMILY, 9), fg=C["warning"], bg=C["bg"]).pack(anchor="w")
            return
        tk.Label(self._model_listbox_frame,
                 text="  Available models (click to select):",
                 font=(FONT_FAMILY, 9), fg=C["text_dim"], bg=C["bg"]).pack(anchor="w")
        btn_row = tk.Frame(self._model_listbox_frame, bg=C["bg"])
        btn_row.pack(fill="x")
        for m in models:
            def _pick(name=m):
                self._model_var.set(name)
            _btn(btn_row, m, _pick, style="secondary", padx=8, pady=3,
                 font=(FONT_FAMILY, 9)).pack(side="left", padx=(0, 4), pady=2)

    def _build_topics(self):
        f = self._section("TOPICS")

        # Scrollable topic list
        list_frame = tk.Frame(f, bg=C["surface"], relief="flat", bd=0)
        list_frame.pack(fill="x")

        canvas  = tk.Canvas(list_frame, bg=C["surface"], bd=0,
                            highlightthickness=0, height=130)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.topics_inner = tk.Frame(canvas, bg=C["surface"])

        self.topics_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.topics_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._refresh_topic_list()

        # Add topic row
        add_frame = tk.Frame(f, bg=C["bg"])
        add_frame.pack(fill="x", pady=(8, 0))

        self._new_topic_var = tk.StringVar()
        entry = tk.Entry(add_frame, textvariable=self._new_topic_var,
                         width=28, font=(FONT_FAMILY, 10),
                         fg=C["text"], bg=C["surface"],
                         relief="flat", bd=4, insertbackground=C["text"])
        entry.pack(side="left")
        entry.bind("<Return>", lambda _: self._add_topic())
        _btn(add_frame, "+ Add Topic", self._add_topic,
             style="secondary", padx=10, pady=5).pack(side="left", padx=(8, 0))

    def _refresh_topic_list(self):
        for w in self.topics_inner.winfo_children():
            w.destroy()
        topics = get_all_topics()
        if not topics:
            tk.Label(self.topics_inner, text="  No topics yet.",
                     font=(FONT_FAMILY, 9), fg=C["text_muted"],
                     bg=C["surface"]).pack(anchor="w", padx=8, pady=4)
            return
        for t in topics:
            row = tk.Frame(self.topics_inner, bg=C["surface"])
            row.pack(fill="x")

            var = tk.BooleanVar(value=bool(t["active"]))
            cb = tk.Checkbutton(
                row, variable=var,
                text=t["name"],
                font=(FONT_FAMILY, 10), fg=C["text"],
                bg=C["surface"], activebackground=C["surface"],
                activeforeground=C["text"], selectcolor=C["bg"],
                anchor="w",
                command=lambda tid=t["id"], v=var: set_topic_active(tid, v.get()),
            )
            cb.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=2)

            del_btn = tk.Label(row, text="🗑", font=(FONT_FAMILY, 10),
                               fg=C["text_muted"], bg=C["surface"], cursor="hand2")
            del_btn.pack(side="right", padx=8)
            del_btn.bind("<Button-1>", lambda _, tid=t["id"]: self._delete_topic(tid))

    def _add_topic(self):
        name = self._new_topic_var.get().strip()
        if name:
            add_topic(name)
            self._new_topic_var.set("")
            self._refresh_topic_list()

    def _delete_topic(self, topic_id: int):
        delete_topic(topic_id)
        self._refresh_topic_list()

    def _build_buttons(self):
        sep = tk.Frame(self.win, bg=C["border"], height=1)
        sep.pack(fill="x", padx=0, pady=(10, 0))

        row = tk.Frame(self.win, bg=C["bg"])
        row.pack(fill="x", padx=20, pady=12)

        _btn(row, "Cancel", self.win.destroy, style="ghost").pack(side="right")
        _btn(row, "Save", self._save, style="primary").pack(side="right", padx=(0, 8))

    def _save(self):
        try:
            interval = int(self._interval_var.get())
            if interval < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid input", "Interval must be a positive integer.",
                                 parent=self.win)
            return

        set_setting("interval_minutes", str(interval))
        set_setting("model", self._model_var.get().strip())
        set_setting("enabled", "1" if self._enabled_var.get() else "0")

        if self.on_save:
            self.on_save()
        self.win.destroy()


class HistoryWindow:
    def __init__(self, root: tk.Tk):
        self.win = tk.Toplevel(root)
        self.win.title("KnowledgePing – History")
        self.win.configure(bg=C["bg"])
        self.win.resizable(True, True)
        self.win.attributes("-topmost", True)
        _center(self.win, 560, 500)

        tk.Frame(self.win, bg=C["accent"], height=4).pack(fill="x")
        _label(self.win, "📜  Session History", size=14, bold=True,
               bg=C["bg"]).pack(anchor="w", padx=20, pady=(14, 10))

        self._build_list()
        self._build_footer()

    def _build_list(self):
        container = tk.Frame(self.win, bg=C["bg"])
        container.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        canvas    = tk.Canvas(container, bg=C["bg"], bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner     = tk.Frame(canvas, bg=C["bg"])

        inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        rows = get_history(40)
        if not rows:
            tk.Label(inner, text="No history yet. Wait for your first ping!",
                     font=(FONT_FAMILY, 10), fg=C["text_muted"], bg=C["bg"]).pack(pady=20)
            return

        for i, r in enumerate(rows):
            bg_row = C["surface"] if i % 2 == 0 else C["bg"]
            card = tk.Frame(inner, bg=bg_row)
            card.pack(fill="x", pady=1)

            badge_color = C["accent_dim"] if r["type"] == "lesson" else C["surface"]
            tk.Label(card,
                     text=f"  {r['type'].upper()}  ",
                     font=(FONT_FAMILY, 8, "bold"),
                     fg=C["text_dim"], bg=badge_color).pack(side="left", padx=(8, 6), pady=6)

            tk.Label(card, text=r["topic"],
                     font=(FONT_FAMILY, 9, "bold"),
                     fg=C["text"], bg=bg_row).pack(side="left")

            ts = r["timestamp"][:16].replace("T", " ")
            tk.Label(card, text=ts,
                     font=(FONT_FAMILY, 8),
                     fg=C["text_muted"], bg=bg_row).pack(side="right", padx=8)

    def _build_footer(self):
        sep = tk.Frame(self.win, bg=C["border"], height=1)
        sep.pack(fill="x")
        row = tk.Frame(self.win, bg=C["bg"])
        row.pack(fill="x", padx=20, pady=10)
        _btn(row, "Clear History", self._clear, style="danger", padx=12, pady=5).pack(side="left")
        _btn(row, "Close", self.win.destroy, style="ghost", padx=12, pady=5).pack(side="right")

    def _clear(self):
        if messagebox.askyesno("Clear History", "Delete all session history?",
                               parent=self.win):
            clear_history()
            self.win.destroy()



def open_settings(root: tk.Tk, on_save: Optional[Callable] = None) -> None:
    SettingsWindow(root, on_save=on_save)


def open_history(root: tk.Tk) -> None:
    HistoryWindow(root)


def new_ping_popup(
    root: tk.Tk,
    topic: str,
    mode: str,
    content:  Optional[str] = None,
    question: Optional[str] = None,
    answer:   Optional[str] = None,
    error:    Optional[str] = None,
) -> PingPopup:
    return PingPopup(
        root, topic, mode,
        content=content, question=question, answer=answer, error=error,
    )
