# REPO CONTEXT
This file contains important context about this repo for [Tonkotsu](https://www.tonkotsu.ai) and helps it work faster and generate better code.

## Repository Structure
This is a full-stack web application with:
- `backend/` - Python Flask API server
- `frontend/` - Static HTML/CSS/JS client

## Initial Setup Commands

### Backend Setup (Python Flask)
```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend Setup
No additional setup required - uses vanilla HTML/CSS/JS with CDN dependencies.

## Build Commands
No specific build commands required for this project.

## Lint Commands
No specific linting configuration found in this project.

## Test Commands
```bash
cd backend
python -m unittest kaz_legal_web_api.TestHTMLFormatting
```

## Dev Server Commands

### Backend Server
```bash
cd backend
python kaz_legal_web_api.py
# Runs on http://localhost:5000
```

### Frontend Server
Serve the frontend directory with any static file server, for example:
```bash
cd frontend
python -m http.server 8000
# Runs on http://localhost:8000
```

## Additional Notes
- Backend requires environment variables (likely for Google Generative AI API and MongoDB)
- Frontend uses Vercel deployment configuration (vercel.json)
- Backend has Railway deployment support
- Virtual environment should be created as `venv/` in the backend directory (standard Python convention)