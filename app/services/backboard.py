"""Backboard.io service layer using SDK."""
import asyncio
import tempfile
import os
import time
from typing import Optional, List, Any
from flask import current_app, session
from backboard import BackboardClient

from app.models.assistant import Assistant, AssistantCreate, AssistantUpdate
from app.models.memory import Memory, MemoryCreate, MemorySearch
from app.models.model import ModelInfo
from app.models.document import Document, DocumentCreate
from app.models.thread import Thread, ThreadCreate

# Simple in-memory cache for models (TTL: 1 hour)
_models_cache = {}
_models_cache_time = 0
_MODELS_CACHE_TTL = 3600  # 1 hour

# Cache for assistant thread/memory counts (TTL: 5 minutes)
# Keyed by api_key -> {assistant_id: {threads: int, memories: int}}
_counts_cache = {}
_counts_cache_time = {}
_COUNTS_CACHE_TTL = 300  # 5 minutes


class BackboardService:
    """Service for interacting with Backboard.io using SDK."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize service with API key."""
        self.api_key = api_key or self._get_api_key()
        if not self.api_key:
            raise ValueError("API key is required")
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from session or config."""
        try:
            return session.get('backboard_api_key') or current_app.config.get('BACKBOARD_API_KEY')
        except RuntimeError:
            return None
    
    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run(coro)
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)
    
    def _dict_to_model(self, data: Any, model_class):
        """Convert dict or object to Pydantic model."""
        # Convert to dict if needed
        if isinstance(data, dict):
            data_dict = data.copy()
        elif hasattr(data, 'model_dump'):
            data_dict = data.model_dump()
        elif hasattr(data, '__dict__'):
            data_dict = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
        else:
            # Try to extract attributes
            data_dict = {}
            for k in dir(data):
                if not k.startswith('_') and not callable(getattr(data, k, None)):
                    try:
                        val = getattr(data, k)
                        # Convert UUID and other objects to string
                        if hasattr(val, '__str__') and not isinstance(val, (str, int, float, bool, type(None), list, dict)):
                            val = str(val)
                        data_dict[k] = val
                    except:
                        pass
        
        # Map SDK field names to our model field names
        if model_class == Assistant:
            # SDK uses assistant_id, we use id
            if 'assistant_id' in data_dict:
                data_dict['id'] = str(data_dict.pop('assistant_id'))
            elif hasattr(data, 'assistant_id'):
                data_dict['id'] = str(getattr(data, 'assistant_id'))
            if 'model' not in data_dict and not hasattr(data, 'model'):
                data_dict['model'] = None
        
        if model_class == Document:
            # API/SDK use document_id, filename, file_size_bytes, document_type, created_at, metadata_
            if 'document_id' in data_dict:
                data_dict['id'] = str(data_dict.pop('document_id', None))
            elif hasattr(data, 'document_id'):
                data_dict['id'] = str(getattr(data, 'document_id', None))
            if 'filename' in data_dict:
                data_dict['name'] = data_dict.pop('filename', '')
            elif hasattr(data, 'filename'):
                data_dict['name'] = getattr(data, 'filename', '') or 'Unnamed'
            if 'file_size_bytes' in data_dict:
                data_dict['size'] = data_dict.pop('file_size_bytes', None)
            elif hasattr(data, 'file_size_bytes'):
                data_dict['size'] = getattr(data, 'file_size_bytes', None)
            if 'document_type' in data_dict:
                data_dict['type'] = data_dict.pop('document_type', None)
            elif hasattr(data, 'document_type'):
                data_dict['type'] = getattr(data, 'document_type', None)
            if 'created_at' in data_dict:
                data_dict['uploaded_at'] = data_dict.pop('created_at', None)
            elif hasattr(data, 'created_at'):
                data_dict['uploaded_at'] = getattr(data, 'created_at', None)
            if 'metadata_' in data_dict:
                data_dict['metadata'] = data_dict.pop('metadata_', None)
            elif hasattr(data, 'metadata_'):
                data_dict['metadata'] = getattr(data, 'metadata_', None)
            if 'name' not in data_dict:
                data_dict['name'] = 'Unnamed'
            # Remove SDK-only fields our Document model doesn't have
            known_fields = {'id', 'name', 'type', 'size', 'uploaded_at', 'metadata', 'url'}
            data_dict = {k: v for k, v in data_dict.items() if k in known_fields}
        
        if model_class == Thread:
            # SDK uses thread_id, we use id
            if 'thread_id' in data_dict:
                data_dict['id'] = str(data_dict.pop('thread_id'))
            elif hasattr(data, 'thread_id'):
                data_dict['id'] = str(getattr(data, 'thread_id'))
            # Handle messages with flexible role validation
            if 'messages' in data_dict and isinstance(data_dict['messages'], list):
                from app.models.thread import Message
                processed_messages = []
                for msg in data_dict['messages']:
                    if isinstance(msg, dict):
                        # Use model_construct to bypass strict validation
                        try:
                            processed_messages.append(Message.model_construct(
                                role=str(msg.get('role', 'user')),
                                content=str(msg.get('content', '')),
                                timestamp=msg.get('timestamp')
                            ))
                        except:
                            # If that fails, try with default role
                            try:
                                processed_messages.append(Message.model_construct(
                                    role='user',
                                    content=str(msg.get('content', '')),
                                    timestamp=msg.get('timestamp')
                                ))
                            except:
                                pass
                    elif hasattr(msg, '__dict__'):
                        # Handle SDK message objects
                        try:
                            processed_messages.append(Message.model_construct(
                                role=str(getattr(msg, 'role', 'user')),
                                content=str(getattr(msg, 'content', '')),
                                timestamp=getattr(msg, 'timestamp', None)
                            ))
                        except:
                            pass
                data_dict['messages'] = processed_messages
        
        try:
            return model_class(**data_dict)
        except Exception as e:
            # If validation fails, try with model_validate and more lenient validation
            try:
                return model_class.model_validate(data_dict, strict=False)
            except Exception:
                # Last resort: create with minimal validation
                if model_class == Thread:
                    # Handle messages separately with flexible role
                    if 'messages' in data_dict:
                        from app.models.thread import Message
                        messages = []
                        for msg in data_dict['messages']:
                            if isinstance(msg, dict):
                                # Force role to be string
                                msg_copy = msg.copy()
                                msg_copy['role'] = str(msg_copy.get('role', 'user'))
                                try:
                                    messages.append(Message(**msg_copy))
                                except:
                                    # Skip invalid messages
                                    pass
                        data_dict['messages'] = messages
                    return model_class(**data_dict)
                raise e
    
    # Assistant methods
    def list_assistants(self, skip: int = 0, limit: int = 0) -> List[Assistant]:
        """List all assistants. Set limit=0 to fetch all pages."""
        page_size = 100

        async def _list_all():
            all_items = []
            async with BackboardClient(api_key=self.api_key) as client:
                current_skip = skip
                while True:
                    batch = await client.list_assistants(skip=current_skip, limit=page_size)
                    if not batch:
                        break
                    all_items.extend(batch)
                    if len(batch) < page_size:
                        break
                    if 0 < limit <= len(all_items):
                        all_items = all_items[:limit]
                        break
                    current_skip += len(batch)
            return all_items

        result = self._run_async(_list_all())
        return [self._dict_to_model(item, Assistant) for item in result]
    
    def get_assistant(self, assistant_id: str) -> Assistant:
        """Get a specific assistant."""
        async def _get():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.get_assistant(assistant_id)
                return result
        
        result = self._run_async(_get())
        return self._dict_to_model(result, Assistant)
    
    def create_assistant(self, assistant: AssistantCreate) -> Assistant:
        """Create a new assistant."""
        async def _create():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.create_assistant(
                    name=assistant.name,
                    system_prompt=assistant.system_prompt,
                )
                return result
        
        result = self._run_async(_create())
        return self._dict_to_model(result, Assistant)
    
    def update_assistant(self, assistant_id: str, assistant: AssistantUpdate) -> Assistant:
        """Update an assistant."""
        async def _update():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.update_assistant(
                    assistant_id,
                    name=assistant.name,
                    system_prompt=assistant.system_prompt,
                )
                return result
        
        result = self._run_async(_update())
        return self._dict_to_model(result, Assistant)
    
    def delete_assistant(self, assistant_id: str) -> bool:
        """Delete an assistant."""
        async def _delete():
            async with BackboardClient(api_key=self.api_key) as client:
                await client.delete_assistant(assistant_id)
                return True
        
        self._run_async(_delete())
        return True
    
    # Memory methods
    def store_memory(self, memory: MemoryCreate, assistant_id: str) -> Memory:
        """Store a new memory."""
        async def _add():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.add_memory(
                    assistant_id=assistant_id,
                    content=memory.content,
                    metadata=memory.metadata,
                )
                return result
        
        result = self._run_async(_add())
        return Memory(
            id=getattr(result, 'id', None),
            content=memory.content,
            metadata=memory.metadata,
            tags=memory.tags,
        )
    
    def retrieve_memory(self, memory_id: str, assistant_id: str) -> Memory:
        """Retrieve a specific memory."""
        async def _get():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.get_memory(assistant_id, memory_id)
                return result
        
        result = self._run_async(_get())
        return Memory(
            id=getattr(result, 'id', memory_id),
            content=getattr(result, 'content', ''),
            metadata=getattr(result, 'metadata', None),
        )
    
    def search_memory(self, search: MemorySearch, assistant_id: str) -> List[Memory]:
        """Search memories."""
        # SDK doesn't have direct search - use get_memories and filter
        async def _list():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.get_memories(assistant_id)
                return result
        
        result = self._run_async(_list())
        if not result or not hasattr(result, 'memories'):
            return []
        
        memories = [
            Memory(
                id=getattr(m, 'id', None),
                content=getattr(m, 'content', ''),
                metadata=getattr(m, 'metadata', None),
            )
            for m in result.memories
        ]
        
        # Filter by search query
        if search.query:
            query_lower = search.query.lower()
            memories = [m for m in memories if query_lower in m.content.lower()]
        
        return memories[:search.limit or 10]
    
    def _parse_memory(self, m) -> Memory:
        """Extract a Memory from an SDK memory object or dict."""
        if isinstance(m, dict):
            base_meta = m.get('metadata') or {}
            content = m.get('content', '')
            mem_id = m.get('id') or m.get('_id')
            tags = m.get('tags')
            created = m.get('created_at')
            updated = m.get('updated_at')
            extra_keys = ('user', 'expiration', 'assistant', 'namespace',
                          'score', 'similarity', 'assistant_id', 'memory_id')
            extra = {k: m[k] for k in extra_keys if m.get(k) is not None}
        else:
            base_meta = getattr(m, 'metadata', None) or {}
            content = getattr(m, 'content', '')
            mem_id = getattr(m, 'id', None) or getattr(m, '_id', None)
            tags = getattr(m, 'tags', None)
            created = getattr(m, 'created_at', None)
            updated = getattr(m, 'updated_at', None)
            extra = {}
            for attr in ('user', 'expiration', 'assistant', 'namespace',
                         'score', 'similarity', 'assistant_id', 'memory_id'):
                val = getattr(m, attr, None)
                if val is not None:
                    extra[attr] = str(val) if not isinstance(val, (str, int, float, bool)) else val

        if not isinstance(base_meta, dict):
            base_meta = {}
        merged_meta = {**base_meta, **extra} if extra else (base_meta or None)

        return Memory(
            id=str(mem_id) if mem_id else None,
            content=content or '',
            metadata=merged_meta,
            tags=tags,
            created_at=created,
            updated_at=updated,
        )

    def list_memories(self, assistant_id: str) -> List[Memory]:
        """List all memories with pagination and full metadata extraction."""
        page_size = 100

        async def _list_all():
            all_raw = []
            async with BackboardClient(api_key=self.api_key) as client:
                skip = 0
                while True:
                    response = await client._make_request(
                        "GET", f"/assistants/{assistant_id}/memories",
                        params={"skip": skip, "limit": page_size}
                    )
                    data = response.json()
                    items = data.get('memories', data) if isinstance(data, dict) else data
                    if not items or not isinstance(items, list):
                        if isinstance(data, dict) and 'memories' in data:
                            break
                        break
                    all_raw.extend(items)
                    if len(items) < page_size:
                        break
                    skip += len(items)
            return all_raw

        try:
            raw_items = self._run_async(_list_all())
        except Exception:
            async def _fallback():
                async with BackboardClient(api_key=self.api_key) as client:
                    result = await client.get_memories(assistant_id)
                    return result
            result = self._run_async(_fallback())
            if not result or not hasattr(result, 'memories'):
                return []
            raw_items = result.memories

        return [self._parse_memory(m) for m in raw_items]
    
    def get_assistant_counts(self, assistant_ids: List[str]) -> dict:
        """Get thread and memory counts for all assistants, with caching.
        
        Returns dict of {assistant_id: {threads: int, memories: int}}.
        """
        global _counts_cache, _counts_cache_time
        
        cache_key = self.api_key
        now = time.time()
        
        # Check cache
        if (cache_key in _counts_cache and 
            cache_key in _counts_cache_time and
            now - _counts_cache_time[cache_key] < _COUNTS_CACHE_TTL):
            cached = _counts_cache[cache_key]
            # Return cached data for requested IDs
            return {aid: cached.get(aid, {'threads': 0, 'memories': 0}) for aid in assistant_ids}
        
        # Fetch all counts concurrently in a single async session
        async def _fetch_all():
            import asyncio as _asyncio
            results = {}
            semaphore = _asyncio.Semaphore(20)  # Limit concurrent requests
            
            async def _fetch_one(client, aid):
                async with semaphore:
                    thread_count = 0
                    memory_count = 0
                    try:
                        response = await client._make_request(
                            "GET", f"/assistants/{aid}/threads", params={"limit": 10000}
                        )
                        data = response.json()
                        thread_count = len(data) if isinstance(data, list) else 0
                    except Exception:
                        pass
                    try:
                        mem_result = await client.get_memories(aid)
                        if mem_result and hasattr(mem_result, 'memories'):
                            memory_count = len(mem_result.memories)
                    except Exception:
                        pass
                    results[aid] = {'threads': thread_count, 'memories': memory_count}
            
            async with BackboardClient(api_key=self.api_key) as client:
                tasks = [_fetch_one(client, aid) for aid in assistant_ids]
                await _asyncio.gather(*tasks)
            
            return results
        
        results = self._run_async(_fetch_all())
        
        # Update cache
        _counts_cache[cache_key] = results
        _counts_cache_time[cache_key] = now
        
        return results
    
    def invalidate_counts_cache(self):
        """Invalidate the counts cache for this API key."""
        global _counts_cache, _counts_cache_time
        cache_key = self.api_key
        _counts_cache.pop(cache_key, None)
        _counts_cache_time.pop(cache_key, None)
    
    def delete_memory(self, memory_id: str, assistant_id: str) -> bool:
        """Delete a memory."""
        async def _delete():
            async with BackboardClient(api_key=self.api_key) as client:
                await client.delete_memory(assistant_id, memory_id)
                return True
        
        self._run_async(_delete())
        return True
    
    # Model methods
    def list_models(self) -> List[ModelInfo]:
        """List all available models with caching."""
        global _models_cache, _models_cache_time
        
        # Check cache first
        current_time = time.time()
        if _models_cache and (current_time - _models_cache_time) < _MODELS_CACHE_TTL:
            return _models_cache
        
        # SDK doesn't have a list_models method, use HTTP API directly
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        try:
            # First request to get total count
            response = requests.get(
                'https://app.backboard.io/api/models',
                headers={'X-API-Key': self.api_key}
            )
            response.raise_for_status()
            data = response.json()
            total = data.get('total', 0)
            models_data = data.get('models', [])
            
            # If total is reasonable, fetch all in parallel batches
            if total > 100:
                all_models_data = list(models_data)  # Start with first batch
                
                # Fetch remaining pages in parallel
                def fetch_page(skip):
                    try:
                        resp = requests.get(
                            'https://app.backboard.io/api/models',
                            headers={'X-API-Key': self.api_key},
                            params={'skip': skip, 'limit': 100},
                            timeout=10
                        )
                        resp.raise_for_status()
                        return resp.json().get('models', [])
                    except Exception:
                        return []
                
                # Use ThreadPoolExecutor for parallel requests
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = []
                    for skip in range(100, total, 100):
                        futures.append(executor.submit(fetch_page, skip))
                    
                    for future in as_completed(futures):
                        try:
                            page_data = future.result()
                            all_models_data.extend(page_data)
                        except Exception:
                            continue
                
                models_data = all_models_data
            else:
                # Small dataset, just use what we got
                models_data = data.get('models', [])
            
            # Convert to ModelInfo objects
            result = []
            for item in models_data:
                try:
                    model_info = ModelInfo(
                        id=item.get('name', ''),
                        name=item.get('name', ''),
                        provider=item.get('provider'),
                        capabilities=[],
                        description=f"{item.get('model_type', 'llm').upper()} model",
                        max_tokens=item.get('context_limit'),
                        supports_streaming=item.get('supports_tools', False)
                    )
                    result.append(model_info)
                except Exception:
                    continue
            
            # Update cache
            _models_cache = result
            _models_cache_time = current_time
            
            return result
        except Exception as e:
            import traceback
            print(f"Error fetching models: {e}")
            print(traceback.format_exc())
            return []
    
    def get_model_info(self, model_id: str) -> ModelInfo:
        """Get information about a specific model."""
        # SDK doesn't have model info methods
        # Return basic info
        return ModelInfo(id=model_id, name=model_id, provider=None)
    
    # Document methods
    def list_documents(self, assistant_id: Optional[str] = None, thread_id: Optional[str] = None) -> List[Document]:
        """List all documents. If neither assistant_id nor thread_id is given, lists documents from all assistants."""
        async def _list():
            if assistant_id:
                async with BackboardClient(api_key=self.api_key) as client:
                    return await client.list_assistant_documents(assistant_id)
            if thread_id:
                async with BackboardClient(api_key=self.api_key) as client:
                    return await client.list_thread_documents(thread_id)
            # List documents from all assistants: long timeout (SDK default 30s hits 500 with many assistants)
            async with BackboardClient(api_key=self.api_key, timeout=600) as client:
                all_docs = []
                page_size = 100
                current_skip = 0
                assistant_ids = []
                while True:
                    batch = await client.list_assistants(skip=current_skip, limit=page_size)
                    if not batch:
                        break
                    for asst in batch:
                        aid = asst.get('id') if isinstance(asst, dict) else getattr(asst, 'id', None)
                        if aid:
                            assistant_ids.append(aid)
                    if len(batch) < page_size:
                        break
                    current_skip += len(batch)

                concurrency = 100
                for i in range(0, len(assistant_ids), concurrency):
                    chunk = assistant_ids[i:i + concurrency]
                    tasks = [client.list_assistant_documents(aid) for aid in chunk]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for aid, res in zip(chunk, results):
                        if isinstance(res, Exception):
                            continue
                        for item in (res or []):
                            if isinstance(item, dict):
                                item = dict(item)
                                item.setdefault('metadata', {})
                                if isinstance(item.get('metadata'), dict):
                                    item['metadata']['assistant_id'] = aid
                            all_docs.append(item)
                return all_docs

        result = self._run_async(_list())
        return [self._dict_to_model(item, Document) for item in result]
    
    def get_document(self, document_id: str) -> Document:
        """Get a specific document."""
        async def _get():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.get_document_status(document_id)
                return result
        
        result = self._run_async(_get())
        return self._dict_to_model(result, Document)
    
    def upload_document(self, document: DocumentCreate, file_content: bytes, filename: str, assistant_id: Optional[str] = None, thread_id: Optional[str] = None) -> Document:
        """Upload a document."""
        async def _upload():
            async with BackboardClient(api_key=self.api_key) as client:
                # SDK requires file_path, so write to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                    tmp.write(file_content)
                    tmp_path = tmp.name
                try:
                    if assistant_id:
                        result = await client.upload_document_to_assistant(assistant_id, tmp_path)
                    elif thread_id:
                        result = await client.upload_document_to_thread(thread_id, tmp_path)
                    else:
                        raise ValueError("assistant_id or thread_id is required")
                    return result
                finally:
                    os.unlink(tmp_path)
        
        result = self._run_async(_upload())
        return self._dict_to_model(result, Document)
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        async def _delete():
            async with BackboardClient(api_key=self.api_key) as client:
                await client.delete_document(document_id)
                return True
        
        self._run_async(_delete())
        return True
    
    # Thread methods
    def count_threads(self) -> int:
        """Get total count of threads across all pages."""
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        try:
            # First request to get total count
            response = requests.get(
                'https://app.backboard.io/api/threads',
                headers={'X-API-Key': self.api_key},
                params={'skip': 0, 'limit': 1}
            )
            response.raise_for_status()
            data = response.json()
            
            # Check if API returns a total count
            if isinstance(data, dict) and 'total' in data:
                return data['total']
            
            # If no total in response, paginate to count all
            if isinstance(data, list):
                # Start counting - first batch already counted
                total_count = len(data)
                skip = len(data)
                batch_size = 1000
                
                while True:
                    resp = requests.get(
                        'https://app.backboard.io/api/threads',
                        headers={'X-API-Key': self.api_key},
                        params={'skip': skip, 'limit': batch_size}
                    )
                    resp.raise_for_status()
                    batch = resp.json()
                    
                    if isinstance(batch, list):
                        batch_len = len(batch)
                        if batch_len == 0:
                            break
                        total_count += batch_len
                        skip += batch_len
                        if batch_len < batch_size:
                            break
                    else:
                        break
                
                return total_count
            
            return 0
        except Exception as e:
            print(f"Error counting threads: {e}")
            return 0
    
    def list_threads(self, assistant_id: Optional[str] = None, skip: int = 0, limit: int = 0) -> List[Thread]:
        """List all threads with pagination. Set limit=0 to fetch all."""
        page_size = 100

        async def _list():
            all_items = []
            async with BackboardClient(api_key=self.api_key) as client:
                current_skip = skip
                while True:
                    if assistant_id:
                        response = await client._make_request(
                            "GET", f"/assistants/{assistant_id}/threads",
                            params={"skip": current_skip, "limit": page_size}
                        )
                    else:
                        response = await client._make_request(
                            "GET", "/threads",
                            params={"skip": current_skip, "limit": page_size}
                        )
                    batch = response.json()
                    if not batch or not isinstance(batch, list):
                        break
                    all_items.extend(batch)
                    if len(batch) < page_size:
                        break
                    if 0 < limit <= len(all_items):
                        all_items = all_items[:limit]
                        break
                    current_skip += len(batch)
            return all_items
        
        result = self._run_async(_list())
        threads = []
        for item in result:
            try:
                # Pre-process messages to handle 'tool' role
                if isinstance(item, dict):
                    if 'messages' in item and isinstance(item['messages'], list):
                        for msg in item['messages']:
                            if isinstance(msg, dict) and 'role' in msg:
                                msg['role'] = str(msg['role'])  # Ensure it's a string
                    threads.append(self._dict_to_model(item, Thread))
                else:
                    # Handle SDK object
                    item_dict = {}
                    if hasattr(item, '__dict__'):
                        item_dict = {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
                    elif hasattr(item, 'model_dump'):
                        item_dict = item.model_dump()
                    
                    # Process messages
                    if 'messages' in item_dict and isinstance(item_dict['messages'], list):
                        for msg in item_dict['messages']:
                            if isinstance(msg, dict) and 'role' in msg:
                                msg['role'] = str(msg['role'])
                            elif hasattr(msg, 'role'):
                                msg_dict = msg.__dict__ if hasattr(msg, '__dict__') else {}
                                msg_dict['role'] = str(getattr(msg, 'role', 'user'))
                    
                    threads.append(self._dict_to_model(item_dict, Thread))
            except Exception as e:
                # If validation fails, create a minimal thread object
                try:
                    thread_data = {
                        'id': str(getattr(item, 'thread_id', None) or (item.get('thread_id') if isinstance(item, dict) else None) or ''),
                        'title': getattr(item, 'title', None) or (item.get('title') if isinstance(item, dict) else None),
                        'messages': [],
                        'created_at': getattr(item, 'created_at', None) or (item.get('created_at') if isinstance(item, dict) else None),
                        'updated_at': getattr(item, 'updated_at', None) or (item.get('updated_at') if isinstance(item, dict) else None),
                    }
                    # Try to extract messages with flexible role handling
                    if isinstance(item, dict) and 'messages' in item:
                        from app.models.thread import Message
                        for msg in item['messages']:
                            if isinstance(msg, dict):
                                try:
                                    # Use model_construct to bypass validation
                                    thread_data['messages'].append(Message.model_construct(
                                        role=str(msg.get('role', 'user')),
                                        content=str(msg.get('content', '')),
                                        timestamp=msg.get('timestamp')
                                    ))
                                except:
                                    # Fallback: create with minimal data
                                    try:
                                        thread_data['messages'].append(Message.model_construct(
                                            role='user',  # Default fallback
                                            content=str(msg.get('content', '')),
                                            timestamp=msg.get('timestamp')
                                        ))
                                    except:
                                        pass
                    threads.append(Thread(**thread_data))
                except:
                    # Skip threads that can't be processed
                    continue
        return threads
    
    def get_thread(self, thread_id: str) -> Thread:
        """Get a specific thread."""
        async def _get():
            async with BackboardClient(api_key=self.api_key) as client:
                # Use raw request to avoid SDK model validation (MessageRole enum)
                response = await client._make_request("GET", f"/threads/{thread_id}")
                return response.json()
        
        result = self._run_async(_get())
        return self._dict_to_model(result, Thread)
    
    def create_thread(self, assistant_id: str, thread: Optional[ThreadCreate] = None) -> Thread:
        """Create a new thread."""
        async def _create():
            async with BackboardClient(api_key=self.api_key) as client:
                result = await client.create_thread(assistant_id)
                return result
        
        result = self._run_async(_create())
        return self._dict_to_model(result, Thread)
    
    def delete_thread(self, thread_id: str) -> bool:
        """Delete a thread."""
        async def _delete():
            async with BackboardClient(api_key=self.api_key) as client:
                await client.delete_thread(thread_id)
                return True
        
        self._run_async(_delete())
        return True

    def add_message(self, thread_id: str, content: str) -> dict:
        """Send a message to a thread and return the response as a dict."""
        async def _send():
            async with BackboardClient(api_key=self.api_key) as client:
                response = await client.add_message(
                    thread_id=thread_id,
                    content=content,
                    stream=False,
                )
                return response

        response = self._run_async(_send())

        if hasattr(response, "model_dump"):
            return response.model_dump()
        elif hasattr(response, "__dict__"):
            return {k: v for k, v in response.__dict__.items() if not k.startswith("_")}
        return response if isinstance(response, dict) else {}

    def submit_tool_outputs(self, thread_id: str, run_id: str, tool_outputs: list) -> dict:
        """Submit tool outputs for a REQUIRES_ACTION run and return the response as a dict."""
        async def _submit():
            async with BackboardClient(api_key=self.api_key) as client:
                response = await client.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run_id,
                    tool_outputs=tool_outputs,
                )
                return response

        response = self._run_async(_submit())

        if hasattr(response, "model_dump"):
            return response.model_dump()
        elif hasattr(response, "__dict__"):
            return {k: v for k, v in response.__dict__.items() if not k.startswith("_")}
        return response if isinstance(response, dict) else {}
