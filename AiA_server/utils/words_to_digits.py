"""
Преобразование произнесённых слов-цифр и символов в цифры и символы.
Например: "тридцать пять тире пятнадцать точка восемь" → "35-15.8"

Версия 2.3: жадный парсинг с разделением "составное число" vs "последовательность цифр".
- Составное число: разряды строго убывают (сотни→десятки→единицы), без повторов
- Последовательность цифр: повторы разрядов, неправильный порядок, или 11-19 перед единицей
- Тысячи/миллионы сбрасывают разрядную иерархию
"""

RUS_NUMBERS = {
    'ноль': 0, 'нуль': 0,
    'один': 1, 'одна': 1, 'одно': 1,
    'два': 2, 'две': 2,
    'три': 3,
    'четыре': 4,
    'пять': 5,
    'шесть': 6,
    'семь': 7,
    'восемь': 8,
    'девять': 9,
    'десять': 10,
    'одиннадцать': 11,
    'двенадцать': 12,
    'тринадцать': 13,
    'четырнадцать': 14,
    'пятнадцать': 15,
    'шестнадцать': 16,
    'семнадцать': 17,
    'восемнадцать': 18,
    'девятнадцать': 19,
    'двадцать': 20,
    'тридцать': 30,
    'сорок': 40,
    'пятьдесят': 50,
    'шестьдесят': 60,
    'семьдесят': 70,
    'восемьдесят': 80,
    'девяносто': 90,
    'сто': 100,
    'двести': 200,
    'триста': 300,
    'четыреста': 400,
    'пятьсот': 500,
    'шестьсот': 600,
    'семьсот': 700,
    'восемьсот': 800,
    'девятьсот': 900,
    'тысяча': 1000, 'тысячи': 1000, 'тысяч': 1000,
    'миллион': 1000000, 'миллиона': 1000000, 'миллионов': 1000000,
    'миллиард': 1000000000, 'миллиарда': 1000000000, 'миллиардов': 1000000000,
}

SYMBOL_WORDS = {
    'тире': '-',
    'минус': '-',
    'дефис': '-',
    'точка': '.',
    'запятая': ',',
    'плюс': '+',
    'слэш': '/',
    'слеш': '/',
    'дробь': '/',
    'равно': '=',
    'двоеточие': ':',
    'процент': '%',
    'решётка': '#',
    'решетка': '#',
    'звёздочка': '*',
    'звездочка': '*',
    'открывающая': '(',
    'закрывающая': ')',
    'восклицательный': '!',
    'вопросительный': '?',
    'пробел': ' ',
}

SYMBOL_PHRASES = {
    'восклицательный знак': '!',
    'вопросительный знак': '?',
    'открывающая скобка': '(',
    'закрывающая скобка': ')',
}


def _normalize_word(word: str) -> str:
    if word == 'одна':
        return 'один'
    elif word == 'две':
        return 'два'
    return word


def _get_rank(val: int) -> int:
    """Разряд числа: 5=миллиарды, 4=миллионы, 3=тысячи, 2=сотни, 1=десятки, 0=единицы."""
    if val >= 1000000000:
        return 5
    elif val >= 1000000:
        return 4
    elif val >= 1000:
        return 3
    elif val >= 100:
        return 2
    elif val >= 10:
        return 1
    else:
        return 0


