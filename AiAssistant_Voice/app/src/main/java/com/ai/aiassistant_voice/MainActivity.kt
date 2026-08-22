package com.ai.aiassistant_voice

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.Observer

/**
 * Первый экран: подключение к серверу, выбор модуля, общий лог.
 * Версия 1.1: добавлен модуль "Работа".
 */
class MainActivity : AppCompatActivity() {
    companion object {
        private const val TAG = "MainActivity"
        private const val PREFS_NAME = "AiAPrefs"
        private const val KEY_IP = "server_ip"
        private const val PERMISSION_REQUEST = 1001
    }

    private lateinit var etIp: EditText
    private lateinit var btnConnect: Button
    private lateinit var tvStatus: TextView
    private lateinit var btnCommands: Button
    private lateinit var btnDialog: Button
    private lateinit var btnWork: Button
    private lateinit var tvLogs: TextView
    private lateinit var scrollLogs: ScrollView

    private val wsManager by lazy { App.instance.webSocketManager }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate")
        setContentView(R.layout.activity_main)

        initViews()
        loadSavedIp()
        checkPermissions()
        setupListeners()
        observeLogs()

        SharedLog.append("Ai Assistant запущен")

        if (!App.instance.isVoskReady) {
            SharedLog.append("Vosk: фоновая загрузка модели...")
            App.instance.initVoskModel {
                runOnUiThread {
                    SharedLog.append("Vosk: модель готова (фоновая загрузка завершена)")
                }
            }
        }
    }

    private fun initViews() {
        etIp = findViewById(R.id.etIp)
        btnConnect = findViewById(R.id.btnConnect)
        tvStatus = findViewById(R.id.tvStatus)
        btnCommands = findViewById(R.id.btnCommands)
        btnDialog = findViewById(R.id.btnDialog)
        btnWork = findViewById(R.id.btnWork)
        tvLogs = findViewById(R.id.tvLogs)
        scrollLogs = findViewById(R.id.scrollLogs)
    }

    private fun loadSavedIp() {
        val ip = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_IP, "") ?: ""
        etIp.setText(ip)
        Log.d(TAG, "Загружен сохранённый IP: $ip")
    }

    private fun saveIp(ip: String) {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit().putString(KEY_IP, ip).apply()
    }

    private fun checkPermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                arrayOf(Manifest.permission.RECORD_AUDIO), PERMISSION_REQUEST)
        }
    }

    private fun setupListeners() {
        btnConnect.setOnClickListener {
            val rawIp = etIp.text.toString().trim()
            val ip = rawIp
                .replace("http://", "")
                .replace("https://", "")
                .replace("ws://", "")
                .replace("wss://", "")
                .substringBefore(":")
                .trim()

            if (ip.isEmpty()) {
                Toast.makeText(this, "Введите IP-адрес сервера", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            etIp.setText(ip)
            saveIp(ip)
            connectToServer(ip)
        }

        btnCommands.setOnClickListener {
            openModule("command_user", "Команды пользователя",
                "Модуль для голосового взаимодействия с LLM и астрологических расчётов.\n\n" +
                        "• Начать запись голосом — отправляет распознанный текст в Ollama и озвучивает ответ.\n" +
                        "• Лунный день — вычисляет текущий лунный день, начало/конец, описание из Excel. Выполняется мгновенно.\n" +
                        "• Перескажи — озвучивает содержимое файла перескажи.* из папки Command_user. Выполняется мгновенно.")
        }

        btnDialog.setOnClickListener {
            openModule("dialog", "Обсуждение",
                "Модуль для создания голосовых заметок и запросов к LLM.\n\n" +
                        "• Записки : начать запись — сохраняет распознанный текст в .docx файл.\n" +
                        "• Запрос : начать запись — сохраняет запрос и ответ LLM в .docx файл.")
        }

        btnWork.setOnClickListener {
            openModule("work", "Работа",
                "Модуль для работы с документами.\n\n" +
                        "• Перескажи — ищет файл перескажи.* (.doc, .docx, .pdf, .xls, .xlsx) " +
                        "в папке Command_user и озвучивает его содержимое. Выполняется мгновенно.")
        }
    }

    private fun connectToServer(ip: String) {
        val url = "ws://$ip:8000/ws"
        Log.d(TAG, "Подключение к $url")
        SharedLog.append("Подключение к $url...")

        wsManager.onConnected = {
            runOnUiThread {
                tvStatus.text = "● Подключено"
                tvStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_green_dark))
                SharedLog.append("Подключение установлено")
            }
        }
        wsManager.onDisconnected = {
            runOnUiThread {
                tvStatus.text = "● Отключено"
                tvStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_red_dark))
                SharedLog.append("Соединение разорвано")
            }
        }
        wsManager.onMessage = { data ->
            runOnUiThread {
                val msg = data["message"] ?: data["text"] ?: data.toString()
                SharedLog.append("Сервер: $msg")
            }
        }
        wsManager.connect(url)
    }

    private fun openModule(moduleId: String, moduleName: String, helpText: String) {
        val ip = etIp.text.toString().trim()
            .replace("http://", "")
            .replace("https://", "")
            .replace("ws://", "")
            .replace("wss://", "")
            .substringBefore(":")
            .trim()

        if (ip.isEmpty()) {
            Toast.makeText(this, "Сначала введите IP и подключитесь", Toast.LENGTH_SHORT).show()
            return
        }
        Log.d(TAG, "Открытие модуля $moduleId, IP=$ip")
        startActivity(Intent(this, ModuleActivity::class.java).apply {
            putExtra("module_id", moduleId)
            putExtra("module_name", moduleName)
            putExtra("help_text", helpText)
            putExtra("server_ip", ip)
        })
    }

    private fun observeLogs() {
        SharedLog.logs.observe(this, Observer { sb ->
            tvLogs.text = sb.toString()
            scrollLogs.post { scrollLogs.fullScroll(ScrollView.FOCUS_DOWN) }
        })
    }

    override fun onResume() {
        super.onResume()
        if (wsManager.isConnected()) {
            tvStatus.text = "● Подключено"
            tvStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_green_dark))
        } else {
            tvStatus.text = "● Отключено"
            tvStatus.setTextColor(ContextCompat.getColor(this, android.R.color.holo_red_dark))
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "onDestroy")
    }
}