"""
Утилиты для синтеза речи через Silero TTS.
Версия 2.1: улучшенное логирование, защита от пустого текста,
корректная работа с тензорами, детальная диагностика ошибок.
ВАЖНО: у модели v5_ru.pt нет метода .eval() — не добавлять!
"""
import torch
import sounddevice as sd
import threading
import re
import logging

from utils.number_to_words import preprocess_text

logger = logging.getLogger("SileroTTS")


class SileroTTS:
    """
    Класс для синтеза и воспроизведения речи.
    Перед синтезом автоматически заменяет числа на русские числительные.
    """
    def __init__(self, model_path: str, device: str = "cpu"):
        """
        Инициализация модели Silero TTS.
        """
        self.device = torch.device(device)
        logger.info(f"Загрузка модели Silero из {model_path} на устройство {device}")
        self.model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
        # НЕ вызываем .eval() — у модели v5_ru.pt этого метода нет!
        self.sample_rate = 48000
        self.speaker = "xenia"
        self._stop_event = threading.Event()
        self._play_thread = None
        logger.info("Silero TTS инициализирован успешно")

    def speak(self, text: str):
        """
        Синтезирует текст в речь и воспроизводит.
        Перед синтезом заменяет числа на слова.
        """
        logger.info(f"speak() вызван, исходный текст ({len(text)} симв.): {text[:120]}...")

        self.stop()
        self._stop_event.clear()

        processed_text = preprocess_text(text)
        logger.info(f"После preprocess_text ({len(processed_text)} симв.): {processed_text[:120]}...")

        if not processed_text or not processed_text.strip():
            logger.error("Текст для озвучивания пустой после preprocess_text!")
            return

        def _play():
            try:
                chunks = self._split_text(processed_text, max_len=800)
                logger.info(f"Текст разбит на {len(chunks)} чанков")

                for i, chunk in enumerate(chunks):
                    if self._stop_event.is_set():
                        logger.info("Воспроизведение прервано по stop_event")
                        return

                    chunk_stripped = chunk.strip()
                    if not chunk_stripped:
                        logger.warning(f"Чанк {i+1} пустой, пропускаем")
                        continue

                    logger.info(f"Синтез чанка {i+1}/{len(chunks)} ({len(chunk_stripped)} симв.)")

                    audio = self.model.apply_tts(
                        text=chunk_stripped,
                        speaker=self.speaker,
                        sample_rate=self.sample_rate
                    )

                    if self._stop_event.is_set():
                        logger.info("Воспроизведение прервано после синтеза")
                        return

                    if audio.is_cuda:
                        audio = audio.cpu()
                    audio_np = audio.numpy()

                    logger.info(f"Аудио сгенерировано: {len(audio_np)} сэмплов, {len(audio_np)/self.sample_rate:.2f} сек")

                    sd.play(audio_np, self.sample_rate)
                    sd.wait()
                    logger.info(f"Чанк {i+1}/{len(chunks)} воспроизведен")

                logger.info("Все чанки воспроизведены успешно")

            except Exception as e:
                logger.error(f"ОШИБКА в потоке воспроизведения: {e}", exc_info=True)

        self._play_thread = threading.Thread(target=_play, daemon=True)
        self._play_thread.start()
        logger.info("Поток воспроизведения запущен")

    def stop(self):
        """Останавливает текущее воспроизведение."""
        logger.info("stop() вызван")
        self._stop_event.set()
        sd.stop()
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=2.0)
            if self._play_thread.is_alive():
                logger.warning("Поток воспроизведения не завершился за 2 сек")
        self._play_thread = None

    def _split_text(self, text: str, max_len: int = 800) -> list:
        """
        Разбивает текст на части по границам предложений.
        """
        if len(text) <= max_len:
            return [text]

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) > max_len:
                if current:
                    chunks.append(current.strip())
                    current = ""
                for i in range(0, len(sentence), max_len):
                    chunks.append(sentence[i:i + max_len])
                continue

            if len(current) + len(sentence) + 1 <= max_len:
                current += " " + sentence if current else sentence
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence

        if current:
            chunks.append(current.strip())

        return chunks if chunks else [text]