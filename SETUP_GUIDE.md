# ROV-GUI Setup and Deployment Guide

Panduan lengkap untuk setup, konfigurasi, dan deployment ROV-GUI system.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Konfigurasi BlueOS](#konfigurasi-blueos)
- [Testing](#testing)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Hardware Requirements

- **Computer/Server**: Minimum 1GB RAM, 1 GHz processor (for development)
- **Network**: Ethernet or Wi-Fi connection to BlueOS device
- **BlueROV2**: With Pixhawk flight controller and BlueOS installed

### Software Requirements

**Backend:**
- Python 3.8 or higher
- pip (Python package manager)

**Frontend:**
- Node.js 18.0.0 or higher
- npm (Node Package Manager)

**System:**
- Git
- Command-line terminal (PowerShell on Windows, bash on macOS/Linux)

### Port Requirements

- **Backend**: Port 5001 (Flask server)
- **Frontend Dev**: Port 5173 (Vite dev server)
- **Frontend Production**: Port 80 (nginx) or configurable
- **UDP**: Port 14552 (MAVLink communication)

---

## Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd rov-gui
```

### 2. Backend Setup (5 minutes)

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install flask flask-cors pymavlink

# Start server
python rov-depth.py
```

Expected output:
```
 * Running on http://0.0.0.0:5001
 * Press CTRL+C to quit
[MAVLink] Connecting via udpin:0.0.0.0:14552 ...
```

### 3. Frontend Setup (3 minutes)

```bash
# In new terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Expected output:
```
  ➜  Local:   http://localhost:5173/
  ➜  Press h + enter to show help
```

### 4. Access Application

Open browser and go to: **http://localhost:5173**

---

## Detailed Setup

### Backend Installation

#### Step 1: Install Python

**Windows:**
```bash
# Download from https://www.python.org/
# OR use chocolatey:
choco install python
```

**macOS:**
```bash
# Using Homebrew
brew install python3
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

#### Step 2: Create Virtual Environment

Navigate to backend directory:
```bash
cd backend
```

Create virtual environment:
```bash
# Windows
python -m venv venv

# macOS/Linux
python3 -m venv venv
```

Activate virtual environment:
```bash
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat

# macOS/Linux
source venv/bin/activate
```

#### Step 3: Install Dependencies

```bash
pip install --upgrade pip

pip install flask flask-cors pymavlink
```

Verify installation:
```bash
python -c "import flask; import pymavlink; print('✓ All dependencies installed')"
```

#### Step 4: Run Backend Server

```bash
python rov-depth.py
```

Server should start on `http://0.0.0.0:5001`

### Frontend Installation

#### Step 1: Install Node.js

**Windows:**
```bash
# Download from https://nodejs.org/
# OR use chocolatey:
choco install nodejs
```

**macOS:**
```bash
# Using Homebrew
brew install node
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install nodejs npm
```

#### Step 2: Verify Installation

```bash
node --version
npm --version
```

Should show Node.js 18+ and npm 8+

#### Step 3: Install Dependencies

Navigate to frontend directory:
```bash
cd frontend
```

Install npm dependencies:
```bash
npm install
```

#### Step 4: Start Development Server

```bash
npm run dev
```

Frontend should be accessible at `http://localhost:5173`

---

## Konfigurasi BlueOS

### MAVLink Endpoint Configuration

For real-time MAVLink data, configure BlueOS:

#### 1. Open BlueOS Web Interface

```
http://<blueos-ip>:80
```

Default IP: `192.168.2.1` (if connected via Ethernet to Pixhawk)

#### 2. Navigate to MAVLink Settings

Menu → System → MAVLink

#### 3. Add New Endpoint

Click "Add MAVLink endpoint"

**Configuration:**
- **Type**: UDP Client
- **IP Address**: `127.0.0.1` (localhost on same machine) or `<backend-server-ip>`
- **Port**: `14552`
- **Persistent**: Enabled
- **Rate**: 10 Hz (recommended)

#### 4. Save and Restart

Click Save, then restart BlueOS if required.

### Testing MAVLink Connection

**From backend server:**
```bash
# Monitor incoming MAVLink messages
python -c "
from pymavlink import mavutil
master = mavutil.mavlink_connection('udpin:0.0.0.0:14552', timeout=5)
print('Waiting for heartbeat...')
hb = master.wait_heartbeat()
if hb:
    print(f'✓ Heartbeat received from system {master.target_system}')
else:
    print('✗ No heartbeat received')
"
```

---

## Testing

### 1. Test Backend API

**Telemetry Endpoint:**
```bash
curl http://localhost:5001/api/telemetry
```

Expected response:
```json
{
  "source": "dummy",
  "depth": 1.234,
  "depth_cm": 123.4,
  "rate": 0.05,
  "mavlink_connected": false,
  "max_depth_m": 2.0,
  "max_depth_cm": 200.0
}
```

**Source Control:**
```bash
# Switch to dummy data
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d '{"source": "dummy"}'

# Switch to real data
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d '{"source": "real"}'
```

### 2. Test Frontend

Open DevTools (F12):

**Check Console:**
- No CORS errors
- API requests showing in Network tab
- Telemetry data updating in real-time

**Test Manual:**
```javascript
// In browser console
fetch('http://localhost:5001/api/telemetry')
  .then(r => r.json())
  .then(data => console.log('Telemetry:', data))
  .catch(e => console.error('Error:', e))
```

### 3. Integration Test Script

**Python:**
```python
#!/usr/bin/env python3
import requests
import time

def test_api():
    base_url = 'http://localhost:5001/api'
    
    print("=" * 50)
    print("ROV-GUI API Test Suite")
    print("=" * 50)
    
    # Test 1: Get Telemetry
    print("\n[1] Testing GET /api/telemetry...")
    try:
        response = requests.get(f'{base_url}/telemetry', timeout=5)
        response.raise_for_status()
        data = response.json()
        print(f"    ✓ Status: {response.status_code}")
        print(f"    ✓ Depth: {data['depth_cm']} cm")
        print(f"    ✓ Source: {data['source']}")
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
    
    # Test 2: Switch to Dummy
    print("\n[2] Testing POST /api/source (dummy)...")
    try:
        response = requests.post(
            f'{base_url}/source',
            json={'source': 'dummy'},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        print(f"    ✓ Status: {response.status_code}")
        print(f"    ✓ Current source: {data['source']}")
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
    
    # Test 3: Switch to Real
    print("\n[3] Testing POST /api/source (real)...")
    try:
        response = requests.post(
            f'{base_url}/source',
            json={'source': 'real'},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        print(f"    ✓ Status: {response.status_code}")
        print(f"    ✓ Current source: {data['source']}")
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
    
    # Test 4: Invalid Source
    print("\n[4] Testing invalid source (error handling)...")
    try:
        response = requests.post(
            f'{base_url}/source',
            json={'source': 'invalid'},
            timeout=5
        )
        if response.status_code == 400:
            print(f"    ✓ Correctly returned 400 Bad Request")
            print(f"    ✓ Error: {response.json()['error']}")
        else:
            print(f"    ✗ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
    
    # Test 5: Polling
    print("\n[5] Testing real-time polling (5 samples)...")
    try:
        for i in range(5):
            response = requests.get(f'{base_url}/telemetry', timeout=5)
            response.raise_for_status()
            data = response.json()
            print(f"    ✓ Sample {i+1}: Depth={data['depth_cm']} cm")
            time.sleep(0.2)
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests passed!")
    print("=" * 50)
    return True

if __name__ == '__main__':
    test_api()
```

Run test:
```bash
python test_api.py
```

---

## Production Deployment

### Backend Deployment (gunicorn + nginx)

#### 1. Install gunicorn

```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate
pip install gunicorn
```

#### 2. Run with gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5001 --access-logfile - rov-depth:app
```

Options:
- `-w 4`: Use 4 worker processes
- `-b 0.0.0.0:5001`: Bind to all interfaces on port 5001
- `--access-logfile -`: Log to stdout

#### 3. Setup nginx Reverse Proxy

**Linux (Ubuntu):**
```bash
sudo apt install nginx

# Create config
sudo nano /etc/nginx/sites-available/rov-gui
```

**Configuration:**
```nginx
upstream rov_backend {
    server 127.0.0.1:5001;
}

server {
    listen 80;
    server_name rov-gui.example.com;
    
    client_max_body_size 10M;
    
    location /api {
        proxy_pass http://rov_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        proxy_pass http://rov_backend;
    }
}
```

Enable:
```bash
sudo ln -s /etc/nginx/sites-available/rov-gui /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Frontend Production Build

```bash
cd frontend
npm run build

# Output in frontend/dist/
```

Serve with nginx:
```nginx
server {
    listen 80;
    server_name rov-gui.example.com;
    
    root /var/www/rov-gui/dist;
    
    index index.html;
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://backend-server:5001;
    }
}
```

### Docker Deployment

**Dockerfile (Backend):**
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .

EXPOSE 5001

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "rov-depth:app"]
```

**Dockerfile (Frontend):**
```dockerfile
FROM node:18 as builder

WORKDIR /app

COPY frontend/package*.json .
RUN npm install

COPY frontend/ .
RUN npm run build

FROM nginx:latest

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

Build and run:
```bash
docker build -f Dockerfile.backend -t rov-gui-backend .
docker build -f Dockerfile.frontend -t rov-gui-frontend .

docker run -p 5001:5001 rov-gui-backend
docker run -p 80:80 rov-gui-frontend
```

---

## Troubleshooting

### Backend Won't Start

**Error**: `Address already in use`

Solution:
```bash
# Find process on port 5001
lsof -i :5001    # macOS/Linux

# Kill process
kill -9 <PID>

# Or use different port
python rov-depth.py --port 5002
```

### Frontend Won't Connect to Backend

**Symptoms**: CORS errors, 404 errors

**Solutions**:
1. Verify backend is running
2. Check API URL in frontend code
3. Verify firewall allows port 5001

### MAVLink Connection Fails

**Symptoms**: `mavlink_connected: false`

**Solutions**:
1. Verify BlueOS is running
2. Check BlueOS configuration (IP:port)
3. Test with `python -c "from pymavlink import mavutil; ..."`

### Can't Find Python/Node Commands

**Windows:**
```bash
# Reinstall and ensure "Add to PATH" is checked
python --version
node --version
```

**macOS/Linux:**
```bash
which python3
which node

# Add to PATH if needed
export PATH="/usr/local/bin:$PATH"
```

---

## Next Steps

1. **Read API Documentation**: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
2. **Explore Frontend Code**: Check `frontend/src/` directory
3. **Configure for Production**: Update security settings, add authentication
4. **Monitor Performance**: Set up logging and monitoring

---

**Last Updated**: 2026-08-19
