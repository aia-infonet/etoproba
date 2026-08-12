"""
Команда "Лунный день" из модуля "Команды пользователя".

Алгоритм:
1. Вычисляет текущий лунный день N.
   Лунный месяц = интервал между предыдущим и следующим новолунием.
   Каждый лунный день = лунный месяц / 30.
   Начало N-го дня = prev_new + (N-1) * (month/30)
   Конец N-го дня  = prev_new + N * (month/30)
2. Читает описание лунного дня из Excel-файла moon-day.xlsx (строка N, столбец 1).
3. Отправляет результат клиенту и озвучивает через TTS.
"""
import ephem
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openpyxl import Workbook, load_workbook
import os

BASE_DIR = Path("D:/AiA") if os.path.exists("D:/") else Path.home() / "AiA"
EXCEL_FILE = BASE_DIR / "Command_user" / "moon-day.xlsx"

DEFAULT_DESCRIPTIONS = [
    "Новолуние. Начало нового лунного цикла. Время для постановки целей и задумок.",
    "Растущая Луна. Символ роста и развития. Подходит для начала новых дел.",
    "Растущая Луна. Активность и энергия нарастают. Хороший день для общения.",
    "Растущая Луна. Время собирать информацию и учиться новому.",
    "Растущая Луна. День силы и решимости. Подходит для важных решений.",
    "Растущая Луна. Гармония и баланс. Благоприятный день для творчества.",
    "Растущая Луна. Энергия достижения пиков. Время для активных действий.",
    "Первая четверть. Половина пути к полнолунию. Проверьте планы.",
    "Растущая Луна. Интуиция усиливается. Доверяйте внутреннему голосу.",
    "Растущая Луна. День изобилия. Подходит для финансовых операций.",
    "Растущая Луна. Эмоции на высоте. Будьте внимательны к близким.",
    "Растущая Луна. Предполнолуние. Завершайте начатые дела.",
    "Полнолуние. Пик лунного цикла. Время ясности и завершения.",
    "Убывающая Луна. Начало фазы освобождения. Избавляйтесь от лишнего.",
    "Убывающая Луна. Время анализа и размышлений. Подведите итоги.",
    "Убывающая Луна. Энергия спадает. Отдыхайте и восстанавливайте силы.",
    "Убывающая Луна. День очищения. Подходит для уборки и порядка.",
    "Убывающая Луна. Время прощения и отпускания обид.",
    "Убывающая Луна. Последняя четверть. Проверьте, что осталось несделанным.",
    "Убывающая Луна. Глубокий анализ. Время для внутренней работы.",
    "Убывающая Луна. Подготовка к новому циклу. Планируйте будущее.",
    "Убывающая Луна. Тихий день. Медитация и самопознание.",
    "Убывающая Луна. Освобождение от старого. Принимайте изменения.",
    "Убывающая Луна. День благодарности. Благодарите за пройденный путь.",
    "Убывающая Луна. Завершение цикла. Подводите окончательные итоги.",
    "Убывающая Луна. Предноволунье. Отпустите всё ненужное.",
    "Убывающая Луна. Последний рывок перед покоем. Завершайте мелочи.",
    "Убывающая Луна. День тишины и покоя. Наблюдайте за собой.",
    "Убывающая Луна. Подготовка к новолунию. Очищайте мысли и пространство.",
    "Убывающая Луна. Финальный день цикла. Отдыхайте и набирайтесь сил."
]


def ensure_excel_exists():
    """Создаёт Excel-файл с шаблонными описаниями, если его нет."""
    if EXCEL_FILE.exists():
        return
    EXCEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Лунные дни"
    for i, desc in enumerate(DEFAULT_DESCRIPTIONS, start=1):
        ws.cell(row=i, column=1, value=desc)
    wb.save(EXCEL_FILE)


def get_moon_day_info():
    """
    Вычисляет номер текущего лунного дня и границы именно ЭТОГО дня.
    
    Лунный месяц = интервал между предыдущим и следующим новолунием.
    Каждый лунный день = лунный месяц / 30.
    
    Returns:
        (day_number, start_dt_local, end_dt_local)
    """
    now_utc = datetime.now(timezone.utc)
    
    # Предыдущее и следующее новолуние (UTC)
    prev_new_moon = ephem.previous_new_moon(now_utc).datetime().replace(tzinfo=timezone.utc)
    next_new_moon = ephem.next_new_moon(now_utc).datetime().replace(tzinfo=timezone.utc)
    
    # Длительность лунного месяца в секундах
    synodic_seconds = (next_new_moon - prev_new_moon).total_seconds()
    
    # Длительность одного лунного дня
    day_seconds = synodic_seconds / 30.0
    
    # Сколько секунд прошло от начала лунного месяца
    elapsed = (now_utc - prev_new_moon).total_seconds()
    
    # Номер текущего лунного дня (1–30)
    day_number = int(elapsed / day_seconds) + 1
    if day_number > 30:
        day_number = 30
    
    # Начало и конец именно этого лунного дня
    start_utc = prev_new_moon + timedelta(seconds=(day_number - 1) * day_seconds)
    end_utc   = prev_new_moon + timedelta(seconds=day_number * day_seconds)
    
    # Конвертируем в локальное время
    local_tz = datetime.now().astimezone().tzinfo
    start_local = start_utc.astimezone(local_tz)
    end_local = end_utc.astimezone(local_tz)
    
    return day_number, start_local, end_local


def read_description(day_number: int) -> str:
    """Читает описание лунного дня из Excel (строка day_number, столбец 1)."""
    ensure_excel_exists()
    try:
        wb = load_workbook(EXCEL_FILE)
        ws = wb.active
        cell = ws.cell(row=day_number, column=1)
        return str(cell.value) if cell.value else "Описание отсутствует"
    except Exception as e:
        return f"Ошибка чтения Excel: {e}"


async def execute(ws_manager, client_ip: str, data: dict,
                  ollama_chat, ollama_model: str, tts_engine, logger):
    """
    Выполняет команду "Лунный день".
    Мгновенная команда — не требует голосового ввода.
    """
    try:
        logger.info("[moon_day] Вычисление лунного дня...")
        
        day_num, start_dt, end_dt = get_moon_day_info()
        
        # Формат: MM_DD hh:mm
        start_str = start_dt.strftime("%m_%d %H:%M")
        end_str = end_dt.strftime("%m_%d %H:%M")
        
        log_msg = f"{day_num} лунный день. Начало: {start_str}, конец: {end_str}"
        logger.info(f"[moon_day] {log_msg}")
        
        # Читаем описание из Excel
        description = read_description(day_num)
        logger.info(f"[moon_day] Описание: {description}")
        
        # Полный текст для клиента и TTS
        full_text = f"{log_msg}. {description}"
        
        # Отправляем клиенту для отображения в логах
        await ws_manager.send_to(client_ip, {
            "type": "response",
            "text": full_text,
            "module": "command_user",
            "command": "moon_day"
        })
        
        # Озвучиваем через Silero TTS (автоматическое разбиение на части)
        if tts_engine:
            tts_engine.speak(full_text)
            logger.info("[moon_day] Текст озвучен")
        else:
            logger.warning("[moon_day] TTS не инициализирован")
            
    except Exception as e:
        logger.error(f"[moon_day] Ошибка: {e}")
        await ws_manager.send_to(client_ip, {
            "type": "error",
            "message": f"Ошибка вычисления лунного дня: {e}",
            "module": "command_user",
            "command": "moon_day"
        })
