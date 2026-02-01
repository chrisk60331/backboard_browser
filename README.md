# Backboard Browser

A Flask web application for browsing and managing Backboard.io resources including assistants, memory, models, documents, and threads.

## Features

- **Dashboard**: Overview of all resources with counts
- **Assistants**: Full CRUD operations for AI assistants
- **Memory**: Store, search, and retrieve memories
- **Models**: Browse available AI models
- **Documents**: Upload and manage documents
- **Threads**: Create and manage conversation threads

## Requirements

- Python 3.10+
- uv (recommended) or pip

## Installation

1. Install dependencies:
   ```bash
   uv pip install -e .
   # or
   pip install -e .
   ```

## Usage

Run the application using the startup script:

```bash
./start.sh
```

Or manually:

```bash
export FLASK_APP=app:create_app
flask run
```

The application will be available at `http://127.0.0.1:5000`

## Configuration

Set your Backboard API key either:
- Via the UI (prompted on first visit)
- Environment variable: `BACKBOARD_API_KEY`
- Flask config: `BACKBOARD_API_KEY`

## Architecture

- **Backend**: Flask with RESTful API endpoints
- **Frontend**: Tailwind CSS with vanilla JavaScript
- **SDK Integration**: Uses `backboard-sdk` with HTTP API fallback
- **Data Models**: Pydantic for type-safe data validation

## Project Structure

```
bb_browser/
├── app/
│   ├── api/          # API route handlers
│   ├── models/       # Pydantic data models
│   ├── services/     # Backboard service layer
│   └── templates/    # Jinja2 templates
├── static/           # Static files (CSS)
├── pyproject.toml    # Dependencies
└── start.sh          # Startup script
```
