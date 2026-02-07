package com.roadcomfort.datacollector

import android.content.Context
import android.util.Log
import org.tensorflow.lite.Interpreter
import org.tensorflow.lite.gpu.CompatibilityList
import org.tensorflow.lite.gpu.GpuDelegate
// import org.tensorflow.lite.nnapi.NnApiDelegate
import java.io.FileInputStream
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.nio.FloatBuffer
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * On-device inference using TensorFlow Lite
 * 
 * Architecture:
 * 1. LSTM encoder: window [T, 6] → [128] embedding
 * 2. RF classifier: embedding + features → comfort_score, pothole_detected
 * 
 * Supports:
 * - GPU acceleration (optional)
 * - Quantized models (8-bit or 16-bit)
 * - Fallback to CPU
 */
class InferenceManager(
    private val context: Context,
    private val lstmModelPath: String = "models/lstm_encoder.tflite",
    private val rfModelPath: String = "models/rf_classifier.tflite"
) {
    
    private var lstmInterpreter: Interpreter? = null
    private var rfInterpreter: Interpreter? = null
    private var gpuDelegate: GpuDelegate? = null
    
    fun initialize(): Boolean {
        return try {
            Log.d(TAG, "Initializing TensorFlow Lite models...")
            
            // Load models from assets
            val lstmBuffer = loadModelBuffer(lstmModelPath)
            val rfBuffer = loadModelBuffer(rfModelPath)
            
            // Try GPU acceleration
            val useGpu = CompatibilityList().isDelegateSupportedOnThisDevice
            Log.d(TAG, "GPU support: $useGpu")
            
            val options = Interpreter.Options()
            if (useGpu) {
                gpuDelegate = GpuDelegate(CompatibilityList().bestOptionsForThisDevice)
                options.addDelegate(gpuDelegate)
                Log.d(TAG, "GPU delegate added")
            }
            }
            
            // Create interpreters
            lstmInterpreter = Interpreter(lstmBuffer, options)
            rfInterpreter = Interpreter(rfBuffer, options)
            
            Log.d(TAG, "Models initialized successfully")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize models: ${e.message}", e)
            false
        }
    }
    
    fun predictComfort(window: SensorWindow): InferenceResult {
        if (lstmInterpreter == null || rfInterpreter == null) {
            Log.e(TAG, "Models not initialized")
            return InferenceResult(
                comfortScore = 0.5f,
                potholeDetected = false,
                confidence = 0.0f,
                error = "Models not initialized"
            )
        }
        
        return try {
            // Step 1: LSTM encoding
            val inputArray = window.toArray()  // [T, 6]
            val lstmOutput = runLstmEncoding(inputArray)  // [128]
            
            // Step 2: Feature engineering
            val features = engineerFeatures(inputArray, lstmOutput)  // [136] = 128 + 8
            
            // Step 3: RF classification
            val (comfortScore, potholeDetected, confidence) = runRfClassification(features)
            
            Log.d(TAG, "Prediction: comfort=$comfortScore, pothole=$potholeDetected, conf=$confidence")
            
            InferenceResult(
                comfortScore = comfortScore,
                potholeDetected = potholeDetected,
                confidence = confidence
            )
        } catch (e: Exception) {
            Log.e(TAG, "Inference error: ${e.message}", e)
            InferenceResult(
                comfortScore = 0.5f,
                potholeDetected = false,
                confidence = 0.0f,
                error = e.message
            )
        }
    }
    
    private fun runLstmEncoding(inputArray: Array<FloatArray>): FloatArray {
        // Reshape: [T, 6] → [1, T, 6] for batch dim
        val input = FloatArray(1 * inputArray.size * 6)
        var idx = 0
        for (t in inputArray.indices) {
            for (d in 0 until 6) {
                input[idx++] = inputArray[t][d]
            }
        }
        
        // Output: [1, 128]
        val output = Array(1) { FloatArray(128) }
        lstmInterpreter?.run(input, output)
        
        return output[0]
    }
    
    private fun engineerFeatures(
        inputArray: Array<FloatArray>,
        lstmOutput: FloatArray
    ): FloatArray {
        // Combine LSTM embedding (128) + handcrafted features (8)
        val handcrafted = extractHandcraftedFeatures(inputArray)
        
        return (lstmOutput.toList() + handcrafted.toList()).toFloatArray()
    }
    
    private fun extractHandcraftedFeatures(inputArray: Array<FloatArray>): FloatArray {
        // 8 features:
        // 1. Mean acceleration magnitude
        // 2. Std acceleration magnitude
        // 3. Max acceleration magnitude (peak shock)
        // 4. RMS jerk (change in acceleration)
        // 5. Mean gyroscope magnitude
        // 6. Peak gyroscope magnitude
        // 7. Window duration (normalized)
        // 8. Energy (integral of squared acceleration)
        
        val features = FloatArray(8)
        
        if (inputArray.isEmpty()) {
            return features
        }
        
        // Extract components
        val ax = FloatArray(inputArray.size)
        val ay = FloatArray(inputArray.size)
        val az = FloatArray(inputArray.size)
        val gx = FloatArray(inputArray.size)
        val gy = FloatArray(inputArray.size)
        val gz = FloatArray(inputArray.size)
        
        for (t in inputArray.indices) {
            ax[t] = inputArray[t][0]
            ay[t] = inputArray[t][1]
            az[t] = inputArray[t][2]
            gx[t] = inputArray[t][3]
            gy[t] = inputArray[t][4]
            gz[t] = inputArray[t][5]
        }
        
        // 1. Mean acceleration magnitude
        var sumAccelMag = 0f
        var maxAccelMag = 0f
        for (t in inputArray.indices) {
            val accelMag = sqrt(ax[t]*ax[t] + ay[t]*ay[t] + az[t]*az[t])
            sumAccelMag += accelMag
            if (accelMag > maxAccelMag) maxAccelMag = accelMag
        }
        features[0] = sumAccelMag / inputArray.size  // mean
        
        // 2. Std acceleration magnitude
        var sumSqDiff = 0f
        for (t in inputArray.indices) {
            val accelMag = sqrt(ax[t]*ax[t] + ay[t]*ay[t] + az[t]*az[t])
            sumSqDiff += (accelMag - features[0]) * (accelMag - features[0])
        }
        features[1] = sqrt(sumSqDiff / inputArray.size)
        
        // 3. Max acceleration magnitude
        features[2] = maxAccelMag
        
        // 4. RMS jerk
        var sumJerkSq = 0f
        for (t in 1 until inputArray.size) {
            val jerkX = ax[t] - ax[t-1]
            val jerkY = ay[t] - ay[t-1]
            val jerkZ = az[t] - az[t-1]
            sumJerkSq += jerkX*jerkX + jerkY*jerkY + jerkZ*jerkZ
        }
        features[3] = sqrt(sumJerkSq / (inputArray.size - 1))
        
        // 5. Mean gyroscope magnitude
        var sumGyroMag = 0f
        for (t in inputArray.indices) {
            val gyroMag = sqrt(gx[t]*gx[t] + gy[t]*gy[t] + gz[t]*gz[t])
            sumGyroMag += gyroMag
        }
        features[4] = sumGyroMag / inputArray.size
        
        // 6. Peak gyroscope magnitude
        var maxGyroMag = 0f
        for (t in inputArray.indices) {
            val gyroMag = sqrt(gx[t]*gx[t] + gy[t]*gy[t] + gz[t]*gz[t])
            if (gyroMag > maxGyroMag) maxGyroMag = gyroMag
        }
        features[5] = maxGyroMag
        
        // 7. Window duration (normalized: 3 sec = 1.0)
        features[6] = inputArray.size.toFloat() / 300f  // assuming 100 Hz
        
        // 8. Energy
        var energy = 0f
        for (t in inputArray.indices) {
            energy += ax[t]*ax[t] + ay[t]*ay[t] + az[t]*az[t]
        }
        features[7] = energy / inputArray.size
        
        return features
    }
    
    private fun runRfClassification(features: FloatArray): Triple<Float, Boolean, Float> {
        // Output: [1, 3] = [comfort_score, is_pothole, confidence]
        val output = Array(1) { FloatArray(3) }
        rfInterpreter?.run(features, output)
        
        val comfortScore = output[0][0]  // 0-1 range
        val isPothole = output[0][1] > 0.5f
        val confidence = abs(output[0][1] - 0.5f) * 2  // normalize
        
        return Triple(comfortScore, isPothole, confidence)
    }
    
    private fun loadModelBuffer(modelPath: String): MappedByteBuffer {
        val file = context.assets.openFd(modelPath)
        val inputStream = FileInputStream(file.fileDescriptor)
        val fileChannel = inputStream.channel
        return fileChannel.map(
            FileChannel.MapMode.READ_ONLY,
            file.startOffset,
            file.declaredLength
        )
    }
    
    fun close() {
        lstmInterpreter?.close()
        rfInterpreter?.close()
        gpuDelegate?.close()
        Log.d(TAG, "Interpreters closed")
    }
    
    companion object {
        private const val TAG = "InferenceManager"
    }
}

data class InferenceResult(
    val comfortScore: Float,
    val potholeDetected: Boolean,
    val confidence: Float,
    val error: String? = null
)
