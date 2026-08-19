# ROV-GUI: BlueROV2 Depth Telemetry Monitoring System

A modern web-based monitoring system for **BlueROV2** remotely operated vehicles, featuring real-time depth telemetry, MAVLink protocol support, and an interactive 3D visualization interface.

## 📋 Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
  - [Telemetry Endpoint](#telemetry-endpoint)
  - [Source Configuration Endpoint](#source-configuration-endpoint)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Features](#features)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Overview

ROV-GUI is a comprehensive solution for monitoring BlueROV2 submersibles in real-time. It provides:

- **Real-time Depth Telemetry**: Monitor depth, descent rate, and MAVLink connectivity
- **Flexible Data Sources**: Switch between real MAVLink data (from Pixhawk) and dummy test data
- **3D Visualization**: Interactive 3D graphics using Three.js and React Three Fiber
- **RESTful API**: Clean API for telemetry data access and configuration
- **CORS Support**: Cross-Origin Resource Sharing enabled for frontend integration

### Use Cases

- Deep-sea research and exploration missions
- ROV testing and validation in controlled environments
- Educational and simulation purposes
- Real-time monitoring dashboards

---

## Project Structure

```
rov-gui/
├── backend/                    # Python Flask backend
│   ├── rov-depth.py           # Main Flask application & MAVLink handler
│   ├── rov-trajectory.py      # Trajectory tracking (optional)
│   ├── model_3d.py            # 3D model utilities
│   ├── test_sender.py         # Testing utilities
│   └── venv/                  # Python virtual environment
│
├── frontend/                   # React + TypeScript frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── types/             # TypeScript type definitions
│   │   ├── App.tsx            # Main App component
│   │   ├── main.tsx           # Entry point
│   │   └── index.css          # Global styles
│   ├── public/                # Static assets
│   ├── package.json           # Frontend dependencies
│   ├── vite.config.ts         # Vite configuration
│   └── tsconfig.json          # TypeScript configuration
│
└── README.md                  # This file
```

---

## Tech Stack

### Backend
- **Framework**: Flask (Python)
- **Protocol**: MAVLink (for ArduSub/Pixhawk communication)
- **Server**: Python built-in server (WSGI)
- **Dependencies**:
  - `flask` - Web framework
  - `flask-cors` - CORS support
  - `pymavlink` - MAVLink protocol library

### Frontend
- **Framework**: React 19
- **Language**: TypeScript
- **Build Tool**: Vite
- **3D Graphics**: Three.js with React Three Fiber (@react-three/fiber)
- **Additional Libraries**: @react-three/drei for 3D helpers
- **Build Tool**: TypeScript + Vite for optimized production builds

---

## Installation

### Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 18+** (for frontend)
- **Git** (for cloning the repository)

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install flask flask-cors pymavlink
   ```

4. **Verify installation:**
   ```bash
   python -c "import flask; import pymavlink; print('All dependencies installed!')"
   ```

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Verify installation:**
   ```bash
   npm run build
   ```

---

## Running the Application

### Start Backend Server

```bash
cd backend
python -m venv venv
# Activate venv (see Backend Setup step 2)
pip install flask flask-cors pymavlink
python rov-depth.py
```

**Expected output:**
```
 * Running on http://0.0.0.0:5001
 * Press CTRL+C to quit
[MAVLink] Connecting via udpin:0.0.0.0:14552 ...
```

### Start Frontend Development Server

```bash
cd frontend
npm run dev
```

**Expected output:**
```
  ➜  Local:   http://localhost:5173/
  ➜  Press h + enter to show help
```

### Access the Application

Open your browser and navigate to: **http://localhost:5173**

The frontend will automatically connect to the backend API at `http://localhost:5001/api/`.

---

## API Endpoints

### Base URL
```
http://localhost:5001/api
```

---

### 1. Telemetry Endpoint

**Retrieve current depth telemetry data and system status.**

#### Request

```http
GET /api/telemetry
```

**Method**: GET  
**Content-Type**: application/json  
**Authentication**: None

#### Response (Success)

**Status Code**: `200 OK`

```json
{
  "source": "dummy",
  "depth": 0.5234,
  "depth_cm": 52.34,
  "rate": 0.1523,
  "mavlink_connected": false,
  "max_depth_m": 2.0,
  "max_depth_cm": 200.0
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Current data source: `"dummy"` (test data) or `"real"` (MAVLink) |
| `depth` | float | Current depth in meters (4 decimal places) |
| `depth_cm` | float | Current depth in centimeters (2 decimal places) |
| `rate` | float | Descent/ascent rate in m/s (positive = descending, negative = ascending) |
| `mavlink_connected` | boolean | MAVLink connection status to Pixhawk/BlueOS |
| `max_depth_m` | float | Maximum depth limit in meters |
| `max_depth_cm` | float | Maximum depth limit in centimeters |

#### Example Usage

**cURL:**
```bash
curl -X GET http://localhost:5001/api/telemetry \
  -H "Content-Type: application/json"
```

**JavaScript/Fetch:**
```javascript
fetch('http://localhost:5001/api/telemetry')
  .then(response => response.json())
  .then(data => {
    console.log(`Current Depth: ${data.depth_cm} cm`);
    console.log(`Descent Rate: ${data.rate} m/s`);
    console.log(`MAVLink Connected: ${data.mavlink_connected}`);
  })
  .catch(error => console.error('Error:', error));
```

**Python (Requests):**
```python
import requests

response = requests.get('http://localhost:5001/api/telemetry')
data = response.json()
print(f"Depth: {data['depth_cm']} cm")
print(f"MAVLink Status: {data['mavlink_connected']}")
```

#### Real-time Polling

For real-time monitoring, poll this endpoint every 100-500ms:

```javascript
const pollTelemetry = async (interval = 200) => {
  setInterval(async () => {
    const response = await fetch('http://localhost:5001/api/telemetry');
    const data = await response.json();
    updateUI(data);
  }, interval);
};
```

---

### 2. Source Configuration Endpoint

**Switch between real MAVLink data and dummy test data.**

#### Request

```http
POST /api/source
Content-Type: application/json

{
  "source": "real"
}
```

**Method**: POST  
**Content-Type**: application/json  
**Authentication**: None

#### Request Body

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `source` | string | Yes | `"real"` \| `"dummy"` |

**`"real"`**: Connect to Pixhawk via MAVLink over UDP  
**`"dummy"`**: Use simulated data (for testing, no hardware required)

#### Response (Success)

**Status Code**: `200 OK`

```json
{
  "status": "ok",
  "source": "real"
}
```

#### Response (Error)

**Status Code**: `400 Bad Request`

```json
{
  "error": "source must be \"real\" or \"dummy\""
}
```

#### Example Usage

**cURL - Switch to Real Data:**
```bash
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d '{"source": "real"}'
```

**cURL - Switch to Dummy Data:**
```bash
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d '{"source": "dummy"}'
```

**JavaScript/Fetch:**
```javascript
async function setDataSource(sourceType) {
  const response = await fetch('http://localhost:5001/api/source', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ source: sourceType })
  });
  
  const result = await response.json();
  if (response.ok) {
    console.log(`✓ Switched to ${result.source} data`);
  } else {
    console.error(`✗ Error: ${result.error}`);
  }
}

