"""
Главный файл сервера Ai Assistant Voice.
Запускает GUI (tkinter) и FastAPI WebSocket-сервер в фоновом потоке.

Структура:
- GUI: окно с выбором модели Ollama и блоком логов
- FastAPI: WebSocket endpoint /ws для связи с Android-приложением
- Логирование: в файл D:\AiA\_log\log_YYYY_MM_DD_hh_mm.txt и в GUI
"""

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

# Добавляем корень проекта в sys.path для импорта utils
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

from utils.ollama import get_models, chat as ollama_chat
from utils.silero import SileroTTS
from utils.command_loader import load_commands

# ═════════════════════
# КОНФИГУРАЦИЯ И ЛОГИРОВАНИЕ
# ═════════════════════

# Базовая директория для документов и логов
BASE_DIR = Path("D:/AiA") if os.path.exists("D:/") else Path.home() / "AiA"
LOG_DIR = BASE_DIR / "_log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Имя лог-файла: log_YYYY_MM_DD_hh_mm.txt
log_filename = datetime.now().strftime("log_%Y_%m_%d_%H_%M.txt")
LOG_FILE = LOG_DIR / log_filename

# Настройка корневого логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
    ]
)
logger = logging.getLogger("AiA_Server")

# ═════════════════
# FASTAPI И WEBSOCKET
# ═════════════════

app = FastAPI(title="Ai Assistant Voice Server")

class ConnectionManager:
    """
    Управляет активными WebSocket-соединениями.
    Хранит словарь {client_ip: websocket}.
    """
    def __init__(self):
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, client_ip: str):
        """Принимает новое соединение и логирует подключение."""
        await websocket.accept()
        self.active_connections[client_ip] = websocket
        logger.info(f"Клиент {client_ip} подключился")
    
    def disconnect(self, client_ip: str):
        """Удаляет соединение и логирует отключение."""
        if client_ip in self.active_connections:
            del self.active_connections[client_ip]
            logger.info(f"Клиент {client_ip} отключился")
    
    async def send_to(self, client_ip: str, message: dict):
        """Отправляет JSON-сообщение конкретному клиенту."""
        if client_ip in self.active_connections:
            try:
                await self.active_connections[client_ip].send_json(message)
            except Exception as e:
                logger.error(f"Ошибка отправки клиенту {client_ip}: {e}")
                self.disconnect(client_ip)

manager = ConnectionManager()