def _is_proper_number_sequence(words, start_idx: int, length: int) -> bool:
    """
    Проверяет, является ли последовательность числительных "правильным" составным числом.
    """
    if length <= 1:
        return True

    # Если есть тысячи/миллионы — считаем числом
    for i in range(start_idx, start_idx + length):
        w = _normalize_word(words[i])
        if RUS_NUMBERS[w] >= 1000:
            return True

    prev_rank = 999
    for i in range(start_idx, start_idx + length):
        w = _normalize_word(words[i])
        val = RUS_NUMBERS[w]
        rank = _get_rank(val)

        # Тысячи/миллионы сбрасывают иерархию
        if val >= 1000:
            prev_rank = 999
            continue

        # Повтор разряда (семь → три) — последовательность цифр
        if rank == prev_rank:
            return False

        # Возрастание разряда (единицы → десятки: 7 → 20) — последовательность цифр
        if rank > prev_rank:
            return False

        # Числа 11-19 перед единицами — не грамматически правильное число
        if 11 <= val <= 19 and i + 1 < start_idx + length:
            next_w = _normalize_word(words[i + 1])
            next_val = RUS_NUMBERS[next_w]
            if _get_rank(next_val) == 0:
                return False

        prev_rank = rank

    return True


def _parse_number(words, start_idx: int, max_length: int = None):
    """Парсит "правильную" последовательность числительных как одно число."""
    total = 0
    current = 0
    i = start_idx
    count = 0

    while i < len(words) and (max_length is None or count < max_length):
        word = _normalize_word(words[i])
        if word not in RUS_NUMBERS:
            break
        val = RUS_NUMBERS[word]

        if val >= 1000:
            if current == 0:
                current = 1
            total += current * val
            current = 0
        else:
            current += val

        count += 1
        i += 1

    total += current
    return total, count


def _get_number_sequence_length(words, start_idx: int) -> int:
    """Считает, сколько подряд идёт числительных, начиная с start_idx."""
    i = start_idx
    while i < len(words):
        if _normalize_word(words[i]) not in RUS_NUMBERS:
            break
        i += 1
    return i - start_idx


def _is_digit_or_symbol(token: str) -> bool:
    """Проверяет, что токен состоит только из цифр и/или разрешённых символов."""
    if not token:
        return False
    for ch in token:
        if not (ch.isdigit() or ch in '-.,+=/:%!?#*() '):
            return False
    return True


def convert_spoken_text(text: str) -> str:
    """Преобразует текст с произнесёнными числами и символами в цифровой формат."""
    if not text:
        return text

    words = text.lower().split()
    tokens = []
    i = 0

    while i < len(words):
        # 1. Многословные фразы символов
        matched = False
        for phrase, symbol in SYMBOL_PHRASES.items():
            phrase_words = phrase.split()
            if i + len(phrase_words) <= len(words):
                if words[i:i + len(phrase_words)] == phrase_words:
                    tokens.append(symbol)
                    i += len(phrase_words)
                    matched = True
                    break
        if matched:
            continue

        word = words[i]

        # 2. Однословные символы
        if word in SYMBOL_WORDS:
            tokens.append(SYMBOL_WORDS[word])
            i += 1
            continue

        # 3. Числительные
        test_word = _normalize_word(word)
        if test_word in RUS_NUMBERS:
            seq_len = _get_number_sequence_length(words, i)

            if seq_len == 1:
                tokens.append(str(RUS_NUMBERS[test_word]))
                i += 1
            else:
                # Жадно разбиваем последовательность на числа и цифры
                consumed = 0
                while consumed < seq_len:
                    # Ищем максимальную правильную подпоследовательность
                    sub_len = 0
                    for length in range(seq_len - consumed, 0, -1):
                        if _is_proper_number_sequence(words, i + consumed, length):
                            sub_len = length
                            break

                    if sub_len > 1:
                        number, _ = _parse_number(words, i + consumed, sub_len)
                        tokens.append(str(number))
                        consumed += sub_len
                    else:
                        w = _normalize_word(words[i + consumed])
                        tokens.append(str(RUS_NUMBERS[w]))
                        consumed += 1

                i += seq_len
            continue

        # 4. Обычное слово
        tokens.append(word)
        i += 1

    # Склеиваем цифры и символы без пробелов
    result = []
    for token in tokens:
        if not result:
            result.append(token)
        else:
            if _is_digit_or_symbol(token) and _is_digit_or_symbol(result[-1]):
                result[-1] += token
            else:
                result.append(token)

    return ' '.join(result)