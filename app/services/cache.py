"""Backboard-based cache service."""
import json
import time
from typing import Optional, Any
from app.services.backboard import BackboardService
from app.models.memory import MemoryCreate, MemorySearch


class BackboardCache:
    """Cache service using Backboard memories."""
    
    CACHE_ASSISTANT_NAME = "bb_browser_cache"
    CACHE_TTL = 3600  # 1 hour default
    
    def __init__(self, api_key: str):
        """Initialize cache with API key."""
        self.service = BackboardService(api_key=api_key)
        self._cache_assistant_id = None
    
    def _get_cache_assistant_id(self) -> str:
        """Get or create cache assistant."""
        if self._cache_assistant_id:
            return self._cache_assistant_id
        
        # Try to find existing cache assistant
        assistants = self.service.list_assistants()
        for assistant in assistants:
            if assistant.name == self.CACHE_ASSISTANT_NAME:
                self._cache_assistant_id = assistant.id
                return self._cache_assistant_id
        
        # Create cache assistant if not found
        from app.models.assistant import AssistantCreate
        cache_assistant = self.service.create_assistant(
            AssistantCreate(
                name=self.CACHE_ASSISTANT_NAME,
                model=None,
                system_prompt="Cache storage for bb_browser application"
            )
        )
        self._cache_assistant_id = cache_assistant.id
        return self._cache_assistant_id
    
    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Get cached value."""
        try:
            assistant_id = self._get_cache_assistant_id()
            
            # List all memories and filter by metadata (more reliable than search)
            memories = self.service.list_memories(assistant_id)
            
            # Find matching memory by metadata
            for memory in memories:
                if memory.metadata and memory.metadata.get('cache_key') == key:
                    # Check TTL
                    cache_time = memory.metadata.get('cache_time', 0)
                    cache_ttl = memory.metadata.get('ttl', ttl or self.CACHE_TTL)
                    if int(time.time()) - cache_time < cache_ttl:
                        # Cache valid, return value
                        try:
                            return json.loads(memory.content)
                        except:
                            return memory.content
                    else:
                        # Cache expired, delete it
                        self.delete(key)
            
            return None
        except Exception as e:
            print(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached value."""
        try:
            assistant_id = self._get_cache_assistant_id()
            
            # Delete existing cache entry if any
            self.delete(key)
            
            # Store new cache entry
            cache_data = {
                'cache_key': key,
                'cache_time': int(time.time()),  # Backboard requires integer timestamps
                'ttl': int(ttl or self.CACHE_TTL)
            }
            
            memory_create = MemoryCreate(
                content=json.dumps(value) if not isinstance(value, str) else value,
                metadata=cache_data,
                tags=['cache', key]
            )
            
            self.service.store_memory(memory_create, assistant_id)
            return True
        except Exception as e:
            print(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete cached value."""
        try:
            assistant_id = self._get_cache_assistant_id()
            
            # List all memories and filter by metadata
            memories = self.service.list_memories(assistant_id)
            
            # Delete matching memories
            for memory in memories:
                if memory.metadata and memory.metadata.get('cache_key') == key:
                    if memory.id:
                        self.service.delete_memory(memory.id, assistant_id)
            
            return True
        except Exception as e:
            print(f"Cache delete error: {e}")
            return False
    
    def clear_expired(self) -> int:
        """Clear expired cache entries."""
        try:
            assistant_id = self._get_cache_assistant_id()
            memories = self.service.list_memories(assistant_id)
            
            expired_count = 0
            current_time = int(time.time())
            
            for memory in memories:
                if memory.metadata and memory.metadata.get('cache_key'):
                    cache_time = memory.metadata.get('cache_time', 0)
                    cache_ttl = memory.metadata.get('ttl', self.CACHE_TTL)
                    if current_time - cache_time >= cache_ttl:
                        if memory.id:
                            self.service.delete_memory(memory.id, assistant_id)
                            expired_count += 1
            
            return expired_count
        except Exception as e:
            print(f"Cache clear expired error: {e}")
            return 0
