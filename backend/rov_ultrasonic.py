#!/usr/bin/env python3
"""
================================================================================
ROV ULTRASONIC TRAJECTORY RECEIVER & MAPPING SERVER (5 x 5 METER)
================================================================================
Deskripsi:
Menerima streaming data sensor ultrasonic dari Jetson Nano melalui WebSocket (port 8765),
menghitung koordinat posisi wahana (X, Y) trajectory secara real-time berdasarkan logika
mapping kolam 5 x 5 meter sesuai diagram catatan tangan (20260902_143750.jpg),
dan menyediakan REST API endpoint untuk dikonsumsi oleh Frontend GCS (TrajectoryPanel.tsx).

LOGIKA MAPPING KOORDINAT DARI SENSOR ULTRASONIC:
1. Kolam berukuran 5 x 5 meter:
   - Sumbu horizontal: X (0.0 m s/d 5.0 m, dari kiri ke kanan)
   - Sumbu vertikal  : Y (0.0 m s/d 5.0 m, dari bawah ke atas)
   - Titik acuan (0, 0) berada di sudut kiri bawah kolam.

2. Posisi dan Arah Sensor pada Wahana (ROV):
   - Sensor 1 (S1) : Terpasang di sisi depan/atas ROV, mengarah ke DINDING ATAS (sumbu +Y).
   - Sensor 2 (S2) : Terpasang di sisi kanan ROV, mengarah ke DINDING KANAN (sumbu +X).

3. Aturan Mapping Berdasarkan Catatan Gambar:
   - Sensor 1 (S1) -> Koordinat Y:
       * if S1 == 500 cm (5.0 m) : Y = 1.0 m
       * elif S1 == 400 cm (4.0 m) : Y = 2.0 m
       * elif S1 == 300 cm (3.0 m) : Y = 3.0 m
       * elif S1 == 200 cm (2.0 m) : Y = 4.0 m
       * elif S1 == 100 cm (1.0 m) : Y = 5.0 m

   - Sensor 2 (S2) -> Koordinat X:
       * if S2 == 500 cm (5.0 m) : X = 1.0 m
       * elif S2 == 400 cm (4.0 m) : X = 2.0 m
       * elif S2 == 300 cm (3.0 m) : X = 3.0 m
       * elif S2 == 200 cm (2.0 m) : X = 4.0 m
       * elif S2 == 100 cm (1.0 m) : X = 5.0 m

4. REST API Endpoints untuk Frontend UI (Port 8007 / 8008):
   - GET  /api/trajectory          -> Data koordinat live untuk TrajectoryPanel.tsx
   - GET  /api/trajectory/history  -> Riwayat titik lintasan breadcrumbs
   - POST /api/origin/calibrate    -> Kalibrasi titik (0, 0)
   - POST /api/origin/reset        -> Reset origin
   - POST /api/mode                -> Ubah mode 'continuous' / 'discrete'
================================================================================
"""

import asyncio
import json
import logging
import math
import os
import socket
import sys
import threading
import time
from collections import deque
import psutil
import websockets
from flask import Flask, jsonify, request
from flask_cors import CORS

# Pastikan encoding UTF-8 aman di terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Redam log akses HTTP Werkzeug yang berlebihan
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Konfigurasi Server & Kolam
# ---------------------------------------------------------------------------
HOST = "0.0.0.0"
WS_PORT = 8765          # Port WebSocket Jetson Nano
DEFAULT_HTTP_PORT = 8007  # Port default REST API untuk Frontend GUI
FALLBACK_HTTP_PORT = 8008

POOL_WIDTH = 5.0        # Dimensi kolam sumbu X (meter)
POOL_HEIGHT = 5.0       # Dimensi kolam sumbu Y (meter)

# Mode mapping:
# - 'continuous' : Interpolasi linier halus (sangat cocok untuk trajectory GUI)
# - 'discrete'   : Nilai diskrit 1, 2, 3, 4, 5 (persis if-elif di kertas)
DEFAULT_MAPPING_MODE = "continuous"
DEFAULT_FORMULA = "diagram"  # Pos = 6.0 - (dist_cm / 100)


