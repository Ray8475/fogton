from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(ROOT_DIR, "logs")


# базовые имена; читаем <name>.log и <name>.error.log, если есть
COMPONENT_LOGS = {
    "API": "api",
    "Bot": "bot",
    "Webapp": "webapp",
    "Tunnel": "tunnel",
}


def _decode_best_effort(data: bytes) -> str:
    """
    Windows-процессы часто пишут логи в OEM codepage (cp866) или в ANSI (cp1251),
    а иногда в UTF-16. Подбираем декодирование с минимальным количеством �.
    """
    # Быстрый путь: UTF-16 (если есть BOM) или похоже на него
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16", errors="replace")
        except Exception:
            pass

    candidates = ["utf-8", "utf-8-sig", "cp866", "cp1251", "latin-1"]

    # Ключевые фразы, которые часто встречаются в Windows-ошибках и логах
    ru_keywords = (
        "только",
        "использование",
        "адрес",
        "сокета",
        "протокол",
        "сетев",
        "порт",
        "ошибка",
        "доступ",
        "занят",
        "разрешается",
        "можно",
    )

    best = None
    best_bad = None
    best_score = None

    def score_text(s: str) -> int:
        # бонус за ключевые слова
        lower = s.lower()
        kw = sum(3 for k in ru_keywords if k in lower)
        # бонус за долю кириллицы (без фанатизма)
        cyr = sum(1 for ch in s if "А" <= ch <= "я" or ch in "Ёё")
        total_letters = sum(1 for ch in s if ch.isalpha())
        cyr_ratio = int((cyr * 100) / max(1, total_letters))
        return kw + min(cyr_ratio, 40)

    for enc in candidates:
        try:
            s = data.decode(enc, errors="replace")
        except Exception:
            continue
        bad = s.count("\ufffd")
        score = score_text(s)
        if best is None:
            best, best_bad, best_score = s, bad, score
            continue
        # Сначала минимизируем "�", а при равенстве выбираем более "русский" текст
        if bad < best_bad or (bad == best_bad and score > (best_score or 0)):
            best, best_bad, best_score = s, bad, score

    # Если идеальная строка без �, всё равно могли выбрать не ту кодировку,
    # но эвристика по ключевым словам должна исправлять такие кейсы.
    return best or data.decode(errors="replace")


def read_tail(path: str, max_bytes: int = 8000) -> str:
    """Читаем хвост файла без лишних технических сообщений."""
    if not os.path.exists(path):
        return ""
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    try:
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(-max_bytes, os.SEEK_END)
            raw = f.read()
        return _decode_best_effort(raw)
    except OSError:
        return ""

def get_active_logs_dir() -> str:
    """
    run-dev.ps1 пишет logs/latest.txt с именем папки последнего запуска.
    Если файла нет — читаем напрямую из logs/.
    """
    # 1) Пробуем latest.txt (если run-dev.ps1 его пишет)
    latest_path = os.path.join(LOGS_DIR, "latest.txt")
    try:
        with open(latest_path, "r", encoding="ascii", errors="ignore") as f:
            run_id = f.read().strip()
        if run_id:
            candidate = os.path.join(LOGS_DIR, run_id)
            if os.path.isdir(candidate):
                return candidate
    except OSError:
        pass

    # 2) Фоллбек: выбираем самую новую папку по времени изменения
    try:
        subdirs = []
        for name in os.listdir(LOGS_DIR):
            p = os.path.join(LOGS_DIR, name)
            if os.path.isdir(p):
                try:
                    subdirs.append((os.path.getmtime(p), p))
                except OSError:
                    continue
        if subdirs:
            subdirs.sort(key=lambda t: t[0], reverse=True)
            return subdirs[0][1]
    except OSError:
        pass

    return LOGS_DIR


class LogViewer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Gifts Bot — Dev Logs")
        self.geometry("1000x700")

        if not os.path.exists(LOGS_DIR):
            os.makedirs(LOGS_DIR, exist_ok=True)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.text_widgets: dict[str, tk.Text] = {}
        self.current_tab: str | None = None
        self.active_logs_dir = get_active_logs_dir()
        self.last_run_id: str = os.path.basename(self.active_logs_dir)
        self.title(f"Gifts Bot — Dev Logs ({self.last_run_id})")

        for name, base in COMPONENT_LOGS.items():
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=name)

            # toolbar
            toolbar = ttk.Frame(frame)
            toolbar.pack(side=tk.TOP, fill=tk.X)
            ttk.Button(toolbar, text="Копировать всё", command=lambda n=name: self.copy_all(n)).pack(
                side=tk.LEFT, padx=6, pady=4
            )

            text = tk.Text(
                frame,
                wrap="word",
                font=("Consolas", 10),
                takefocus=0,   # не получать фокус (не будет caret/курсора)
                insertwidth=0, # скрыть caret полностью
            )
            text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

            # всегда read-only: запрещаем любые попытки ввода, но выделение мышью работает
            text.bind("<Key>", lambda _e: "break")

            yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            yscroll.pack(side=tk.RIGHT, fill=tk.Y)
            text.configure(yscrollcommand=yscroll.set)

            self.text_widgets[name] = text

        self.after(500, self.refresh_logs)

    def copy_all(self, tab_name: str) -> None:
        """Копирует весь текст текущего таба в буфер обмена (без выделения)."""
        widget = self.text_widgets[tab_name]
        try:
            content = widget.get("1.0", tk.END)
        except tk.TclError:
            return
        self.clipboard_clear()
        self.clipboard_append(content)

    def refresh_logs(self) -> None:
        # если стартанули новый run-dev.ps1 — переключаемся на новые логи
        new_dir = get_active_logs_dir()
        new_run_id = os.path.basename(new_dir)
        if new_dir != self.active_logs_dir:
            self.active_logs_dir = new_dir
            self.last_run_id = new_run_id
            self.title(f"Gifts Bot — Dev Logs ({self.last_run_id})")

        for name, base in COMPONENT_LOGS.items():
            text = self.text_widgets[name]
            out_path = os.path.join(self.active_logs_dir, base + ".log")
            err_path = os.path.join(self.active_logs_dir, base + ".error.log")

            out_content = read_tail(out_path).strip()
            err_content = read_tail(err_path).strip()

            content = ""
            if not out_content and not err_content:
                content = "Пока нет записей. Запусти run-dev.bat и подожди несколько секунд."
            else:
                if out_content:
                    content = out_content + "\n"
                if err_content:
                    if out_content:
                        content += "\n"
                    content += "Ошибки (stderr):\n"
                    content += err_content

            # Обновляем текст без фокуса/курсора
            text.delete("1.0", tk.END)
            text.insert("1.0", content)
            # всегда показываем левую часть строки (без горизонтального скролла)
            try:
                text.xview_moveto(0)
            except Exception:
                pass
            text.see(tk.END)

        # обновляем каждые 1 секунду
        self.after(1000, self.refresh_logs)


def main() -> None:
    try:
        app = LogViewer()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Error", f"Unexpected error in GUI: {e}")


if __name__ == "__main__":
    main()
