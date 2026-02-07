package com.roadcomfort.datacollector

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import android.os.Build

/**
 * Auto-starts sensor collection when device boots
 * 
 * Ensures collection resumes even after device restart
 * User must have granted permissions before boot
 */
class BootReceiver : BroadcastReceiver() {
    
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            Log.d(TAG, "Device boot detected")
            
            // Check if collection was enabled
            val prefs = context.getSharedPreferences("collection_prefs", Context.MODE_PRIVATE)
            val wasEnabled = prefs.getBoolean("collection_enabled", false)
            
            if (wasEnabled) {
                Log.d(TAG, "Resuming collection after boot...")
                
                // Start the service
                val serviceIntent = Intent(context, SensorCollectionService::class.java)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent)
                } else {
                    context.startService(serviceIntent)
                }
            }
        }
    }
    
    companion object {
        private const val TAG = "BootReceiver"
    }
}
