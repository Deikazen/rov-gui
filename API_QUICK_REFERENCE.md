# ROV-GUI API Quick Reference

Referensi cepat untuk ROV-GUI REST API endpoints.

## Base URL

```
http://localhost:5001/api
```

---

## Endpoints Overview

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/telemetry` | Get current depth & status |
| POST | `/source` | Switch data source |

---

## 1. GET /api/telemetry

**Get telemetry data.**

### Quick Example

```bash
curl http://localhost:5001/api/telemetry
```

### Response

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

### Fields

| Field | Type | Meaning |
|-------|------|---------|
| `source` | string | `"dummy"` or `"real"` |
| `depth` | float | Depth in meters |
| `depth_cm` | float | Depth in centimeters |
| `rate` | float | Vertical speed (m/s) |
| `mavlink_connected` | bool | MAVLink connection status |
| `max_depth_m` | float | Max depth limit |
| `max_depth_cm` | float | Max depth limit (cm) |

### Code Examples

**JavaScript:**
```javascript
const data = await fetch('http://localhost:5001/api/telemetry')
  .then(r => r.json());
console.log(`Depth: ${data.depth_cm} cm`);
```

**Python:**
```python
import requests
data = requests.get('http://localhost:5001/api/telemetry').json()
print(f"Depth: {data['depth_cm']} cm")
```

**cURL:**
```bash
curl -s http://localhost:5001/api/telemetry | jq .
```

---

## 2. POST /api/source

**Switch data source.**

### Quick Example

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

### Request Body

```json
{
  "source": "real"
}
```

| Field | Type | Values |
|-------|------|--------|
| `source` | string | `"real"` or `"dummy"` |

### Response

```json
{
  "status": "ok",
  "source": "real"
}
```

### Error Response

```json
{
  "error": "source must be \"real\" or \"dummy\""
}
```

### Code Examples

**JavaScript:**
```javascript
const response = await fetch('http://localhost:5001/api/source', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ source: 'real' })
});
const result = await response.json();
console.log('Source:', result.source);
```

**Python:**
```python
import requests
response = requests.post('http://localhost:5001/api/source',
  json={'source': 'real'})
print(response.json()['source'])
```

---

## Common Use Cases

### Real-time Monitoring

```javascript
// Poll every 200ms
setInterval(async () => {
  const data = await fetch('http://localhost:5001/api/telemetry')
    .then(r => r.json());
  console.log(`Depth: ${data.depth_cm} cm, Rate: ${data.rate} m/s`);
}, 200);
```

### Switch Data Source

```javascript
// Toggle between real and dummy
async function toggleSource() {
  const current = await fetch('http://localhost:5001/api/telemetry')
    .then(r => r.json());
  
  const newSource = current.source === 'real' ? 'dummy' : 'real';
  
  const response = await fetch('http://localhost:5001/api/source', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: newSource })
  });
  
  console.log('Switched to:', (await response.json()).source);
}
```

### Monitor Connectivity

```javascript
async function checkConnectivity() {
  const data = await fetch('http://localhost:5001/api/telemetry')
    .then(r => r.json());
  
  if (data.mavlink_connected) {
    console.log('✓ Connected to Pixhawk');
  } else {
    console.log('✗ Disconnected from Pixhawk');
  }
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid data) |
| 500 | Server error |

---

## Testing

**Test if backend is running:**
```bash
curl -s http://localhost:5001/api/telemetry | jq .
```

**Expected output:**
```json
{
  "source": "dummy",
  "depth": 0.5234,
  ...
}
```

---

## Troubleshooting

**CORS Error?**
- Backend must be running
- Frontend must request from correct URL

**Connection Refused?**
- Backend not running: `python rov-depth.py`
- Wrong port: Check backend runs on 5001

**Invalid Source?**
- Only values are `"real"` and `"dummy"`
- Check JSON syntax

---

## Data Source Modes

### Real Mode (`"real"`)
- Connects to Pixhawk via MAVLink
- Reads actual sensor data
- Requires hardware + BlueOS configuration
- Returns `false` for `mavlink_connected` if no Pixhawk detected

### Dummy Mode (`"dummy"`)
- Generates simulated depth data
- Uses sine wave oscillation
- No hardware required
- Good for testing without ROV

---

**For full documentation, see:**
- [README.md](README.md) - Complete guide
- [API_DOCUMENTATION.md](API_DOCUMENTATION.md) - Detailed API reference
- [SETUP_GUIDE.md](SETUP_GUIDE.md) - Setup and deployment
