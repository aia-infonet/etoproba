"""
Команда "Начать запись голосом" из модуля "Команды пользователя".
Версия 3.2: стриминг + преобразование слов-цифр.
"""
import asyncio
from typing import Dict, Any

from utils.ollama import chat_stream_async

async def execute(ws_manager, client_ip: str, data: Dict[str, Any],
                  ollama_chat, ollama_model: str, tts_engine, logger):
    raw_text = data.get("text", "").strip()
    text = data.get("converted_text", raw_text).strip()

    if not raw_text:
        logger.warning("[voice_rec] Получен пустой текст от клиента")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": "Текст не распознан. Повторите, пожалуйста.",
            "module": "command_user",
            "command": "voice_rec"
        })
        return

    logger.info(f"[voice_rec] Распознанный текст ({len(raw_text)} симв.): {raw_text[:200]}...")
    if text != raw_text:
        logger.info(f"[voice_rec] Преобразовано: '{text}'")

    await ws_manager.send_to(client_ip, {
        "type": "status",
        "message": "Обработка через LLM...",
        "module": "command_user",
        "command": "voice_rec"
    })

    try:
        messages = [{"role": "user", "content": raw_text}]
        full_text = ""

        chunk_count = 0
        async for chunk in chat_stream_async(ollama_model, messages, timeout=60):
            full_text += chunk
            chunk_count += 1
            await ws_manager.send_to(client_ip, {
                "type": "stream_chunk",
                "text": chunk,
                "module": "command_user",
                "command": "voice_rec"
            })

        logger.info(f"[voice_rec] Стрим завершен. Получено {chunk_count} чанков, итого {len(full_text)} симв.")

        await ws_manager.send_to(client_ip, {
            "type": "stream_end",
            "text": full_text,
            "module": "command_user",
            "command": "voice_rec"
        })

        if not full_text.strip():
            logger.error("[voice_rec] Полный текст пустой после стриминга! Озвучивание пропущено.")
            await ws_manager.send_to(client_ip, {
                "type": "error",
                "message": "Получен пустой ответ от модели.",
                "module": "command_user",
                "command": "voice_rec"
            })
            return

        logger.info(f"[voice_rec] Полный ответ LLM ({len(full_text)} симв.): {full_text[:200]}...")

        if tts_engine:
            logger.info("[voice_rec] Запуск озвучивания через Silero TTS...")
            tts_engine.speak(full_text)
            logger.info("[voice_rec] Вызов tts_engine.speak() завершен (поток запущен)")
        else:
            logger.warning("[voice_rec] TTS не инициализирован, озвучивание пропущено")

    except asyncio.TimeoutError:
        logger.error("[voice_rec] Таймаут ожидания ответа от Ollama")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": "Модель слишком долго обрабатывает запрос. Попробуйте упростить вопрос.",
            "module": "command_user",
            "command": "voice_rec"
        })
    except Exception as e:
        logger.error(f"[voice_rec] Ошибка обработки: {e}", exc_info=True)
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": f"Ошибка обработки: {e}",
            "module": "command_user",
            "command": "voice_rec"
        })