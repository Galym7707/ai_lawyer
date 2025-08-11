# REPO CONTEXT
This file contains important context about this repo for [Tonkotsu](https://www.tonkotsu.ai) and helps it work faster and generate better code.

## REPO STRUCTURE
- **backend/**: Flask-based Python API server for AI legal assistant
- **frontend/**: Static HTML/CSS/JS frontend with Vercel serverless API proxy

## INITIAL SETUP
```bash
# Backend setup (Python/Flask)
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup (Static files)
cd frontend
# No package installation needed - uses vanilla HTML/CSS/JS with CDN dependencies
```

## BUILD
```bash
# Backend: No build step required (Python)
# Frontend: No build step required (static files)
```

## LINT
```bash
# No linting configuration found in the repo
```

## TESTS
```bash
# Backend: Run unit tests in Flask app
cd backend
python -m unittest kaz_legal_web_api.TestHTMLFormatting

# Frontend: No tests found
```

## DEV SERVER
```bash
# Backend: Run Flask development server
cd backend
python kaz_legal_web_api.py
# Server runs on http://localhost:5000

# Frontend: Serve static files (any method)
cd frontend
python -m http.server 8000
# Or use any static file server
```

## PRODUCTION DEPLOYMENT
- Backend: Deployed on Railway (configured via environment variables)
- Frontend: Deployed on Vercel (configured via vercel.json)
- Frontend proxies API requests to backend via /api/* routes