"""
Преобразование чисел в русские числительные.
Поддерживает числа от 0 до 999999.
Используется как препроцессор для TTS Silero,
т.к. Silero v5_ru не умеет озвучивать цифры.
"""
import re

# Единицы (0-19)
_UNITS = [
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
    "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать",
    "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"
]

# Десятки (20-90)
_TENS = [
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто"
]

# Сотни (100-900)
_HUNDREDS = [
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
    "семьсот", "восемьсот", "девятьсот"
]


def _less_than_thousand(n: int) -> str:
    """Преобразует число 0-999 в слова."""
    if n == 0:
        return ""
    parts = []
    h = n // 100
    if h > 0:
        parts.append(_HUNDREDS[h])
    n %= 100
    if n >= 20:
        t = n // 10
        parts.append(_TENS[t])
        u = n % 10
        if u > 0:
            parts.append(_UNITS[u])
    elif n > 0:
        parts.append(_UNITS[n])
    return " ".join(parts)


def num2words_ru(n: int) -> str:
    """
    Преобразует число 0-999999 в русское числительное.
    
    Args:
        n: Целое число от 0 до 999999
        
    Returns:
        Строка с числительным
    """
    if n < 0 or n > 999999:
        return str(n)
    if n == 0:
        return "ноль"
    if n < 1000:
        return _less_than_thousand(n) or "ноль"
    
    thousands = n // 1000
    remainder = n % 1000
    
    # Склонение "тысяча" в зависимости от числа
    if thousands == 1:
        t_word = "одна тысяча"
    elif thousands == 2:
        t_word = "две тысячи"
    elif 3 <= thousands <= 4:
        t_base = _less_than_thousand(thousands)
        t_word = f"{t_base} тысячи"
    else:
        t_base = _less_than_thousand(thousands)
        t_word = f"{t_base} тысяч"
    
    if remainder == 0:
        return t_word
    
    r_word = _less_than_thousand(remainder)
    return f"{t_word} {r_word}"


def preprocess_text(text: str) -> str:
    """
    Заменяет все числа в тексте на русские числительные.
    
    Пример:
        "28 лунный день. Начало: 08_11 02:14" 
        → "двадцать восемь лунный день. Начало: восемь_одиннадцать два:четырнадцать"
    
    Args:
        text: Исходный текст с цифрами
        
    Returns:
        Текст, где все числа заменены на слова
    """
    def replace_num(match):
        num_str = match.group()
        # Преобразуем строку цифр в число (ведущие нули игнорируются)
        n = int(num_str)
        if n <= 999999:
            return num2words_ru(n)
        return num_str  # Если число слишком большое — оставляем как есть
    
    return re.sub(r'\d+', replace_num, text)
