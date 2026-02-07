"""
Road Comfort System - FastAPI Backend

REST API endpoints for:
- Receiving vehicle predictions (POST /api/v1/predictions)
- Querying segment comfort scores (GET /api/v1/segments/{segment_id})
- Route evaluation (POST /api/v1/routes/evaluate)
- Visualization tiles (GET /api/v1/tiles/{z}/{x}/{y})
- Health check (GET /health)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import uvicorn
import logging
from datetime import datetime
from typing import Optional
import yaml
from pathlib import Path

from models import (
    RoadSegment, VehiclePrediction, SegmentCache,
    VehiclePredictionRequest, SegmentComfortResponse,
    RouteEvaluationRequest, RouteEvaluationResponse,
    HealthResponse
)
from aggregator import AggregationService
from cache import CacheManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize FastAPI app
app = FastAPI(
    title="Road Comfort Analysis API",
    version="1.0.0",
    description="Hybrid LSTM-RF system for road surface quality and pothole detection"
)

# Global services
agg_service = AggregationService(segment_buffer_limit=10, ttl_days=30)
cache_mgr = CacheManager()


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """System health check endpoint."""
    components = {
        "api": "healthy",
        "aggregation": "healthy",
        "cache": "healthy" if cache_mgr.is_available() else "degraded"
    }
    
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat(),
        components=components
    )


@app.get("/api/v1/stats")
async def get_stats():
    """Get system statistics."""
    stats = agg_service.get_stats()
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "aggregation": stats,
        "cache_size": cache_mgr.size()
    }


# ============================================================================
# Prediction Ingestion Endpoint
# ============================================================================

@app.post("/api/v1/predictions")
async def ingest_prediction(
    request: VehiclePredictionRequest,
    background_tasks: BackgroundTasks
):
    """
    Ingest vehicle-level prediction and update segment aggregation.
    
    Request body:
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
            "timestamp": "2026-01-28T10:30:00Z"
        }
    }
    """
    
    try:
        # Extract fields
        segment_id = request.segment_id
        vehicle_id = request.vehicle_id
        comfort_score = request.prediction.get("comfort_score", 0.5)
        confidence = request.prediction.get("confidence", 0.5)
        speed = request.metadata.speed
        heading = request.metadata.heading
        
        # Ingest to aggregation service
        agg_score, sample_count, is_finalized = agg_service.ingest_prediction(
            segment_id=segment_id,
            comfort_score=comfort_score,
            confidence=confidence,
            vehicle_id=vehicle_id,
            speed=speed,
            heading=heading
        )
        
        # Schedule cache update (non-blocking)
        background_tasks.add_task(
            cache_mgr.update_segment,
            segment_id=segment_id,
            comfort_score=agg_score,
            sample_count=sample_count
        )
        
        return {
            "status": "accepted",
            "segment_id": segment_id,
            "aggregated_score": agg_score,
            "sample_count": sample_count,
            "is_finalized": is_finalized,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Internal error during prediction ingestion")


# ============================================================================
# Query Endpoints
# ============================================================================

@app.get("/api/v1/segments/{segment_id}", response_model=SegmentComfortResponse)
async def get_segment_comfort(segment_id: str):
    """
    Query comfort score for a road segment.
    
    Returns:
    {
        "segment_id": "seg_12345",
        "comfort_score": 0.72,
        "sample_count": 8,
        "last_updated": "2026-01-28T09:00:00Z",
        "expires_at": "2026-02-27T09:00:00Z",
        "color": "yellow"
    }
    """
    
    # Try cache first
    cached = cache_mgr.get_segment(segment_id)
    if cached:
        return cached
    
    # Fall back to aggregation service
    segment_data = agg_service.get_segment_score(segment_id)
    if not segment_data:
        raise HTTPException(status_code=404, detail=f"Segment {segment_id} not found")
    
    # Format response
    comfort_score = segment_data['comfort_score']
    
    def score_to_color(score: float) -> str:
        """Map comfort score to visualization color."""
        if score > 0.7:
            return "green"
        elif score > 0.4:
            return "yellow"
        else:
            return "red"
    
    response = SegmentComfortResponse(
        segment_id=segment_id,
        comfort_score=comfort_score,
        sample_count=segment_data['sample_count'],
        last_updated=segment_data['last_updated'].isoformat(),
        expires_at=segment_data['expires_at'].isoformat() if segment_data['expires_at'] else None,
        color=score_to_color(comfort_score)
    )
    
    return response


@app.get("/api/v1/segments")
async def list_segments(
    valid_only: bool = True,
    finalized_only: bool = False
):
    """List all segments in cache."""
    
    segments = agg_service.get_all_segments(
        include_invalid=not valid_only,
        include_finalized_only=finalized_only
    )
    
    def score_to_color(score: float) -> str:
        if score > 0.7:
            return "green"
        elif score > 0.4:
            return "yellow"
        else:
            return "red"
    
    results = [
        SegmentComfortResponse(
            segment_id=seg['segment_id'],
            comfort_score=seg['comfort_score'],
            sample_count=seg['sample_count'],
            last_updated=seg['last_updated'].isoformat(),
            expires_at=seg['expires_at'].isoformat() if seg['expires_at'] else None,
            color=score_to_color(seg['comfort_score'])
        )
        for seg in segments
    ]
    
    return {
        "segments": results,
        "total_count": len(segments),
        "cached_count": len([s for s in segments if s['is_valid']]),
        "expired_count": len([s for s in segments if not s['is_valid']])
    }


@app.post("/api/v1/routes/evaluate", response_model=RouteEvaluationResponse)
async def evaluate_route(request: RouteEvaluationRequest):
    """
    Evaluate route comfort based on cached segment scores.
    
    Combines travel time cost and comfort cost.
    
    Request:
    {
        "segments": ["seg_123", "seg_124", "seg_125"],
        "time_weight": 0.5,
        "comfort_weight": 0.5
    }
    """
    
    segments = request.segments
    time_weight = request.time_weight
    comfort_weight = request.comfort_weight
    
    segment_details = []
    total_comfort_cost = 0.0
    total_time_cost = 0.0
    comfort_scores = []
    
    for segment_id in segments:
        segment_data = agg_service.get_segment_score(segment_id)
        
        if segment_data:
            comfort_score = segment_data['comfort_score']
            comfort_cost = 1.0 - comfort_score  # Inverse: lower score -> higher cost
        else:
            comfort_score = 0.5  # Unknown, neutral
            comfort_cost = 0.5
        
        # Time cost (simplified; assumes unit distance)
        time_cost = 1.0  # Placeholder
        
        comfort_scores.append(comfort_score)
        total_comfort_cost += comfort_cost
        total_time_cost += time_cost
        
        segment_details.append({
            "segment_id": segment_id,
            "comfort_score": comfort_score,
            "comfort_cost": comfort_cost,
            "time_cost": time_cost,
            "known": segment_data is not None
        })
    
    # Normalize costs
    n_segments = len(segments) if segments else 1
    avg_time_cost = total_time_cost / n_segments
    avg_comfort_cost = total_comfort_cost / n_segments
    
    # Weighted total cost
    total_cost = (avg_time_cost * time_weight) + (avg_comfort_cost * comfort_weight)
    avg_comfort = (sum(comfort_scores) / len(comfort_scores)) if comfort_scores else 0.5
    
    return RouteEvaluationResponse(
        total_cost=total_cost,
        time_cost=avg_time_cost,
        comfort_cost=avg_comfort_cost,
        average_comfort=avg_comfort,
        segments=segment_details
    )


@app.get("/api/v1/segments/{segment_id}/history")
async def get_segment_history(segment_id: str, limit: int = 10):
    """Get recent predictions for a segment."""
    
    predictions = agg_service.get_recent_predictions(segment_id, limit=limit)
    
    if not predictions:
        raise HTTPException(status_code=404, detail=f"No predictions for segment {segment_id}")
    
    return {
        "segment_id": segment_id,
        "predictions": predictions,
        "count": len(predictions)
    }


# ============================================================================
# Administrative Endpoints
# ============================================================================

@app.post("/api/v1/admin/cleanup")
async def cleanup_expired():
    """Clean up expired cache entries."""
    
    removed = agg_service.cleanup_expired()
    
    return {
        "status": "completed",
        "removed_segments": removed,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/v1/admin/cache-clear")
async def clear_cache():
    """Clear entire cache."""
    
    cache_mgr.clear()
    
    return {
        "status": "cache cleared",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": "Validation error", "errors": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ============================================================================
# Application Startup / Shutdown
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("Road Comfort API starting up...")
    logger.info(f"Aggregation service initialized")
    logger.info(f"Cache manager initialized")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Road Comfort API shutting down...")
    agg_service.cleanup_expired()


if __name__ == "__main__":
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
