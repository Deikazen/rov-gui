"""
QR Proxy — service TERPISAH dari camera_proxy.py, khusus menangani data
QR Code Detector dari unified_rov_server.py (Jetson).

Kenapa dipisah jadi service sendiri (bukan ditambahkan ke camera_proxy.py):
  - Di frontend, panel "Camera 01" dan "QR Code Detector" adalah container
    berbeda -> lebih rapi kalau backend-nya juga independen.
  - Kalau qr_proxy.py crash/restart, video stream Camera 01 di camera_proxy.py
    tidak ikut terganggu, begitu juga sebaliknya.
  - Bisa di-deploy/scale terpisah, port beda, log beda.

Service ini melakukan 2 hal:
  1. Polling ke Jetson (/qr_status) tiap ~150ms di background, simpan state terakhir.
  2. Expose state itu ke frontend lewat:
        - GET  /api/qr/status   -> polling biasa (paling gampang dipakai)
        - WS   /ws/qr/status    -> push real-time (instan begitu QR terdeteksi,
                                    ini yang jadi "indikator" yang kamu maksud)

Install dependency:
    pip install fastapi uvicorn httpx websockets

Jalankan:
    python3 qr_proxy.py
    # atau: uvicorn qr_proxy:app --host 0.0.0.0 --port 8091
"""

import asyncio
import time
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- KONFIGURASI: sesuaikan dengan IP ZeroTier Jetson Anda ---
JETSON_QR_STATUS_URL = "http://10.147.48.168:9010/qr_status"
POLL_INTERVAL_SEC = 0.15  # ~6-7x/detik, cukup responsif tanpa membebani Jetson

app = FastAPI(title="ROV QR Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # produksi: ganti "*" dengan domain website Anda
    allow_methods=["GET"],
    allow_headers=["*"],
)

# State QR terakhir yang berhasil diambil dari Jetson
latest_qr_status = {
    "detected": False,
    "data": None,
    "rect": None,
    "quality": 0,
    "scan_count": 0,
    "last_seen_ms_ago": None,
    "timestamp": 0,
    "jetson_reachable": False,   # <-- indikator koneksi ke Jetson, bukan cuma QR
}

# Daftar client WebSocket yang sedang terhubung (untuk broadcast realtime)
active_websockets: list[WebSocket] = []


async def poll_jetson_qr_status():
    """Background task: polling terus-menerus ke Jetson, broadcast tiap ada perubahan."""
    global latest_qr_status
    prev_detected = None

    async with httpx.AsyncClient(timeout=3.0) as client:
        while True:
            try:
                resp = await client.get(JETSON_QR_STATUS_URL)
                resp.raise_for_status()
                data = resp.json()
                data["jetson_reachable"] = True
                latest_qr_status = data

                # Broadcast hanya kalau status berubah (QR baru kedetect / hilang)
                # -> ini yang bikin indikator di frontend terasa "instan"
                if data["detected"] != prev_detected:
                    prev_detected = data["detected"]
                    await broadcast(data)

            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
                latest_qr_status = {
                    "detected": False,
                    "data": None,
                    "rect": None,
                    "quality": 0,
                    "scan_count": latest_qr_status.get("scan_count", 0),
                    "last_seen_ms_ago": None,
                    "timestamp": time.time(),
                    "jetson_reachable": False,
                }
                if prev_detected is not False:
                    prev_detected = False
                    await broadcast(latest_qr_status)

            await asyncio.sleep(POLL_INTERVAL_SEC)


async def broadcast(payload: dict):
    """Kirim update ke semua client WebSocket yang sedang terhubung."""
    dead = []
    for ws in active_websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_websockets.remove(ws)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poll_jetson_qr_status())


@app.get("/api/qr/status")
async def qr_status():
    """Polling biasa — dipanggil frontend tiap beberapa ratus ms kalau tidak pakai WebSocket."""
    return latest_qr_status


@app.websocket("/ws/qr/status")
async def qr_status_ws(websocket: WebSocket):
    """Push real-time — frontend connect sekali, lalu terima update otomatis
    setiap kali QR terdeteksi/hilang, tanpa perlu polling manual."""
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Kirim state terakhir begitu client connect
        await websocket.send_json(latest_qr_status)
        while True:
            # Jaga koneksi tetap hidup; kita tidak butuh pesan dari client
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "qr_proxy", "jetson_reachable": latest_qr_status["jetson_reachable"]}


if __name__ == "__main__":
    import uvicorn

    print("[QR PROXY] Aktif di http://0.0.0.0:8091")
    print(f"[QR PROXY] Polling dari: {JETSON_QR_STATUS_URL}")
    print("[QR PROXY] Endpoints: GET /api/qr/status  |  WS /ws/qr/status")
    uvicorn.run(app, host="0.0.0.0", port=8091)