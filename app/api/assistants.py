"""Assistant API routes."""
from flask import Blueprint, jsonify, request
from app.services.backboard import BackboardService
from app.models.assistant import AssistantCreate, AssistantUpdate

assistants_bp = Blueprint('assistants', __name__)

def get_service():
    """Get BackboardService instance."""
    from flask import session
    api_key = session.get('backboard_api_key')
    if not api_key:
        raise ValueError("API key not found in session")
    return BackboardService(api_key=api_key)

@assistants_bp.route('/api/assistants', methods=['GET'])
def list_assistants():
    """List all assistants with pagination."""
    try:
        service = get_service()
        skip = int(request.args.get('skip', 0))
        limit = int(request.args.get('limit', 1000))  # Default to 1000 to get all
        assistants = service.list_assistants(skip=skip, limit=limit)
        return jsonify({'data': [a.model_dump() for a in assistants], 'count': len(assistants)})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@assistants_bp.route('/api/assistants/<assistant_id>', methods=['GET'])
def get_assistant(assistant_id):
    """Get a specific assistant."""
    try:
        service = get_service()
        assistant = service.get_assistant(assistant_id)
        return jsonify(assistant.model_dump())
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@assistants_bp.route('/api/assistants', methods=['POST'])
def create_assistant():
    """Create a new assistant."""
    try:
        service = get_service()
        data = request.get_json()
        assistant_create = AssistantCreate(**data)
        assistant = service.create_assistant(assistant_create)
        return jsonify(assistant.model_dump()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@assistants_bp.route('/api/assistants/<assistant_id>', methods=['PUT'])
def update_assistant(assistant_id):
    """Update an assistant."""
    try:
        service = get_service()
        data = request.get_json()
        assistant_update = AssistantUpdate(**data)
        assistant = service.update_assistant(assistant_id, assistant_update)
        return jsonify(assistant.model_dump())
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@assistants_bp.route('/api/assistants/<assistant_id>', methods=['DELETE'])
def delete_assistant(assistant_id):
    """Delete an assistant."""
    try:
        service = get_service()
        service.delete_assistant(assistant_id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@assistants_bp.route('/api/assistants/<assistant_id>/threads', methods=['GET'])
def get_assistant_threads(assistant_id):
    """Get threads for an assistant."""
    try:
        service = get_service()
        threads = service.list_threads()
        # Filter threads by assistant_id if SDK provides it
        # For now, return all threads
        return jsonify({'data': [t.model_dump() for t in threads]})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@assistants_bp.route('/api/assistants/<assistant_id>/memories', methods=['GET'])
def get_assistant_memories(assistant_id):
    """Get memories for an assistant."""
    try:
        service = get_service()
        memories = service.list_memories(assistant_id)
        return jsonify({'data': [m.model_dump() for m in memories]})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
