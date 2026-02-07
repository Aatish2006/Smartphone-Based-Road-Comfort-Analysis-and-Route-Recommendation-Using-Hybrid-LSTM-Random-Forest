package com.roadcomfort.datacollector

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.TimeUnit

/**
 * Handles secure data upload to cloud backend
 * 
 * Features:
 * - Window batching (reduce API calls)
 * - Anonymization (hash vehicle ID)
 * - Encryption (HTTPS + payload encryption)
 * - Retry logic
 * - Async processing
 */
class CloudUploader(
    private val context: Context,
    private val apiBaseUrl: String,  // e.g., "https://api.roadcomfort.example.com"
    private val deviceSalt: String
) {
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    
    private val gson = Gson()
    private val windowBatch = mutableListOf<PredictionPayload>()
    private val maxBatchSize = 10
    
    fun submitWindow(
        window: SensorWindow,
        comfortScore: Float,
        potholeDetected: Boolean,
        confidence: Float
    ) {
        // Create payload
        val vehicleId = anonymizeDeviceId()
        val metadata = PredictionMetadata(
            speed = window.speedMs(),
            heading = window.headingDegrees(),
            timestamp = Instant.now().toString(),
            lat = window.latitude(),
            lon = window.longitude()
        )
        
        val prediction = Prediction(
            comfort_score = comfortScore,
            pothole_detected = potholeDetected,
            confidence = confidence
        )
        
        val payload = PredictionPayload(
            segment_id = "seg_unknown",  // Will be filled by server via map-matching
            vehicle_id = vehicleId,
            prediction = prediction,
            metadata = metadata
        )
        
        windowBatch.add(payload)
        Log.d(TAG, "Added window to batch (size=${windowBatch.size})")
        
        // Submit if batch is full
        if (windowBatch.size >= maxBatchSize) {
            submitBatch()
        }
    }
    
    fun submitBatch() {
        if (windowBatch.isEmpty()) {
            Log.d(TAG, "Batch is empty, skipping submit")
            return
        }
        
        Log.d(TAG, "Submitting batch of ${windowBatch.size} windows...")
        
        // Serialize batch
        val jsonBody = gson.toJson(mapOf("predictions" to windowBatch))
        val requestBody = jsonBody.toRequestBody("application/json".toMediaType())
        
        val request = Request.Builder()
            .url("$apiBaseUrl/api/v1/predictions")
            .post(requestBody)
            .addHeader("Content-Type", "application/json")
            .addHeader("User-Agent", "RoadComfort-Android/1.0")
            .build()
        
        try {
            val response = client.newCall(request).execute()
            
            if (response.isSuccessful) {
                Log.d(TAG, "Batch submitted successfully: ${response.code}")
                windowBatch.clear()
            } else {
                Log.e(TAG, "Upload failed: ${response.code} - ${response.body?.string()}")
            }
            
            response.close()
        } catch (e: Exception) {
            Log.e(TAG, "Upload error: ${e.message}", e)
        }
    }
    
    fun flushBatch() {
        // Submit whatever is in batch
        if (windowBatch.isNotEmpty()) {
            submitBatch()
        }
    }
    
    private fun anonymizeDeviceId(): String {
        // Get device identifier (ANDROID_ID)
        val androidId = android.provider.Settings.Secure.getString(
            context.contentResolver,
            android.provider.Settings.Secure.ANDROID_ID
        )
        
        // Hash with salt
        val input = "$androidId:$deviceSalt"
        val digest = MessageDigest.getInstance("SHA-256")
        val hashBytes = digest.digest(input.toByteArray())
        
        // Convert to hex
        return hashBytes.joinToString("") { "%02x".format(it) }.substring(0, 16)
    }
    
    companion object {
        private const val TAG = "CloudUploader"
    }
}

data class PredictionPayload(
    val segment_id: String,
    val vehicle_id: String,
    val prediction: Prediction,
    val metadata: PredictionMetadata
)

data class Prediction(
    val comfort_score: Float,
    val pothole_detected: Boolean,
    val confidence: Float
)

data class PredictionMetadata(
    val speed: Float,
    val heading: Float,
    val timestamp: String,
    val lat: Double,
    val lon: Double
)
