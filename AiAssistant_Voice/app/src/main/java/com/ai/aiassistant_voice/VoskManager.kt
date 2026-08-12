package com.ai.aiassistant_voice

import android.content.Context
import android.util.Log
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.SpeechService
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

/**
 * Менеджер распознавания речи Vosk с буферизацией результатов.
 *
 * Живёт на уровне Application (Singleton) и не пересоздаётся при смене Activity.
 * Модель загружается один раз при старте приложения.
 *
 * Логика работы:
 * 1. startListening() — включает микрофон, накапливает фрагменты в буфере.
 * 2. stopListening() — выключает микрофон, возвращает объединённый текст.
 * 3. Текст отправляется на сервер только при явном вызове stopListening().
 */
class VoskManager(private val context: Context) {
    companion object {
        private const val TAG = "VoskManager"
        private const val ASSET_MODEL_DIR = "model-ru"
        private const val CACHE_MODEL_DIR = "vosk-model"
    }

    private var model: Model? = null
    private var speechService: SpeechService? = null
    private val recognizedTexts = mutableListOf<String>()

    /** Флаг: идёт ли сейчас запись */
    @Volatile
    var isListening = false
        private set

    /** Флаг: модель загружена и готова к работе */
    @Volatile
    var isModelReady = false
        private set

    /** Колбэк при ошибке */
    var onError: ((String) -> Unit)? = null

    /**
     * Загружает модель Vosk из assets во внутреннее хранилище.
     * Вызывается один раз при старте приложения (из App.initVoskModel).
     */
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

    /**
     * Начинает слушать микрофон.
     * Все распознанные фрагменты накапливаются в буфере.
     */
    fun startListening() {
        val m = model
        if (m == null) {
            onError?.invoke("Модель Vosk не загружена")
            return
        }
        recognizedTexts.clear()
        isListening = true

        try {
            Log.d(TAG, "Запуск распознавания речи, буфер очищен")
            val recognizer = Recognizer(m, 16000.0f)
            speechService = SpeechService(recognizer, 16000.0f)

            speechService?.startListening(object : org.vosk.android.RecognitionListener {
                override fun onPartialResult(hypothesis: String?) {}

                override fun onResult(hypothesis: String?) {
                    val text = extractText(hypothesis)
                    if (text.isNotEmpty() && isListening) {
                        Log.d(TAG, "Фрагмент распознан: '$text'")
                        recognizedTexts.add(text)
                    }
                }

                override fun onFinalResult(hypothesis: String?) {
                    val text = extractText(hypothesis)
                    if (text.isNotEmpty() && isListening) {
                        Log.d(TAG, "Финальный фрагмент: '$text'")
                        recognizedTexts.add(text)
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
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка запуска STT: ${e.message}", e)
            isListening = false
            onError?.invoke("Ошибка запуска микрофона: ${e.message}")
        }
    }

    /**
     * Останавливает прослушивание.
     * Возвращает объединённый текст всех распознанных фрагментов.
     */
    fun stopListening(): String {
        Log.d(TAG, "Остановка распознавания, фрагментов в буфере: ${recognizedTexts.size}")
        isListening = false
        speechService?.stop()
        speechService = null

        val result = recognizedTexts.joinToString(" ").trim()
        recognizedTexts.clear()
        Log.d(TAG, "Итоговый текст: '$result'")
        return result
    }

    /** Принудительная остановка (например, при убийстве процесса). */
    fun forceStop() {
        Log.d(TAG, "Принудительная остановка Vosk")
        isListening = false
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