def kill_process_on_port(port: int):
    """Mencari dan mematikan proses lain yang sedang menduduki port target."""
    current_pid = os.getpid()
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == port and conn.pid:
            if conn.pid != current_pid:
                try:
                    proc = psutil.Process(conn.pid)
                    proc_name = proc.name()
                    print(
                        f"[*] Port {port} sedang dipakai oleh PID {conn.pid} ({proc_name}). Mematikan proses...")
                    proc.kill()
                    proc.wait(timeout=3)
                    time.sleep(0.5)
                except (psutil.NoSuchProcess, psutil.AccessDenied) as err:
                    print(f"[!] Gagal mematikan proses PID {conn.pid}: {err}")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Cek apakah suatu port sedang digunakan."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


# ---------------------------------------------------------------------------
# Shared State & Trajectory Buffer
# ---------------------------------------------------------------------------
state_lock = threading.Lock()

current_state = {
    "source": "ultrasonic",
    "mapping_mode": DEFAULT_MAPPING_MODE,
    "formula": DEFAULT_FORMULA,
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "raw_x": 0.0,
    "raw_y": 0.0,
    "raw_z": 0.0,
    "origin_x": 0.0,
    "origin_y": 0.0,
    "origin_z": 0.0,
    "yaw": 0.0,
    "mavlink_connected": True,
    "ultrasonic_connected": False,
    # Sensor 1 (S1 -> Sumbu Y)
    "s1_mm": None,
    "s1_cm": None,
    "s1_status": "N/A",
    # Sensor 2 (S2 -> Sumbu X)
    "s2_mm": None,
    "s2_cm": None,
    "s2_status": "N/A",
    # Metadata
    "last_update": 0.0,
    "in_bounds": True,
    "connected_client": None,
    "active_http_port": DEFAULT_HTTP_PORT,
}

# Buffer riwayat lintasan (breadcrumbs)
trajectory_history = deque(maxlen=2000)


# ---------------------------------------------------------------------------
# Logika Konversi Sensor Ultrasonic ke Koordinat X & Y
# ---------------------------------------------------------------------------
def parse_sensor_reading(sensor_data):
    """
    Ekstraksi data sensor ultrasonic dengan penanganan tipe data yang fleksibel
    (mendukung int, float, str, mm, atau cm), dan memfilter pembacaan tidak valid.
    """
    if not isinstance(sensor_data, dict):
        return None, None, "NO_DATA"

    status = str(sensor_data.get("status", "N/A"))

    raw_dist = sensor_data.get("distance_mm")
    is_cm = False
    if raw_dist is None:
        raw_dist = sensor_data.get("distance_cm")
        is_cm = True
    if raw_dist is None:
        raw_dist = sensor_data.get("distance")

    if raw_dist is None:
        return None, None, status

    try:
        dist_val = float(raw_dist)
    except (ValueError, TypeError):
        return None, None, status

    # Abaikan pembacaan error, 0, negatif, atau Out of range
    if dist_val <= 0 or "out of range" in status.lower() or "error" in status.lower():
        return None, None, status

    if is_cm:
        dist_cm = round(dist_val, 2)
        dist_mm = round(dist_val * 10.0, 1)
    else:
        dist_mm = round(dist_val, 1)
        dist_cm = round(dist_val / 10.0, 2)

    return dist_mm, dist_cm, status


def map_sensor_discrete(dist_cm):
    """
    Logika if-elif diskrit persis sesuai catatan tangan di gambar:
        if S == 500 cm : Pos = 1.0 m
        elif S == 400 cm : Pos = 2.0 m
        elif S == 300 cm : Pos = 3.0 m
        elif S == 200 cm : Pos = 4.0 m
        elif S == 100 cm : Pos = 5.0 m
    """
    if dist_cm is None or dist_cm <= 0:
        return None

    if dist_cm >= 450.0:         # Sekitar 500 cm
        return 1.0
    elif dist_cm >= 350.0:       # Sekitar 400 cm
        return 2.0
    elif dist_cm >= 250.0:       # Sekitar 300 cm
        return 3.0
    elif dist_cm >= 150.0:       # Sekitar 200 cm
        return 4.0
    elif dist_cm >= 10.0:        # Sekitar 100 cm (min sensor 10cm s/d <150cm)
        return 5.0
    else:
        return None


