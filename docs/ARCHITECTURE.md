# System Architecture

## Overview

The Road Comfort Analysis system is a **hybrid LSTM–Random Forest** platform for detecting potholes and estimating road surface comfort from smartphone-based motion sensors. The system is designed for scalability, robustness, and real-time responsiveness using event-triggered inference and crowdsourced aggregation.

## Design Philosophy

### Event-Triggered Inference
- **Why**: Continuous inference is computationally expensive and drains mobile batteries.
- **How**: Monitor acceleration magnitude locally on the device; only invoke ML pipeline when $ a_{mag} > \mu + 2.5\sigma $.
- **Benefit**: Reduces inference cost by ~95% while capturing anomalies (potholes).

### Crowdsensed Aggregation
- **Why**: Single-vehicle predictions are noisy; aggregation improves robustness.
- **How**: Buffer predictions per road segment; average when N = 10 vehicles contribute.
- **Benefit**: Stabilizes scores, reduces false positives, provides confidence estimates.

### Time-Based Caching
- **Why**: Road conditions change slowly; repeated aggregation is wasteful.
- **How**: Cache segment scores with 30-day TTL; invalidate only on expiration.
- **Benefit**: Minimal recomputation, consistent UI, fast API response.

## System Components

### 1. Mobile Client (Android / iOS)

**Responsibilities:**
- Sample sensors (accelerometer, gyroscope, GPS) at fixed rates
- Compute rolling baseline (μ, σ) for trigger threshold
- Detect events when acceleration exceeds threshold
- Windowing: extract 2–5 second segments around events
- Preprocessing: normalize, align, resample
- Inference options:
  - On-device LSTM encoding + optional RF classification
  - Or upload embedding + features to cloud for inference
- Batch upload with privacy: anonymize, encrypt, rate-limit

**Key Modules:**
- `SensorManager`: Streaming data collection
- `TriggerDetector`: Threshold-based event detection (μ + 2.5σ)
- `Preprocessor`: Window alignment, normalization
- `LocalInference`: LSTM encoder on-device (optional)
- `DataUploader`: Batching, encryption, retry logic

### 2. Cloud Backend (FastAPI / Python)

**Responsibilities:**
- Ingest vehicle predictions via REST API
- Map-match GPS to road segments
- Aggregate per-segment predictions (N = 10)
- Maintain 30-day cache of segment scores
- Serve segment queries and route evaluations
- Provide visualization tile API

**Key Modules:**
- `ingestion.py`: POST /api/v1/predictions endpoint
- `aggregator.py`: Segment-level crowdsensing logic
- `cache.py`: TTL-aware caching (Redis or in-memory)
- `query.py`: GET segment scores, route evaluation
- `models.py`: SQLAlchemy ORM + Pydantic schemas
- `main.py`: FastAPI application bootstrap

### 3. ML Pipeline (PyTorch + scikit-learn)

**Training:**
- Data: Labeled sensor windows (normal, pothole, varying comfort)
- LSTM: 2-layer bidirectional encoder (128 → 64 units)
  - Input: multivariate time series [T, 6]
  - Output: embedding [64]
  - Trained end-to-end with classification loss
- Random Forest: 200 trees, depth ≤ 30
  - Input: LSTM embedding [64] + handcrafted features [24]
  - Output: pothole class + confidence
  - Trained on frozen LSTM embeddings

**Inference:**
- Preprocessing: normalize, align to vehicle frame
- LSTM encoding: compress temporal info
- Feature engineering: spectral + statistical features
- RF prediction: classification + confidence
- Result: comfort score + pothole flag + confidence

### 4. Visualization Layer

**Capabilities:**
- Map tiles with per-segment color overlay
  - Green (score > 0.7): good road
  - Yellow (0.4 ≤ score ≤ 0.7): average
  - Red (score < 0.4): poor road / pothole-prone
- Heatmap of aggregate comfort across region
- Route recommendation with comfort weighting

