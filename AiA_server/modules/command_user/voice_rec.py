"""
Команда "Начать запись голосом" из модуля "Команды пользователя".
Получает распознанный текст от клиента, отправляет его в Ollama,
получает ответ и озвучивает его через Silero TTS.
"""
from typing import Dict, Any

async def execute(ws_manager, client_ip: str, data: Dict[str, Any], 
                  ollama_chat, ollama_model: str, tts_engine, logger):
    """
    Выполняет команду голосовой записи.
    
    Args:
        ws_manager: Менеджер WebSocket соединений (для отправки ответа клиенту)
        client_ip: IP-адрес клиента
        data: Данные от клиента (содержит "text" — распознанную речь)
        ollama_chat: Функция для запроса к Ollama
        ollama_model: Имя выбранной модели Ollama
        tts_engine: Экземпляр SileroTTS
        logger: Логгер сервера
    """
    text = data.get("text", "").strip()
    
    if not text:
        logger.warning("[voice_rec] Получен пустой текст от клиента")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": "Текст не распознан. Повторите, пожалуйста.",
            "module": "command_user",
            "command": "voice_rec"
        })
        return
    
    logger.info(f"[voice_rec] Распознанный текст: {text}")
    
    # Отправляем статус клиенту — начинаем обработку
    await ws_manager.send_to(client_ip, {
        "type": "status",
        "message": "Обработка через LLM...",
        "module": "command_user",
        "command": "voice_rec"
    })
    
    try:
        # Формируем запрос к LLM
        messages = [{"role": "user", "content": text}]
        response = ollama_chat(ollama_model, messages)
        
        logger.info(f"[voice_rec] Ответ LLM: {response[:200]}...")
        
        # Отправляем текстовый ответ клиенту
        await ws_manager.send_to(client_ip, {
            "type": "response",
            "text": response,
            "module": "command_user",
            "command": "voice_rec"
        })
        
        # Озвучиваем ответ на сервере
        if tts_engine:
            tts_engine.speak(response)
            logger.info("[voice_rec] Ответ озвучен через Silero TTS")
        else:
            logger.warning("[voice_rec] TTS не инициализирован, озвучивание пропущено")
            
    except Exception as e:
        logger.error(f"[voice_rec] Ошибка обработки: {e}")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": f"Ошибка обработки: {e}",
            "module": "command_user",
            "command": "voice_rec"
        })
