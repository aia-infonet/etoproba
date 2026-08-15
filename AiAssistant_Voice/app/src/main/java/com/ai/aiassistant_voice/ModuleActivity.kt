package com.ai.aiassistant_voice

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.Observer

/**
 * Второй экран: кнопки команд модуля, справка, логи, управление Vosk STT.
 *
 * Версия 3.4: добавлена команда "Заказ" в модуль "work".
 * Поддерживает интерактивный протокол zakaz_prompt / zakaz_done.
 */
class ModuleActivity : AppCompatActivity() {
    companion object {
        private const val TAG = "ModuleActivity"
    }

    private lateinit var tvModuleName: TextView
    private lateinit var tvHelp: TextView
    private lateinit var llCommandsContainer: LinearLayout
    private lateinit var tvLogs: TextView
    private lateinit var scrollLogs: ScrollView
    private lateinit var tvCommandStatus: TextView

    private lateinit var moduleId: String
    private lateinit var moduleName: String
    private lateinit var helpText: String
    private lateinit var serverIp: String

    private val wsManager by lazy { App.instance.webSocketManager }
    private val voskManager by lazy { App.instance.voskManager }

    private var currentState = "idle"
    private var activeCommandName: String = ""
    private var idleLabel: String = ""
    private var activeButton: Button? = null
    private var streamingBuffer = StringBuilder()

    /**
     * Конфигурация команд по модулям.
     */
    private val moduleCommands = mapOf(
        "command_user" to listOf(
            Pair("Начать запись голосом", "voice_rec"),
            Pair("Лунный день", "moon_day"),
            Pair("Перескажи", "resume")
        ),
        "dialog" to listOf(
            Pair("Записки : начать запись", "record"),
            Pair("Запрос : начать запись", "request")
        ),
        "work" to listOf(
            Pair("Заказ", "zakaz")
        )
    )

