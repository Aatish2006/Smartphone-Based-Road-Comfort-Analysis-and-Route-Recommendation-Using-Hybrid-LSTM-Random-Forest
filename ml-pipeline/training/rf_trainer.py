"""
Random Forest Classifier Training Module

Trains a Random Forest classifier on top of LSTM embeddings + handcrafted features
for pothole detection and road comfort classification.

Input: [LSTM embedding (64-dim), handcrafted features (24-dim)]
Output: Pothole class (0=normal, 1=pothole) + confidence score
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
)
import joblib
import yaml
from pathlib import Path
import logging
from typing import Tuple, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HandcraftedFeatureExtractor:
    """
    Extracts handcrafted features from sensor windows.
    
    Features:
    - Statistical: mean, std, rms per axis + magnitude
    - Spectral: energy in frequency bands, centroid, bandwidth
    - Temporal: peak count, max/min, zero-crossing rate
    - Context: speed, heading, grade
    
    Total: ~24 features
    """
    
    def __init__(self, sampling_rate: int = 100):
        self.sampling_rate = sampling_rate
    
    def extract(self, window: np.ndarray, speed: float = 0, heading: float = 0) -> np.ndarray:
        """
        Extract handcrafted features from a sensor window.
        
        Args:
            window: [sequence_length, 6] with columns [ax, ay, az, gx, gy, gz]
            speed: vehicle speed in m/s
            heading: vehicle heading in degrees
        
        Returns:
            features: [24] feature vector
        """
        features = []
        
        # Extract accel and gyro
        accel = window[:, :3]  # [T, 3]
        gyro = window[:, 3:]   # [T, 3]
        
        # Magnitude
        accel_mag = np.linalg.norm(accel, axis=1)  # [T]
        
        # Statistical features
        features.extend(self._statistical_features(accel, accel_mag))
        features.extend(self._spectral_features(accel_mag))
        features.extend(self._temporal_features(accel_mag))
        features.extend(self._context_features(speed, heading))
        
        return np.array(features)
    
    def _statistical_features(self, accel: np.ndarray, accel_mag: np.ndarray) -> list:
        """Statistical moments and dispersion."""
        features = []
        for i in range(3):
            features.append(np.mean(accel[:, i]))  # mean ax, ay, az
            features.append(np.std(accel[:, i]))   # std ax, ay, az
        features.append(np.mean(accel_mag))         # mean magnitude
        features.append(np.std(accel_mag))          # std magnitude
        features.append(np.sqrt(np.mean(accel_mag ** 2)))  # RMS
        return features
    
    def _spectral_features(self, signal: np.ndarray) -> list:
        """Frequency domain features."""
        # Compute power spectral density via FFT
        fft = np.abs(np.fft.fft(signal))
        freqs = np.fft.fftfreq(len(signal), 1.0 / self.sampling_rate)
        
        # Positive frequencies only
        pos_idx = freqs > 0
        fft = fft[pos_idx]
        freqs = freqs[pos_idx]
        
        # Spectral energy in bands
        energy_0_5 = np.sum(fft[(freqs >= 0) & (freqs < 5)]) ** 2
        energy_5_15 = np.sum(fft[(freqs >= 5) & (freqs < 15)]) ** 2
        energy_15_30 = np.sum(fft[(freqs >= 15) & (freqs <= 30)]) ** 2
        
        # Spectral centroid
        spectral_centroid = np.sum(freqs * fft) / np.sum(fft) if np.sum(fft) > 0 else 0
        
        # Spectral bandwidth
        spectral_bandwidth = np.sqrt(
            np.sum(((freqs - spectral_centroid) ** 2) * fft) / np.sum(fft)
        ) if np.sum(fft) > 0 else 0
        
        return [energy_0_5, energy_5_15, energy_15_30, spectral_centroid, spectral_bandwidth]
    
    def _temporal_features(self, signal: np.ndarray) -> list:
        """Temporal pattern features."""
        # Peak count (local maxima)
        peaks = np.sum((signal[1:-1] > signal[:-2]) & (signal[1:-1] > signal[2:]))
        
        # Max and min
        max_val = np.max(signal)
        min_val = np.min(signal)
        
        # Zero crossing rate (impulses)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(signal - np.mean(signal)))) > 0)
        zcr = zero_crossings / len(signal) if len(signal) > 0 else 0
        
        return [peaks, max_val, min_val, zcr]
    
    def _context_features(self, speed: float, heading: float) -> list:
        """Context features from vehicle state."""
        return [speed, heading, 0.0]  # Third feature reserved for road grade


def load_config(config_path: str = "../config/model_config.yaml") -> Dict[str, Any]:
    """Load model configuration."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def train_random_forest(
    X_embedding: np.ndarray,
    X_handcrafted: np.ndarray,
    y: np.ndarray,
    config: Dict[str, Any],
    output_dir: str = "./models",
    scaler_path: Optional[str] = None
) -> Tuple[RandomForestClassifier, StandardScaler]:
    """
    Train Random Forest on LSTM embeddings + handcrafted features.
    
    Args:
        X_embedding: [num_samples, 64] LSTM embeddings
        X_handcrafted: [num_samples, 24] handcrafted features
        y: [num_samples] class labels (0=normal, 1=pothole)
        config: model config dict
        output_dir: directory to save models
        scaler_path: optional path to pre-fitted scaler
    
    Returns:
        Trained RandomForestClassifier, StandardScaler
    """
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Combine features
    X = np.hstack([X_embedding, X_handcrafted])
    logger.info(f"Combined feature shape: {X.shape}")
    
    # Normalize features
    if scaler_path and Path(scaler_path).exists():
        scaler = joblib.load(scaler_path)
        logger.info(f"Loaded pre-fitted scaler from {scaler_path}")
    else:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)
        joblib.dump(scaler, Path(output_dir) / "scaler.pkl")
        logger.info("Fitted and saved new scaler")
    
    X_scaled = scaler.transform(X)
    
    # Cross-validation setup
    rf_cfg = config['random_forest']
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # Initialize model
    rf = RandomForestClassifier(
        n_estimators=rf_cfg['n_estimators'],
        max_depth=rf_cfg['max_depth'],
        min_samples_split=rf_cfg['min_samples_split'],
        min_samples_leaf=rf_cfg['min_samples_leaf'],
        max_features=rf_cfg['max_features'],
        criterion=rf_cfg['criterion'],
        class_weight=rf_cfg['class_weight'],
        n_jobs=rf_cfg['n_jobs'],
        random_state=rf_cfg['random_state'],
        verbose=1
    )
    
    # Cross-validation evaluation
    logger.info("Running 5-fold cross-validation...")
    cv_metrics = cross_validate(
        rf, X_scaled, y,
        cv=cv,
        scoring=['accuracy', 'precision', 'recall', 'f1', 'roc_auc'],
        n_jobs=-1
    )
    
    logger.info("Cross-Validation Results:")
    for metric, scores in cv_metrics.items():
        logger.info(f"  {metric}: {scores['test_' + metric if 'test_' in metric else metric].mean():.4f} "
                    f"(± {scores['test_' + metric if 'test_' in metric else metric].std():.4f})")
    
    # Train on full dataset
    logger.info("Training final model on full dataset...")
    rf.fit(X_scaled, y)
    
    # Feature importance
    feature_importance = rf.feature_importances_
    logger.info(f"\nTop 10 Important Features:")
    top_indices = np.argsort(feature_importance)[-10:][::-1]
    for idx in top_indices:
        feature_type = "Embedding" if idx < 64 else "Handcrafted"
        logger.info(f"  Feature {idx} ({feature_type}): {feature_importance[idx]:.4f}")
    
    # Save model and scaler
    model_path = Path(output_dir) / "rf_classifier.pkl"
    joblib.dump(rf, model_path)
    logger.info(f"Model saved to {model_path}")
    
    return rf, scaler


