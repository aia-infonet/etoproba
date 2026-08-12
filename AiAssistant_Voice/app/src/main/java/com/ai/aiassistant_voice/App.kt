package com.ai.aiassistant_voice

import android.app.Application
import android.util.Log

/**
 * Глобальный контекст приложения.
 * Хранит WebSocketManager и VoskManager как Singleton на уровне процесса.
 * Оба менеджера живут от запуска приложения до его убийства системой.
 */
class App : Application() {
    companion object {
        lateinit var instance: App
            private set
        private const val TAG = "App"
    }

    /** Единственный экземпляр WebSocketManager на всю сессию */
    val webSocketManager = WebSocketManager()

    /** Единственный экземпляр VoskManager на всю сессию */
    lateinit var voskManager: VoskManager
        private set

    /** Флаг: модель Vosk загружена и готова к работе */
    @Volatile
    var isVoskReady = false
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        voskManager = VoskManager(this)
        Log.d(TAG, "Application создан, менеджеры инициализированы")
    }

    /**
     * Загружает модель Vosk в фоновом потоке.
     * Вызывается из MainActivity при старте приложения.
     * Если модель уже загружена — сразу вызывает onReady.
     *
     * ВАЖНО: onReady вызывается в фоновом потоке!
     *        Для обновления UI оборачивайте вызов в runOnUiThread в Activity.
     */
    fun initVoskModel(onReady: () -> Unit) {
        if (isVoskReady) {
            onReady()
            return
        }
        Thread {
            voskManager.initModel {
                isVoskReady = true
                onReady()
            }
        }.start()
    }
}
