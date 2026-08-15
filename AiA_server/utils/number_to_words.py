"""
Улучшенное преобразование чисел в русские числительные для TTS Silero.

Поддерживает:
- Количественные числительные (с учётом рода: один/одна/одно, два/две)
- Порядковые числительные (первый, второй, двадцать восьмой...)
- Согласование с существительными (1 день, 2 дня, 5 дней, 21 день...)
- Время (02:14 → два часа четырнадцать минут)
- Даты в формате MM_DD (08_11 → одиннадцатое августа)
- Числа до миллиардов

Используется в silero.py перед синтезом речи.
"""
import re

# ═══════════════════════════════════════════════════════════
# БАЗОВЫЕ СПРАВОЧНИКИ
# ═══════════════════════════════════════════════════════════

_UNITS_M = [
    "ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь",
    "восемь", "девять", "десять", "одиннадцать", "двенадцать",
    "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
    "семнадцать", "восемнадцать", "девятнадцать"
]

_UNITS_F = [
    "ноль", "одна", "две", "три", "четыре", "пять", "шесть", "семь",
    "восемь", "девять", "десять", "одиннадцать", "двенадцать",
    "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
    "семнадцать", "восемнадцать", "девятнадцать"
]

_UNITS_N = [
    "ноль", "одно", "два", "три", "четыре", "пять", "шесть", "семь",
    "восемь", "девять", "десять", "одиннадцать", "двенадцать",
    "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
    "семнадцать", "восемнадцать", "девятнадцать"
]

_TENS = [
    "", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят",
    "семьдесят", "восемьдесят", "девяносто"
]

_HUNDREDS = [
    "", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот",
    "семьсот", "восемьсот", "девятьсот"
]

_THOUSANDS = ("тысяча", "тысячи", "тысяч")
_MILLIONS  = ("миллион", "миллиона", "миллионов")
_BILLIONS  = ("миллиард", "миллиарда", "миллиардов")

# Порядковые (мужской род)
_ORDINAL_UNITS_M = [
    "нулевой", "первый", "второй", "третий", "четвёртый", "пятый",
    "шестой", "седьмой", "восьмой", "девятый", "десятый",
    "одиннадцатый", "двенадцатый", "тринадцатый", "четырнадцатый",
    "пятнадцатый", "шестнадцатый", "семнадцатый", "восемнадцатый",
    "девятнадцатый"
]

_ORDINAL_TENS = [
    "", "", "двадцатый", "тридцатый", "сороковой", "пятидесятый",
    "шестидесятый", "семидесятый", "восьмидесятый", "девяностый"
]

_ORDINAL_HUNDREDS = [
    "", "сотый", "двухсотый", "трёхсотый", "четырёхсотый",
    "пятисотый", "шестисотый", "семисотый", "восьмисотый", "девятисотый"
]

# Месяцы для дат (родительный падеж)
_MONTHS = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

# Род существительных для согласования
# "m" = мужской, "f" = женский, "n" = средний
_NOUN_GENDERS = {
    # мужской род
    "час": "m", "часа": "m", "часов": "m",
    "день": "m", "дня": "m", "дней": "m",
    "год": "m", "года": "m", "лет": "m",
    "месяц": "m", "месяца": "m", "месяцев": "m",
    # женский род
    "минута": "f", "минуты": "f", "минут": "f",
    "секунда": "f", "секунды": "f", "секунд": "f",
    "неделя": "f", "недели": "f", "недель": "f",
    "тысяча": "f", "тысячи": "f", "тысяч": "f",
}

# ═══════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════

def _plural_form(n: int, forms: tuple) -> str:
    """
    Выбирает правильную форму существительного по числу.
    forms = (единственное, 2-4, 5-20)
    Примеры:
        1 → forms[0]   (день)
        2 → forms[1]   (дня)
        5 → forms[2]   (дней)
        21 → forms[0]  (день)
        22 → forms[1]  (дня)
        25 → forms[2]  (дней)
    """
    n = abs(n) % 100
    if 11 <= n <= 19:
        return forms[2]
    n = n % 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]


def _get_units(gender: str):
    """Возвращает справочник единиц по роду."""
    if gender == "f":
        return _UNITS_F
    if gender == "n":
        return _UNITS_N
    return _UNITS_M


def _less_than_thousand(n: int, gender: str = "m") -> str:
    """Преобразует число 0-999 в количественное числительное с учётом рода."""
    if n == 0:
        return ""
    units = _get_units(gender)
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
            parts.append(units[u])
    elif n > 0:
        parts.append(units[n])
    return " ".join(parts)


