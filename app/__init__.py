from flask import Flask
import os

def create_app():
    """Flask application factory."""
    # Get the base directory
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    app = Flask(__name__, 
                template_folder=os.path.join(basedir, 'templates'),
                static_folder=os.path.join(os.path.dirname(basedir), 'static'))
    app.config.from_object('app.config.Config')
    
    # Register blueprints
    from app.api.routes import api_bp
    app.register_blueprint(api_bp)
    
    return app
