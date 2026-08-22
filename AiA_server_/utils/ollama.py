"""
Утилиты для работы с локальным сервером Ollama.
Версия 2.2: асинхронные вызовы, таймаут, оптимизация скорости,
прогрев модели, ограничение длины ответа,
принудительный русский язык через system-сообщение в messages.
"""
import ollama
import asyncio
from typing import List, Dict, Optional

DEFAULT_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 512,
    "num_ctx": 4096,
    "repeat_penalty": 1.1,
}

# System prompt, принудительно устанавливающий русский язык
RU_SYSTEM_MSG = {"role": "system", "content": "Отвечай только на русском языке."}


def _inject_system(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Добавляет system-сообщение в начало списка messages."""
    # Если первое сообщение уже system — заменяем, иначе вставляем в начало
    if messages and messages[0].get("role") == "system":
        return messages
    return [RU_SYSTEM_MSG] + messages


def get_models() -> List[str]:
    """Получает список доступных моделей из Ollama."""
    try:
        response = ollama.list()
        models = response.get("models", [])
        return [m.get("name", m.get("model", "unknown")) for m in models]
    except Exception as e:
        print(f"[Ollama] Ошибка получения списка моделей: {e}")
        return []


def warmup_model(model: str) -> bool:
    """Прогрев модели в фоне."""
    if not model:
        return False
    try:
        messages = _inject_system([{"role": "user", "content": "Привет"}])
        ollama.chat(
            model=model,
            messages=messages,
            options={"num_predict": 1},
            stream=False
        )
        print(f"[Ollama] Модель {model} прогрета")
        return True
    except Exception as e:
        print(f"[Ollama] Ошибка прогрева: {e}")
        return False


def chat(model: str, messages: List[Dict[str, str]],
         options: Optional[Dict] = None) -> str:
    """Синхронный запрос (обратная совместимость)."""
    try:
        opts = {**DEFAULT_OPTIONS, **(options or {})}
        messages = _inject_system(messages)
        response = ollama.chat(
            model=model, messages=messages,
            stream=False, options=opts
        )
        return response["message"]["content"]
    except Exception as e:
        return f"Ошибка Ollama: {e}"


async def chat_async(model: str, messages: List[Dict[str, str]],
                     options: Optional[Dict] = None,
                     timeout: int = 60) -> str:
    """Асинхронный запрос с таймаутом и русским system prompt."""
    if not model:
        return "Ошибка: модель Ollama не выбрана"
    loop = asyncio.get_event_loop()
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    messages = _inject_system(messages)

    def _call():
        return ollama.chat(
            model=model, messages=messages,
            stream=False, options=opts
        )

    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _call),
            timeout=timeout
        )
        return response["message"]["content"]
    except asyncio.TimeoutError:
        return (
            "Превышено время ожидания ответа (60 сек). "
            "Попробуйте задать более короткий вопрос "
            "или выбрать более легкую модель."
        )
    except Exception as e:
        return f"Ошибка Ollama: {e}"


async def chat_stream_async(model: str, messages: List[Dict[str, str]],
                            options: Optional[Dict] = None,
                            timeout: int = 60):
    """Асинхронный стриминг с русским system prompt."""
    if not model:
        yield "Ошибка: модель Ollama не выбрана"
        return
    loop = asyncio.get_event_loop()
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    messages = _inject_system(messages)

    def _stream():
        return ollama.chat(
            model=model, messages=messages,
            stream=True, options=opts
        )

    stream_gen = await asyncio.wait_for(
        loop.run_in_executor(None, _stream),
        timeout=10
    )
    token_queue = asyncio.Queue()

    def _reader():
        try:
            for chunk in stream_gen:
                token = chunk["message"]["content"]
                asyncio.run_coroutine_threadsafe(
                    token_queue.put(token), loop
                )
            asyncio.run_coroutine_threadsafe(
                token_queue.put(None), loop
            )
        except Exception as e:
            asyncio.run_coroutine_threadsafe(
                token_queue.put(f"__ERROR__:{e}"), loop
            )

    import threading
    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()

    while True:
        token = await token_queue.get()
        if token is None:
            break
        if isinstance(token, str) and token.startswith("__ERROR__:"):
            raise Exception(token[9:])
        yield token