// Usage
setDataSource('real');    // Switch to MAVLink
setDataSource('dummy');   // Switch to test data
```

**Python (Requests):**
```python
import requests
import json

def set_data_source(source_type):
    payload = {'source': source_type}
    response = requests.post(
        'http://localhost:5001/api/source',
        json=payload
    )
    data = response.json()
    
    if response.status_code == 200:
        print(f"✓ Source switched to: {data['source']}")
    else:
        print(f"✗ Error: {data['error']}")

# Usage
set_data_source('real')
set_data_source('dummy')
```

---

### API Response Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Invalid request body or source value |
| `500` | Internal Server Error | Backend error (MAVLink connection issue, etc.) |

---

### API Error Handling

**Example error response:**
```json
{
  "error": "source must be \"real\" or \"dummy\""
}
```

Always check the HTTP status code before processing response data. Wrap API calls in try-catch blocks:

```javascript
async function fetchTelemetry() {
  try {
    const response = await fetch('http://localhost:5001/api/telemetry');
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch telemetry:', error);
    return null;
  }
}
```

---

## Configuration

### Backend Configuration

Edit configuration variables in `backend/rov-depth.py`:

```python
# UDP Endpoint for MAVLink (must match BlueOS configuration)
MAVLINK_UDP_ENDPOINT = 'udpin:0.0.0.0:14552'

