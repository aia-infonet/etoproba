"""
Утилиты для синтеза речи через Silero TTS.
Модель v5_ru.pt загружается локально из папки silero/.
Поддерживает озвучивание длинных текстов (автоматическое разбиение на части).
"""
import torch
import sounddevice as sd
import threading
import re

class SileroTTS:
    """
    Класс для синтеза и воспроизведения речи.
    Работает в отдельном потоке, чтобы не блокировать основной event loop.
    """
    def __init__(self, model_path: str, device: str = 'cpu'):
        """
        Инициализация модели Silero TTS.
        
        Args:
            model_path: Путь к файлу v5_ru.pt
            device: 'cpu' или 'cuda' (если есть GPU)
        """
        self.device = torch.device(device)
        self.model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
        self.model.to(self.device)
        
        self.sample_rate = 48000
        self.speaker = 'xenia'
        
        self._stop_event = threading.Event()
        self._play_thread = None
        
    def speak(self, text: str):
        """
        Синтезирует текст в речь и воспроизводит.
        Для длинных текстов автоматически разбивает на части.
        
        Args:
            text: Текст для озвучивания
        """
        self.stop()
        self._stop_event.clear()
        
        def _play():
            try:
                # Разбиваем длинный текст на части по ~800 символов
                chunks = self._split_text(text, max_len=800)
                for chunk in chunks:
                    if self._stop_event.is_set():
                        return
                    audio = self.model.apply_tts(
                        text=chunk,
                        speaker=self.speaker,
                        sample_rate=self.sample_rate
                    )
                    if self._stop_event.is_set():
                        return
                    sd.play(audio.numpy(), self.sample_rate)
                    sd.wait()
            except Exception as e:
                print(f"[SileroTTS] Ошибка воспроизведения: {e}")
        
        self._play_thread = threading.Thread(target=_play, daemon=True)
        self._play_thread.start()
        
    def stop(self):
        """Останавливает текущее воспроизведение."""
        self._stop_event.set()
        sd.stop()
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)
    
    def _split_text(self, text: str, max_len: int = 800) -> list:
        """
        Разбивает текст на части по границам предложений,
        чтобы каждая часть не превышала max_len символов.
        
        Args:
            text: Исходный текст
            max_len: Максимальная длина одной части
            
        Returns:
            Список строк-чанков
        """
        if len(text) <= max_len:
            return [text]
        
        # Разбиваем по предложениям (точка/воскл/вопр + пробел/конец строки)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            # Если одно предложение длиннее max_len — разрезаем принудительно
            if len(sentence) > max_len:
                if current:
                    chunks.append(current.strip())
                    current = ""
                # Режем кусками по max_len
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
