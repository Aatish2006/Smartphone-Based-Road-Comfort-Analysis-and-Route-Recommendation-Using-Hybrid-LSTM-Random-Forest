# Road Comfort Analysis & Route Recommendation System

A hybrid **LSTM–Random Forest** system for smartphone-based road comfort estimation and pothole detection using crowdsensed data with event-triggered inference and intelligent caching.

## Project Overview

### Core Components

- **Mobile Client** (Android/iOS): Sensor data collection, trigger detection, windowing, and optional on-device inference
- **Cloud Backend** (Python/FastAPI): Ingestion APIs, map-matching, aggregation, caching, route evaluation
- **ML Pipeline** (PyTorch + scikit-learn): LSTM temporal encoding + Random Forest classification/regression
- **Visualization**: Map overlay (green/yellow/red comfort levels)

### Key Design Constraints

| Constraint | Value |
|-----------|-------|
| Hybrid Model | LSTM → Random Forest |
| Trigger Condition | $ a_{mag} > \mu + 2.5\sigma $ |
| Crowdsensing Aggregation | N = 10 vehicles per segment |
| Cache Validity | 30 days TTL |
| Visualization | Map overlay (green/yellow/red) |

## System Flow

```
Smartphone Sensors
    ↓
Trigger Check (acceleration magnitude threshold)
    ↓
Windowing (2–5 second windows)
    ↓
Preprocessing (resample, normalize, align)
    ↓
LSTM Encoder (temporal vibration embedding)
    ↓
Random Forest (classification/regression on embedding + features)
    ↓
Vehicle-level Prediction
    ↓
Upload to Cloud (batch, secure)
    ↓
Segment-level Aggregation (average N samples)
    ↓
Cached Comfort Score (30-day TTL)
    ↓
Route Evaluation (comfort-aware routing)
    ↓
Map Visualization (green/yellow/red overlay)
```

## Project Structure

```
road-comfort-system/
├── mobile/
│   ├── android/          # Android (Kotlin) implementation
│   │   ├── SensorManager.kt
│   │   ├── TriggerDetector.kt
│   │   ├── DataUploader.kt
│   │   └── ...
│   └── ios/              # iOS (Swift) implementation
│       ├── SensorManager.swift
│       ├── TriggerDetector.swift
│       └── ...
├── cloud/
│   ├── backend/          # FastAPI/Python backend
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── ingestion.py
│   │   │   ├── query.py
│   │   │   └── routes.py
│   │   ├── models/
│   │   │   ├── segment.py
│   │   │   └── schemas.py
│   │   ├── services/
│   │   │   ├── aggregator.py
│   │   │   ├── cache.py
│   │   │   └── map_matcher.py
│   │   └── config.py
│   └── visualization/    # Map overlay API
│       ├── tiles.py
│       └── color_mapping.py
├── ml-pipeline/
│   ├── training/         # Model training scripts
│   │   ├── lstm_trainer.py
│   │   ├── rf_trainer.py
│   │   ├── preprocessing.py
│   │   └── hyperparams.yaml
│   ├── inference/        # Inference utilities
│   │   ├── lstm_encoder.py
│   │   ├── rf_classifier.py
│   │   └── pipeline.py
│   └── data/
│       ├── synthetic_generator.py
│       ├── dataset.py
│       └── README.md
├── tests/
│   ├── test_trigger.py
│   ├── test_aggregation.py
│   ├── test_inference.py
│   └── test_integration.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API_SPEC.md
│   ├── METHODOLOGY.md
│   └── EVALUATION.md
├── config/
│   ├── model_config.yaml
│   ├── system_config.yaml
│   └── sensor_config.yaml
├── README.md             # This file
├── requirements.txt      # Python dependencies
└── .env.example          # Environment variables template
```

## Installation & Setup

### Prerequisites

- Python 3.9+
- Node.js 16+ (for backend/optional frontend)
- Android SDK (for mobile development) or Xcode (for iOS)
- Docker (optional, for containerization)

### Backend Setup

```bash
cd cloud/backend
pip install -r ../../requirements.txt
cp ../../.env.example .env
# Edit .env with your cloud credentials
python main.py
```

Backend runs on `http://localhost:8000`. API docs available at `/docs`.

### ML Pipeline Setup

```bash
cd ml-pipeline/training
pip install -r ../../requirements.txt
python preprocessing.py  # (if data available)
python lstm_trainer.py   # Train LSTM encoder
python rf_trainer.py     # Train Random Forest classifier
```

