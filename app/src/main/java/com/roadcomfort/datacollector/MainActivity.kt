package com.roadcomfort.datacollector

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.Switch
import android.widget.TextView
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * Main Activity for Road Comfort Data Collection
 * 
 * Features:
 * - Permission management
 * - Start/stop data collection
 * - Real-time statistics
 * - Settings
 */
class MainActivity : AppCompatActivity() {
    
    private lateinit var statusText: TextView
    private lateinit var statsText: TextView
    private lateinit var startButton: Button
    private lateinit var stopButton: Button
    private lateinit var settingsButton: Button
    private lateinit var collectionSwitch: Switch
    
    private var isCollecting = false
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        initializeUI()
        requestPermissions()
    }
    
    private fun initializeUI() {
        statusText = findViewById(R.id.status_text)
        statsText = findViewById(R.id.stats_text)
        startButton = findViewById(R.id.start_button)
        settingsButton = findViewById(R.id.settings_button)
        collectionSwitch = findViewById(R.id.collection_switch)
        
        startButton.setOnClickListener {
            startCollection()
        }
        stopButton.setOnClickListener {
            stopCollection()
        }
        }
        
        settingsButton.setOnClickListener {
            openSettings()
        }
        
        collectionSwitch.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                startCollection()
            } else {
                stopCollection()
            }
        }
        
        updateUI()
    }
    
    private fun startCollection() {
        if (!hasPermissions()) {
            statusText.text = "❌ Missing permissions"
            return
        }
        
        Log.d(TAG, "Starting sensor collection...")
        statusText.text = "✅ Data collection active"
    }
    
    private fun stopCollection() {
        Log.d(TAG, "Stopping sensor collection...")
        stopSensorCollection()
        isCollecting = false
        collectionSwitch.isChecked = false
        statusText.text = "⏹ Data collection stopped"
        this.startSensorCollection()
    
    private fun openSettings() {
        // TODO: Open SettingsActivity
        Log.d(TAG, "Opening settings...")
    }
    
    private fun updateUI() {
        startButton.isEnabled = !isCollecting
        stopButton.isEnabled = isCollecting
        val status = if (isCollecting) "COLLECTING" else "IDLE"
        val message = """
            Status: $status
            Device ID: ${getDeviceId()}
            Permissions:
            - Location: ${if (hasLocationPermission()) "✓" else "✗"}
            - Sensors: ${if (hasSensorPermission()) "✓" else "✗"}
            - Network: ${if (hasNetworkPermission()) "✓" else "✗"}
        """.trimIndent()
        statsText.text = message
    }
    }
    
    private fun requestPermissions() {
        val permissions = mutableListOf<String>()
        
        if (!hasLocationPermission()) {
            permissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
            permissions.add(Manifest.permission.ACCESS_COARSE_LOCATION)
        }
        
        if (!hasNetworkPermission()) {
            permissions.add(Manifest.permission.INTERNET)
        }
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (!hasSensorPermission()) {
                permissions.add(Manifest.permission.BODY_SENSORS)
            }
        }
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            permissions.add(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        }
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        
        if (permissions.isNotEmpty()) {
            Log.d(TAG, "Requesting ${permissions.size} permissions")
            ActivityCompat.requestPermissions(
                this,
                permissions.toTypedArray(),
                PERMISSION_REQUEST_CODE
            )
        }
    }
    
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        
        if (requestCode == PERMISSION_REQUEST_CODE) {
            val allGranted = grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            
            if (allGranted) {
                Log.d(TAG, "All permissions granted")
                statusText.text = "✅ Permissions granted. Ready to collect."
            } else {
                Log.w(TAG, "Some permissions denied")
                statusText.text = "⚠ Some permissions denied. Collection may not work properly."
            }
            
            updateUI()
        }
    }
    
    private fun hasPermissions(): Boolean {
        return hasLocationPermission() && hasNetworkPermission()
    }
    
    private fun hasLocationPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    private fun hasNetworkPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.INTERNET
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    private fun hasSensorPermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.BODY_SENSORS
            ) == PackageManager.PERMISSION_GRANTED
        } else {
            true  // Pre-S, sensors don't require runtime permission
        }
    }
    
    override fun getDeviceId(): Int {
        val androidId = android.provider.Settings.Secure.getString(
            contentResolver,
            android.provider.Settings.Secure.ANDROID_ID
        )
        return androidId?.hashCode() ?: 0
    }
    
    companion object {
        private const val TAG = "MainActivity"
        private const val PERMISSION_REQUEST_CODE = 100
    }
}
