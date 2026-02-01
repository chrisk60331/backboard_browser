"""Model API routes."""
from flask import Blueprint, jsonify
from app.services.backboard import BackboardService

models_bp = Blueprint('models', __name__)

def get_service():
    """Get BackboardService instance."""
    from flask import session
    api_key = session.get('backboard_api_key')
    if not api_key:
        raise ValueError("API key not found in session")
    return BackboardService(api_key=api_key)

@models_bp.route('/api/models', methods=['GET'])
def list_models():
    """List all available models."""
    try:
        service = get_service()
        models = service.list_models()
        # Add cache headers
        response = jsonify({'data': [m.model_dump() for m in models]})
        response.headers['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@models_bp.route('/api/models/<model_id>', methods=['GET'])
def get_model_info(model_id):
    """Get information about a specific model."""
    try:
        service = get_service()
        model = service.get_model_info(model_id)
        return jsonify(model.model_dump())
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
