"""Main API routes."""
from flask import Blueprint, jsonify, request, session, render_template
from app.services.backboard import BackboardService
from app.models.assistant import AssistantCreate, AssistantUpdate
from app.models.memory import MemoryCreate, MemorySearch
from app.models.document import DocumentCreate
from app.models.thread import ThreadCreate

api_bp = Blueprint('api', __name__)

@api_bp.route('/')
def index():
    """Dashboard home page."""
    return render_template('index.html')

@api_bp.route('/assistants')
def assistants_page():
    """Assistants page."""
    return render_template('assistants.html')

@api_bp.route('/memory')
def memory_page():
    """Memory page."""
    return render_template('memory.html')

@api_bp.route('/models')
def models_page():
    """Models page."""
    return render_template('models.html')

@api_bp.route('/documents')
def documents_page():
    """Documents page."""
    return render_template('documents.html')

@api_bp.route('/threads')
def threads_page():
    """Threads page."""
    return render_template('threads.html')

@api_bp.route('/api/auth', methods=['POST'])
def set_api_key():
    """Set API key in session."""
    data = request.get_json()
    api_key = data.get('api_key')
    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    session['backboard_api_key'] = api_key
    return jsonify({'success': True})

@api_bp.route('/api/auth/check', methods=['GET'])
def check_auth():
    """Check if API key is set."""
    api_key = session.get('backboard_api_key')
    return jsonify({'authenticated': bool(api_key)})

# Import resource-specific routes
from app.api.assistants import assistants_bp
from app.api.memory import memory_bp
from app.api.models import models_bp
from app.api.documents import documents_bp
from app.api.threads import threads_bp
from app.api.cache import cache_bp

# Register blueprints
api_bp.register_blueprint(assistants_bp)
api_bp.register_blueprint(memory_bp)
api_bp.register_blueprint(models_bp)
api_bp.register_blueprint(documents_bp)
api_bp.register_blueprint(threads_bp)
api_bp.register_blueprint(cache_bp)