def map_sensor_continuous(dist_cm, formula="diagram"):
    """
    Logika continuous linear interpolation tanpa batas kaku 5 meter:
    - Rumus diagram: Pos = 6.0 - (dist_cm / 100.0)
    - Tidak ada pembatasan/clamping ke 5 meter, jarak bebas.
    """
    if dist_cm is None or dist_cm <= 0:
        return None

    dist_m = dist_cm / 100.0
    pos = 6.0 - dist_m
    return round(pos, 3)


def calculate_trajectory(s1_dict, s2_dict, mode=DEFAULT_MAPPING_MODE, formula=DEFAULT_FORMULA):
    """
    Menghitung posisi wahana (X, Y) dari pembacaan sensor S1 dan S2:
    - Sensor 1 (S1) -> Mengendalikan Sumbu Y (depan/atas kolam)
    - Sensor 2 (S2) -> Mengendalikan Sumbu X (kanan kolam)
    - Jarak maksimum tidak dibatasi 5 meter (bebas)
    """
    s1_mm, s1_cm, s1_status = parse_sensor_reading(s1_dict)
    s2_mm, s2_cm, s2_status = parse_sensor_reading(s2_dict)

    if mode == "discrete":
        calc_y = map_sensor_discrete(s1_cm)
        calc_x = map_sensor_discrete(s2_cm)
    else:
        calc_y = map_sensor_continuous(s1_cm, formula=formula)
        calc_x = map_sensor_continuous(s2_cm, formula=formula)

    return {
        "x": calc_x,
        "y": calc_y,
        "s1_mm": s1_mm,
        "s1_cm": s1_cm,
        "s1_status": s1_status,
        "s2_mm": s2_mm,
        "s2_cm": s2_cm,
        "s2_status": s2_status,
        "in_bounds": True,
    }


def format_sensor(dist_mm, dist_cm, status):
    if dist_mm is None or dist_cm is None:
        return f"--- [{status}]"
    return f"{dist_cm:5.1f}cm ({dist_mm:4.0f}mm) [{status}]"


