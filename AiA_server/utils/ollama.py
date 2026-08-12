"""
Утилиты для работы с локальным сервером Ollama.
Предоставляет функции получения списка моделей и отправки запросов на генерацию текста.
"""
import ollama
from typing import List, Dict

def get_models() -> List[str]:
    """
    Получает список доступных моделей из Ollama.
    Возвращает список строк с именами моделей.
    При ошибке возвращает пустой список.
    """
    try:
        response = ollama.list()
        # Ollama возвращает словарь с ключом 'models', содержащим список словарей
        models = response.get('models', [])
        return [m.get('name', m.get('model', 'unknown')) for m in models]
    except Exception as e:
        print(f"[Ollama] Ошибка получения списка моделей: {e}")
        return []

def chat(model: str, messages: List[Dict[str, str]]) -> str:
    """
    Отправляет запрос к Ollama и возвращает сгенерированный текст.
    
    Args:
        model: Имя модели (например, 'llama3:8b')
        messages: Список сообщений в формате [{'role': 'user', 'content': '...'}, ...]
    
    Returns:
        Строка с ответом модели или сообщение об ошибке.
    """
    try:
        response = ollama.chat(model=model, messages=messages, stream=False)
        return response['message']['content']
    except Exception as e:
        return f"Ошибка Ollama: {e}"
