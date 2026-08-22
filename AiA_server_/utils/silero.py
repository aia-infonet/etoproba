"""
Модуль Silero TTS (Text-to-Speech).
Загружает модель Silero и предоставляет метод speak() для озвучивания текста.
Воспроизведение выполняется в отдельном потоке, чтобы не блокировать основной.

Версия 3.3: добавлены on_start / on_end callbacks + num2words для озвучивания чисел.
"""
import logging
import re
import threading
import warnings
import numpy as np
import sounddevice as sd
import torch

logger = logging.getLogger("SileroTTS")

# === num2words для русского языка (0 - 999 999) ===

def _num_to_words_0_999(n: int) -> str:
    """Преобразует число 0-999 в русские слова."""
    ONES = [
        "", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять",
        "десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
        "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"
    ]
    TENS = [
        "", "", "двадцать", "тридцать", "сорок", "пятьдесят",
        "шестьдесят", "семьдесят", "восемьдесят", "девяносто"
    ]
    HUNDREDS = [
        "", "сто", "двести", "триста", "четыреста", "пятьсот",
        "шестьсот", "семьсот", "восемьсот", "девятьсот"
    ]

    if n == 0:
        return ""

    parts = []
    h = n // 100
    if h > 0:
        parts.append(HUNDREDS[h])

    r = n % 100
    if 0 < r < 20:
        parts.append(ONES[r])
    elif r >= 20:
        t = r // 10
        o = r % 10
        parts.append(TENS[t])
        if o > 0:
            parts.append(ONES[o])

    return " ".join(parts)


def _thousands_form(n: int) -> str:
    """Возвращает правильную форму слова 'тысяча' для числа n (1-999)."""
    if 11 <= n % 100 <= 19:
        return "тысяч"
    last = n % 10
    if last == 1:
        return "тысяча"
    elif 2 <= last <= 4:
        return "тысячи"
    else:
        return "тысяч"


def _num_to_words_ru(n: int) -> str:
    """Преобразует число 0-999999 в русские слова."""
    if n == 0:
        return "ноль"
    if n < 0:
        return "минус " + _num_to_words_ru(-n)

    parts = []

    thousands = n // 1000
    if thousands > 0:
        words = _num_to_words_0_999(thousands)
        # Заменяем "один" → "одна", "два" → "две" только как целые слова
        words = re.sub(r'\bодин\b', 'одна', words)
        words = re.sub(r'\bдва\b', 'две', words)
        form = _thousands_form(thousands)
        parts.append(f"{words} {form}")

    remainder = n % 1000
    if remainder > 0:
        parts.append(_num_to_words_0_999(remainder))

    return " ".join(parts)


def num2words(text: str) -> str:
    """Заменяет все числа в тексте на их словесное представление."""
    def replace_num(match):
        num_str = match.group()
        try:
            num = int(num_str)
            if 0 <= num <= 999999:
                return _num_to_words_ru(num)
            else:
                return " ".join(_num_to_words_ru(int(d)) if d != "0" else "ноль" for d in num_str)
        except ValueError:
            return num_str

    return re.sub(r'\b\d+\b', replace_num, text)
# ==================================================


class SileroTTS:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.sample_rate = 48000
        self._thread = None
        self._stop_event = threading.Event()
        self.on_start = None   # callback(text: str) — перед началом
        self.on_end = None     # callback(text: str) — после окончания

        logger.info(f"Загрузка модели Silero TTS из {model_path}")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
            self.model.to(torch.device('cpu'))
            logger.info("Модель Silero TTS загружена")
        except Exception as e:
            logger.error(f"Ошибка загрузки модели Silero: {e}")
            raise

    def speak(self, text: str):
        """Озвучить текст. Воспроизведение в фоновом потоке."""
        if not text or not text.strip():
            logger.warning("Пустой текст для TTS, пропускаем")
            return

        if self._thread and self._thread.is_alive():
            logger.info("Предыдущее воспроизведение активно, останавливаем")
            self.stop()

        self._stop_event.clear()

        # === Преобразуем числа в слова перед озвучиванием ===
        text_for_tts = num2words(text)
        logger.info(f"TTS текст: '{text[:60]}...' → '{text_for_tts[:60]}...'")
        # ==================================================

        # Сигнализируем о начале (исходный текст для логов)
        if self.on_start:
            try:
                self.on_start(text)
            except Exception as e:
                logger.error(f"on_start callback error: {e}")

        self._thread = threading.Thread(target=self._play, args=(text_for_tts,), daemon=True)
        self._thread.start()
        logger.info(f"TTS запущен: '{text[:80]}...'")

    def _play(self, text: str):
        try:
            logger.info(f"Генерация аудио для: '{text[:80]}...'")
            audio = self.model.apply_tts(
                text=text,
                speaker="baya",
                sample_rate=self.sample_rate
            )

            if self._stop_event.is_set():
                logger.info("TTS остановлен до воспроизведения")
                return

            audio_np = audio.numpy() if hasattr(audio, 'numpy') else np.array(audio)
            sd.play(audio_np, self.sample_rate)
            sd.wait()
            logger.info("TTS воспроизведение завершено")

        except Exception as e:
            logger.error(f"Ошибка TTS: {e}")
        finally:
            # Сигнализируем о завершении
            if self.on_end:
                try:
                    self.on_end(text)
                except Exception as e:
                    logger.error(f"on_end callback error: {e}")

    def stop(self):
        """Остановить текущее воспроизведение."""
        logger.info("Остановка TTS...")
        self._stop_event.set()
        sd.stop()
        if self._thread:
            self._thread.join(timeout=1)
            if self._thread.is_alive():
                logger.warning("Поток TTS не завершился за 1 сек")