def _ordinal_less_than_thousand(n: int) -> str:
    """Преобразует число 1-999 в порядковое числительное (муж. род)."""
    if n < 20:
        return _ORDINAL_UNITS_M[n]

    h = n // 100
    remainder = n % 100

    if remainder == 0:
        return _ORDINAL_HUNDREDS[h]

    hundreds_word = _HUNDREDS[h] if h > 0 else ""

    if remainder < 20:
        ordinal_word = _ORDINAL_UNITS_M[remainder]
    else:
        t = remainder // 10
        u = remainder % 10
        tens_word = _TENS[t]
        if u == 0:
            ordinal_word = _ORDINAL_TENS[t]
        else:
            ordinal_word = f"{tens_word} {_ORDINAL_UNITS_M[u]}"

    if hundreds_word:
        return f"{hundreds_word} {ordinal_word}"
    return ordinal_word


# ═══════════════════════════════════════════════════════════
# ОСНОВНЫЕ ФУНКЦИИ ПРЕОБРАЗОВАНИЯ
# ═══════════════════════════════════════════════════════════

def num2words_ru(n: int, gender: str = "m") -> str:
    """
    Количественное числительное. Поддержка до 999 999 999 999.
    gender: "m" (муж), "f" (жен), "n" (сред)
    """
    if n < 0:
        return f"минус {num2words_ru(-n, gender)}"
    if n == 0:
        return "ноль"
    if n < 1000:
        return _less_than_thousand(n, gender) or "ноль"

    parts = []

    # Миллиарды
    billions = n // 1_000_000_000
    if billions > 0:
        parts.append(_less_than_thousand(billions, "m"))
        parts.append(_plural_form(billions, _BILLIONS))
        n %= 1_000_000_000

    # Миллионы
    millions = n // 1_000_000
    if millions > 0:
        parts.append(_less_than_thousand(millions, "m"))
        parts.append(_plural_form(millions, _MILLIONS))
        n %= 1_000_000

    # Тысячи (всегда женский род)
    thousands = n // 1000
    if thousands > 0:
        parts.append(_less_than_thousand(thousands, "f"))
        parts.append(_plural_form(thousands, _THOUSANDS))
        n %= 1000

    # Единицы
    if n > 0:
        parts.append(_less_than_thousand(n, gender))

    return " ".join(parts)


def num2ordinal_ru(n: int) -> str:
    """
    Порядковое числительное (мужской род).
    1 → первый, 28 → двадцать восьмой, 100 → сотый
    """
    if n <= 0:
        return str(n)
    if n > 999_999_999_999:
        return str(n)

    if n >= 1000:
        qty = num2words_ru(n, "m")
        return f"{qty}ый"

    return _ordinal_less_than_thousand(n)


def num2words_with_noun(n: int, forms: tuple, gender: str = "m") -> str:
    """
    Числительное + согласованное существительное.
    forms = ("день", "дня", "дней")
    Пример: 28 → "двадцать восемь дней"
    """
    noun = _plural_form(n, forms)
    return f"{num2words_ru(n, gender)} {noun}"


# ═══════════════════════════════════════════════════════════
# ОБРАБОТКА СПЕЦИАЛЬНЫХ ПАТТЕРНОВ
# ═══════════════════════════════════════════════════════════

def _process_time(match) -> str:
    """
    Время HH:MM → 'H часов M минут' (с правильным склонением).
    Примеры: 02:14 → 'два часа четырнадцать минут'
             01:01 → 'один час одна минута'
             05:05 → 'пять часов пять минут'
    """
    h = int(match.group(1))
    m = int(match.group(2))

    hour_word = _plural_form(h, ("час", "часа", "часов"))
    minute_word = _plural_form(m, ("минута", "минуты", "минут"))

    hour_num = num2words_ru(h, "m")
    minute_num = num2words_ru(m, "f")

    if h == 0 and m == 0:
        return "ноль часов ноль минут"
    if h == 0:
        return f"{minute_num} {minute_word}"
    if m == 0:
        return f"{hour_num} {hour_word} ровно"

    return f"{hour_num} {hour_word} {minute_num} {minute_word}"


def _process_date_md(match) -> str:
    """
    Дата MM_DD → 'D-е число месяца'.
    Формат MM_DD: месяц_день (из moon_day.py strftime "%m_%d").
    Примеры: 08_11 → 'одиннадцатое августа'
             01_01 → 'первое января'
    """
    month = int(match.group(1))
    day = int(match.group(2))

    if not (1 <= month <= 12 and 1 <= day <= 31):
        return match.group(0)

    # Порядковое среднего рода для дня
    if day == 1:
        day_str = "первое"
    elif day == 2:
        day_str = "второе"
    elif day == 3:
        day_str = "третье"
    else:
        day_ord = num2ordinal_ru(day)
        day_str = day_ord.replace("ый", "ое").replace("ой", "ое").replace("ий", "ье")
        if "сотый" in day_str:
            day_str = day_str.replace("сотый", "сотое")
        if "тысячный" in day_str:
            day_str = day_str.replace("тысячный", "тысячное")

    month_name = _MONTHS[month] if month <= 12 else ""
    return f"{day_str} {month_name}" if month_name else day_str


