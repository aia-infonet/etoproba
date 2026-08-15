"""
Динамический загрузчик команд из папки modules/.
Сканирует подпапки, импортирует Python-файлы и извлекает функцию execute().
"""
import os
import importlib.util
from pathlib import Path
from typing import Dict, Callable

def load_commands() -> Dict[str, Dict[str, Callable]]:
    """
    Сканирует директорию modules/ и загружает все команды.
    
    Структура ожидается:
        modules/
            module_name/
                command_name.py  (должен содержать async def execute(...))
    
    Returns:
        Словарь {module_name: {command_name: execute_function}}
    """
    commands = {}
    # Путь к папке modules относительно этого файла
    modules_dir = Path(__file__).parent.parent / "modules"
    
    if not modules_dir.exists():
        print(f"[CommandLoader] Папка modules/ не найдена: {modules_dir}")
        return commands
    
    # Перебираем папки модулей
    for module_dir in modules_dir.iterdir():
        if not module_dir.is_dir() or module_dir.name.startswith('_'):
            continue
            
        module_name = module_dir.name
        commands[module_name] = {}
        
        # Перебираем .py файлы в папке модуля
        for file_path in module_dir.glob("*.py"):
            if file_path.name.startswith('_'):
                continue
                
            command_name = file_path.stem
            try:
                # Динамический импорт
                spec = importlib.util.spec_from_file_location(
                    f"modules.{module_name}.{command_name}",
                    file_path
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                
                if hasattr(mod, 'execute'):
                    commands[module_name][command_name] = mod.execute
                    print(f"[CommandLoader] Загружена команда: {module_name}/{command_name}")
                else:
                    print(f"[CommandLoader] Предупреждение: {file_path} не содержит функции execute()")
            except Exception as e:
                print(f"[CommandLoader] Ошибка загрузки {file_path}: {e}")
    
    return commands
