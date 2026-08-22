package com.ai.aiassistant_voice

import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData

/**
 * Singleton для хранения общих логов всех экранов.
 * Использует LiveData, чтобы автоматически обновлять UI при добавлении записи.
 */
object SharedLog {
    private val _logs = MutableLiveData<StringBuilder>(StringBuilder())
    val logs: LiveData<StringBuilder> = _logs

    /**
     * Добавляет строку в лог.
     * Каждое сообщение начинается с новой строки (настоящий символ перевода строки).
     */
    fun append(message: String) {
        val current = _logs.value ?: StringBuilder()
        current.append(message).append('\n')
        _logs.postValue(current)
    }

    fun clear() {
        _logs.postValue(StringBuilder())
    }
}
