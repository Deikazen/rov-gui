"""
Camera Proxy — meneruskan MJPEG stream dari unified_rov_server.py (Jetson)
ke frontend, tanpa frontend perlu tahu IP Jetson secara langsung.

REVISI ANTI-LAG:
  - read timeout eksplisit (dulu None -> bisa nge-hang selamanya kalau upstream diam)
  - tangkap ReadTimeout supaya browser bisa reconnect otomatis lewat <img> onerror,
    bukan koneksi menggantung tanpa akhir

TIPS PENTING SOAL IP:
  Kalau komputer yang menjalankan file ini SATU JARINGAN LOKAL (WiFi/LAN yang sama)
  dengan Jetson, GANTI JETSON_CAM1_URL di bawah dengan IP LOKAL Jetson
  (contoh: 192.168.1.xx), BUKAN IP ZeroTier. Ini mengurangi lag karena:
    1. Tidak ada overhead enkripsi/tunneling ZeroTier.
    2. ZeroTier kadang RELAY lewat server publik kalau P2P gagal terbentuk
       (cek dengan `sudo zerotier-cli listpeers` di Jetson - kalau ada baris
       RELAY bukan DIRECT, itu penyebab lag).
  ZeroTier tetap perlu dipakai kalau proxy ini dijalankan di luar jaringan
  lokal Jetson (misal proxy di cloud atau laptop yang beda jaringan).
"""

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# --- KONFIGURASI ---
# Kalau proxy ini satu jaringan lokal dengan Jetson, pakai IP LOKAL Jetson,
# misal: "http://192.168.1.50:9010/video_feed"
# Kalau beda jaringan (remote), baru pakai IP ZeroTier seperti sebelumnya.
JETSON_CAM1_URL = "http://10.147.48.168:9010/video_feed"
# JETSON_CAM2_URL = "http://<ip-jetson-kedua-jika-ada>:9010/video_feed"

# Timeout baca per-chunk. Kalau upstream diam lebih lama dari ini, dianggap
# stuck dan koneksi ditutup (browser akan reconnect otomatis).
READ_TIMEOUT_SEC = 15.0

app = FastAPI(title="ROV Camera Proxy")

# Izinkan frontend (domain/port berbeda) fetch endpoint ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # produksi: ganti "*" dengan domain website Anda
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/camera1/stream")
async def camera1_stream():
    timeout = httpx.Timeout(10.0, connect=5.0, read=READ_TIMEOUT_SEC)
    client = httpx.AsyncClient(timeout=timeout)
    try:
        upstream = await client.send(
            client.build_request("GET", JETSON_CAM1_URL), stream=True
        )
    except httpx.ConnectError as e:
        await client.aclose()
        raise HTTPException(
            status_code=502, detail=f"Tidak bisa konek ke Jetson di {JETSON_CAM1_URL}: {e}"
        )
    except httpx.TimeoutException as e:
        await client.aclose()
        raise HTTPException(
            status_code=504, detail=f"Timeout konek ke Jetson: {e}"
        )

    if upstream.status_code != 200:
        await upstream.aclose()
        await client.aclose()
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
        except httpx.ReadTimeout:
            # Upstream (Jetson) berhenti mengirim frame lebih lama dari
            # READ_TIMEOUT_SEC -> stream dianggap macet, tutup dengan tenang
            # supaya frontend reconnect, alih-alih koneksi menggantung selamanya.
            print(
                "[CAMERA PROXY] Upstream diam terlalu lama (read timeout), "
                "menutup stream supaya client reconnect."
            )
        except (httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError):
            # Koneksi ke Jetson putus di tengah stream (browser reload,
            # tab ditutup, ZeroTier sempat drop, dsb). Ini NORMAL untuk
            # proxy MJPEG — cukup hentikan generator dengan tenang,
            # tanpa melempar traceback yang bikin panik di console.
            print(
                "[CAMERA PROXY] Stream terputus (client/upstream disconnect), "
                "reconnect akan terjadi otomatis dari sisi <img>."
            )
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
    return {"status": "ok", "service": "camera1_proxy", "jetson_cam1_url": JETSON_CAM1_URL}


if __name__ == "__main__":
    import uvicorn

    print("[CAMERA PROXY] Aktif di http://0.0.0.0:8090")
    print(f"[CAMERA PROXY] Meneruskan dari: {JETSON_CAM1_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8090)