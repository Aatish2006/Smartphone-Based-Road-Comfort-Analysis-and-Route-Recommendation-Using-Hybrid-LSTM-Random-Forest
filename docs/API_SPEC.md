# API Specification

## Base URL

```
http://localhost:8000/api/v1  (development)
https://api.roadcomfort.example.com/api/v1  (production)
```

## Authentication

Current implementation uses optional header-based API keys (future enhancement):
```
Authorization: Bearer {api_key}
```

## Endpoints

### Health Check

#### GET `/health`

Check system health.

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2026-01-28T10:30:00Z",
  "components": {
    "api": "healthy",
    "aggregation": "healthy",
    "cache": "healthy"
  }
}
```

### Statistics

#### GET `/api/v1/stats`

Get system-wide statistics.

**Response (200 OK):**
```json
{
  "timestamp": "2026-01-28T10:30:00Z",
  "aggregation": {
    "total_segments": 1250,
    "valid_segments": 980,
    "finalized_segments": 450,
    "avg_samples_per_segment": 6.5,
    "avg_comfort_score": 0.68,
    "finalization_rate": 0.36
  },
  "cache_size": 980
}
```

---

## Prediction Ingestion

### POST `/api/v1/predictions`

Ingest a vehicle-level prediction for a road segment.

**Request Body:**
```json
{
  "segment_id": "seg_12345",
  "vehicle_id": "hash_e8f5a2c3",
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

**Response (200 OK):**
```json
{
  "status": "accepted",
  "segment_id": "seg_12345",
  "aggregated_score": 0.72,
  "sample_count": 6,
  "is_finalized": false,
  "timestamp": "2026-01-28T10:30:15Z"
}
```

**Error Responses:**
- **400 Bad Request**: Validation error (missing fields, invalid types)
- **500 Internal Server Error**: Processing error

**Notes:**
- `vehicle_id` must be anonymized (hashed with per-device salt)
- `comfort_score` should be in [0, 1]; 0.5 = neutral
- `confidence` in [0, 1]; higher = more certain
- `timestamp` must be ISO 8601 format
- Batch multiple predictions in single request for efficiency

---

## Segment Queries

### GET `/api/v1/segments/{segment_id}`

Retrieve comfort score for a specific segment.

**Parameters:**
- `segment_id` (path): Road segment identifier

**Response (200 OK):**
```json
{
  "segment_id": "seg_12345",
  "comfort_score": 0.72,
  "sample_count": 8,
  "last_updated": "2026-01-28T09:00:00Z",
  "expires_at": "2026-02-27T09:00:00Z",
  "color": "yellow",
  "metadata": {
    "road_type": "residential",
    "finalized": false
  }
}
```

**Color Mapping:**
- `green`: comfort_score > 0.70 (good road)
- `yellow`: 0.40 ≤ comfort_score ≤ 0.70 (average)
- `red`: comfort_score < 0.40 (poor/pothole-prone)

**Error Responses:**
- **404 Not Found**: Segment not in cache

---

### GET `/api/v1/segments`

List all cached segments (with optional filters).

**Query Parameters:**
- `valid_only` (boolean, default=true): Include only non-expired entries
- `finalized_only` (boolean, default=false): Include only finalized segments (N ≥ 10)

**Response (200 OK):**
```json
{
  "segments": [
    {
      "segment_id": "seg_001",
      "comfort_score": 0.85,
      "sample_count": 10,
      "last_updated": "2026-01-28T08:00:00Z",
      "expires_at": "2026-02-27T08:00:00Z",
      "color": "green"
    },
    {
      "segment_id": "seg_002",
      "comfort_score": 0.35,
      "sample_count": 5,
      "last_updated": "2026-01-28T07:30:00Z",
      "expires_at": "2026-02-27T07:30:00Z",
      "color": "red"
    }
  ],
  "total_count": 2,
  "cached_count": 2,
  "expired_count": 0
}
```

---

### GET `/api/v1/segments/{segment_id}/history`

Retrieve recent vehicle predictions for a segment.

**Parameters:**
- `segment_id` (path): Segment identifier
- `limit` (query, default=10): Max predictions to return

**Response (200 OK):**
```json
{
  "segment_id": "seg_12345",
  "predictions": [
    {
      "vehicle_id": "hash_abc123",
      "comfort_score": 0.75,
      "confidence": 0.92,
      "timestamp": "2026-01-28T10:30:00Z",
      "speed": 45.5,
      "heading": 180.0
    },
    {
      "vehicle_id": "hash_def456",
      "comfort_score": 0.70,
      "confidence": 0.85,
      "timestamp": "2026-01-28T10:15:00Z",
      "speed": 42.0,
      "heading": 180.0
    }
  ],
  "count": 2
}
```

---

## Route Evaluation

### POST `/api/v1/routes/evaluate`

Evaluate a route based on comfort and time costs.

**Request Body:**
```json
{
  "segments": ["seg_123", "seg_124", "seg_125"],
  "time_weight": 0.5,
  "comfort_weight": 0.5
}
```

**Response (200 OK):**
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
    },
    {
      "segment_id": "seg_124",
      "comfort_score": 0.80,
      "comfort_cost": 0.20,
      "time_cost": 0.50,
      "known": true
    },
    {
      "segment_id": "seg_125",
      "comfort_score": 0.50,
      "comfort_cost": 0.50,
      "time_cost": 0.50,
      "known": false
    }
  ]
}
```

**Notes:**
- Weights must sum to 1.0 (or will be normalized)
- Unknown segments (not in cache) use neutral cost (0.5)
- Total cost combines time and comfort; lower is better

---

## Administration

### POST `/api/v1/admin/cleanup`

Clean up expired cache entries.

**Response (200 OK):**
```json
{
  "status": "completed",
  "removed_segments": 42,
  "timestamp": "2026-01-28T10:30:00Z"
}
```

### POST `/api/v1/admin/cache-clear`

Clear entire cache (use with caution).

**Response (200 OK):**
```json
{
  "status": "cache cleared",
  "timestamp": "2026-01-28T10:30:00Z"
}
```

---

## Error Handling

All error responses follow this format:

```json
{
  "detail": "Error description"
}
```

**Common Status Codes:**
- **200 OK**: Successful request
- **400 Bad Request**: Invalid request format or validation error
- **404 Not Found**: Requested resource not found
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server-side error

---

## Rate Limiting

- **Default**: 100 requests per hour per device (via vehicle_id)
- **Burst**: Up to 10 concurrent requests
- **Headers**:
  - `X-RateLimit-Limit`: Maximum requests
  - `X-RateLimit-Remaining`: Requests remaining
  - `X-RateLimit-Reset`: Unix timestamp of reset

---

## Batch Operations

### Batch Prediction Ingestion

POST a list of predictions in a single request:

```json
{
  "predictions": [
    {
      "segment_id": "seg_001",
      "vehicle_id": "hash_v1",
      ...
    },
    {
      "segment_id": "seg_002",
      "vehicle_id": "hash_v2",
      ...
    }
  ]
}
```

**Response:**
```json
{
  "status": "batch_accepted",
  "count": 2,
  "results": [
    { "segment_id": "seg_001", "status": "ok" },
    { "segment_id": "seg_002", "status": "ok" }
  ]
}
```

---

## Data Types

| Type | Format | Example |
|------|--------|---------|
| `segment_id` | String (alphanumeric + underscore) | `seg_12345` |
| `vehicle_id` | String (SHA256 hash) | `a7f3c2e1...` |
| `comfort_score` | Float [0, 1] | `0.72` |
| `confidence` | Float [0, 1] | `0.92` |
| `speed` | Float (m/s) | `45.5` |
| `heading` | Float [0, 360) degrees | `180.0` |
| `timestamp` | ISO 8601 string | `2026-01-28T10:30:00Z` |
| `lat` | Float | `40.7128` |
| `lon` | Float | `-74.0060` |