def evaluate_random_forest(
    rf: RandomForestClassifier,
    scaler: StandardScaler,
    X_embedding: np.ndarray,
    X_handcrafted: np.ndarray,
    y: np.ndarray,
    dataset_name: str = "Test"
) -> Dict[str, float]:
    """
    Evaluate Random Forest on a dataset.
    
    Args:
        rf: Trained RandomForestClassifier
        scaler: Fitted StandardScaler
        X_embedding: [num_samples, 64]
        X_handcrafted: [num_samples, 24]
        y: [num_samples] true labels
        dataset_name: Name of dataset (for logging)
    
    Returns:
        metrics dict
    """
    
    X = np.hstack([X_embedding, X_handcrafted])
    X_scaled = scaler.transform(X)
    
    y_pred = rf.predict(X_scaled)
    y_pred_proba = rf.predict_proba(X_scaled)[:, 1]
    
    metrics = {
        'accuracy': accuracy_score(y, y_pred),
        'precision': precision_score(y, y_pred, zero_division=0),
        'recall': recall_score(y, y_pred, zero_division=0),
        'f1': f1_score(y, y_pred, zero_division=0),
        'roc_auc': roc_auc_score(y, y_pred_proba) if len(np.unique(y)) > 1 else 0.0
    }
    
    logger.info(f"\n{dataset_name} Set Evaluation:")
    for metric, value in metrics.items():
        logger.info(f"  {metric}: {value:.4f}")
    
    logger.info(f"\nConfusion Matrix:\n{confusion_matrix(y, y_pred)}")
    logger.info(f"\nClassification Report:\n{classification_report(y, y_pred)}")
    
    return metrics


if __name__ == "__main__":
    config = load_config()
    logger.info("Random Forest Classifier Training Module")
    logger.info(f"Config loaded: {config['random_forest']}")
    logger.info("To train, call train_random_forest() with LSTM embeddings + handcrafted features.")
