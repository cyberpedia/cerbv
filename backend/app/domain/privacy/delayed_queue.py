"""
Delayed disclosure queue for scoreboard updates.
Uses Redis sorted sets to manage delayed reveals.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import UUID
import redis
import json


class DelayedDisclosureQueue:
    """
    Manages delayed scoreboard updates using Redis sorted sets.
    Items are scored by their reveal timestamp.
    """
    
    def __init__(self, redis_client: redis.Redis, queue_key: str = "delayed_disclosures"):
        self.redis = redis_client
        self.queue_key = queue_key
    
    def add_disclosure(
        self, 
        item_id: str, 
        reveal_at: datetime,
        data: Dict[str, Any]
    ) -> bool:
        """
        Add an item to the delayed disclosure queue.
        
        Args:
            item_id: Unique identifier for the item
            reveal_at: When the item should be revealed
            data: Data to be revealed
            
        Returns:
            True if added successfully
        """
        score = reveal_at.timestamp()
        value = json.dumps({
            "item_id": item_id,
            "data": data,
            "scheduled_at": reveal_at.isoformat(),
        })
        
        try:
            self.redis.zadd(self.queue_key, {value: score})
            return True
        except Exception:
            return False
    
    def get_pending_disclosures(self, max_count: int = 100) -> List[Dict[str, Any]]:
        """
        Get all items that should now be revealed.
        
        Args:
            max_count: Maximum number of items to return
            
        Returns:
            List of disclosures ready to be revealed
        """
        current_time = datetime.now(timezone.utc).timestamp()
        
        try:
            # Get all items with score <= current_time
            results = self.redis.zrangebyscore(
                self.queue_key, 
                "-inf", 
                current_time,
                start=0,
                num=max_count
            )
            
            disclosures = []
            for result in results:
                try:
                    parsed = json.loads(result)
                    disclosures.append(parsed)
                except json.JSONDecodeError:
                    continue
            
            return disclosures
        except Exception:
            return []
    
    def remove_disclosure(self, item_id: str) -> bool:
        """
        Remove a specific item from the queue.
        
        Args:
            item_id: The item identifier to remove
            
        Returns:
            True if removed
        """
        try:
            # Find and remove by iterating (Redis doesn't support direct removal by field)
            results = self.redis.zrange(self.queue_key, 0, -1)
            for result in results:
                try:
                    parsed = json.loads(result)
                    if parsed.get("item_id") == item_id:
                        self.redis.zrem(self.queue_key, result)
                        return True
                except json.JSONDecodeError:
                    continue
            return False
        except Exception:
            return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the delayed queue.
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            current_time = datetime.now(timezone.utc).timestamp()
            pending = self.redis.zcount(self.queue_key, current_time + 1, "+inf")
            ready = self.redis.zcount(self.queue_key, "-inf", current_time)
            total = self.redis.zcard(self.queue_key)
            
            return {
                "total_items": total,
                "pending_reveal": pending,
                "ready_to_reveal": ready,
            }
        except Exception:
            return {"error": "Failed to get queue stats"}
    
    def clear_expired(self, max_age_seconds: int = 86400) -> int:
        """
        Clear old processed items from the queue.
        
        Args:
            max_age_seconds: How old items can be before removal
            
        Returns:
            Number of items removed
        """
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - max_age_seconds
            removed = self.redis.zremrangebyscore(self.queue_key, "-inf", cutoff_time)
            return removed
        except Exception:
            return 0
