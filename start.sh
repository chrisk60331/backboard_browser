#!/bin/bash

# Clear local environment state
unset BACKBOARD_API_KEY
unset FLASK_DEBUG


echo "Using uv to install dependencies..."
uv pip install -e .


# Start Flask development server
export FLASK_APP=app:create_app
export FLASK_ENV=development

echo "Starting Flask development server..."
echo "Access the app at http://127.0.0.1:9900"
uv run flask run --host=0.0.0.0 --port=9900
