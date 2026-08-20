"""
Camera Proxy — meneruskan MJPEG stream dari unified_rov_server.py (Jetson)
ke frontend, tanpa frontend perlu tahu IP Jetson secara langsung.

Kenapa perlu ini (bukan langsung <img src="http://jetson-ip:9010/video_feed">):
  - Frontend / user lain yang buka website TIDAK perlu join ZeroTier network Anda.
    Cukup backend ini yang punya akses ZeroTier ke Jetson.
  - Satu titik kontrol: kalau nanti ada 2+ kamera, tinggal tambah endpoint di sini.
  - Bisa ditambah auth/rate-limit di depan tanpa sentuh kode Jetson.

Jalankan di komputer yang PUNYA akses ZeroTier ke Jetson (laptop Anda / server GCS,
sama seperti tempat model_3d.py biasanya dijalankan) — BUKAN di Jetson itu sendiri.

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
JETSON_CAM1_URL = "http://10.37.36.168:9010/video_feed"
# JETSON_CAM2_URL = "http://<ip-jetson-kedua-jika-ada>:9010/video_feed"

app = FastAPI(title="ROV Camera Proxy")

# Izinkan frontend (domain/port berbeda) fetch endpoint ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # produksi: ganti "*" dengan domain website Anda
    allow_methods=["GET"],
    allow_headers=["*"],
)


async def relay_mjpeg(source_url: str):
    """Generator yang streaming byte demi byte dari Jetson ke client, tanpa buffering penuh di memori."""
    timeout = httpx.Timeout(
        10.0, read=None)  # read=None -> stream tanpa batas waktu
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("GET", source_url) as upstream:
                if upstream.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Jetson merespons status {upstream.status_code}",
                    )
                content_type = upstream.headers.get(
                    "content-type", "multipart/x-mixed-replace"
                )
                async for chunk in upstream.aiter_bytes():
                    yield chunk
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Tidak bisa konek ke Jetson di {source_url}: {e}",
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
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    print("[CAMERA PROXY] Aktif di http://0.0.0.0:8090")
    print(f"[CAMERA PROXY] Meneruskan dari: {JETSON_CAM1_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8090)
