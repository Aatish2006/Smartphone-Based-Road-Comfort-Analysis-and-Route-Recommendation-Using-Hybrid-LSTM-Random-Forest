# Quick Start Guide

## Project Structure Overview

```
road-comfort-system/
├── cloud/backend/           → FastAPI backend server
├── ml-pipeline/
│   ├── training/            → LSTM + Random Forest training scripts
│   ├── inference/           → ML pipeline for predictions
│   └── data/                → Dataset utilities
├── mobile/
│   ├── android/             → Kotlin skeleton
│   └── ios/                 → Swift skeleton
├── config/                  → YAML configuration files
├── docs/                    → Architecture, API docs, methodology
├── tests/                   → Unit tests
└── README.md, requirements.txt, .env.example, Dockerfile
```

## Prerequisites

- **Python 3.9+**
- **pip** and **venv** (for Python virtual environment)
- **Git** (for version control)
- **Docker** (optional, for containerized deployment)
- **Redis** (optional, for distributed caching)

## Installation

### 1. Clone or Setup Repository

```bash
cd /path/to/road-comfort-system
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings (API keys, paths, database URLs)
```

### 5. Verify Installation

```bash
python -c "import torch, sklearn, fastapi; print('All dependencies OK')"
```

## Running the Backend

### Development Mode (Local)

```bash
cd cloud/backend
python main.py
```

Server runs on `http://localhost:8000`

Interactive API docs: `http://localhost:8000/docs`

### Production Mode (Docker)

```bash
docker build -t road-comfort-system .
docker run -p 8000:8000 --env-file .env road-comfort-system
```

## Running ML Training

### Preprocess Data

```bash
cd ml-pipeline/training
python preprocessing.py  # Requires labeled dataset
```

### Train LSTM Encoder

```bash
python lstm_trainer.py
```

Output: `./models/lstm_encoder_best.pt`

### Train Random Forest

```bash
python rf_trainer.py
```

Output: `./models/rf_classifier.pkl` and `./models/scaler.pkl`

## Running Tests

```bash
pytest tests/ -v
pytest tests/test_core.py -v
```

## API Usage Examples

### Health Check

```bash
curl http://localhost:8000/health
```

### Ingest Prediction

```bash
curl -X POST http://localhost:8000/api/v1/predictions \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### Query Segment Score

```bash
curl http://localhost:8000/api/v1/segments/seg_12345
```

### Evaluate Route

```bash
curl -X POST http://localhost:8000/api/v1/routes/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "segments": ["seg_001", "seg_002", "seg_003"],
    "time_weight": 0.5,
    "comfort_weight": 0.5
  }'
```

### List All Segments

```bash
curl http://localhost:8000/api/v1/segments?valid_only=true
```

### Get Statistics

```bash
curl http://localhost:8000/api/v1/stats
```

## Configuration Files

- **`config/system_config.yaml`**: System-wide settings (aggregation N, TTL, trigger threshold)
- **`config/model_config.yaml`**: ML model architecture and hyperparameters
- **`config/sensor_config.yaml`**: Mobile sensor sampling rates and calibration
- **`.env`**: Environment-specific secrets and cloud credentials

## Development Workflow

### 1. Make Code Changes

Edit files in `cloud/backend/`, `ml-pipeline/`, etc.

### 2. Run Linting & Type Checking

```bash
black cloud/backend/
flake8 cloud/backend/
mypy cloud/backend/
```

### 3. Run Tests

```bash
pytest tests/ -v --cov=cloud
```

### 4. Test API Manually

Use `curl`, Postman, or VS Code REST Client (`.http` files)

### 5. Commit Changes

```bash
git add .
git commit -m "Feature: add route comfort weighting"
git push origin main
```

## Deployment Checklist

- [ ] All tests passing locally
- [ ] No linting errors (black, flake8)
- [ ] Docker image builds successfully
- [ ] Environment variables set in `.env`
- [ ] Database migrations applied
- [ ] ML models packaged and versioned
- [ ] API documentation updated
- [ ] Monitoring/alerts configured
- [ ] Rate limiting enabled
- [ ] Data retention policies enforced
- [ ] Privacy/compliance review complete

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'torch'`
**Solution**: Reinstall dependencies: `pip install -r requirements.txt`

### Issue: `ConnectionRefusedError` to Redis
**Solution**: Start Redis server or disable caching:
```bash
# Option 1: Start Redis
redis-server

# Option 2: Use in-memory cache (disable Redis in .env)
REDIS_URL=  # Leave empty
```

### Issue: CUDA device not available
**Solution**: Ensure PyTorch is installed for CPU:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Issue: Database connection error
**Solution**: Check PostgreSQL is running and `.env` has correct `DATABASE_URL`

## Next Steps

1. **Mobile Client**: Implement Android (Kotlin) and iOS (Swift) apps using pseudocode in `mobile/`
2. **Map Matching**: Integrate OSRM or Valhalla for GPS-to-segment mapping
3. **Visualization Frontend**: Build web/mobile map overlay with segment colors
4. **Federated Learning**: Implement on-device model updates with privacy
5. **A/B Testing**: Compare single-vehicle vs. crowdsensed comfort predictions
6. **Data Pipeline**: ETL for batch processing and model retraining

## Resources

- **Architecture Docs**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **API Specification**: [docs/API_SPEC.md](docs/API_SPEC.md)
- **Methodology**: [docs/METHODOLOGY.md](docs/METHODOLOGY.md) (to be created)
- **FastAPI**: https://fastapi.tiangolo.com/
- **PyTorch LSTM**: https://pytorch.org/docs/stable/nn.html#lstm
- **scikit-learn RF**: https://scikit-learn.org/stable/modules/ensemble.html#forests

## Support

For questions, open an issue in the repository or contact the development team.

Happy hacking! 🚗💨