# Глобальные переменные, управляемые через GUI
ollama_model = None
commands = {}
tts_engine = None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint. Принимает JSON-сообщения от Android-приложения.
    Ожидаемый формат:
        {"type": "command", "module": "...", "command": "...", "text": "..."}
        {"type": "stop_tts"} — остановить озвучивание
    """
    client_ip = websocket.client.host
    await manager.connect(websocket, client_ip)
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # ── Остановка TTS ──
            if msg_type == "stop_tts":
                if tts_engine:
                    tts_engine.stop()
                    logger.info(f"[{client_ip}] TTS остановлен по запросу клиента")
                continue
            
            # ── Выполнение команды ──
            if msg_type == "command":
                module = data.get("module")
                command = data.get("command")
                
                if module in commands and command in commands[module]:
                    logger.info(f"[{client_ip}] Вызов команды: {module}/{command}")
                    # Запускаем асинхронную функцию команды
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
                    await manager.send_to(client_ip, {
                        "type": "error",
                        "message": err_msg
                    })
            
            # ── Просто текст (без привязки к команде) ──
            elif msg_type == "text":
                text = data.get("text", "")
                logger.info(f"[{client_ip}] Получен текст: {text}")
                # Можно добавить обработку голосового ввода вне команд
                
    except WebSocketDisconnect:
        manager.disconnect(client_ip)
    except Exception as e:
        logger.error(f"[{client_ip}] Ошибка WebSocket: {e}")
        manager.disconnect(client_ip)

# ══════════
# GUI (TKINTER)
# ══════════

class GuiLogHandler(logging.Handler):
    """
    Кастомный Handler для logging.
    Помещает записи в очередь, чтобы GUI мог забрать их из основного потока.
    """
    def __init__(self, msg_queue: queue.Queue):
        super().__init__()
        self.msg_queue = msg_queue
    
    def emit(self, record):
        self.msg_queue.put(record)


class ServerGUI:
    """
    Графический интерфейс сервера.
    Масштабируемое окно с выбором модели Ollama и блоком логов.
    """
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ai Assistant Voice — Сервер")
        self.root.geometry("900x700")
        self.root.minsize(600, 400)
        
        # Очередь для потокобезопасного обмена сообщениями
        self.msg_queue = queue.Queue()
        
        # ── Верхняя панель: выбор модели ──
        self.frame_top = ttk.Frame(root)
        self.frame_top.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(self.frame_top, text="Модель Ollama:", font=("Segoe UI", 10)).pack(side=tk.LEFT)
        
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            self.frame_top,
            textvariable=self.model_var,
            state="readonly",
            width=45,
            font=("Segoe UI", 10)
        )
        self.model_combo.pack(side=tk.LEFT, padx=8)
        # При смене модели обновляем глобальную переменную
        self.model_combo.bind("<<ComboboxSelected>>", self.on_model_change)
        
        ttk.Button(
            self.frame_top,
            text="🔄 Обновить список",
            command=self.refresh_models
        ).pack(side=tk.LEFT, padx=5)
        
        # ── Блок логов ──
        self.frame_log = ttk.LabelFrame(root, text="Логи сервера", padding=5)
        self.frame_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(
            self.frame_log,
            state='disabled',
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # ── Нижняя панель ──
        self.frame_bottom = ttk.Frame(root)
        self.frame_bottom.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            self.frame_bottom,
            text=f"Лог-файл: {LOG_FILE}",
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            self.frame_bottom,
            text="🗑 Очистить логи",
            command=self.clear_logs
        ).pack(side=tk.RIGHT)
        
        # ── Подключение логгера к GUI ──
        self.gui_handler = GuiLogHandler(self.msg_queue)
        self.gui_handler.setLevel(logging.INFO)
        logger.addHandler(self.gui_handler)
        
        # ── Инициализация ──
        self.log("=== Ai Assistant Voice Server ===")
        self.log(f"Лог-файл: {LOG_FILE}")
        self.refresh_models()
        self.load_commands()
        self.init_tts()
        
        # ── Запуск проверки очереди (каждые 100 мс) ──
        self.check_queue()
        
        # ── Запуск FastAPI в фоновом потоке ──
        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()
        self.log("WebSocket-сервер запущен на ws://0.0.0.0:8000/ws")
        
        # ── Обработка закрытия окна ──
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_model_change(self, event=None):
        """Обновляет глобальную переменную при смене модели в выпадающем списке."""
        global ollama_model
        ollama_model = self.model_var.get()
        self.log(f"Выбрана модель: {ollama_model}")
    
    def refresh_models(self):
        """Запрашивает список моделей у Ollama и обновляет Combobox."""
        models = get_models()
        self.model_combo['values'] = models
        
        global ollama_model
        if models:
            if not ollama_model or ollama_model not in models:
                ollama_model = models[0]
                self.model_var.set(ollama_model)
            self.log(f"Модели Ollama загружены: {', '.join(models)}")
        else:
            self.log("⚠️ Модели Ollama не найдены. Убедитесь, что Ollama запущена.")
            ollama_model = None
    
    def load_commands(self):
        """Загружает команды из папки modules/."""
        global commands
        commands = load_commands()
        for mod_name, cmds in commands.items():
            self.log(f"Модуль '{mod_name}': загружено команд — {len(cmds)}")
    
    def init_tts(self):
        """Инициализирует Silero TTS, если файл модели найден."""
        global tts_engine
        model_path = Path(__file__).parent / "silero" / "v5_ru.pt"
        
        if model_path.exists():
            try:
                tts_engine = SileroTTS(str(model_path))
                self.log("✅ Silero TTS инициализирован")
            except Exception as e:
                self.log(f"❌ Ошибка инициализации Silero TTS: {e}")
        else:
            self.log(f"⚠️ Файл модели TTS не найден: {model_path}")
            self.log("   Положите v5_ru.pt в папку silero/")
    
    def log(self, message: str):
        """Добавляет строку в блок логов GUI."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}"
        
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, full_msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
    
    def check_queue(self):
        """Проверяет очередь логов из других потоков и выводит в GUI."""
        while not self.msg_queue.empty():
            try:
                record = self.msg_queue.get_nowait()
                self.log(record.getMessage())
            except Exception:
                pass
        self.root.after(100, self.check_queue)
    
    def clear_logs(self):
        """Очищает текстовое поле логов."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.log("Логи очищены")
    
    def run_server(self):
        """Запускает uvicorn в отдельном потоке."""
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    
    def on_close(self):
        """Обработчик закрытия окна. Сохраняет логи и завершает процесс."""
        self.log("Завершение работы сервера...")
        logger.info("Сервер выключен оператором")
        
        # Закрываем лог-файл
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)
        
        self.root.destroy()
        os._exit(0)


# ══════════
# ТОЧКА ВХОДА
# ══════════

if __name__ == "__main__":
    # Корректное завершение по Ctrl+C в консоли
    signal.signal(signal.SIGINT, lambda s, f: os._exit(0))
    
    root = tk.Tk()
    app_gui = ServerGUI(root)
    root.mainloop()
