"""
Команда "Запрос : начать запись" из модуля "Диалог".

Алгоритм:
1. Получает распознанный текст от клиента.
2. Создаёт файл "запрос_MM_DD_hh_mm.docx" в D:\\AiA\\Dialog\\YYYY\\.
3. Записывает в файл "Запрос : " + текст.
4. Отправляет текст в Ollama, получает ответ.
5. Дописывает в файл с нового абзаца "Ответ : " + ответ LLM.
6. Сохраняет файл, отправляет ответ клиенту для отображения в логах.
"""
from datetime import datetime
from pathlib import Path
from docx import Document
from docx.shared import Pt
from typing import Dict, Any
import os

BASE_DIR = Path("D:/AiA") if os.path.exists("D:/") else Path.home() / "AiA"
DIALOG_DIR = BASE_DIR / "Dialog"

async def execute(ws_manager, client_ip: str, data: Dict[str, Any],
                  ollama_chat, ollama_model: str, tts_engine, logger):
    """
    Выполняет команду запроса с сохранением в .docx.
    
    Args:
        ws_manager: Менеджер WebSocket соединений
        client_ip: IP-адрес клиента
        data: Данные от клиента (содержит "text")
        ollama_chat: Функция для запроса к Ollama
        ollama_model: Имя выбранной модели Ollama
        tts_engine: Не используется (для единого интерфейса)
        logger: Логгер сервера
    """
    text = data.get("text", "").strip()
    
    if not text:
        logger.warning("[request] Получен пустой текст от клиента")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": "Текст не распознан. Повторите, пожалуйста.",
            "module": "dialog",
            "command": "request"
        })
        return
    
    logger.info(f"[request] Запрос: {text}")
    
    try:
        now = datetime.now()
        year = str(now.year)
        # Формат: запрос_MM_DD_hh_mm.docx
        filename = f"запрос_{now.month:02d}_{now.day:02d}_{now.hour:02d}_{now.minute:02d}.docx"
        
        # Создаём папку года, если её нет
        year_dir = DIALOG_DIR / year
        year_dir.mkdir(parents=True, exist_ok=True)
        file_path = year_dir / filename
        
        # Создаём документ Word
        doc = Document()
        
        # Заголовок
        title = doc.add_heading("Голосовой запрос и ответ", level=1)
        
        # Метаданные
        doc.add_paragraph(f"Дата: {now.strftime('%Y-%m-%d %H:%M')}")
        doc.add_paragraph(f"Источник: {client_ip}")
        doc.add_paragraph("")  # пустая строка
        
        # Записываем запрос ("Запрос : " жирным, затем текст)
        p_request = doc.add_paragraph()
        run_label = p_request.add_run("Запрос : ")
        run_label.bold = True
        run_label.font.size = Pt(12)
        p_request.add_run(text)
        
        logger.info(f"[request] Запрос записан в документ")
        
        # Отправляем статус клиенту — начинаем обработку
        await ws_manager.send_to(client_ip, {
            "type": "status",
            "message": "Обработка через LLM...",
            "module": "dialog",
            "command": "request"
        })
        
        # Отправляем текст в Ollama для обработки
        messages = [{"role": "user", "content": text}]
        response = ollama_chat(ollama_model, messages)
        
        logger.info(f"[request] Ответ LLM: {response[:200]}...")
        
        # Отправляем ответ клиенту для отображения в логах
        await ws_manager.send_to(client_ip, {
            "type": "response",
            "text": response,
            "module": "dialog",
            "command": "request"
        })
        
        # Дописываем ответ LLM в документ (с нового абзаца)
        doc.add_paragraph("")  # пустая строка-разделитель
        p_response = doc.add_paragraph()
        run_resp_label = p_response.add_run("Ответ : ")
        run_resp_label.bold = True
        run_resp_label.font.size = Pt(12)
        p_response.add_run(response)
        
        # Сохраняем файл
        doc.save(file_path)
        
        logger.info(f"Файл {filename} сохранён в {year_dir}")
        
        # Отправляем подтверждение клиенту
        await ws_manager.send_to(client_ip, {
            "type": "status",
            "message": f"Файл {filename} сохранён",
            "module": "dialog",
            "command": "request"
        })
        
    except Exception as e:
        logger.error(f"[request] Ошибка обработки: {e}")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": f"Ошибка обработки: {e}",
            "module": "dialog",
            "command": "request"
        })