# ---------------------------------------------------------------------------
# WebSocket Server Handler (Menerima Data Streaming dari Jetson Nano)
# ---------------------------------------------------------------------------
async def ws_handler(websocket):
    client_ip = websocket.remote_address[0]
    print(f"\n[+] Jetson Nano terhubung dari: {client_ip}")
    print(
        f"[*] Mode Mapping: {current_state['mapping_mode'].upper()} | Ukuran Kolam: {POOL_WIDTH:.0f}x{POOL_HEIGHT:.0f}m")
    print(f"{'Timestamp':<10} | {'Sensor 1 (-> Y)':<26} | {'Sensor 2 (-> X)':<26} | {'Posisi (X, Y)':<18} | {'Status'}")
    print("-" * 92)

    with state_lock:
        current_state["connected_client"] = client_ip
        current_state["ultrasonic_connected"] = True

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if not isinstance(data, dict):
                    continue

                ts = data.get("timestamp", time.time())
                sensors = data.get("sensors")
                if not isinstance(sensors, dict):
                    sensors = {}

                s1_dict = sensors.get("sensor_1")
                if not isinstance(s1_dict, dict):
                    s1_dict = {}
                s2_dict = sensors.get("sensor_2")
                if not isinstance(s2_dict, dict):
                    s2_dict = {}

                with state_lock:
                    mode = current_state["mapping_mode"]
                    formula = current_state["formula"]

                res = calculate_trajectory(
                    s1_dict, s2_dict, mode=mode, formula=formula)

                with state_lock:
                    current_state["last_update"] = ts
                    current_state["ultrasonic_connected"] = True
                    current_state["s1_mm"] = res["s1_mm"]
                    current_state["s1_cm"] = res["s1_cm"]
                    current_state["s1_status"] = res["s1_status"]
                    current_state["s2_mm"] = res["s2_mm"]
                    current_state["s2_cm"] = res["s2_cm"]
                    current_state["s2_status"] = res["s2_status"]
                    current_state["in_bounds"] = res["in_bounds"]

                    # UPDATE SUMBU X DAN Y SECARA INDEPENDEN DAN INSTAN!
                    if res["x"] is not None:
                        current_state["raw_x"] = res["x"]
                        current_state["x"] = round(
                            res["x"] - current_state["origin_x"], 3)
                    if res["y"] is not None:
                        current_state["raw_y"] = res["y"]
                        current_state["y"] = round(
                            res["y"] - current_state["origin_y"], 3)

                    cur_x = current_state["x"]
                    cur_y = current_state["y"]

                    # Catat riwayat titik trajectory instan jika koordinat bergeser
                    last_pt = trajectory_history[-1] if trajectory_history else None
                    if not last_pt or math.hypot(cur_x - last_pt["x"], cur_y - last_pt["y"]) >= 0.01:
                        trajectory_history.append({
                            "x": cur_x,
                            "y": cur_y,
                            "raw_x": current_state["raw_x"],
                            "raw_y": current_state["raw_y"],
                            "timestamp": ts,
                        })

                s1_str = format_sensor(
                    res["s1_mm"], res["s1_cm"], res["s1_status"])
                s2_str = format_sensor(
                    res["s2_mm"], res["s2_cm"], res["s2_status"])
                pos_str = f"X:{cur_x:4.2f}m, Y:{cur_y:4.2f}m"
                bound_status = "OK" if res["in_bounds"] else "OUT_OF_BOUNDS"

                # Format timestamp aman
                try:
                    ts_float = float(ts)
                    ts_str = f"{ts_float:<10.2f}"
                except Exception:
                    ts_str = f"{str(ts)[:10]:<10}"

                print(
                    f"\r{ts_str} | {s1_str:<26} | {s2_str:<26} | {pos_str:<18} | {bound_status:<10}",
                    end="",
                    flush=True,
                )
            except Exception:
                # Cegah 1 paket rusak menghentikan seluruh koneksi
                continue

    except websockets.exceptions.ConnectionClosed as err:
        print(f"\n[-] Koneksi dari {client_ip} terputus (Code: {err.code}, Reason: '{err.reason}').")
        with state_lock:
            current_state["connected_client"] = None
            current_state["ultrasonic_connected"] = False
    except Exception as e:
        print(f"\n[!] Error tak terduga pada ws_handler: {type(e).__name__}: {e}")
        with state_lock:
            current_state["connected_client"] = None
            current_state["ultrasonic_connected"] = False


# ---------------------------------------------------------------------------
# Flask REST API Server (Endpoint untuk Frontend TrajectoryPanel.tsx)
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)


@app.route("/api/trajectory", methods=["GET"])
def get_trajectory():
    """Mengembalikan data posisi trajectory yang langsung kompatibel dengan TrajectoryPanel.tsx."""
    with state_lock:
        return jsonify({
            "source": current_state["source"],
            "x": current_state["x"],
            "y": current_state["y"],
            "z": current_state["z"],
            "raw_x": current_state["raw_x"],
            "raw_y": current_state["raw_y"],
            "raw_z": current_state["raw_z"],
            "origin_x": current_state["origin_x"],
            "origin_y": current_state["origin_y"],
            "origin_z": current_state["origin_z"],
            "yaw": current_state["yaw"],
            "mavlink_connected": current_state["mavlink_connected"],
            "ultrasonic_connected": current_state["ultrasonic_connected"],
            "mapping_mode": current_state["mapping_mode"],
            "sensor_1": {
                "distance_cm": current_state["s1_cm"],
                "distance_mm": current_state["s1_mm"],
                "status": current_state["s1_status"],
                "target_axis": "Y",
            },
            "sensor_2": {
                "distance_cm": current_state["s2_cm"],
                "distance_mm": current_state["s2_mm"],
                "status": current_state["s2_status"],
                "target_axis": "X",
            },
            "pool_size": {"width": POOL_WIDTH, "height": POOL_HEIGHT},
            "history_points": len(trajectory_history),
        })


