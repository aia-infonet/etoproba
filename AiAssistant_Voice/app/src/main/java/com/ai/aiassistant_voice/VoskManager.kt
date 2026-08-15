package com.ai.aiassistant_voice

import android.content.Context
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.SpeechService
import org.vosk.android.RecognitionListener
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

/**
 * Менеджер распознавания речи Vosk с буферизацией результатов.
 *
 * Версия 2.3: исправлен таймер тишины.
 *   - 10 секунд на первое слово (чтобы пользователь успел подготовиться)
 *   - 2 секунды паузы после последнего распознанного слова
 *   - Защита от повторного создания SpeechService
 */
class VoskManager(private val context: Context) {
    companion object {
        private const val TAG = "VoskManager"
        private const val ASSET_MODEL_DIR = "model-ru"
        private const val CACHE_MODEL_DIR = "vosk-model"
        private const val SILENCE_TIMEOUT_MS = 2000L      // пауза после речи
        private const val FIRST_WORD_TIMEOUT_MS = 10000L  // время на первое слово
        private const val TIMER_INTERVAL_MS = 500L        // интервал проверки
    }

    private var model: Model? = null
    private var speechService: SpeechService? = null
    private val recognizedTexts = mutableListOf<String>()

    private val handler = Handler(Looper.getMainLooper())
    private var silenceRunnable: Runnable? = null
    private var lastSpeechTime = 0L
    private var firstResultReceived = false
    private var onResultCallback: ((String) -> Unit)? = null

    @Volatile
    var isListening = false
        private set

    @Volatile
    var isModelReady = false
        private set

    var onError: ((String) -> Unit)? = null

    fun initModel(onReady: () -> Unit) {
        if (isModelReady) {
            onReady()
            return
        }
        try {
            Log.d(TAG, "Начало загрузки модели Vosk...")
            val targetDir = File(context.filesDir, CACHE_MODEL_DIR)
            val uuidFile = File(targetDir, "uuid")

            if (!targetDir.exists() || !uuidFile.exists()) {
                Log.d(TAG, "Копирование модели из assets в $targetDir")
                copyAssetsDir(ASSET_MODEL_DIR, targetDir)
            } else {
                Log.d(TAG, "Модель уже скопирована, пропускаем")
            }

            if (!uuidFile.exists()) {
                throw IOException("Файл uuid не найден после копирования")
            }

            Log.d(TAG, "Загрузка модели из $targetDir")
            model = Model(targetDir.absolutePath)
            isModelReady = true
            Log.d(TAG, "Модель Vosk успешно загружена")
            onReady()

        } catch (e: Exception) {
            Log.e(TAG, "Критическая ошибка Vosk: ${e.message}", e)
            onError?.invoke("Ошибка загрузки модели Vosk: ${e.message}")
        }
    }

    private fun hasRecordPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context, android.Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Начинает слушать микрофон.
     *
     * @param onResult Callback с финальным текстом. Если null — ручной режим.
     */
    fun startListening(onResult: ((String) -> Unit)? = null) {
        val m = model
        if (m == null) {
            onError?.invoke("Модель Vosk не загружена")
            return
        }

        if (!hasRecordPermission()) {
            onError?.invoke("Нет разрешения на запись аудио")
            return
        }

        if (isListening) {
            stopListening()
        }

        onResultCallback = onResult
        recognizedTexts.clear()
        lastSpeechTime = System.currentTimeMillis()
        firstResultReceived = false
        isListening = true

        try {
            Log.d(TAG, "Запуск распознавания речи")
            val recognizer = Recognizer(m, 16000.0f)
            speechService = SpeechService(recognizer, 16000.0f)

            speechService?.startListening(object : RecognitionListener {
                override fun onPartialResult(hypothesis: String?) {}

                override fun onResult(hypothesis: String?) {
                    val text = extractText(hypothesis)
                    if (text.isNotEmpty() && isListening) {
                        Log.d(TAG, "Фрагмент: '$text'")
                        recognizedTexts.add(text)
                        lastSpeechTime = System.currentTimeMillis()
                        if (!firstResultReceived) {
                            firstResultReceived = true
                            Log.d(TAG, "Первое слово получено, переключаемся на короткий таймаут")
                        }
                    }
                }

                override fun onFinalResult(hypothesis: String?) {
                    val text = extractText(hypothesis)
                    if (text.isNotEmpty() && isListening) {
                        Log.d(TAG, "Финал: '$text'")
                        recognizedTexts.add(text)
                        lastSpeechTime = System.currentTimeMillis()
                        if (!firstResultReceived) {
                            firstResultReceived = true
                        }
                    }
                }

                override fun onError(exception: Exception?) {
                    Log.e(TAG, "Ошибка распознавания: ${exception?.message}")
                    if (isListening) {
                        onError?.invoke("Ошибка распознавания: ${exception?.message}")
                    }
                }

                override fun onTimeout() {
                    Log.d(TAG, "Таймаут распознавания")
                }
            })

            if (onResult != null) {
                startSilenceTimer()
            }

        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException", e)
            onError?.invoke("Ошибка: нет разрешения на запись аудио")
            isListening = false
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка запуска STT: ${e.message}", e)
            isListening = false
            onError?.invoke("Ошибка запуска микрофона: ${e.message}")
        }
    }