# Maximum depth limit (in meters)
MAX_DEPTH_M = 2.0

# MAVLink connection timeouts
HEARTBEAT_TIMEOUT_S = 10.0
RECV_TIMEOUT_S = 2.0
RECONNECT_DELAY_S = 3.0

# Server configuration
# app.run(host='0.0.0.0', port=5001, debug=False)
```

### BlueOS MAVLink Configuration

For real MAVLink data:

1. Open BlueOS Web Interface (typically http://192.168.2.1:80)
2. Navigate to **System → MAVLink**
3. Add a new endpoint:
   - **Type**: UDP Client
   - **IP**: `127.0.0.1` (or your backend server IP)
   - **Port**: `14552`

### Frontend Configuration

The frontend automatically connects to the backend. Adjust the API base URL in frontend source code if needed:

```javascript
const API_BASE_URL = 'http://localhost:5001/api';
```

---

## Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (React + Three.js)                │
│              http://localhost:5173                           │
│  - Real-time Telemetry Display                              │
│  - 3D Visualization                                          │
│  - User Controls (Source Toggle, etc.)                       │
└──────────────┬──────────────────────────────────────────────┘
               │ HTTP Requests (Fetch API)
               │
┌──────────────▼──────────────────────────────────────────────┐
│              Backend (Flask) - http://localhost:5001         │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ REST API Endpoints                                  │   │
│  │ - GET  /api/telemetry (current depth, rate, etc.)  │   │
│  │ - POST /api/source (switch data source)            │   │
│  └────────┬──────────────────────────────────────────┘   │
│           │                                                 │
│  ┌────────▼──────────────────────────────────────────┐    │
│  │ Telemetry Processing Layer                         │    │
│  │ - Data normalization & aggregation                 │    │
│  │ - Real/Dummy source selection                      │    │
│  └────────┬──────────────────────────────────────────┘    │
│           │                                                 │
│  ┌────────▼────────────┐   ┌──────────────────────────┐   │
│  │ MAVLink Thread      │   │ Dummy Data Thread        │   │
│  │ (Real Data Source)  │   │ (Test/Simulation Data)   │   │
│  └────────┬────────────┘   └──────────────────────────┘   │
│           │                                                 │
└──────────▼─┴─────────────────────────────────────────────┘
             │
             ▼
        ┌─────────────────────┐
        │  Pixhawk/ArduSub    │
        │   (Via MAVLink UDP) │
        └─────────────────────┘
```

### Threading Model

The backend runs three concurrent threads:

1. **Main Thread**: Flask web server
   - Handles HTTP requests
   - Serves frontend files

2. **MAVLink Thread** (`mavlink_worker`):
   - Connects to Pixhawk via UDP
   - Receives telemetry data in real-time
   - Updates shared state with depth & rate

3. **Dummy Data Thread** (`dummy_worker`):
   - Generates simulated depth data (sine oscillation)
   - Used for testing without hardware
   - Updates shared state continuously

### Data Synchronization

All threads safely access shared state using Python's `threading.Lock`:

```python
state_lock = threading.Lock()
```

This prevents race conditions and ensures data consistency.

---

## Features

### ✅ Real-time Depth Monitoring
- Continuous telemetry updates from Pixhawk
- Support for multiple depth sensors:
  - GLOBAL_POSITION_INT (relative altitude)
  - VFR_HUD (altitude + climb rate)
  - SCALED_PRESSURE (Bar30 pressure sensor)

### ✅ Flexible Data Sources
- **Real Mode**: Direct MAVLink connection to BlueROV2
- **Dummy Mode**: Simulated data for testing & development

### ✅ MAVLink Protocol Support
- Full ArduSub/Pixhawk compatibility
- Automatic heartbeat detection
- Graceful reconnection handling
- Support for all MAVLink data streams

### ✅ RESTful API
- Clean, intuitive endpoint design
- JSON request/response format
- CORS support for cross-origin requests
- Comprehensive error handling

