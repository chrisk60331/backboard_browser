"""Document API routes."""
from flask import Blueprint, jsonify, request
from app.services.backboard import BackboardService
from app.models.document import DocumentCreate

documents_bp = Blueprint('documents', __name__)

def get_service():
    """Get BackboardService instance."""
    from flask import session
    api_key = session.get('backboard_api_key')
    if not api_key:
        raise ValueError("API key not found in session")
    return BackboardService(api_key=api_key)

@documents_bp.route('/api/documents', methods=['GET'])
def list_documents():
    """List all documents."""
    try:
        service = get_service()
        documents = service.list_documents()
        return jsonify({'data': [d.model_dump() for d in documents]})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@documents_bp.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    """Get a specific document."""
    try:
        service = get_service()
        document = service.get_document(document_id)
        return jsonify(document.model_dump())
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@documents_bp.route('/api/documents', methods=['POST'])
def upload_document():
    """Upload a new document."""
    try:
        service = get_service()
        if 'file' in request.files:
            file = request.files['file']
            file_content = file.read()
            filename = file.filename
            data = request.form.to_dict()
            assistant_id = data.get('assistant_id')
            thread_id = data.get('thread_id')
            document_create = DocumentCreate(**{k: v for k, v in data.items() if k not in ('assistant_id', 'thread_id')})
            document = service.upload_document(document_create, file_content=file_content, filename=filename, assistant_id=assistant_id, thread_id=thread_id)
        else:
            return jsonify({'error': 'File is required'}), 400
        return jsonify(document.model_dump()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@documents_bp.route('/api/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a document."""
    try:
        service = get_service()
        service.delete_document(document_id)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
