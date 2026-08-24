"""
Camera Proxy — meneruskan MJPEG stream dari unified_rov_server.py (Jetson)
ke frontend, tanpa frontend perlu tahu IP Jetson secara langsung.

Service ini KHUSUS untuk video Camera 01. Data QR ditangani oleh
service terpisah: qr_proxy.py (port berbeda), supaya panel Camera 01
dan panel QR Code Detector di frontend punya backend independen —
salah satu down/restart tidak mematikan yang lain.

Jalankan di komputer yang PUNYA akses ZeroTier ke Jetson (laptop Anda / server GCS)
— BUKAN di Jetson itu sendiri.

Install dependency:
    pip install fastapi uvicorn httpx

Jalankan:
    python3 camera_proxy.py
    # atau: uvicorn camera_proxy:app --host 0.0.0.0 --port 8090
"""

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# --- KONFIGURASI: sesuaikan dengan IP ZeroTier Jetson Anda ---
JETSON_CAM1_URL = "http://10.147.48.168:9010/video_feed"
# JETSON_CAM2_URL = "http://<ip-jetson-kedua-jika-ada>:9010/video_feed"

app = FastAPI(title="ROV Camera Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # produksi: ganti "*" dengan domain website Anda
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/camera1/stream")
async def camera1_stream():
    timeout = httpx.Timeout(10.0, read=None)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            upstream = await client.send(
                client.build_request("GET", JETSON_CAM1_URL), stream=True
            )
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=502, detail=f"Tidak bisa konek ke Jetson: {e}"
            )

    if upstream.status_code != 200:
        raise HTTPException(
            status_code=502, detail=f"Jetson merespons status {upstream.status_code}"
        )

    content_type = upstream.headers.get(
        "content-type", "multipart/x-mixed-replace; boundary=frame"
    )

    async def stream_and_close():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(stream_and_close(), media_type=content_type)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "camera_proxy"}


if __name__ == "__main__":
    import uvicorn

    print("[CAMERA PROXY] Aktif di http://0.0.0.0:8090")
    print(f"[CAMERA PROXY] Meneruskan dari: {JETSON_CAM1_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8090)