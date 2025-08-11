# REPO CONTEXT
This file contains important context about this repo for [Tonkotsu](https://www.tonkotsu.ai) and helps it work faster and generate better code.

## Initial Setup
```bash
# Backend setup (Python Flask API)
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# or: source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Frontend setup (Static HTML/JS)
cd frontend
# No package manager needed - uses CDN dependencies
```

## Build
```bash
# No build process required - static frontend with Python backend
```

## Lint
```bash
# No linting configuration found in the repository
```

## Tests
```bash
# Backend has basic unit tests built into kaz_legal_web_api.py
cd backend
python -m unittest kaz_legal_web_api
```

## Dev Server
```bash
# Start backend server
cd backend
python kaz_legal_web_api.py
# Server runs on http://localhost:5000

# Frontend is static files - can be served with any HTTP server
cd frontend
python -m http.server 8000  # Simple Python server
# or use any static file server
```

## Architecture Notes
- **Backend**: Flask API with Google Generative AI integration
- **Frontend**: Static HTML/CSS/JS using CDN dependencies (marked.js, Font Awesome)
- **Deployment**: Configured for Railway (backend) and Vercel (frontend) with API proxy
- **Database**: MongoDB integration for conversation history
- **Features**: Document upload (PDF, DOCX, images), legal AI chat, conversation history

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
- MongoDB is used for conversation storage
- Project includes legal document processing and Kazakh law database