    fun stopListening(): String {
        Log.d(TAG, "Остановка, фрагментов: ${recognizedTexts.size}")
        isListening = false
        stopSilenceTimer()
        speechService?.stop()
        speechService = null

        val result = recognizedTexts.joinToString(" ").trim()
        recognizedTexts.clear()
        Log.d(TAG, "Итог: '$result'")
        return result
    }

    fun forceStop() {
        Log.d(TAG, "Принудительная остановка")
        isListening = false
        stopSilenceTimer()
        recognizedTexts.clear()
        speechService?.stop()
        speechService = null
    }

    private fun extractText(hypothesis: String?): String {
        if (hypothesis == null) return ""
        return try {
            org.json.JSONObject(hypothesis).optString("text", "").trim()
        } catch (e: Exception) {
            ""
        }
    }

    /**
     * Таймер тишины:
     * - До первого слова: ждем FIRST_WORD_TIMEOUT_MS (10 сек)
     * - После первого слова: ждем SILENCE_TIMEOUT_MS (2 сек) паузы
     */
    private fun startSilenceTimer() {
        silenceRunnable = Runnable {
            if (!isListening) return@Runnable

            val elapsed = System.currentTimeMillis() - lastSpeechTime
            val timeout = if (firstResultReceived) SILENCE_TIMEOUT_MS else FIRST_WORD_TIMEOUT_MS

            if (elapsed >= timeout) {
                val text = stopListening()
                handler.post {
                    onResultCallback?.invoke(text)
                }
            } else {
                handler.postDelayed(silenceRunnable!!, TIMER_INTERVAL_MS)
            }
        }
        handler.postDelayed(silenceRunnable!!, TIMER_INTERVAL_MS)
    }

    private fun stopSilenceTimer() {
        silenceRunnable?.let { handler.removeCallbacks(it) }
        silenceRunnable = null
    }

    private fun copyAssetsDir(assetPath: String, targetDir: File) {
        val assetManager = context.assets
        val files = assetManager.list(assetPath)
            ?: throw IOException("Не удалось получить список файлов в assets/$assetPath")

        if (files.isEmpty()) {
            copyAssetFile(assetPath, targetDir)
            return
        }

        targetDir.mkdirs()

        for (fileName in files) {
            val assetFilePath = "$assetPath/$fileName"
            val outFile = File(targetDir, fileName)
            val subFiles = assetManager.list(assetFilePath)
            if (subFiles != null && subFiles.isNotEmpty()) {
                copyAssetsDir(assetFilePath, outFile)
            } else {
                copyAssetFile(assetFilePath, outFile)
            }
        }
    }

    private fun copyAssetFile(assetPath: String, target: File) {
        val outFile = if (target.isDirectory) {
            File(target, assetPath.substringAfterLast("/"))
        } else {
            target.parentFile?.mkdirs()
            target
        }
        context.assets.open(assetPath).use { input ->
            FileOutputStream(outFile).use { output ->
                input.copyTo(output)
            }
        }
    }
}