"""Memory API routes."""
from flask import Blueprint, jsonify, request
from app.services.backboard import BackboardService
from app.models.memory import MemoryCreate, MemorySearch

memory_bp = Blueprint('memory', __name__)

def get_service():
    """Get BackboardService instance."""
    from flask import session
    api_key = session.get('backboard_api_key')
    if not api_key:
        raise ValueError("API key not found in session")
    return BackboardService(api_key=api_key)

@memory_bp.route('/api/memory', methods=['GET'])
def list_memories():
    """List all memories or search."""
    try:
        service = get_service()
        assistant_id = request.args.get('assistant_id')
        
        # If no assistant_id, return empty list (frontend handles aggregation)
        if not assistant_id:
            return jsonify({'data': []})
        
        # If assistant_id provided, return memories for that assistant only
        query = request.args.get('query')
        if query:
            search = MemorySearch(query=query, limit=int(request.args.get('limit', 10)))
            memories = service.search_memory(search, assistant_id)
        else:
            memories = service.list_memories(assistant_id)
        return jsonify({'data': [m.model_dump() for m in memories]})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@memory_bp.route('/api/memory/<memory_id>', methods=['GET'])
def get_memory(memory_id):
    """Get a specific memory."""
    try:
        service = get_service()
        assistant_id = request.args.get('assistant_id')
        if not assistant_id:
            return jsonify({'error': 'assistant_id is required'}), 400
        memory = service.retrieve_memory(memory_id, assistant_id)
        return jsonify(memory.model_dump())
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@memory_bp.route('/api/memory', methods=['POST'])
def store_memory():
    """Store a new memory."""
    try:
        service = get_service()
        data = request.get_json()
        assistant_id = data.get('assistant_id')
        if not assistant_id:
            return jsonify({'error': 'assistant_id is required'}), 400
        memory_create = MemoryCreate(**{k: v for k, v in data.items() if k != 'assistant_id'})
        memory = service.store_memory(memory_create, assistant_id)
        return jsonify(memory.model_dump()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@memory_bp.route('/api/memory/search', methods=['POST'])
def search_memory():
    """Search memories."""
    try:
        service = get_service()
        data = request.get_json()
        assistant_id = data.get('assistant_id')
        
        # If no assistant_id, search across all assistants
        if not assistant_id:
            all_memories = []
            assistants = service.list_assistants(skip=0, limit=10000)
            
            # Filter out cache assistant
            cache_assistant_name = "bb_browser_cache"
            assistants = [a for a in assistants if a.name != cache_assistant_name]
            
            query = data.get('query', '').lower()
            limit = data.get('limit', 50)
            
            for assistant in assistants:
                try:
                    memories = service.list_memories(assistant.id)
                    for memory in memories:
                        if query in memory.content.lower():
                            memory_dict = memory.model_dump()
                            memory_dict['assistant_id'] = assistant.id
                            memory_dict['assistant_name'] = assistant.name
                            all_memories.append(memory_dict)
                            if len(all_memories) >= limit:
                                break
                    if len(all_memories) >= limit:
                        break
                except Exception:
                    continue
            
            return jsonify({'data': all_memories[:limit]})
        
        # If assistant_id provided, search in that assistant only
        search = MemorySearch(**{k: v for k, v in data.items() if k != 'assistant_id'})
        memories = service.search_memory(search, assistant_id)
        return jsonify({'data': [m.model_dump() for m in memories]})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@memory_bp.route('/api/memory/<memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    """Delete a memory."""
    try:
        service = get_service()
        assistant_id = request.args.get('assistant_id')
        if not assistant_id:
            return jsonify({'error': 'assistant_id is required'}), 400
        service.delete_memory(memory_id, assistant_id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