def _process_moon_day(match) -> str:
    """
    'N лунный день' → 'N-й лунный день' (порядковое).
    Пример: '28 лунный день' → 'двадцать восьмой лунный день'
    """
    n = int(match.group(1))
    ordinal = num2ordinal_ru(n)
    return f"{ordinal} лунный день"


def _process_with_noun(match, forms: tuple, gender: str = "m") -> str:
    """Общая функция: число + существительное с согласованием."""
    n = int(match.group(1))
    noun = _plural_form(n, forms)
    return f"{num2words_ru(n, gender)} {noun}"


# ═══════════════════════════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ ПРЕПРОЦЕССИНГА
# ═══════════════════════════════════════════════════════════

def preprocess_text(text: str) -> str:
    """
    Преобразует числа в тексте в русские числительные с учётом контекста.

    Порядок обработки (от специфичного к общему):
    1. Время HH:MM
    2. Даты MM_DD
    3. 'N лунный день' → порядковое
    4. Число + известное существительное (с учётом рода)
    5. Оставшиеся числа → количественные

    Примеры:
        "28 лунный день. Начало: 08_11 02:14"
        → "двадцать восьмой лунный день. Начало: одиннадцатое августа два часа четырнадцать минут"

        "1 день, 2 дня, 5 дней, 21 день"
        → "один день, два дня, пять дней, двадцать один день"
    """
    result = text

    # 1. Время HH:MM (строгий формат)
    result = re.sub(r'\b(\d{1,2}):(\d{2})\b', _process_time, result)

    # 2. Даты MM_DD (формат из moon_day)
    result = re.sub(r'\b(\d{1,2})[_-](\d{1,2})\b', _process_date_md, result)

    # 3. 'N лунный день' → порядковое
    result = re.sub(r'\b(\d+)\s+лунный\s+день\b', _process_moon_day, result, flags=re.IGNORECASE)

    # 4. Число + существительные (согласование с учётом рода)
    # День/дня/дней (мужской)
    result = re.sub(
        r'\b(\d+)\s+(дней|дня|день)\b',
        lambda m: _process_with_noun(m, ("день", "дня", "дней"), "m"),
        result,
        flags=re.IGNORECASE
    )
    # Час/часа/часов (мужской)
    result = re.sub(
        r'\b(\d+)\s+(часов|часа|час)\b',
        lambda m: _process_with_noun(m, ("час", "часа", "часов"), "m"),
        result,
        flags=re.IGNORECASE
    )
    # Минута/минуты/минут (женский)
    result = re.sub(
        r'\b(\d+)\s+(минут|минуты|минута)\b',
        lambda m: _process_with_noun(m, ("минута", "минуты", "минут"), "f"),
        result,
        flags=re.IGNORECASE
    )
    # Секунда/секунды/секунд (женский)
    result = re.sub(
        r'\b(\d+)\s+(секунд|секунды|секунда)\b',
        lambda m: _process_with_noun(m, ("секунда", "секунды", "секунд"), "f"),
        result,
        flags=re.IGNORECASE
    )
    # Год/года/лет (мужской)
    result = re.sub(
        r'\b(\d+)\s+(лет|года|год)\b',
        lambda m: _process_with_noun(m, ("год", "года", "лет"), "m"),
        result,
        flags=re.IGNORECASE
    )
    # Месяц/месяца/месяцев (мужской)
    result = re.sub(
        r'\b(\d+)\s+(месяцев|месяца|месяц)\b',
        lambda m: _process_with_noun(m, ("месяц", "месяца", "месяцев"), "m"),
        result,
        flags=re.IGNORECASE
    )
    # Неделя/недели/недель (женский)
    result = re.sub(
        r'\b(\d+)\s+(недель|недели|неделя)\b',
        lambda m: _process_with_noun(m, ("неделя", "недели", "недель"), "f"),
        result,
        flags=re.IGNORECASE
    )

    # 5. Оставшиеся числа → количественные (мужской род по умолчанию)
    def replace_num(match):
        num_str = match.group()
        n = int(num_str)
        if n <= 999_999_999_999:
            return num2words_ru(n, "m")
        return num_str

    result = re.sub(r'\d+', replace_num, result)

    return result


# ═══════════════════════════════════════════
# ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ (для использования в командах)
# ═══════════════════════════════════════════

def format_number_with_noun(n: int, forms: tuple, gender: str = "m") -> str:
    """
    Явное форматирование: число + существительное.
    Используется в командах при формировании текста для TTS.

    Args:
        n: Число
        forms: Кортеж (единственное, 2-4, 5-20)
        gender: "m", "f" или "n"

    Пример:
        format_number_with_noun(28, ("день", "дня", "дней"), "m")
        → "двадцать восемь дней"
    """
    return num2words_with_noun(n, forms, gender)