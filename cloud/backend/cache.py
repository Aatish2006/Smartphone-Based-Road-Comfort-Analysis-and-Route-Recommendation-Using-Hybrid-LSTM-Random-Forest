"""
Cache Management Service

Wraps Redis/in-memory caching for segment comfort scores.
Provides TTL-aware storage with 30-day validity.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pickle

logger = logging.getLogger(__name__)


class CacheManager:
    """
    In-memory cache for segment comfort scores.
    
    In production, replace with Redis for distributed caching.
    """
    
    def __init__(self, backend: str = "memory", ttl_seconds: int = 2592000):
        """
        Initialize cache manager.
        
        Args:
            backend: "memory" or "redis"
            ttl_seconds: 30 days = 2,592,000 seconds
        """
        
        self.backend = backend
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"CacheManager initialized: backend={backend}, ttl={ttl_seconds}s")
    
    def update_segment(
        self,
        segment_id: str,
        comfort_score: float,
        sample_count: int,
        confidence: float = 0.0
    ) -> None:
        """
        Update cached segment score.
        
        Args:
            segment_id: Road segment ID
            comfort_score: Aggregated comfort [0, 1]
            sample_count: Number of samples
            confidence: Average model confidence
        """
        
        self.cache[segment_id] = {
            'comfort_score': comfort_score,
            'sample_count': sample_count,
            'confidence': confidence,
            'cached_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(seconds=self.ttl_seconds)).isoformat()
        }
    
    def get_segment(self, segment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached segment score.
        
        Returns:
            Cache entry dict or None if expired/not found
        """
        
        if segment_id not in self.cache:
            return None
        
        entry = self.cache[segment_id]
        expires_at = datetime.fromisoformat(entry['expires_at'])
        
        if datetime.utcnow() > expires_at:
            del self.cache[segment_id]
            return None
        
        return entry
    
    def clear(self) -> None:
        """Clear entire cache."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def size(self) -> int:
        """Return number of cached entries."""
        return len(self.cache)
    
    def cleanup_expired(self) -> int:
        """Remove expired entries; return count."""
        
        expired_keys = []
        for key, entry in self.cache.items():
            expires_at = datetime.fromisoformat(entry['expires_at'])
            if datetime.utcnow() > expires_at:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def is_available(self) -> bool:
        """Check if cache backend is operational."""
        return True
    
    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all non-expired cache entries."""
        
        valid = {}
        for key, entry in self.cache.items():
            expires_at = datetime.fromisoformat(entry['expires_at'])
            if datetime.utcnow() <= expires_at:
                valid[key] = entry
        
        return valid
