"""Thread API routes."""
from flask import Blueprint, jsonify, request
from app.services.backboard import BackboardService
from app.models.thread import ThreadCreate

threads_bp = Blueprint('threads', __name__)

def get_service():
    """Get BackboardService instance."""
    from flask import session
    api_key = session.get('backboard_api_key')
    if not api_key:
        raise ValueError("API key not found in session")
    return BackboardService(api_key=api_key)

@threads_bp.route('/api/threads', methods=['GET'])
def list_threads():
    """List all threads."""
    try:
        service = get_service()
        threads = service.list_threads()
        # Use model_dump with mode='json' to handle validation issues
        result = []
        for thread in threads:
            try:
                result.append(thread.model_dump(mode='json'))
            except Exception as e:
                # If individual thread fails, try to serialize manually
                try:
                    thread_dict = {
                        'id': str(thread.id) if thread.id else None,
                        'title': thread.title,
                        'created_at': thread.created_at.isoformat() if thread.created_at else None,
                        'updated_at': thread.updated_at.isoformat() if thread.updated_at else None,
                        'metadata': thread.metadata,
                    }
                    if thread.messages:
                        thread_dict['messages'] = [
                            {
                                'role': str(msg.role),
                                'content': str(msg.content),
                                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                            }
                            for msg in thread.messages
                        ]
                    result.append(thread_dict)
                except Exception:
                    # Skip threads that can't be serialized
                    continue
        return jsonify({'data': result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@threads_bp.route('/api/threads/<thread_id>', methods=['GET'])
def get_thread(thread_id):
    """Get a specific thread."""
    try:
        service = get_service()
        thread = service.get_thread(thread_id)
        return jsonify(thread.model_dump())
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/threads', methods=['POST'])
def create_thread():
    """Create a new thread."""
    try:
        service = get_service()
        data = request.get_json()
        assistant_id = data.get('assistant_id')
        if not assistant_id:
            return jsonify({'error': 'assistant_id is required'}), 400
        thread_create = ThreadCreate(**{k: v for k, v in data.items() if k != 'assistant_id'})
        thread = service.create_thread(assistant_id, thread_create)
        return jsonify(thread.model_dump()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@threads_bp.route('/api/threads/<thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    """Delete a thread."""
    try:
        service = get_service()
        service.delete_thread(thread_id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
