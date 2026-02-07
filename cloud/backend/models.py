"""
Data Models and Schemas for Road Comfort System

SQLAlchemy ORM models for segment data, predictions, and cache.
Pydantic schemas for API request/response validation.
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

Base = declarative_base()


# ============================================================================
# SQLAlchemy ORM Models
# ============================================================================

class RoadSegment(Base):
    """
    Road segment entity with cached comfort score.
    
    Attributes:
        segment_id: Unique segment identifier (from map-matching)
        latitude, longitude: Segment center coordinates
        comfort_score: Aggregated comfort score in [0, 1]
        sample_count: Number of vehicles contributing to this segment
        last_updated: Timestamp of last aggregation update
        expires_at: Cache expiration timestamp (30 days from last_updated)
    """
    
    __tablename__ = "road_segments"
    
    id = Column(Integer, primary_key=True)
    segment_id = Column(String, unique=True, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    comfort_score = Column(Float, default=0.5)  # [0, 1]
    sample_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)
    metadata = Column(JSON, default={})  # Extra context (road type, weather, etc.)
    
    def __repr__(self):
        return f"<RoadSegment {self.segment_id}: score={self.comfort_score:.2f}, n={self.sample_count}>"


class VehiclePrediction(Base):
    """
    Individual vehicle prediction (audit log).
    
    Attributes:
        segment_id: Road segment ID
        vehicle_id: Anonymized vehicle identifier
        comfort_score: Per-vehicle prediction
        pothole_detected: Boolean pothole flag
        confidence: Model confidence [0, 1]
        speed, heading: Context
        timestamp: Prediction timestamp
    """
    
    __tablename__ = "vehicle_predictions"
    
    id = Column(Integer, primary_key=True)
    segment_id = Column(String, nullable=False, index=True)
    vehicle_id = Column(String, nullable=False, index=True)
    comfort_score = Column(Float, nullable=False)
    pothole_detected = Column(Boolean, default=False)
    confidence = Column(Float, nullable=False)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metadata = Column(JSON, default={})
    
    def __repr__(self):
        return f"<VehiclePrediction {self.vehicle_id} @ {self.segment_id}>"


class SegmentCache(Base):
    """
    Cached segment comfort scores for fast retrieval.
    
    Attributes:
        segment_id: Road segment ID
        comfort_score: Cached aggregated score
        sample_count: Number of contributing samples
        confidence: Average model confidence
        cached_at: Timestamp when cache was last updated
        ttl_seconds: Time-to-live (30 days = 2,592,000 seconds)
    """
    
    __tablename__ = "segment_cache"
    
    segment_id = Column(String, primary_key=True, index=True)
    comfort_score = Column(Float, nullable=False)
    sample_count = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    cached_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ttl_seconds = Column(Integer, default=2592000)  # 30 days
    
    def is_valid(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = (datetime.utcnow() - self.cached_at).total_seconds()
        return elapsed < self.ttl_seconds
    
    def __repr__(self):
        return f"<SegmentCache {self.segment_id}: {self.comfort_score:.2f} @ {self.cached_at}>"


# ============================================================================
# Pydantic Schemas (API Contracts)
# ============================================================================

class PredictionMetadata(BaseModel):
    """Vehicle context at time of prediction."""
    
    speed: float = Field(..., description="Speed in m/s")
    heading: float = Field(..., description="Heading in degrees [0, 360)")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    lat: Optional[float] = Field(None, description="Latitude")
    lon: Optional[float] = Field(None, description="Longitude")


class VehiclePredictionRequest(BaseModel):
    """Request body for POST /api/v1/predictions."""
    
    segment_id: str = Field(..., description="Map-matched segment ID")
    vehicle_id: str = Field(..., description="Anonymized vehicle hash")
    prediction: Dict[str, Any] = Field(..., description="Model output")
    metadata: PredictionMetadata = Field(..., description="Context")
    
    class Config:
        schema_extra = {
            "example": {
                "segment_id": "seg_12345",
                "vehicle_id": "hash_abc123",
                "prediction": {
                    "comfort_score": 0.75,
                    "pothole_detected": False,
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
        }


class SegmentComfortResponse(BaseModel):
    """Response body for GET /api/v1/segments/{segment_id}."""
    
    segment_id: str
    comfort_score: float = Field(..., ge=0, le=1, description="Aggregated comfort [0, 1]")
    sample_count: int = Field(..., ge=0, description="Number of samples")
    last_updated: str = Field(..., description="ISO 8601 timestamp")
    expires_at: str = Field(..., description="Cache expiration timestamp")
    color: str = Field(..., description="Viz color: green/yellow/red")
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "segment_id": "seg_12345",
                "comfort_score": 0.72,
                "sample_count": 8,
                "last_updated": "2026-01-28T09:00:00Z",
                "expires_at": "2026-02-27T09:00:00Z",
                "color": "yellow",
                "metadata": {
                    "road_type": "residential",
                    "traffic_density": "medium"
                }
            }
        }


class RouteEvaluationRequest(BaseModel):
    """Request body for POST /api/v1/routes/evaluate."""
    
    segments: List[str] = Field(..., description="List of segment IDs")
    time_weight: float = Field(0.5, ge=0, le=1, description="Weight for travel time cost")
    comfort_weight: float = Field(0.5, ge=0, le=1, description="Weight for comfort cost")


class RouteEvaluationResponse(BaseModel):
    """Response for route evaluation."""
    
    total_cost: float = Field(..., description="Total route cost")
    time_cost: float = Field(..., description="Time-based cost")
    comfort_cost: float = Field(..., description="Comfort-based cost")
    average_comfort: float = Field(..., description="Average segment comfort")
    segments: List[Dict[str, Any]] = Field(..., description="Per-segment details")


class SegmentListResponse(BaseModel):
    """Response for GET /api/v1/segments (list all)."""
    
    segments: List[SegmentComfortResponse]
    total_count: int
    cached_count: int
    expired_count: int


class HealthResponse(BaseModel):
    """Response for health check endpoint."""
    
    status: str = "ok"
    timestamp: str = Field(..., description="Current timestamp")
    components: Dict[str, str] = Field(...)
