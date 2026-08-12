package com.ai.aiassistant_voice

import android.util.Log
import okhttp3.*
import com.google.gson.Gson
import java.util.concurrent.TimeUnit

/**
 * Менеджер WebSocket-соединения с сервером.
 * Singleton на уровне Application. Живёт всю сессию приложения.
 */
class WebSocketManager {
    companion object {
        private const val TAG = "WebSocketManager"
    }

    private var client: OkHttpClient? = null
    private var ws: WebSocket? = null
    private val gson = Gson()

    var onConnected: (() -> Unit)? = null
    var onDisconnected: (() -> Unit)? = null
    var onMessage: ((Map<String, Any>) -> Unit)? = null

    /** Возвращает true, если WebSocket в данный момент подключён */
    fun isConnected(): Boolean = ws != null

    fun connect(url: String) {
        if (!url.startsWith("ws://") && !url.startsWith("wss://")) {
            Log.e(TAG, "Некорректный URL: $url")
            SharedLog.append("Ошибка: некорректный URL сервера")
            onDisconnected?.invoke()
            return
        }

        disconnect()

        client = OkHttpClient.Builder()
            .pingInterval(30, TimeUnit.SECONDS)
            .build()

        val request = Request.Builder().url(url).build()

        Log.d(TAG, "Подключение к $url...")
        ws = client?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "Соединение установлено")
                onConnected?.invoke()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Получено сообщение: $text")
                try {
                    @Suppress("UNCHECKED_CAST")
                    val data = gson.fromJson(text, Map::class.java) as Map<String, Any>
                    onMessage?.invoke(data)
                } catch (e: Exception) {
                    Log.e(TAG, "Ошибка парсинга JSON: ${e.message}")
                    SharedLog.append("Ошибка парсинга JSON: ${e.message}")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "Соединение закрывается: $reason")
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "Соединение закрыто")
                ws = null
                onDisconnected?.invoke()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "Ошибка соединения: ${t.message}")
                SharedLog.append("Ошибка соединения: ${t.message}")
                ws = null
                onDisconnected?.invoke()
            }
        })
    }

    fun send(data: Map<String, Any>) {
        val json = gson.toJson(data)
        Log.d(TAG, "Отправка: $json")
        ws?.send(json)
    }

    fun disconnect() {
        Log.d(TAG, "Отключение...")
        ws?.close(1000, "Client disconnect")
        client?.dispatcher?.executorService?.shutdown()
        ws = null
        client = null
    }
}