@app.route("/api/trajectory/history", methods=["GET"])
def get_trajectory_history():
    """Mengembalikan seluruh titik riwayat lintasan."""
    with state_lock:
        points = list(trajectory_history)
    return jsonify({
        "status": "ok",
        "count": len(points),
        "trajectory": points,
    })


@app.route("/api/origin/calibrate", methods=["POST"])
@app.route("/api/calibrate", methods=["POST"])
def calibrate_origin():
    """Set posisi wahana saat ini sebagai origin (0, 0)."""
    with state_lock:
        current_state["origin_x"] = current_state["raw_x"]
        current_state["origin_y"] = current_state["raw_y"]
        current_state["x"] = 0.0
        current_state["y"] = 0.0
        return jsonify({
            "status": "ok",
            "message": "Origin berhasil diset ke posisi saat ini",
            "origin": {
                "x": current_state["origin_x"],
                "y": current_state["origin_y"],
            },
        })


@app.route("/api/origin/reset", methods=["POST"])
def reset_origin():
    """Reset titik origin ke default (0, 0)."""
    with state_lock:
        current_state["origin_x"] = 0.0
        current_state["origin_y"] = 0.0
        current_state["x"] = current_state["raw_x"]
        current_state["y"] = current_state["raw_y"]
        return jsonify({
            "status": "ok",
            "message": "Origin direset ke default (0, 0)",
            "origin": {"x": 0.0, "y": 0.0},
        })


@app.route("/api/mode", methods=["POST"])
def set_mapping_mode():
    """Ubah mode antara 'continuous' atau 'discrete'."""
    payload = request.get_json(silent=True) or {}
    new_mode = payload.get("mode")
    if new_mode not in ("continuous", "discrete"):
        return jsonify({"error": "mode harus 'continuous' atau 'discrete'"}), 400

    with state_lock:
        current_state["mapping_mode"] = new_mode

    return jsonify({"status": "ok", "mode": new_mode})


def run_http_server():
    """Menjalankan HTTP REST server Flask di background thread dengan penentuan port cerdas."""
    target_port = DEFAULT_HTTP_PORT
    if is_port_in_use(DEFAULT_HTTP_PORT):
        print(
            f"[*] Port {DEFAULT_HTTP_PORT} sedang digunakan (misal oleh rov-trajectory2.py).")
        print(
            f"[*] Menjalankan REST API Ultrasonic di port cadangan {FALLBACK_HTTP_PORT}...")
        target_port = FALLBACK_HTTP_PORT
    else:
        print(
            f"[*] REST API Trajectory aktif di http://localhost:{DEFAULT_HTTP_PORT}/api/trajectory")

    with state_lock:
        current_state["active_http_port"] = target_port

    try:
        app.run(host=HOST, port=target_port, debug=False,
                threaded=True, use_reloader=False)
    except Exception as err:
        print(f"[!] Gagal menjalankan REST API pada port {target_port}: {err}")


# ---------------------------------------------------------------------------
# Main Asyncio Loop (WebSocket Server)
# ---------------------------------------------------------------------------
async def main():
    # 1. Bersihkan port WebSocket jika ada proses zombie
    kill_process_on_port(WS_PORT)

    # 2. Jalankan REST API di background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    print(
        f"[*] WebSocket Server aktif di port {WS_PORT}. Menunggu data dari Jetson Nano...")
    print(f"[*] Dimensi Kolam: {POOL_WIDTH} x {POOL_HEIGHT} Meter")
    print(f"[*] Mapping Mode : {DEFAULT_MAPPING_MODE} | S1 -> Y, S2 -> X")

    async with websockets.serve(
        ws_handler,
        HOST,
        WS_PORT,
        ping_interval=None,   # Matikan ping_interval bawaan agar tidak terputus timeout saat Jetson sibuk
        ping_timeout=None,    # Matikan timeout ping agresif
        close_timeout=15,     # Waktu toleransi penutupan koneksi
        max_size=2**20,       # Kapasitas payload 1MB
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Server dihentikan oleh pengguna.")
