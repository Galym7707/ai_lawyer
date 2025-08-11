# REPO CONTEXT
This file contains important context about this repo for [Tonkotsu](https://www.tonkotsu.ai) and helps it work faster and generate better code.

## Project Structure
This is a Flask backend + vanilla JS frontend project for a legal AI assistant.

- `backend/` - Flask API server with Gemini AI integration
- `frontend/` - Static HTML/CSS/JS frontend with Vercel proxy

## Initial Setup
```bash
# Backend setup
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Frontend setup (no additional dependencies needed)
cd frontend
# Static files, no package installation required
```

## Running Build
No explicit build process - this is a Flask + static files project.

## Running Lint
No linting configuration found in the project.

## Running Tests
```bash
# Backend tests (unittest is used within the main file)
cd backend
python -m unittest kaz_legal_web_api.py
```

## Running Dev Server
```bash
# Backend server
cd backend
python kaz_legal_web_api.py
# Runs on http://localhost:5000

# Frontend development
cd frontend
# Open index.html in browser or use a local server like:
# python -m http.server 8000
```

## Environment Variables
Create `.env` file in backend directory:
```
GEMINI_API_KEY=your_api_key
MONGO_URI=your_mongo_connection_string
CORS_ORIGINS=http://localhost:5000,http://127.0.0.1:5000
PORT=5000
MAX_CONTENT_LENGTH=16777216
```

## Notes
- Backend uses Python Flask with Gemini AI integration
- Frontend uses vanilla JS with Vercel proxy for API calls
- MongoDB is used for conversation storage
- Project includes legal document processing and Kazakh law database