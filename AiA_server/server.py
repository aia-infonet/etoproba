"""
Главный файл сервера Ai Assistant Voice.
Запускает GUI (tkinter) и FastAPI WebSocket-сервер в фоновом потоке.

Структура:
- GUI: окно с выбором модели Ollama и блоком логов (копируемый)
- FastAPI: WebSocket endpoint /ws для связи с Android-приложением
- Логирование: в файл D:/AiA/_log/log_YYYY_MM_DD_hh_mm.txt и в GUI

Версия 3.3: добавлена сигнализация TTS started/ended всем клиентам.
"""

import asyncio          # <-- ИСПРАВЛЕНО: добавлен импорт
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import logging
import os
import sys
import signal
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

from utils.ollama import get_models, chat_async as ollama_chat, warmup_model
from utils.silero import SileroTTS
from utils.command_loader import load_commands

BASE_DIR = Path("D:/AiA") if os.path.exists("D:/") else Path.home() / "AiA"
LOG_DIR = BASE_DIR / "_log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_filename = datetime.now().strftime("log_%Y_%m_%d_%H_%M.txt")
LOG_FILE = LOG_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)
logger = logging.getLogger("AiA_Server")

app = FastAPI(title="Ai Assistant Voice Server")

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
        self._loop = None

    def set_loop(self, loop):
        """Устанавливает event loop для безопасной отправки из других потоков."""
        self._loop = loop

    async def connect(self, websocket: WebSocket, client_ip: str):
        await websocket.accept()
        self.active_connections[client_ip] = websocket
        logger.info(f"Клиент {client_ip} подключился")

    def disconnect(self, client_ip: str):
        if client_ip in self.active_connections:
            del self.active_connections[client_ip]
            logger.info(f"Клиент {client_ip} отключился")

    async def send_to(self, client_ip: str, message: dict):
        if client_ip in self.active_connections:
            try:
                await self.active_connections[client_ip].send_json(message)
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту {client_ip}: {e}")
                self.disconnect(client_ip)

    def broadcast_sync(self, message: dict):
        """Синхронная отправка сообщения всем подключенным клиентам.
        Безопасно вызывать из любого потока (включая callback TTS)."""
        if not self._loop or not self._loop.is_running():
            logger.warning("broadcast_sync: event loop не доступен")
            return
        for ip in list(self.active_connections.keys()):
            try:
                asyncio.run_coroutine_threadsafe(
                    self.send_to(ip, message),
                    self._loop
                )
            except Exception as e:
                logger.error(f"Broadcast error для {ip}: {e}")

manager = ConnectionManager()

ollama_model = None
commands = {}
tts_engine = None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # <-- ИСПРАВЛЕНО: получаем loop из running coroutine
    manager.set_loop(asyncio.get_running_loop())

    client_ip = websocket.client.host
    await manager.connect(websocket, client_ip)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # === Универсальное преобразование слов-цифр ===
            if msg_type in ("command", "text"):
                raw_text = data.get("text", "")
                if raw_text and isinstance(raw_text, str):
                    from utils.words_to_digits import convert_spoken_text
                    converted = convert_spoken_text(raw_text)
                    data["converted_text"] = converted
                    if converted != raw_text:
                        await manager.send_to(client_ip, {
                            "type": "converted",
                            "original": raw_text,
                            "converted": converted,
                            "module": data.get("module", ""),
                            "command": data.get("command", "")
                        })
                        logger.info(f"[{client_ip}] Преобразовано: '{raw_text}' → '{converted}'")
            # ==============================================

            if msg_type == "stop_tts":
                if tts_engine:
                    tts_engine.stop()
                    logger.info(f"[{client_ip}] TTS остановлен по запросу клиента")
                continue
            if msg_type == "command":
                module = data.get("module")
                command = data.get("command")
                if module in commands and command in commands[module]:
                    logger.info(f"[{client_ip}] Вызов команды: {module}/{command}")
                    await commands[module][command](
                        ws_manager=manager,
                        client_ip=client_ip,
                        data=data,
                        ollama_chat=ollama_chat,
                        ollama_model=ollama_model,
                        tts_engine=tts_engine,
                        logger=logger
                    )
                else:
                    err_msg = f"Команда {module}/{command} не найдена"
                    logger.warning(f"[{client_ip}] {err_msg}")
                    await manager.send_to(client_ip, {"type": "error", "message": err_msg})
            elif msg_type == "text":
                text = data.get("text", "")
                logger.info(f"[{client_ip}] Получен текст: {text}")
    except WebSocketDisconnect:
        manager.disconnect(client_ip)
    except Exception as e:
        logger.error(f"[{client_ip}] Ошибка WebSocket: {e}")
        manager.disconnect(client_ip)

class GuiLogHandler(logging.Handler):
    def __init__(self, msg_queue: queue.Queue):
        super().__init__()
        self.msg_queue = msg_queue
    def emit(self, record):
        self.msg_queue.put(record)

class ServerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ai Assistant Voice — Сервер")
        self.root.geometry("900x700")
        self.root.minsize(600, 400)
        self.msg_queue = queue.Queue()

        self.frame_top = ttk.Frame(root)
        self.frame_top.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(self.frame_top, text="Модель Ollama:", font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            self.frame_top, textvariable=self.model_var,
            state="readonly", width=40, font=("Segoe UI", 10)
        )
        self.model_combo.pack(side=tk.LEFT, padx=8)
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_change)

        ttk.Button(self.frame_top, text="Обновить список", command=self.refresh_models).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.frame_top, text="Перезагрузить TTS", command=self.init_tts).pack(side=tk.LEFT, padx=5)

        self.frame_log = ttk.LabelFrame(root, text="Логи сервера", padding=5)
        self.frame_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            self.frame_log,
            state='normal',
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            insertwidth=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.log_text.bind('<Key>', self._on_log_key)
        self.log_text.bind('<Button-1>', lambda e: None)
        self.log_text.bind('<Control-a>', lambda e: self.log_text.tag_add('sel', '1.0', 'end'))
        self.log_text.bind('<Button-3>', self._show_context_menu)

        self.frame_bottom = ttk.Frame(root)
        self.frame_bottom.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(self.frame_bottom, text=f"Лог-файл: {LOG_FILE}", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        ttk.Button(self.frame_bottom, text="Очистить логи", command=self.clear_logs).pack(side=tk.RIGHT)

        self.gui_handler = GuiLogHandler(self.msg_queue)
        self.gui_handler.setLevel(logging.INFO)
        logger.addHandler(self.gui_handler)

        self.log("=== Ai Assistant Voice Server ===")
        self.log(f"Лог-файл: {LOG_FILE}")
        self.refresh_models()
        self.load_commands()
        self.init_tts()
        self.check_queue()

        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()
        self.log("WebSocket-сервер запущен на ws://0.0.0.0:8000/ws")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _on_log_key(self, event):
        if event.state & 0x4 and event.keysym.lower() in ('c', 'a'):
            return None
        return 'break'

    def _show_context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Копировать", command=self._copy_selection)
        menu.add_command(label="Выделить всё", command=lambda: self.log_text.tag_add('sel', '1.0', 'end'))
        menu.post(event.x_root, event.y_root)

    def _copy_selection(self):
        try:
            selected = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.root.clipboard_clear()
            self.root.clipboard_append(selected)
        except tk.TclError:
            pass

    def on_model_change(self, event=None):
        global ollama_model
        ollama_model = self.model_var.get()
        self.log(f"Выбрана модель: {ollama_model}")
        if ollama_model:
            threading.Thread(target=warmup_model, args=(ollama_model,), daemon=True).start()

    def refresh_models(self):
        models = get_models()
        self.model_combo['values'] = models
        global ollama_model
        if models:
            if not ollama_model or ollama_model not in models:
                ollama_model = models[0]
                self.model_var.set(ollama_model)
            self.log(f"Модели Ollama: {', '.join(models)}")
        else:
            self.log("Модели Ollama не найдены. Убедитесь, что Ollama запущена.")
            ollama_model = None

    def load_commands(self):
        global commands
        commands = load_commands()
        for mod_name, cmds in commands.items():
            self.log(f"Модуль '{mod_name}': {len(cmds)} команд")

    def init_tts(self):
        global tts_engine
        tts_engine = None
        base = Path(__file__).parent
        search_paths = [
            base / "silero" / "v5_ru.pt",
            base / "models" / "v5_ru.pt",
            base / "utils" / "silero" / "v5_ru.pt",
            base / "tts" / "v5_ru.pt",
            Path("D:/AiA/models/v5_ru.pt"),
            Path.home() / "AiA" / "models" / "v5_ru.pt",
        ]
        self.log("Поиск модели Silero TTS...")
        found_path = None
        for p in search_paths:
            if p.exists():
                found_path = p
                break
        if not found_path:
            self.log("Модель v5_ru.pt не найдена. Положите ее в папку silero/ рядом с server.py")
            return
        self.log(f"Модель найдена: {found_path}")
        try:
            tts_engine = SileroTTS(str(found_path))

            # === TTS callbacks: сигнализация клиентам ===
            def on_tts_start(text: str):
                manager.broadcast_sync({"type": "tts_started", "text": text[:100]})
                self.log(f"TTS начало: {text[:60]}...")

            def on_tts_end(text: str):
                manager.broadcast_sync({"type": "tts_ended", "text": text[:100]})
                self.log(f"TTS окончено: {text[:60]}...")

            tts_engine.on_start = on_tts_start
            tts_engine.on_end = on_tts_end
            # ============================================

            self.log("Silero TTS инициализирован")
        except Exception as e:
            self.log(f"Ошибка инициализации Silero TTS: {e}")
            logger.exception("init_tts")

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, full_msg + "\n")
        self.log_text.see(tk.END)

    def check_queue(self):
        while not self.msg_queue.empty():
            try:
                record = self.msg_queue.get_nowait()
                self.log(record.getMessage())
            except Exception:
                pass
        self.root.after(100, self.check_queue)

    def clear_logs(self):
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='normal')
        self.log("Логи очищены")

    # <-- ИСПРАВЛЕНО: убрано ручное создание event loop, uvicorn управляет сам
    def run_server(self):
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

    def on_close(self):
        self.log("Завершение работы...")
        logger.info("Сервер выключен")
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)
        self.root.destroy()
        os._exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: os._exit(0))
    root = tk.Tk()
    app_gui = ServerGUI(root)
    root.mainloop()