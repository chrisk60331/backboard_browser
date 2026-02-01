import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Flask configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    BACKBOARD_API_KEY = os.environ.get('BACKBOARD_API_KEY')
    BACKBOARD_API_BASE_URL = os.environ.get('BACKBOARD_API_BASE_URL', 'https://api.backboard.io/v1')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