    /** Мгновенные команды с кнопкой "Стоп"/"Отмена" для TTS */
    private val instantCommands = setOf("moon_day", "resume", "zakaz")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate начат")
        try {
            setContentView(R.layout.activity_module)
            Log.d(TAG, "setContentView выполнен")
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка setContentView: ${e.message}", e)
            Toast.makeText(this, "Ошибка загрузки интерфейса: ${e.message}", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        moduleId = intent.getStringExtra("module_id") ?: ""
        moduleName = intent.getStringExtra("module_name") ?: ""
        helpText = intent.getStringExtra("help_text") ?: ""
        serverIp = intent.getStringExtra("server_ip") ?: ""

        Log.d(TAG, "Параметры: moduleId=$moduleId, moduleName=$moduleName, serverIp=$serverIp")

        if (serverIp.isEmpty()) {
            Log.e(TAG, "IP сервера пустой!")
            Toast.makeText(this, "IP сервера не указан", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        try {
            initViews()
            Log.d(TAG, "initViews выполнен")
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка initViews: ${e.message}", e)
            Toast.makeText(this, "Ошибка инициализации: ${e.message}", Toast.LENGTH_LONG).show()
            finish()
            return
        }

        setupListeners()
        createCommandButtons()
        Log.d(TAG, "setupListeners + createCommandButtons выполнены")

        try {
            setupWebSocket()
            Log.d(TAG, "setupWebSocket выполнен")
        } catch (e: Exception) {
            Log.e(TAG, "Ошибка WebSocket: ${e.message}", e)
            SharedLog.append("Ошибка WebSocket: ${e.message}")
            tvCommandStatus.text = "Ошибка подключения"
        }

        setupVoskCallbacks()
        Log.d(TAG, "setupVoskCallbacks выполнен")
        observeLogs()
        Log.d(TAG, "onCreate завершен")
    }

    override fun onResume() {
        super.onResume()
        Log.d(TAG, "onResume")
        setupWebSocketCallbacks()
        setupVoskCallbacks()
    }

    override fun onPause() {
        super.onPause()
        Log.d(TAG, "onPause, currentState=$currentState")
        when (currentState) {
            "recording" -> {
                Log.d(TAG, "Автоматическое завершение записи при уходе с экрана")
                finishRecording()
            }
            "playing" -> {
                if (activeCommandName in instantCommands) {
                    if (activeCommandName == "zakaz") {
                        Log.d(TAG, "Автоматическая отмена zakaz при уходе с экрана")
                        wsManager.send(mapOf(
                            "type" to "command",
                            "module" to moduleId,
                            "command" to "zakaz",
                            "text" to "__CANCEL__"
                        ))
                    } else {
                        wsManager.send(mapOf("type" to "stop_tts"))
                    }
                    currentState = "idle"
                    restoreButtonState()
                }
            }
        }
    }

    private fun initViews() {
        tvModuleName = findViewById(R.id.tvModuleName)
        tvHelp = findViewById(R.id.tvHelp)
        llCommandsContainer = findViewById(R.id.llCommandsContainer)
        tvLogs = findViewById(R.id.tvLogs)
        scrollLogs = findViewById(R.id.scrollLogs)
        tvCommandStatus = findViewById(R.id.tvCommandStatus)
        tvModuleName.text = moduleName
    }

    private fun setupListeners() {
        tvHelp.setOnClickListener {
            startActivity(Intent(this, HelpActivity::class.java).apply {
                putExtra("module_name", moduleName)
                putExtra("help_text", helpText)
            })
        }
    }

    private fun createCommandButtons() {
        llCommandsContainer.removeAllViews()
        val commands = moduleCommands[moduleId] ?: return

        if (commands.isEmpty()) {
            val tvEmpty = TextView(this)
            tvEmpty.text = "В этом модуле пока нет команд."
            tvEmpty.textSize = 16f
            tvEmpty.setTextColor(ContextCompat.getColor(this, android.R.color.darker_gray))
            val params = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            params.topMargin = 32
            tvEmpty.layoutParams = params
            llCommandsContainer.addView(tvEmpty)
            return
        }

        for ((label, cmdName) in commands) {
            val btn = Button(this)
            btn.text = label
            btn.isAllCaps = false
            btn.setTextColor(ContextCompat.getColor(this, android.R.color.white))
            btn.setBackgroundColor(ContextCompat.getColor(this, android.R.color.holo_blue_dark))

            val params = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            params.topMargin = 16
            btn.layoutParams = params

            btn.setOnClickListener { onCommandButtonClick(cmdName, label, btn) }
            llCommandsContainer.addView(btn)
        }
    }

    private fun onCommandButtonClick(commandName: String, label: String, button: Button) {
        Log.d(TAG, "Нажата кнопка команды=$commandName, currentState=$currentState")

        // --- Мгновенные команды с поддержкой "Стоп"/"Отмена" ---
        if (commandName in instantCommands) {
            when (currentState) {
                "idle" -> {
                    activeCommandName = commandName
                    idleLabel = label
                    activeButton = button
                    currentState = "playing"
                    button.text = if (commandName == "zakaz") "Отмена" else "Стоп"
                    tvCommandStatus.text = "Обработка..."

                    if (commandName == "zakaz") {
                        sendInstantCommand(commandName)
                    } else {
                        sendInstantCommand(commandName)
                    }
                    return
                }
                "playing" -> {
                    if (activeCommandName == commandName) {
                        if (commandName == "zakaz") {
                            // Отправляем отмену на сервер
                            wsManager.send(mapOf(
                                "type" to "command",
                                "module" to moduleId,
                                "command" to "zakaz",
                                "text" to "__CANCEL__"
                            ))
                            currentState = "idle"
                            restoreButtonState()
                            tvCommandStatus.text = "Отменено"
                        } else {
                            stopPlayback()
                        }
                    } else {
                        Toast.makeText(this, "Сначала остановите текущее действие", Toast.LENGTH_SHORT).show()
                    }
                    return
                }
            }
        }

        when (currentState) {
            "idle" -> startCommand(commandName, label, button)
            "recording" -> {
                if (activeCommandName == commandName) {
                    finishRecording()
                } else {
                    Toast.makeText(this, "Сначала завершите текущую запись", Toast.LENGTH_SHORT).show()
                }
            }
            "playing" -> {
                if (activeCommandName == commandName) {
                    stopPlayback()
                }
            }
        }
    }

    private fun setupVoskCallbacks() {
        voskManager.onError = { error ->
            runOnUiThread {
                SharedLog.append("STT ошибка: $error")
                if (currentState == "recording") {
                    currentState = "idle"
                    restoreButtonState()
                    tvCommandStatus.text = "Ошибка распознавания"
                }
            }
        }
    }

    private fun setupWebSocket() {
        if (!wsManager.isConnected()) {
            val url = "ws://$serverIp:8000/ws"
            Log.d(TAG, "WebSocket не подключен, подключаемся к $url")
            SharedLog.append("Подключение к серверу $url...")
            wsManager.connect(url)
        } else {
            Log.d(TAG, "WebSocket уже подключен")
            SharedLog.append("Сервер уже подключен")
        }
        setupWebSocketCallbacks()
    }

    private fun setupWebSocketCallbacks() {
        wsManager.onConnected = {
            runOnUiThread {
                Log.d(TAG, "WebSocket подключен")
                SharedLog.append("Подключено к серверу")
                tvCommandStatus.text = "Подключено"
            }
        }
        wsManager.onDisconnected = {
            runOnUiThread {
                Log.d(TAG, "WebSocket отключен")
                SharedLog.append("Отключено от сервера")
                tvCommandStatus.text = "Отключено"
            }
        }
        wsManager.onMessage = { data ->
            runOnUiThread {
                Log.d(TAG, "Сообщение от сервера: $data")
                when (data["type"] as? String) {
                    "stream_chunk" -> {
                        val chunk = data["text"] as? String ?: ""
                        streamingBuffer.append(chunk)
                        tvCommandStatus.text = "Генерация: ${streamingBuffer}"
                    }
                    "stream_end" -> {
                        val fullText = data["text"] as? String ?: ""
                        streamingBuffer.clear()
                        SharedLog.append("Ответ: $fullText")
                        if (activeCommandName == "voice_rec") {
                            currentState = "playing"
                            activeButton?.text = "Стоп"
                            tvCommandStatus.text = "Озвучивание..."
                        } else {
                            currentState = "idle"
                            restoreButtonState()
                            tvCommandStatus.text = "Готово"
                        }
                    }
                    "response" -> {
                        streamingBuffer.clear()
                        val responseText = data["text"] as? String ?: ""
                        SharedLog.append("Ответ: $responseText")
                        if (activeCommandName == "voice_rec") {
                            currentState = "playing"
                            activeButton?.text = "Стоп"
                            tvCommandStatus.text = "Озвучивание..."
                        } else if (activeCommandName in instantCommands) {
                            tvCommandStatus.text = "Озвучивание..."
                        } else {
                            tvCommandStatus.text = "Готово"
                        }
                    }
                    // === ИНТЕРАКТИВНЫЙ ЗАКАЗ ===
                    "zakaz_prompt" -> {
                        val promptText = data["text"] as? String ?: ""
                        val col = data["col"] as? Int ?: 0
                        val total = data["total"] as? Int ?: 0
                        tvCommandStatus.text = "[$col/$total] Скажите: $promptText"
                        SharedLog.append("Заказ [$col/$total]: $promptText")

                        // Автоматически запускаем Vosk с callback
                        if (App.instance.isVoskReady) {
                            startAutoListeningForZakaz()
                        } else {
                            Toast.makeText(this, "Vosk не готов", Toast.LENGTH_SHORT).show()
                        }
                    }
                    "zakaz_done" -> {
                        val msg = data["message"] as? String ?: "Готово"
                        SharedLog.append("Заказ: $msg")
                        tvCommandStatus.text = msg
                        currentState = "idle"
                        restoreButtonState()
                    }
                    // ===========================
                    "status" -> {
                        val msg = data["message"] as? String ?: ""
                        tvCommandStatus.text = msg
                        SharedLog.append("Статус: $msg")
                        if (msg.contains("сохранена") || msg.contains("сохранен")) {
                            currentState = "idle"
                            restoreButtonState()
                            tvCommandStatus.text = "Готово"
                        }
                    }
                    "error" -> {
                        streamingBuffer.clear()
                        val msg = data["message"] as? String ?: "Ошибка"
                        SharedLog.append("Ошибка сервера: $msg")
                        if (currentState != "recording") {
                            currentState = "idle"
                            restoreButtonState()
                        }
                        tvCommandStatus.text = "Ошибка: $msg"
                    }
                }
            }
        }
    }

    /**
     * Автоматически запускает Vosk для команды Zakaz.
     * При получении результата автоматически отправляет на сервер.
     * Остановка по тишине 2 секунды (реализовано в VoskManager).
     */
    private fun startAutoListeningForZakaz() {
        currentState = "recording"
        tvCommandStatus.text = "Слушаю..."

        voskManager.startListening { recognizedText ->
            runOnUiThread {
                if (recognizedText.isBlank()) {
                    SharedLog.append("Zakaz: ничего не распознано")
                    tvCommandStatus.text = "Не распознано, повторите..."
                    // Перезапускаем слушание
                    Handler(Looper.getMainLooper()).postDelayed({
                        if (activeCommandName == "zakaz" && currentState != "idle") {
                            startAutoListeningForZakaz()
                        }
                    }, 500)
                    return@runOnUiThread
                }

                SharedLog.append("Zakaz распознано: $recognizedText")
                currentState = "playing"
                tvCommandStatus.text = "Обработка..."

                // Отправляем на сервер
                wsManager.send(mapOf(
                    "type" to "command",
                    "module" to "work",
                    "command" to "zakaz",
                    "text" to recognizedText
                ))
            }
        }
    }

    private fun sendInstantCommand(commandName: String) {
        Log.d(TAG, "Мгновенная команда: $commandName")
        SharedLog.append("Выполнение команды: $commandName")

        wsManager.send(mapOf(
            "type" to "command",
            "module" to moduleId,
            "command" to commandName,
            "text" to ""
        ))
    }

    private fun startCommand(commandName: String, label: String, button: Button) {
        if (!App.instance.isVoskReady) {
            Log.w(TAG, "Модель Vosk еще не загружена")
            Toast.makeText(this, "Модель Vosk загружается, подождите...", Toast.LENGTH_SHORT).show()
            return
        }
        currentState = "recording"
        activeCommandName = commandName
        idleLabel = label
        activeButton = button
        button.text = "Закончить запись"
        tvCommandStatus.text = "Слушаю..."
        SharedLog.append("Начато распознавание речи [$commandName]")

        voskManager.startListening()
    }

    private fun finishRecording() {
        Log.d(TAG, "Завершение записи")
        tvCommandStatus.text = "Обработка..."

        val text = voskManager.stopListening()
        Log.d(TAG, "Получен текст из Vosk: '$text'")

        if (text.isBlank()) {
            SharedLog.append("STT: ничего не распознано")
            currentState = "idle"
            restoreButtonState()
            tvCommandStatus.text = "Не распознано"
            return
        }

        SharedLog.append("Распознанный текст: $text")
        sendTextToServer(text)
    }

    private fun sendTextToServer(text: String) {
        val cmd = activeCommandName
        Log.d(TAG, "Отправка текста на сервер: '$text' (команда=$cmd)")

        if (cmd == "voice_rec") {
            currentState = "playing"
            activeButton?.text = "Стоп"
            tvCommandStatus.text = "Обработка..."
        } else {
            currentState = "idle"
            restoreButtonState()
            tvCommandStatus.text = "Обработка..."
        }

        wsManager.send(mapOf(
            "type" to "command",
            "module" to moduleId,
            "command" to cmd,
            "text" to text
        ))
    }

    private fun restoreButtonState() {
        activeButton?.text = idleLabel
        activeButton = null
        activeCommandName = ""
        idleLabel = ""
    }

    private fun stopPlayback() {
        Log.d(TAG, "Остановка воспроизведения")
        wsManager.send(mapOf("type" to "stop_tts"))
        currentState = "idle"
        restoreButtonState()
        tvCommandStatus.text = "Остановлено"
    }

    private fun observeLogs() {
        SharedLog.logs.observe(this, Observer { sb ->
            tvLogs.text = sb.toString()
            scrollLogs.post { scrollLogs.fullScroll(ScrollView.FOCUS_DOWN) }
        })
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "onDestroy")
    }
}