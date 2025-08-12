# Deployment Troubleshooting Guide
## Kaz Legal Bot: Frontend-Backend Connection Issues

This comprehensive guide provides step-by-step debugging instructions for resolving deployment connection issues between the Vercel frontend and Railway backend.

## Table of Contents
1. [Quick Diagnostics](#quick-diagnostics)
2. [Environment Variables Verification](#environment-variables-verification)
3. [Health Check Testing](#health-check-testing)
4. [CORS Configuration](#cors-configuration)
5. [Proxy Function Analysis](#proxy-function-analysis)
6. [Backend API Testing](#backend-api-testing)
7. [Common Error Scenarios](#common-error-scenarios)
8. [Advanced Debugging](#advanced-debugging)

---

## Quick Diagnostics

### 1. Test Proxy Diagnostics Endpoint
**Command:**
```bash
curl https://your-frontend.vercel.app/api/__diag
```

**Expected Output:**
```json
{
  "ok": true,
  "method": "GET",
  "validatedBase": "https://your-backend.railway.app",
  "targetPath": "/__diag",
  "queryString": "",
  "backendUrl": "https://your-backend.railway.app/__diag"
}
```

**If Failed:**
- ❌ Error 500: Environment variable `RAILWAY_BACKEND_URL` not configured
- ❌ Error 404: Proxy function not deployed properly
- ❌ Timeout: Network connectivity issues

---

## Environment Variables Verification

### Vercel Frontend Environment Variables

**Step 1: Check Vercel Configuration**
```bash
# Login to Vercel CLI
vercel login

# Navigate to project directory
cd frontend

# Check environment variables
vercel env ls
```

**Required Variables:**
```env
RAILWAY_BACKEND_URL=https://your-backend.railway.app
```

**Step 2: Add Missing Environment Variable**
```bash
# Add environment variable to Vercel
vercel env add RAILWAY_BACKEND_URL

# When prompted, enter:
# - Development: https://your-backend.railway.app
# - Preview: https://your-backend.railway.app  
# - Production: https://your-backend.railway.app

# Redeploy
vercel --prod
```

### Railway Backend Environment Variables

**Step 1: Check Railway Configuration**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Navigate to backend directory
cd backend

# Check environment variables
railway variables
```

**Required Variables:**
```env
GEMINI_API_KEY=your_gemini_api_key
MONGO_URI=mongodb://username:password@host:port/database
CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5000,http://127.0.0.1:5000
PORT=5000
MAX_CONTENT_LENGTH=16777216
```

**Step 2: Add Missing Variables**
```bash
# Add environment variables
railway variables set GEMINI_API_KEY=your_api_key
railway variables set MONGO_URI=your_mongo_connection_string
railway variables set CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5000,http://127.0.0.1:5000

# Redeploy
railway up
```

---

## Health Check Testing

### Backend Health Check

**Step 1: Test Direct Backend Connection**
```bash
curl -X GET "https://your-backend.railway.app/health" \
  -H "Accept: application/json"
```

**Expected Output:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-XX:XX:XX.XXXZ",
  "version": "1.0.0"
}
```

**Step 2: Test Through Proxy**
```bash
curl -X GET "https://your-frontend.vercel.app/api/health" \
  -H "Accept: application/json"
```

**Troubleshooting Health Check Issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| Connection refused | Backend not running | Check Railway deployment logs |
| 404 Not Found | Health endpoint missing | Add health endpoint to backend |
| Timeout | Network issues | Check Railway service status |

---

## CORS Configuration

### Step 1: Verify CORS Origins

**Test CORS Preflight:**
```bash
curl -X OPTIONS "https://your-backend.railway.app/api/chat" \
  -H "Origin: https://your-frontend.vercel.app" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v
```

**Expected Headers:**
```
Access-Control-Allow-Origin: https://your-frontend.vercel.app
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
```

### Step 2: Test CORS with Actual Request

**Command:**
```bash
curl -X POST "https://your-backend.railway.app/api/chat" \
  -H "Origin: https://your-frontend.vercel.app" \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "session_id": "test-session"}' \
  -v
```

**Common CORS Issues:**

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Origin not allowed | CORS policy error in browser | Add domain to CORS_ORIGINS |
| Missing preflight headers | OPTIONS request fails | Check `handle_options` route |
| Credentials blocked | Authentication fails | Verify `Access-Control-Allow-Credentials` |

---

## Proxy Function Analysis

### Step 1: Check Proxy Function Logs

**Vercel Dashboard Method:**
1. Go to Vercel dashboard → Project → Functions
2. Click on `/api/proxy/[...path].js`
3. View real-time logs

**CLI Method:**
```bash
# Stream logs in real-time
vercel logs --follow
```

### Step 2: Test Proxy Function Directly

**Test with Simple GET:**
```bash
curl -X GET "https://your-frontend.vercel.app/api/__diag" \
  -H "Accept: application/json" \
  -v
```

**Test with POST Request:**
```bash
curl -X POST "https://your-frontend.vercel.app/api/chat" \
  -H "Content-Type: application/json" \
  -H "Origin: https://your-frontend.vercel.app" \
  -d '{"message": "hello", "session_id": "test"}' \
  -v
```

**Common Proxy Errors:**

| Error Code | Meaning | Debug Steps |
|------------|---------|-------------|
| 500 | Function crashed | Check logs for error details |
| 404 | Route not found | Verify vercel.json configuration |
| 502 | Backend unreachable | Test backend URL directly |
| 504 | Timeout | Check backend response time |

---

## Backend API Testing

### Step 1: Test Core Endpoints

**Chat API:**
```bash
curl -X POST "https://your-backend.railway.app/api/chat" \
  -H "Content-Type: application/json" \
  -H "Origin: https://your-frontend.vercel.app" \
  -d '{
    "message": "Помогите с трудовым правом",
    "session_id": "test-session-123"
  }' \
  -v
```

**Sessions API:**
```bash
curl -X GET "https://your-backend.railway.app/api/sessions" \
  -H "Accept: application/json" \
  -H "Origin: https://your-frontend.vercel.app" \
  -v
```

**File Upload API:**
```bash
curl -X POST "https://your-backend.railway.app/api/upload-document" \
  -H "Origin: https://your-frontend.vercel.app" \
  -F "file=@test-document.pdf" \
  -F "session_id=test-session-123" \
  -v
```

### Step 2: Validate Response Format

**Expected Chat Response:**
```json
{
  "response": "AI generated response in HTML format",
  "session_id": "test-session-123"
}
```

**Expected Sessions Response:**
```json
{
  "sessions": [
    {
      "session_id": "session-123",
      "title": "Трудовое право",
      "last_message": "2024-01-XX:XX:XX"
    }
  ]
}
```

---

## Common Error Scenarios

### Scenario 1: "Network Error" in Browser

**Symptoms:**
- Browser console shows network error
- No request reaches backend
- CORS errors in developer tools

**Debug Commands:**
```bash
# Test if proxy is working
curl -v https://your-frontend.vercel.app/api/__diag

# Check if backend is accessible
curl -v https://your-backend.railway.app/health

# Verify CORS preflight
curl -X OPTIONS https://your-backend.railway.app/api/chat \
  -H "Origin: https://your-frontend.vercel.app" \
  -v
```

**Solutions:**
1. Verify `RAILWAY_BACKEND_URL` environment variable
2. Check CORS_ORIGINS includes your Vercel domain
3. Ensure Railway service is running

### Scenario 2: "500 Internal Server Error"

**Symptoms:**
- Backend returns 500 error
- Error logs show exceptions
- Some endpoints work, others don't

**Debug Commands:**
```bash
# Check Railway logs
railway logs

# Test specific failing endpoint
curl -X POST https://your-backend.railway.app/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "session_id": "test"}' \
  -v

# Check environment variables
railway variables
```

**Common Causes & Solutions:**
- Missing GEMINI_API_KEY → Add API key
- Invalid MONGO_URI → Check database connection
- Missing dependencies → Verify requirements.txt
- Memory/timeout issues → Check Railway resource limits

### Scenario 3: "Connection Timeout"

**Symptoms:**
- Requests hang indefinitely
- No response from backend
- Intermittent connectivity

**Debug Commands:**
```bash
# Test connection with timeout
curl --max-time 30 https://your-backend.railway.app/health

# Check Railway service status
railway status

# Test different endpoints
curl --max-time 10 https://your-backend.railway.app/
```

**Solutions:**
1. Check Railway service health
2. Verify backend isn't blocking/crashing
3. Increase timeout limits if needed
4. Check for infinite loops in code

### Scenario 4: "File Upload Failures"

**Symptoms:**
- File uploads fail
- 413 Payload Too Large errors
- Multipart form data issues

**Debug Commands:**
```bash
# Test file size limits
curl -X POST https://your-backend.railway.app/api/upload-document \
  -F "file=@small-test.pdf" \
  -F "session_id=test" \
  -v

# Check proxy for large files
curl -X POST https://your-frontend.vercel.app/api/upload-document \
  -F "file=@test.pdf" \
  -F "session_id=test" \
  -v
```

**Solutions:**
1. Check MAX_CONTENT_LENGTH environment variable
2. Verify proxy handles multipart data correctly
3. Test with smaller files first
4. Check Railway storage limits

---

## Advanced Debugging

### Enable Debug Logging

**Backend Debug Mode:**
```bash
# Add to Railway environment variables
railway variables set DEBUG=True
railway variables set LOG_LEVEL=DEBUG
```

**Frontend Debug Mode:**
```javascript
// Add to proxy function for debugging
console.log('[proxy] Request details:', {
  method,
  url: backendUrl,
  headers: headersToForward,
  bodyType: typeof requestBody,
  bodyLength: requestBody ? requestBody.length : 0
});
```

### Monitor Real-time Logs

**Railway Logs:**
```bash
# Follow logs in real-time
railway logs --follow

# Filter for specific errors
railway logs --follow | grep ERROR
```

**Vercel Logs:**
```bash
# Monitor function invocations
vercel logs --follow --scope=functions

# Monitor specific function
vercel logs --follow --scope=functions --filter="proxy"
```

### Performance Testing

**Load Test Backend:**
```bash
# Simple load test
for i in {1..10}; do
  curl -s -w "%{time_total}s\n" \
    https://your-backend.railway.app/health &
done; wait
```

**Test Concurrent Requests:**
```bash
# Apache Bench test
ab -n 100 -c 10 https://your-backend.railway.app/health

# Verify proxy handles concurrent requests
ab -n 50 -c 5 https://your-frontend.vercel.app/api/health
```

### Database Connection Testing

**MongoDB Connection Test:**
```bash
# Test from Railway container (if possible)
railway run python -c "
import os
from pymongo import MongoClient
try:
    client = MongoClient(os.getenv('MONGO_URI'))
    client.admin.command('ping')
    print('MongoDB connected successfully')
except Exception as e:
    print(f'MongoDB connection failed: {e}')
"
```

---

## Validation Checklist

Before considering the deployment fixed, verify all items:

### ✅ Environment Variables
- [ ] `RAILWAY_BACKEND_URL` set in Vercel
- [ ] `GEMINI_API_KEY` set in Railway  
- [ ] `MONGO_URI` set in Railway
- [ ] `CORS_ORIGINS` includes Vercel domain
- [ ] All environment variables deployed

### ✅ Connectivity
- [ ] Backend health check returns 200
- [ ] Proxy diagnostic endpoint works
- [ ] CORS preflight requests succeed
- [ ] POST requests work through proxy
- [ ] File uploads function correctly

### ✅ Error Handling
- [ ] No 500 errors in normal operation
- [ ] Timeout errors handled gracefully
- [ ] File size limits respected
- [ ] Database connections stable

### ✅ Performance
- [ ] Response times under 10 seconds
- [ ] No memory leaks in logs
- [ ] Concurrent requests handled
- [ ] Large files process successfully

---

## Emergency Recovery

If all else fails, try these recovery steps:

### 1. Complete Redeployment
```bash
# Frontend
cd frontend
vercel --prod --force

# Backend  
cd backend
railway up --detach
```

### 2. Reset Environment Variables
```bash
# Clear and reset all environment variables
vercel env rm RAILWAY_BACKEND_URL
vercel env add RAILWAY_BACKEND_URL

railway variables set GEMINI_API_KEY=your_key --force
railway variables set MONGO_URI=your_uri --force
```

### 3. Rollback to Last Working Version
```bash
# Check deployment history
vercel ls
railway deployments

# Rollback if needed
vercel rollback
railway rollback <deployment-id>
```

---

## Contact Points

When seeking additional help, provide:

1. **Error logs** from both Vercel and Railway
2. **curl command outputs** showing the exact failure
3. **Environment variable status** (without sensitive values)
4. **Deployment timestamps** of both services
5. **Browser console errors** if applicable

This information will help identify the root cause quickly and provide targeted solutions.