**API Endpoints:**
- GET `/api/v1/segments/{segment_id}` → comfort score + color
- GET `/api/v1/segments` → all segments
- POST `/api/v1/routes/evaluate` → route cost breakdown
- GET `/api/v1/tiles/{z}/{x}/{y}` → raster/vector tiles

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    SMARTPHONE CLIENT                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Accelerometer ──┐                                               │
│  Gyroscope      ├──> [Trigger Check]                             │
│  GPS            │    μ + 2.5σ threshold                          │
│                 └──> [No Event] → idle                           │
│                      [Event] ↓                                    │
│                   [Windowing: 2-5s]                              │
│                        ↓                                          │
│                  [Preprocessing]                                 │
│                  (align, normalize)                              │
│                        ↓                                          │
│              ┌─────────────────────┐                             │
│              │  LSTM Encoder       │ (optional on-device)        │
│              │  Input: [T, 6]      │                             │
│              │  Output: [64]       │                             │
│              └─────────────────────┘                             │
│                        ↓                                          │
│        [Upload: segment_id, embedding, features, metadata]       │
│        (Batch + Encrypt + Anonymize)                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                          ↓ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│                  CLOUD BACKEND (FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  POST /api/v1/predictions                                        │
│    ├─> Validate request                                          │
│    ├─> [Random Forest Inference] (if not on-device)             │
│    │   Input: embedding [64] + features [24]                    │
│    │   Output: pothole class + confidence                       │
│    └─> [Aggregation Service]                                    │
│        └─> Segment buffer (N=10)                                │
│            ├─> Add vehicle prediction                           │
│            ├─> Compute weighted mean                            │
│            └─> Update cache (30-day TTL)                        │
│                                                                   │
│  GET /api/v1/segments/{segment_id}                               │
│    ├─> Check cache [valid?]                                     │
│    └─> Return: {segment_id, comfort_score, color, expires_at}  │
│                                                                   │
│  POST /api/v1/routes/evaluate                                    │
│    ├─> Fetch cached scores for segments                         │
│    ├─> Compute route cost (time + comfort weighted)             │
│    └─> Return: total_cost, avg_comfort, segment breakdown       │
│                                                                   │
│  GET /api/v1/tiles/{z}/{x}/{y}                                   │
│    └─> Return: map tile with color overlay                      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Models

### Mobile → Cloud Payload

```json
{
  "segment_id": "seg_12345",
  "vehicle_id": "hash_abc123",
  "prediction": {
    "comfort_score": 0.75,
    "pothole_detected": false,
    "confidence": 0.92
  },
  "metadata": {
    "speed": 45.5,
    "heading": 180.0,
    "timestamp": "2026-01-28T10:30:00Z",
    "lat": 40.7128,
    "lon": -74.0060
  }
}
```

### Segment Cache Entry

```json
{
  "segment_id": "seg_12345",
  "comfort_score": 0.72,
  "sample_count": 8,
  "confidence": 0.88,
  "last_updated": "2026-01-28T09:00:00Z",
  "expires_at": "2026-02-27T09:00:00Z",
  "is_valid": true,
  "is_finalized": false
}
```

### Route Evaluation Result

```json
{
  "total_cost": 0.45,
  "time_cost": 0.50,
  "comfort_cost": 0.40,
  "average_comfort": 0.80,
  "segments": [
    {
      "segment_id": "seg_123",
      "comfort_score": 0.85,
      "comfort_cost": 0.15,
      "time_cost": 0.50,
      "known": true
    }
  ]
}
```

## Scalability Considerations

### Mobile → Cloud
- **Batching**: Collect 5–10 predictions before upload → reduce network calls
- **Compression**: LZMA or gzip payloads → reduce bandwidth
- **Parallel uploads**: Multiple segments in single request

### Cloud Backend
- **Stateless**: Horizontally scalable; replicate aggregation service
- **Caching layer**: Redis cluster for distributed cache
- **Database**: PostgreSQL for audit log; separate from cache
- **Message queue**: Optional Kafka/RabbitMQ for async aggregation

### ML Inference
- **Model quantization**: Convert LSTM/RF to ONNX or TFLite for faster inference
- **Batch inference**: Group predictions by segment in cloud
- **On-device inference**: Optional offloading to edge for privacy/latency

## Security & Privacy

- **Device anonymization**: Hash vehicle ID with salt; rotate salt regularly
- **Encryption in transit**: TLS 1.3 for all mobile ↔ cloud communication
- **Data retention**: Purge raw sensor data after 7 days; keep only aggregated scores
- **Opt-in consent**: Explicit user permission for data collection
- **Differential privacy**: Add noise to segment scores to prevent re-identification

## Operational Monitoring

**Metrics to track:**
- Event trigger rate (per device, per segment)
- Aggregation finalization rate (segments with N samples)
- Cache hit/miss ratio
- API response latency (p50, p95, p99)
- Model inference latency
- Data freshness (age of cached scores)

**Logging:**
- Ingest request/response (sample-based)
- Aggregation updates per segment
- Cache invalidations
- ML inference failures
- API errors

**Alerts:**
- High false positive rate (pothole detection)
- Segment cache expiry rate > threshold
- API latency > SLA
- Model drift (confidence trends)
