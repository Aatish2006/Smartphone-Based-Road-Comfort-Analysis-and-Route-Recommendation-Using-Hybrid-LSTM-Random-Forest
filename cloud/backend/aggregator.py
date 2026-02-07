"""
Aggregation Service

Implements crowdsensing logic: ingests per-vehicle predictions,
aggregates to segment-level comfort scores, and manages cache.

Design:
- Maintain in-memory buffer per segment (size N=10)
- On new prediction: add to buffer, compute aggregated score
- On query: return cached score if valid; otherwise mark as stale
- TTL: 30 days per segment
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class VehicleSample:
    """Single vehicle sample for a segment."""
    
    comfort_score: float
    confidence: float
    vehicle_id: str
    timestamp: datetime
    speed: float = 0.0
    heading: float = 0.0


@dataclass
class SegmentBuffer:
    """Aggregation buffer for a road segment."""
    
    segment_id: str
    samples: deque = field(default_factory=lambda: deque(maxlen=10))  # N=10
    aggregated_score: float = 0.5
    last_updated: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def add_sample(self, sample: VehicleSample) -> None:
        """Add vehicle sample and update aggregated score."""
        self.samples.append(sample)
        self.last_updated = datetime.utcnow()
        self._update_aggregation()
    
    def _update_aggregation(self) -> None:
        """Recompute aggregated score from buffer samples."""
        if not self.samples:
            self.aggregated_score = 0.5
            return
        
        # Weighted mean by confidence
        scores = np.array([s.comfort_score for s in self.samples])
        weights = np.array([s.confidence for s in self.samples])
        weights = weights / np.sum(weights)  # Normalize
        
        self.aggregated_score = float(np.average(scores, weights=weights))
        
        # Update expiration time (30 days from last update)
        self.expires_at = self.last_updated + timedelta(days=30)
    
    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() < self.expires_at
    
    def is_finalized(self) -> bool:
        """Check if buffer has enough samples (N=10)."""
        return len(self.samples) >= 10
    
    def sample_count(self) -> int:
        return len(self.samples)
    
    def average_confidence(self) -> float:
        if not self.samples:
            return 0.0
        return np.mean([s.confidence for s in self.samples])


class AggregationService:
    """
    Manages segment-level aggregation and caching.
    
    Constraints (from spec):
    - N = 10 vehicles per segment
    - TTL = 30 days
    - Finalization: compute score when buffer is full (or periodically)
    - Weighting: by model confidence
    """
    
    def __init__(self, segment_buffer_limit: int = 10, ttl_days: int = 30):
        self.BUFFER_LIMIT = segment_buffer_limit
        self.TTL = timedelta(days=ttl_days)
        
        # In-memory segment buffers
        self.buffers: Dict[str, SegmentBuffer] = {}
        
        logger.info(f"AggregationService initialized: N={self.BUFFER_LIMIT}, TTL={ttl_days} days")
    
    def ingest_prediction(
        self,
        segment_id: str,
        comfort_score: float,
        confidence: float,
        vehicle_id: str,
        speed: float = 0.0,
        heading: float = 0.0,
        timestamp: Optional[datetime] = None
    ) -> Tuple[float, int, bool]:
        """
        Ingest a vehicle prediction and update segment aggregation.
        
        Args:
            segment_id: Road segment identifier
            comfort_score: Vehicle's comfort prediction [0, 1]
            confidence: Model confidence [0, 1]
            vehicle_id: Anonymized vehicle ID
            speed: Vehicle speed m/s
            heading: Vehicle heading degrees
            timestamp: Prediction timestamp (default: now)
        
        Returns:
            (aggregated_score, sample_count, is_finalized)
        """
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Get or create buffer
        if segment_id not in self.buffers:
            self.buffers[segment_id] = SegmentBuffer(segment_id=segment_id)
        
        buffer = self.buffers[segment_id]
        
        # Create and add sample
        sample = VehicleSample(
            comfort_score=comfort_score,
            confidence=confidence,
            vehicle_id=vehicle_id,
            timestamp=timestamp,
            speed=speed,
            heading=heading
        )
        
        buffer.add_sample(sample)
        
        is_finalized = buffer.is_finalized()
        
        if is_finalized:
            logger.info(f"Segment {segment_id}: finalized with {buffer.sample_count()} samples")
        
        return buffer.aggregated_score, buffer.sample_count(), is_finalized
    
    def get_segment_score(self, segment_id: str) -> Optional[Dict[str, any]]:
        """
        Retrieve cached segment score.
        
        Returns:
            {
                'segment_id': str,
                'comfort_score': float,
                'sample_count': int,
                'confidence': float,
                'last_updated': datetime,
                'is_valid': bool,
                'is_finalized': bool
            }
            or None if segment not in cache
        """
        
        if segment_id not in self.buffers:
            return None
        
        buffer = self.buffers[segment_id]
        
        return {
            'segment_id': segment_id,
            'comfort_score': buffer.aggregated_score,
            'sample_count': buffer.sample_count(),
            'confidence': buffer.average_confidence(),
            'last_updated': buffer.last_updated,
            'expires_at': buffer.expires_at,
            'is_valid': buffer.is_valid(),
            'is_finalized': buffer.is_finalized()
        }
    
    def get_all_segments(
        self,
        include_invalid: bool = False,
        include_finalized_only: bool = False
    ) -> List[Dict[str, any]]:
        """
        List all cached segments.
        
        Args:
            include_invalid: Include expired cache entries
            include_finalized_only: Only return finalized segments
        
        Returns:
            List of segment data dicts
        """
        
        results = []
        for segment_id, buffer in self.buffers.items():
            if include_finalized_only and not buffer.is_finalized():
                continue
            if not include_invalid and not buffer.is_valid():
                continue
            
            results.append({
                'segment_id': segment_id,
                'comfort_score': buffer.aggregated_score,
                'sample_count': buffer.sample_count(),
                'confidence': buffer.average_confidence(),
                'last_updated': buffer.last_updated,
                'expires_at': buffer.expires_at,
                'is_valid': buffer.is_valid(),
                'is_finalized': buffer.is_finalized()
            })
        
        return results
    
    def get_recent_predictions(
        self,
        segment_id: str,
        limit: int = 10
    ) -> List[Dict[str, any]]:
        """
        Retrieve recent vehicle predictions for a segment.
        
        Args:
            segment_id: Target segment
            limit: Max predictions to return
        
        Returns:
            List of prediction records (sorted by recency)
        """
        
        if segment_id not in self.buffers:
            return []
        
        buffer = self.buffers[segment_id]
        
        predictions = [
            {
                'vehicle_id': s.vehicle_id,
                'comfort_score': s.comfort_score,
                'confidence': s.confidence,
                'timestamp': s.timestamp,
                'speed': s.speed,
                'heading': s.heading
            }
            for s in list(buffer.samples)[:limit]
        ]
        
        return predictions
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of removed segments
        """
        
        expired_ids = [
            seg_id for seg_id, buffer in self.buffers.items()
            if not buffer.is_valid()
        ]
        
        for seg_id in expired_ids:
            del self.buffers[seg_id]
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired segments")
        
        return len(expired_ids)
    
    def get_stats(self) -> Dict[str, any]:
        """Get aggregation service statistics."""
        
        all_segments = list(self.buffers.values())
        valid_segments = [b for b in all_segments if b.is_valid()]
        finalized = [b for b in valid_segments if b.is_finalized()]
        
        avg_samples = (
            np.mean([b.sample_count() for b in valid_segments])
            if valid_segments else 0
        )
        avg_comfort = (
            np.mean([b.aggregated_score for b in valid_segments])
            if valid_segments else 0.5
        )
        
        return {
            'total_segments': len(all_segments),
            'valid_segments': len(valid_segments),
            'finalized_segments': len(finalized),
            'avg_samples_per_segment': float(avg_samples),
            'avg_comfort_score': float(avg_comfort),
            'finalization_rate': float(len(finalized) / len(valid_segments)) if valid_segments else 0.0
        }


if __name__ == "__main__":
    # Example usage
    agg = AggregationService(segment_buffer_limit=10, ttl_days=30)
    
    # Simulate vehicle predictions
    for vehicle in range(5):
        score, count, finalized = agg.ingest_prediction(
            segment_id="seg_001",
            comfort_score=np.random.uniform(0.4, 0.9),
            confidence=np.random.uniform(0.8, 1.0),
            vehicle_id=f"vehicle_{vehicle}"
        )
        print(f"Vehicle {vehicle}: score={score:.3f}, n={count}, finalized={finalized}")
    
    # Query
    result = agg.get_segment_score("seg_001")
    print(f"\nSegment score: {result}")
    
    # Stats
    stats = agg.get_stats()
    print(f"\nStats: {stats}")
