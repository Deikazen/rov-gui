"""
Camera Proxy — meneruskan MJPEG stream dari webcam.service (Camera 02,
/dev/video1 di Jetson Nano, lihat "webcam.service loaded active running")
ke frontend, tanpa frontend perlu tahu IP Jetson secara langsung.

Service ini KHUSUS untuk video Camera 02 (bottom/side view, USB webcam
monitoring-only). Camera 01 punya proxy sendiri: camera_jetson1.py
(port 8090) — sengaja dipisah supaya salah satu down/restart tidak
mematikan yang lain.

Jalankan di komputer yang PUNYA akses jaringan ke Jetson (laptop Anda /
server GCS) — BUKAN di Jetson itu sendiri (di Jetson yang jalan adalah
webcam.service, yaitu script capture asli /dev/video1 di port 9011).

Install dependency:
    pip install fastapi uvicorn httpx

Jalankan:
    python3 webcam.py
    # atau: uvicorn webcam:app --host 0.0.0.0 --port 8092

Di frontend (.env), arahkan VITE_CAM2_URL ke:
    http://<ip-komputer-backend-ini>:8092/api/camera2/stream
"""

import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# --- KONFIGURASI ---
# Bisa di-override lewat environment variable tanpa ubah kode, contoh:
#   JETSON_CAM2_URL="http://192.168.99.244:9011/video_feed" python3 webcam.py
JETSON_CAM2_URL = os.environ.get(
    "JETSON_CAM2_URL", "http://192.168.99.244:9011/video_feed"
)

# Origin frontend yang boleh akses proxy ini. "*" gampang untuk development,
# tapi untuk produksi sebaiknya isi domain website Anda, contoh:
#   ALLOWED_ORIGINS="https://rov.situs-anda.com,http://localhost:5173"
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")
allow_origins = (
    ["*"] if ALLOWED_ORIGINS == "*" else [o.strip() for o in ALLOWED_ORIGINS.split(",")]
)

# Timeout: connect dibatasi, tapi baca stream dibiarkan tanpa batas waktu
# karena MJPEG memang stream yang terus mengalir.
HTTPX_TIMEOUT = httpx.Timeout(10.0, connect=5.0, read=None)

app = FastAPI(title="ROV Camera 02 Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/camera2/stream")
async def camera2_stream():
    """Proxy MJPEG stream dari webcam.service (Jetson) ke frontend, byte demi byte (tanpa buffer penuh)."""
    client = httpx.AsyncClient(timeout=HTTPX_TIMEOUT)
    try:
        req = client.build_request("GET", JETSON_CAM2_URL)
        upstream = await client.send(req, stream=True)
    except httpx.ConnectError as e:
        await client.aclose()
        raise HTTPException(
            status_code=502, detail=f"Tidak bisa konek ke Jetson (Camera 02) di {JETSON_CAM2_URL}: {e}"
        )
    except httpx.TimeoutException as e:
        await client.aclose()
        raise HTTPException(
            status_code=504, detail=f"Timeout konek ke Jetson (Camera 02): {e}"
        )

    if upstream.status_code != 200:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=502, detail=f"webcam.service merespons status {upstream.status_code}"
        )

    content_type = upstream.headers.get(
        "content-type", "multipart/x-mixed-replace; boundary=frame"
    )

    async def stream_and_close():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            # Tutup upstream response + client HANYA setelah frontend
            # berhenti nonton (browser close / error), supaya tidak
            # membiarkan koneksi ke Jetson menggantung.
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_and_close(),
        media_type=content_type,
        headers={
            # Cegah browser/proxy di tengah jalan nge-cache atau nge-buffer
            # frame MJPEG, supaya stream tetap terasa real-time.
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "camera2_proxy", "jetson_cam2_url": JETSON_CAM2_URL}


if __name__ == "__main__":
    import uvicorn

    print("[CAMERA 02 PROXY] Aktif di http://0.0.0.0:8092")
    print(f"[CAMERA 02 PROXY] Meneruskan dari: {JETSON_CAM2_URL}")
    print(f"[CAMERA 02 PROXY] Allowed origins: {allow_origins}")
    uvicorn.run(app, host="0.0.0.0", port=8092)