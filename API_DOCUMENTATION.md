# ROV-GUI API Documentation

Complete API reference for the ROV-GUI backend service.

## Table of Contents

- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [Request/Response Format](#requestresponse-format)
- [API Endpoints](#api-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

---

## Overview

The ROV-GUI API provides RESTful endpoints for accessing real-time telemetry data from BlueROV2 submersibles and controlling data sources (real vs. simulated data).

### Key Features

- **Real-time Telemetry**: Access current depth, descent rate, and system status
- **Source Control**: Switch between MAVLink (real hardware) and dummy (simulated) data
- **JSON Format**: All requests and responses use JSON
- **CORS Enabled**: Cross-origin requests from frontend are supported
- **No Authentication**: Endpoints are open for development (consider adding auth for production)

---

## Base URL

```
http://localhost:5001/api
```

**Production**: Replace `localhost:5001` with your server address and port.

---

## Authentication

Currently, the API **does not require authentication**. All endpoints are publicly accessible.

**Note**: For production deployments, consider implementing:
- API Key authentication
- Bearer token (JWT) authentication
- OAuth 2.0
- IP-based access control

---

## Request/Response Format

### Request Headers

All requests should include:

```http
Content-Type: application/json
```

### Response Format

All responses use JSON format with the following structure:

**Success Response:**
```json
{
  "status": "ok",
  "data": { /* endpoint-specific data */ }
}
```

**Error Response:**
```json
{
  "error": "Error message describing what went wrong"
}
```

### Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 400 | Bad Request - Invalid request body or parameters |
| 404 | Not Found - Endpoint does not exist |
| 500 | Internal Server Error - Backend error |

---

## API Endpoints

### Endpoint: GET /api/telemetry

Retrieve current depth telemetry data and system status.

#### Purpose

Get real-time telemetry information including current depth, descent/ascent rate, and connection status to the Pixhawk/MAVLink system.

#### HTTP Method

```
GET
```

#### URL

```
http://localhost:5001/api/telemetry
```

#### Headers

```http
Content-Type: application/json
```

#### Query Parameters

None

#### Request Body

None

#### Response (HTTP 200 - Success)

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

| Field | Type | Description | Range |
|-------|------|-------------|-------|
| `source` | string | Data source mode | `"real"`, `"dummy"` |
| `depth` | float | Current depth in meters | 0.0 - max_depth_m |
| `depth_cm` | float | Current depth in centimeters | 0.0 - max_depth_cm |
| `rate` | float | Vertical speed in m/s | - |
| `mavlink_connected` | boolean | MAVLink/Pixhawk connection status | true/false |
| `max_depth_m` | float | Maximum depth limit in meters | 2.0 (default) |
| `max_depth_cm` | float | Maximum depth limit in centimeters | 200.0 (default) |

#### Example Request

**cURL:**
```bash
curl -X GET http://localhost:5001/api/telemetry \
  -H "Content-Type: application/json"
```

**JavaScript (Fetch API):**
```javascript
fetch('http://localhost:5001/api/telemetry', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  }
})
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(data => {
    console.log('Telemetry:', data);
  })
  .catch(error => console.error('Error:', error));
```

**JavaScript (Axios):**
```javascript
import axios from 'axios';

axios.get('http://localhost:5001/api/telemetry')
  .then(response => {
    console.log('Telemetry:', response.data);
  })
  .catch(error => {
    console.error('Error fetching telemetry:', error.message);
  });
```

**Python (Requests):**
```python
import requests

try:
    response = requests.get('http://localhost:5001/api/telemetry')
    response.raise_for_status()
    data = response.json()
    
    print(f"Depth: {data['depth_cm']} cm")
    print(f"Rate: {data['rate']} m/s")
    print(f"Source: {data['source']}")
    print(f"MAVLink Connected: {data['mavlink_connected']}")
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")
```

**Go (http package):**
```go
package main

import (
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

type Telemetry struct {
    Source           string  `json:"source"`
    Depth            float64 `json:"depth"`
    DepthCm          float64 `json:"depth_cm"`
    Rate             float64 `json:"rate"`
    MAVLinkConnected bool    `json:"mavlink_connected"`
    MaxDepthM        float64 `json:"max_depth_m"`
    MaxDepthCm       float64 `json:"max_depth_cm"`
}

func getTelemetry() {
    resp, err := http.Get("http://localhost:5001/api/telemetry")
    if err != nil {
        fmt.Println("Error:", err)
        return
    }
    defer resp.Body.Close()
    
    body, _ := io.ReadAll(resp.Body)
    var data Telemetry
    json.Unmarshal(body, &data)
    
    fmt.Printf("Depth: %.2f cm\n", data.DepthCm)
}
```

#### Polling Strategy

For real-time monitoring, implement polling:

```javascript
// Poll every 200ms (5 updates per second)
const pollInterval = setInterval(async () => {
  try {
    const response = await fetch('http://localhost:5001/api/telemetry');
    const data = await response.json();
    
    // Update UI with new telemetry data
    updateDepthDisplay(data.depth_cm);
    updateRateDisplay(data.rate);
    updateConnectionStatus(data.mavlink_connected);
  } catch (error) {
    console.error('Polling error:', error);
  }
}, 200);

// Stop polling when done
clearInterval(pollInterval);
```

---

### Endpoint: POST /api/source

Switch between real MAVLink data and dummy test data.

#### Purpose

Control which data source the system should use. Select between:
- **Real**: Connect to physical Pixhawk/BlueROV2 via MAVLink
- **Dummy**: Use simulated data for testing without hardware

#### HTTP Method

```
POST
```

#### URL

```
http://localhost:5001/api/source
```

#### Headers

```http
Content-Type: application/json
```

#### Request Body (Required)

```json
{
  "source": "real"
}
```

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `source` | string | Yes | `"real"` or `"dummy"` |

#### Response (HTTP 200 - Success)

```json
{
  "status": "ok",
  "source": "real"
}
```

#### Response (HTTP 400 - Bad Request)

```json
{
  "error": "source must be \"real\" or \"dummy\""
}
```

#### Error Conditions

| Condition | Status | Response |
|-----------|--------|----------|
| Missing `source` field | 400 | `{"error": "source must be \"real\" or \"dummy\""}` |
| Invalid `source` value | 400 | `{"error": "source must be \"real\" or \"dummy\""}` |
| Malformed JSON | 400 | `{"error": ...}` |

#### Example Request

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

**JavaScript (Fetch API):**
```javascript
async function setDataSource(sourceType) {
  const validSources = ['real', 'dummy'];
  
  if (!validSources.includes(sourceType)) {
    console.error('Invalid source:', sourceType);
    return;
  }
  
  try {
    const response = await fetch('http://localhost:5001/api/source', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ source: sourceType })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      console.log(`✓ Successfully switched to ${data.source} mode`);
      return data;
    } else {
      console.error('✗ Failed to switch source:', data.error);
      return null;
    }
  } catch (error) {
    console.error('Network error:', error);
    return null;
  }
}

// Usage
setDataSource('real');    // Switch to real data
setDataSource('dummy');   // Switch to dummy data
```

**JavaScript (Axios):**
```javascript
import axios from 'axios';

async function switchDataSource(source) {
  try {
    const response = await axios.post('http://localhost:5001/api/source', {
      source: source
    });
    
    console.log('Source switched:', response.data.source);
    return response.data;
  } catch (error) {
    console.error('Error:', error.response?.data?.error || error.message);
    throw error;
  }
}

// Usage
await switchDataSource('dummy');
await switchDataSource('real');
```

**Python (Requests):**
```python
import requests
import json

def switch_data_source(source):
    """
    Switch between real and dummy data sources.
    
    Args:
        source (str): 'real' for MAVLink or 'dummy' for simulated data
        
    Returns:
        dict: Response data or None on error
    """
    url = 'http://localhost:5001/api/source'
    payload = {'source': source}
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        print(f"✓ Source changed to: {data['source']}")
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        return None

# Usage
switch_data_source('real')
switch_data_source('dummy')
```

**Go (net/http package):**
```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

type SourceRequest struct {
    Source string `json:"source"`
}

type SourceResponse struct {
    Status string `json:"status"`
    Source string `json:"source"`
}

func switchDataSource(sourceType string) error {
    payload := SourceRequest{Source: sourceType}
    body, _ := json.Marshal(payload)
    
    resp, err := http.Post(
        "http://localhost:5001/api/source",
        "application/json",
        bytes.NewBuffer(body),
    )
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    respBody, _ := io.ReadAll(resp.Body)
    var result SourceResponse
    json.Unmarshal(respBody, &result)
    
    fmt.Printf("Switched to: %s\n", result.Source)
    return nil
}
```

#### Source Behavior

**Real Mode (`"real"`):**
- Attempts to connect to Pixhawk via MAVLink over UDP
- Expects BlueOS to send data to `0.0.0.0:14552`
- Falls back to dummy data if connection fails
- Continuously monitors connection status

**Dummy Mode (`"dummy"`):**
- Generates simulated depth data (sine wave oscillation)
- No hardware required
- Ideal for UI testing and development
- Runs independently from MAVLink thread

---

## Error Handling

### HTTP Status Codes

All API responses use standard HTTP status codes:

```
200 OK           - Request succeeded
400 Bad Request  - Invalid request parameters
404 Not Found    - Endpoint does not exist
500 Server Error - Internal backend error
```

### Error Response Format

```json
{
  "error": "Detailed error message"
}
```

### Common Errors

#### Missing Request Body

```bash
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d ''
```

Response (400):
```json
{
  "error": "source must be \"real\" or \"dummy\""
}
```

#### Invalid Source Value

```bash
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d '{"source": "invalid"}'
```

Response (400):
```json
{
  "error": "source must be \"real\" or \"dummy\""
}
```

#### Malformed JSON

```bash
curl -X POST http://localhost:5001/api/source \
  -H "Content-Type: application/json" \
  -d '{invalid json}'
```

Response (400):
```json
{
  "error": "..."
}
```

### Error Handling Best Practice

Always wrap API calls in error handlers:

```javascript
async function safeApiCall(endpoint, options = {}) {
  try {
    const response = await fetch(endpoint, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    
    // Check HTTP status
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || `HTTP ${response.status}`);
    }
    
    return await response.json();
    
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error.message);
    throw error;
  }
}

// Usage
try {
  const telemetry = await safeApiCall('/api/telemetry');
  console.log('Depth:', telemetry.depth_cm);
} catch (error) {
  // Handle error appropriately
}
```

---

## Rate Limiting

Currently, **no rate limiting is implemented**. For production:

**Recommendations:**
- Implement token bucket or sliding window rate limiting
- Limit to 100-1000 requests per minute per client
- Use IP-based or key-based tracking
- Return `429 Too Many Requests` when exceeded

---

## Examples

### Complete Monitoring Loop

```javascript
class ROVMonitor {
  constructor(apiUrl = 'http://localhost:5001/api') {
    this.apiUrl = apiUrl;
    this.pollInterval = null;
    this.callbacks = {
      onData: null,
      onError: null,
      onConnectivityChange: null
    };
    this.lastState = null;
  }

  async fetchTelemetry() {
    try {
      const response = await fetch(`${this.apiUrl}/telemetry`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      this.callbacks.onError?.(error);
      throw error;
    }
  }

  async setDataSource(source) {
    try {
      const response = await fetch(`${this.apiUrl}/source`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source })
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      this.callbacks.onError?.(error);
      throw error;
    }
  }

  startMonitoring(interval = 200) {
    this.pollInterval = setInterval(async () => {
      try {
        const data = await this.fetchTelemetry();
        
        // Check for connectivity changes
        if (this.lastState?.mavlink_connected !== data.mavlink_connected) {
          this.callbacks.onConnectivityChange?.(data.mavlink_connected);
        }
        
        this.callbacks.onData?.(data);
        this.lastState = data;
      } catch (error) {
        console.error('Monitoring error:', error);
      }
    }, interval);
  }

  stopMonitoring() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }
}

// Usage
const monitor = new ROVMonitor();

monitor.callbacks.onData = (data) => {
  console.log(`Depth: ${data.depth_cm.toFixed(2)} cm`);
  console.log(`Rate: ${data.rate.toFixed(3)} m/s`);
};

monitor.callbacks.onConnectivityChange = (connected) => {
  console.log(`MAVLink ${connected ? 'CONNECTED' : 'DISCONNECTED'}`);
};

monitor.callbacks.onError = (error) => {
  console.error('API Error:', error.message);
};

monitor.startMonitoring(200);

// Later: switch to real data
await monitor.setDataSource('real');

// Stop monitoring
monitor.stopMonitoring();
```

### Batch Telemetry Collection

```python
import requests
import time
from datetime import datetime

class TelemetryRecorder:
    def __init__(self, api_url='http://localhost:5001/api'):
        self.api_url = api_url
        self.data = []
    
    def record_telemetry(self, duration_seconds=60, interval=0.2):
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            try:
                response = requests.get(f'{self.api_url}/telemetry')
                response.raise_for_status()
                
                data = response.json()
                data['timestamp'] = datetime.now().isoformat()
                self.data.append(data)
                
                print(f"[{data['timestamp']}] Depth: {data['depth_cm']:.2f} cm")
                
            except requests.RequestException as e:
                print(f"Error: {e}")
            
            time.sleep(interval)
    
    def export_csv(self, filename='telemetry.csv'):
        import csv
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.data[0].keys())
            writer.writeheader()
            writer.writerows(self.data)
        
        print(f"Exported {len(self.data)} records to {filename}")

# Usage
recorder = TelemetryRecorder()
recorder.record_telemetry(duration_seconds=30, interval=0.2)
recorder.export_csv('rov_telemetry.csv')
```

---

## Changelog

### v1.0.0 (2026-08-19)

- Initial API release
- `GET /api/telemetry` endpoint
- `POST /api/source` endpoint
- CORS support
- JSON request/response format

---

**Last Updated**: 2026-08-19