Models saved to `ml-pipeline/inference/models/`.

### Mobile Development

**Android (Kotlin):**
```bash
cd mobile/android
# Open in Android Studio
# Build and run on emulator or device
```

**iOS (Swift):**
```bash
cd mobile/ios
# Open in Xcode
# Build and run on simulator or device
```

## Configuration

Key configuration files:

- **`config/system_config.yaml`**: Aggregation size (N=10), cache TTL (30 days), trigger thresholds
- **`config/model_config.yaml`**: LSTM architecture, RF hyperparameters
- **`config/sensor_config.yaml`**: Sampling rates, window lengths, sensor calibration

## API Overview

### Ingestion Endpoint (Mobile → Cloud)

**POST** `/api/v1/predictions`

```json
{
  "segment_id": "seg_12345",
  "vehicle_id": "hash_vehicle_xxx",
  "prediction": {
    "comfort_score": 0.75,
    "pothole_detected": false,
    "confidence": 0.92
  },
  "metadata": {
    "speed": 45.5,
    "heading": 180,
    "timestamp": "2026-01-28T10:30:00Z"
  }
}
```

### Query Endpoint (App → Cloud)

**GET** `/api/v1/segments/{segment_id}`

```json
{
  "segment_id": "seg_12345",
  "comfort_score": 0.72,
  "sample_count": 8,
  "last_updated": "2026-01-28T09:00:00Z",
  "expires_at": "2026-02-27T09:00:00Z",
  "color": "yellow"
}
```

### Route Evaluation Endpoint

**POST** `/api/v1/routes/evaluate`

Input: list of segment IDs or coordinates  
Output: comfort-aware route with aggregated cost

## Model Architecture

### LSTM Encoder

- **Input**: Multivariate time series (accel x/y/z, gyro x/y/z; shape: [T, 6])
- **Layers**: 2 stacked LSTM (units: 128 → 64), dropout 0.2
- **Output**: Embedding vector (size: 64)
- **Framework**: PyTorch or TensorFlow

### Random Forest

- **Input**: LSTM embedding (64-dim) + handcrafted features (e.g., spectral energy, peak counts)
- **Output**: Classification (pothole yes/no) and/or regression (comfort score ∈ [0, 1])
- **Hyperparameters**:
  - n_estimators: 200
  - max_depth: tuned via CV [10–30]
  - min_samples_leaf: 5
- **Framework**: scikit-learn

## Testing

Run all tests:

```bash
pytest tests/ -v
```

Specific test suites:

```bash
pytest tests/test_trigger.py        # Trigger logic
pytest tests/test_aggregation.py    # Segment aggregation
pytest tests/test_inference.py      # ML pipeline
pytest tests/test_integration.py    # End-to-end integration
```

## Deployment

### Docker

```bash
docker build -t road-comfort-system .
docker run -p 8000:8000 --env-file .env road-comfort-system
```

### Cloud Platforms

- **AWS**: ECS/Lambda + RDS + ElastiCache (for cache)
- **GCP**: Cloud Run + Firestore + Memorystore
- **Azure**: Container Instances + Cosmos DB + Azure Cache

## Evaluation Metrics

- **Window-level**: Precision, Recall, F1-score, ROC-AUC, Calibration
- **Segment-level**: Concordance (Kendall Tau / Spearman), Stability, Coverage, Detection Latency
- **System**: Inference latency, Network traffic, Cache hit rate, Energy consumption

See `docs/EVALUATION.md` for detailed validation strategy.

## Methodology & Academic References

The design follows principles from:

- **Event-triggered learning**: Reduces continuous inference overhead
- **Crowdsensing aggregation**: Stabilizes estimates, improves coverage
- **Temporal + statistical modeling**: LSTM captures dynamics; RF provides robustness
- **Map-aware processing**: Ensures aggregation consistency via segment-level caching

See `docs/METHODOLOGY.md` for detailed methodology and `docs/ARCHITECTURE.md` for system design rationale.

## Future Enhancements

1. **Domain adaptation** to handle device/mount variation
2. **Federated learning** for privacy-preserving model updates
3. **Real-time continuous monitoring** for critical segments
4. **Multi-modal fusion** (audio, camera-based) for pothole detection
5. **Predictive maintenance** routing to minimize future repairs

## License

[Specify License]

## Contributors

- AI System Architect & ML Researcher

## Contact & Support

For questions or issues, contact: [your-email@example.com]
