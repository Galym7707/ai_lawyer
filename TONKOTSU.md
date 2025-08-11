# REPO CONTEXT
This file contains important context about this repo for [Tonkotsu](https://www.tonkotsu.ai) and helps it work faster and generate better code.

## Repository Structure
This is a full-stack AI legal assistant application with:
- `backend/` - Flask Python API server
- `frontend/` - Static HTML/CSS/JS frontend with Vercel deployment

## Initial Setup

### Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Setup
The frontend is static HTML/CSS/JS with no build dependencies. It uses Vercel for deployment with a Node.js proxy API.

## Commands

### Build
- **Backend**: No build step required (Python Flask)
- **Frontend**: No build step required (static files)

### Lint
- **Backend**: No linting configured
- **Frontend**: No linting configured

### Tests
- **Backend**: `python -m unittest kaz_legal_web_api.TestHTMLFormatting` (requires dependencies installed)
- **Frontend**: No tests configured

### Dev Server
- **Backend**: `python kaz_legal_web_api.py` (runs on port 5000 by default, or PORT env var)
- **Frontend**: Serve static files (e.g., `python -m http.server 8000` from frontend directory)

## Notes
- Backend requires environment variables (likely GOOGLE_API_KEY and MongoDB connection)
- Frontend uses Vercel proxy to route `/api/*` requests to backend
- Backend includes MongoDB for session storage and Google Generative AI integration
- Virtual environment should be created in `backend/.venv` based on typical Python conventions