### ✅ 3D Visualization
- Interactive 3D graphics using Three.js
- Real-time depth gauge rendering
- Responsive design for multiple screen sizes

### ✅ Development-Friendly
- TypeScript support for type safety
- Vite for fast development builds
- ESLint configuration for code quality
- Comprehensive logging for debugging

---

## Troubleshooting

### Issue: "Failed to connect to backend"

**Symptoms**: Frontend shows connection errors, API requests fail

**Solutions**:
1. Verify backend is running: `python rov-depth.py`
2. Check backend URL in frontend code (should be `http://localhost:5001`)
3. Verify Flask server is accessible: `curl http://localhost:5001/api/telemetry`
4. Check firewall settings allow port 5001

### Issue: "MAVLink connection lost"

**Symptoms**: `mavlink_connected: false`, even with "real" mode enabled

**Solutions**:
1. Verify BlueOS is running and accessible
2. Check BlueOS MAVLink endpoint configuration (IP:port must match)
3. Verify network connectivity between backend and BlueOS
4. Check firewall on both machines allows UDP port 14552
5. Monitor backend logs for detailed error messages

### Issue: "Depth reading stuck at 0.0"

**Symptoms**: Depth always shows 0, even in real mode with MAVLink connected

**Solutions**:
1. Verify sensor is connected to Pixhawk (Bar30, etc.)
2. Check ArduSub firmware version supports the sensor
3. Monitor MAVLink message stream for depth data
4. Try switching to dummy mode to verify UI is working
5. Check backend logs for sensor-specific errors

### Issue: "Frontend won't build"

**Symptoms**: TypeScript or build errors

**Solutions**:
```bash
# Clean and rebuild
rm -rf node_modules dist
npm install
npm run build

# Check for TypeScript errors
npm run lint

# Check Node version
node --version  # Should be 18+
```

### Issue: "CORS errors in browser console"

**Symptoms**: Fetch requests fail with CORS policy errors

**Solutions**:
1. Verify backend has CORS enabled: `CORS(app)` in rov-depth.py
2. Check backend API URL is correct in frontend
3. Verify backend is running before starting frontend
4. Try accessing API directly: `curl http://localhost:5001/api/telemetry`

---

## Development

### Project Setup for Development

1. **Clone repository:**
   ```bash
   git clone <repository-url>
   cd rov-gui
   ```

2. **Install dependencies (both backend & frontend):**
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install flask flask-cors pymavlink

   # Frontend
   cd ../frontend
   npm install
   ```

3. **Start development servers:**
   ```bash
   # Terminal 1: Backend
   cd backend
   python rov-depth.py

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

### Building for Production

**Frontend:**
```bash
cd frontend
npm run build
# Output in frontend/dist/
```

**Backend:**
Flask is ready for production deployment. Consider using:
- `gunicorn` for WSGI server
- `nginx` as reverse proxy
- Docker for containerization

Example with gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 rov-depth:app
```

### Code Quality

**Lint frontend code:**
```bash
cd frontend
npm run lint
```

**Format code:**
```bash
cd frontend
npm run lint -- --fix
```

### Debugging

**Backend Debugging:**
```python
# Add to rov-depth.py for verbose logging
app.run(host='0.0.0.0', port=5001, debug=True)  # Enable Flask debug mode
```

**Frontend Debugging:**
- Open DevTools: `F12` or `Ctrl+Shift+I`
- Check Console for errors
- Use React DevTools extension
- Network tab to monitor API calls

---

## License

Please refer to project documentation for licensing information.

---

## Support & Contribution

For issues, feature requests, or contributions:

1. Create a detailed issue description
2. Include steps to reproduce
3. Provide relevant logs and error messages
4. Submit pull requests with clear commit messages

---

## Related Resources

- [BlueRobotics BlueROV2 Documentation](https://www.bluerobotics.com/learn/)
- [ArduSub Documentation](https://www.ardupilot.org/ardusub/)
- [MAVLink Protocol](https://mavlink.io/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Documentation](https://react.dev/)
- [Three.js Documentation](https://threejs.org/docs/)

---

**Last Updated**: 2026-08-19  
**Version**: 1.0.0
