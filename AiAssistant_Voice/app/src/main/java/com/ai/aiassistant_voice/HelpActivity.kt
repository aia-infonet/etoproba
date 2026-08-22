package com.ai.aiassistant_voice

import android.os.Bundle
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Третий экран: текстовая справка по модулю.
 */
class HelpActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_help)
        val moduleName = intent.getStringExtra("module_name") ?: ""
        val helpText = intent.getStringExtra("help_text") ?: ""
        findViewById<TextView>(R.id.tvHelpTitle).text = "Справка: $moduleName"
        findViewById<TextView>(R.id.tvHelpContent).text = helpText
    }
}
