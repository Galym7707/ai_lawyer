# REPO CONTEXT
This file contains important context about this repo for [Tonkotsu](https://www.tonkotsu.ai) and helps it work faster and generate better code.

## Project Structure
This is a Flask backend + vanilla JS frontend project for a legal AI assistant.

- `backend/` - Flask API server with Gemini AI integration
- `frontend/` - Static HTML/CSS/JS frontend with Vercel proxy

## Initial Setup
```bash
# Backend setup (Python Flask app)
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Frontend is static HTML/JS/CSS - no package installation needed
```

## Running Build
```bash
# This is a simple Flask app with static frontend - no build step required
# The backend uses Python dependencies from requirements.txt
# The frontend is served as static files
```

## Running Lint
```bash
# No specific linting configured in this repo
# Can use standard Python linters:
# pip install flake8 black
# flake8 backend/
# black backend/
```

## Running Tests
```bash
# Basic unit tests are included in the main Flask file
cd backend
python -m unittest kaz_legal_web_api.TestCleanAndFormatHtml
```

## Running Dev Server
```bash
# Backend (Flask API server)
cd backend
python kaz_legal_web_api.py
# Runs on http://localhost:5000

# Frontend (can be served locally)
# The frontend is static files that make API calls to the backend
# Can be opened directly in browser or served with a local server:
# python -m http.server 8000  # from frontend directory
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
- This is a Flask-based legal AI assistant for Kazakhstan law
- Backend requires environment variables (GEMINI_API_KEY, MONGO_URI, etc.)
- Frontend uses Vercel for deployment with proxy configuration
- The app uses Google's Gemini AI model for legal consultations
- Backend uses Python Flask with Gemini AI integration
- Frontend uses vanilla JS with Vercel proxy for API calls
- MongoDB is used for conversation storage
- Project includes legal document processing and Kazakh law database