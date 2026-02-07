"""
Unified ML Inference Pipeline

Orchestrates LSTM encoder → Random Forest classifier for road comfort prediction.
Handles preprocessing, embedding extraction, classification, and confidence scoring.
"""

import numpy as np
import torch
import joblib
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class RoadComfortPipeline:
    """
    End-to-end inference pipeline for road comfort analysis.
    
    Flow:
    1. Preprocess sensor window (normalize, align)
    2. LSTM encoder → temporal embedding
    3. Feature engineering → handcrafted features
    4. Random Forest → comfort score + pothole prediction
    """
    
    def __init__(
        self,
        lstm_encoder_path: str,
        rf_classifier_path: str,
        scaler_path: str,
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        """
        Initialize pipeline with pre-trained models.
        
        Args:
            lstm_encoder_path: Path to LSTM encoder weights
            rf_classifier_path: Path to Random Forest model
            scaler_path: Path to feature scaler
            device: torch device (cuda or cpu)
        """
        self.device = device
        
        # Load LSTM encoder
        self.lstm_encoder = self._load_lstm_encoder(lstm_encoder_path)
        self.lstm_encoder.to(device)
        self.lstm_encoder.eval()
        
        # Load Random Forest and scaler
        self.rf_classifier = joblib.load(rf_classifier_path)
        self.scaler = joblib.load(scaler_path)
        
        logger.info(f"Pipeline initialized on {device}")
    
    def _load_lstm_encoder(self, path: str):
        """Load LSTM encoder from checkpoint."""
        # This assumes encoder.pth or similar format
        # Adjust based on actual model serialization format
        import torch.nn as nn
        
        # Placeholder: actual loading depends on model structure
        logger.info(f"Loading LSTM encoder from {path}")
        return torch.load(path, map_location=self.device)
    
    def predict(
        self,
        sensor_window: np.ndarray,
        speed: float = 0.0,
        heading: float = 0.0
    ) -> Dict[str, Any]:
        """
        Run full inference pipeline on sensor window.
        
        Args:
            sensor_window: [sequence_length, 6] with [ax, ay, az, gx, gy, gz]
            speed: vehicle speed m/s
            heading: vehicle heading degrees
        
        Returns:
            Dict with keys:
            - 'pothole': bool (detected or not)
            - 'comfort_score': float in [0, 1]
            - 'confidence': float in [0, 1]
            - 'embedding': np.ndarray shape (64,)
            - 'features': np.ndarray shape (88,)
        """
        
        # Step 1: Preprocess
        window_processed = self._preprocess_window(sensor_window)
        
        # Step 2: LSTM encoding
        with torch.no_grad():
            X_tensor = torch.FloatTensor(window_processed).unsqueeze(0).to(self.device)
            embedding = self.lstm_encoder(X_tensor).cpu().numpy()[0]
        
        # Step 3: Handcrafted features
        handcrafted = self._extract_handcrafted_features(sensor_window, speed, heading)
        
        # Step 4: Combine features and normalize
        X_combined = np.concatenate([embedding, handcrafted])
        X_scaled = self.scaler.transform([X_combined])[0]
        
        # Step 5: Random Forest inference
        logits = self.rf_classifier.predict([X_scaled])[0]
        probs = self.rf_classifier.predict_proba([X_scaled])[0]
        
        # Decode predictions
        pothole_detected = bool(logits == 1)
        confidence = float(np.max(probs))
        
        # Comfort score: derived from pothole confidence
        # If pothole confidence high -> comfort score low
        pothole_confidence = probs[1] if len(probs) > 1 else 0
        comfort_score = 1.0 - pothole_confidence
        
        result = {
            'pothole': pothole_detected,
            'comfort_score': comfort_score,
            'confidence': confidence,
            'embedding': embedding,
            'features': X_combined,
            'pothole_confidence': pothole_confidence
        }
        
        return result
    
    def _preprocess_window(self, window: np.ndarray) -> np.ndarray:
        """
        Preprocess sensor window.
        
        Steps:
        - Remove gravity via filtering
        - Resample if needed
        - Normalize
        """
        
        # Remove gravity (simple high-pass filter on accel)
        accel = window[:, :3]
        accel_filtered = accel - np.mean(accel, axis=0)  # Remove DC offset
        
        # Normalize to [-1, 1] per axis
        accel_norm_max = np.max(np.abs(accel_filtered), axis=0, keepdims=True)
        accel_norm_max[accel_norm_max == 0] = 1.0  # Avoid division by zero
        accel_normalized = accel_filtered / accel_norm_max
        
        gyro = window[:, 3:]  # Keep gyro as-is (already relative)
        
        window_processed = np.hstack([accel_normalized, gyro])
        
        # Ensure correct shape
        assert window_processed.shape[1] == 6, f"Expected 6 features, got {window_processed.shape[1]}"
        
        return window_processed
    
    def _extract_handcrafted_features(
        self,
        window: np.ndarray,
        speed: float,
        heading: float
    ) -> np.ndarray:
        """Extract handcrafted features (24-dim vector)."""
        
        accel = window[:, :3]
        accel_mag = np.linalg.norm(accel, axis=1)
        
        features = []
        
        # Statistical: mean, std per axis + magnitude
        for i in range(3):
            features.append(np.mean(accel[:, i]))
            features.append(np.std(accel[:, i]))
        features.append(np.mean(accel_mag))
        features.append(np.std(accel_mag))
        features.append(np.sqrt(np.mean(accel_mag ** 2)))
        
        # Spectral (simplified)
        fft = np.abs(np.fft.fft(accel_mag))
        freqs = np.fft.fftfreq(len(accel_mag), 1.0 / 100)  # 100 Hz sampling
        pos_idx = freqs > 0
        
        energy_0_5 = np.sum(fft[pos_idx & (freqs < 5)]) ** 2 if np.any(pos_idx) else 0
        energy_5_15 = np.sum(fft[pos_idx & (freqs < 15)]) ** 2 if np.any(pos_idx) else 0
        energy_15_30 = np.sum(fft[pos_idx & (freqs <= 30)]) ** 2 if np.any(pos_idx) else 0
        
        features.extend([energy_0_5, energy_5_15, energy_15_30])
        
        # Spectral centroid, bandwidth
        if np.any(pos_idx):
            fft_pos = fft[pos_idx]
            freqs_pos = freqs[pos_idx]
            centroid = np.sum(freqs_pos * fft_pos) / np.sum(fft_pos) if np.sum(fft_pos) > 0 else 0
            bandwidth = np.sqrt(
                np.sum(((freqs_pos - centroid) ** 2) * fft_pos) / np.sum(fft_pos)
            ) if np.sum(fft_pos) > 0 else 0
        else:
            centroid = 0
            bandwidth = 0
        
        features.extend([centroid, bandwidth])
        
        # Temporal: peaks, max, min, zero-crossings
        peaks = np.sum((accel_mag[1:-1] > accel_mag[:-2]) & (accel_mag[1:-1] > accel_mag[2:]))
        features.extend([peaks, np.max(accel_mag), np.min(accel_mag)])
        
        zcr = np.sum(np.abs(np.diff(np.sign(accel_mag - np.mean(accel_mag)))) > 0) / len(accel_mag)
        features.append(zcr)
        
        # Context: speed, heading, grade
        features.extend([speed, heading, 0.0])
        
        assert len(features) == 24, f"Expected 24 features, got {len(features)}"
        
        return np.array(features)


if __name__ == "__main__":
    logger.info("Road Comfort ML Pipeline")
    logger.info("To use, instantiate RoadComfortPipeline with model paths and call predict().")
