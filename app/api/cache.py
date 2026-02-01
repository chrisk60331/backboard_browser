"""Cache API routes."""
from flask import Blueprint, jsonify, request, session
from app.services.cache import BackboardCache
from app.services.backboard import BackboardService
from concurrent.futures import ThreadPoolExecutor, as_completed

cache_bp = Blueprint('cache', __name__)

def get_cache():
    """Get BackboardCache instance."""
    api_key = session.get('backboard_api_key')
    if not api_key:
        raise ValueError("API key not found in session")
    return BackboardCache(api_key=api_key)

@cache_bp.route('/api/cache/assistants-count', methods=['GET'])
def get_assistants_count():
    """Get cached assistants count or compute and cache it."""
    try:
        api_key = session.get('backboard_api_key')
        if not api_key:
            return jsonify({'error': 'API key not found'}), 401
        
        cache = BackboardCache(api_key=api_key)
        
        # Try to get from cache
        cached_count = cache.get('assistants_count_total')
        if cached_count is not None:
            return jsonify({'count': cached_count, 'cached': True})
        
        # Compute total assistants count
        service = BackboardService(api_key=api_key)
        assistants = service.list_assistants(skip=0, limit=10000)
        total_count = len(assistants)
        
        # Cache the result
        cache.set('assistants_count_total', total_count, ttl=3600)
        
        return jsonify({'count': total_count, 'cached': False})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        print(f"Error in get_assistants_count: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/api/cache/memory-count', methods=['GET'])
def get_memory_count():
    """Get cached memory count or compute and cache it."""
    try:
        api_key = session.get('backboard_api_key')
        if not api_key:
            return jsonify({'error': 'API key not found'}), 401
        
        cache = BackboardCache(api_key=api_key)
        
        # Try to get from cache
        cached_count = cache.get('memory_count_total')
        if cached_count is not None:
            return jsonify({'count': cached_count, 'cached': True})
        
        # Compute total memory count
        service = BackboardService(api_key=api_key)
        
        # Get all assistants
        assistants = service.list_assistants(skip=0, limit=10000)
        total_memories = 0
        
        # Fetch memories for all assistants in parallel batches
        def fetch_memories(assistant_id):
            try:
                memories = service.list_memories(assistant_id)
                return len(memories)
            except Exception as e:
                print(f"Error fetching memories for {assistant_id}: {e}")
                return 0
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_memories, a.id): a.id for a in assistants}
            for future in as_completed(futures):
                total_memories += future.result()
        
        # Cache the result
        cache.set('memory_count_total', total_memories, ttl=3600)
        
        return jsonify({'count': total_memories, 'cached': False})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        print(f"Error in get_memory_count: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/api/cache/models-count', methods=['GET'])
def get_models_count():
    """Get cached models count or compute and cache it."""
    try:
        api_key = session.get('backboard_api_key')
        if not api_key:
            return jsonify({'error': 'API key not found'}), 401
        
        cache = BackboardCache(api_key=api_key)
        
        # Try to get from cache
        cached_data = cache.get('models_count_data')
        if cached_data is not None:
            return jsonify({
                'count': cached_data.get('count', 0),
                'providers': cached_data.get('providers', 0),
                'cached': True
            })
        
        # Compute total models count
        service = BackboardService(api_key=api_key)
        models = service.list_models()
        total_count = len(models)
        
        # Count unique providers
        providers = set(m.provider for m in models if m.provider)
        providers_count = len(providers)
        
        cache_data = {'count': total_count, 'providers': providers_count}
        
        # Cache the result
        cache.set('models_count_data', cache_data, ttl=3600)
        
        return jsonify({
            'count': total_count,
            'providers': providers_count,
            'cached': False
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        print(f"Error in get_models_count: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/api/cache/documents-count', methods=['GET'])
def get_documents_count():
    """Get cached documents count or compute and cache it."""
    try:
        api_key = session.get('backboard_api_key')
        if not api_key:
            return jsonify({'error': 'API key not found'}), 401
        
        cache = BackboardCache(api_key=api_key)
        
        # Try to get from cache
        cached_count = cache.get('documents_count_total')
        if cached_count is not None:
            return jsonify({'count': cached_count, 'cached': True})
        
        # Compute total documents count
        service = BackboardService(api_key=api_key)
        documents = service.list_documents()
        total_count = len(documents)
        
        # Cache the result
        cache.set('documents_count_total', total_count, ttl=3600)
        
        return jsonify({'count': total_count, 'cached': False})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        print(f"Error in get_documents_count: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@cache_bp.route('/api/cache/threads-count', methods=['GET'])
def get_threads_count():
    """Get cached threads count or compute and cache it."""
    try:
        api_key = session.get('backboard_api_key')
        if not api_key:
            return jsonify({'error': 'API key not found'}), 401
        
        cache = BackboardCache(api_key=api_key)
        
        # Try to get from cache
        cached_count = cache.get('threads_count_total')
        if cached_count is not None:
            return jsonify({'count': cached_count, 'cached': True})
        
        # Compute total threads count
        service = BackboardService(api_key=api_key)
        threads = service.list_threads()
        total_count = len(threads)
        
        # Cache the result
        cache.set('threads_count_total', total_count, ttl=3600)
        
        return jsonify({'count': total_count, 'cached': False})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        print(f"Error in get_threads_count: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
