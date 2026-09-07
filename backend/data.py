"""
================================================================================
DATA.PY - SERVER DATA PUSAT (CENTRAL DATA HUB)
================================================================================
Deskripsi:
Mengumpulkan SELURUH data sensor ROV dari berbagai backend:
  1. DEPTH       <- WebSocket client ke rov-depth.py (ws://127.0.0.1:5002)
  2. TRAJECTORY  <- HTTP polling ke rov-trajectory2.py (http://127.0.0.1:8007/api/trajectory)
  3. ULTRASONIC  <- HTTP polling ke rov_ultrasonic.py (http://127.0.0.1:8007/api/trajectory
                    atau http://127.0.0.1:8008/api/trajectory jika port 8007 sudah dipakai)

Menyediakan REST API terpusat di port 5000 untuk dikonsumsi Frontend:
  GET /api/all-data       -> Seluruh data sensor gabungan
  GET /api/depth          -> Data depth saja
  GET /api/trajectory     -> Data trajectory saja
  GET /api/ultrasonic     -> Data ultrasonic saja
  GET /api/status         -> Status koneksi semua backend

Cara Menjalankan:
  1. Jalankan rov-depth.py          (WS server di port 5002)
  2. Jalankan rov-trajectory2.py    (REST API di port 8007)
  3. Jalankan rov_ultrasonic.py     (REST API di port 8007/8008 + WS server di port 8765)
  4. Jalankan data.py               (Server pusat di port 5000)
================================================================================
"""

import json
import threading
import time
import logging
import csv
import os
from datetime import datetime

import websocket  # pip install websocket-client
import requests   # pip install requests
from flask import Flask, jsonify
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
DATA_SERVER_PORT = 5000

# Endpoint backend sensor
DEPTH_WS_URL = "ws://127.0.0.1:5002"
TRAJECTORY_HTTP_URL = "http://127.0.0.1:8007/api/trajectory"
ULTRASONIC_HTTP_URLS = [
    "http://127.0.0.1:8008/api/trajectory",  # Port cadangan (jika trajectory sudah pakai 8007)
    "http://127.0.0.1:8007/api/trajectory",  # Port utama
]

# Interval polling HTTP (detik)
TRAJECTORY_POLL_INTERVAL = 0.1   # 10 Hz
ULTRASONIC_POLL_INTERVAL = 0.1   # 10 Hz

# Timeout koneksi HTTP (detik)
HTTP_TIMEOUT = 2.0

# Delay reconnect WebSocket (detik)
WS_RECONNECT_DELAY = 3.0

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# Redam log akses Werkzeug yang berlebihan
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Konfigurasi CSV Logging
# ---------------------------------------------------------------------------
# Folder output CSV (dibuat otomatis di subfolder 'logs/' sejajar data.py)
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# Interval minimum penulisan CSV per sensor (detik)
# Agar file CSV tidak membengkak, data ditulis max 2 Hz (setiap 0.5 detik)
CSV_LOG_INTERVAL = 0.5

# Lock khusus untuk operasi file CSV (terpisah dari data_lock agar tidak saling blokir)
csv_lock = threading.Lock()

# Timestamp terakhir penulisan CSV per sensor
_last_csv_write = {
    'depth': 0.0,
    'trajectory': 0.0,
    'ultrasonic': 0.0,
}

# Path file CSV aktif saat ini (diisi saat init)
csv_paths = {
    'depth': '',
    'trajectory': '',
    'ultrasonic': '',
}


def init_csv_logs():
    """
    Membuat folder logs/ dan file CSV baru dengan header untuk setiap sensor.
    Nama file menggunakan timestamp sesi agar riwayat sesi sebelumnya tidak tertimpa.
    Dipanggil sekali saat program dimulai.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    session_ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ----- DEPTH CSV -----
    csv_paths['depth'] = os.path.join(LOG_DIR, f'depth_{session_ts}.csv')
    with open(csv_paths['depth'], mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([
            'timestamp', 'depth_m', 'depth_cm', 'rate_m_s',
            'source', 'mavlink_connected',
            'surface_pressure_hpa', 'raw_pressure_hpa',
        ])

    # ----- TRAJECTORY CSV -----
    csv_paths['trajectory'] = os.path.join(LOG_DIR, f'trajectory_{session_ts}.csv')
    with open(csv_paths['trajectory'], mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([
            'timestamp', 'source',
            'x', 'y', 'z',
            'raw_x', 'raw_y', 'raw_z',
            'origin_x', 'origin_y', 'origin_z',
            'yaw', 'mavlink_connected',
            'servo1', 'servo2', 'servo5',
            'v_surge', 'v_sway',
        ])

    # ----- ULTRASONIC CSV -----
    csv_paths['ultrasonic'] = os.path.join(LOG_DIR, f'ultrasonic_{session_ts}.csv')
    with open(csv_paths['ultrasonic'], mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([
            'timestamp', 'source', 'mapping_mode',
            'x_cm', 'y_cm', 'z_cm',
            'raw_x_cm', 'raw_y_cm',
            'origin_x_cm', 'origin_y_cm',
            's1_distance_cm', 's1_distance_mm', 's1_status',
            's2_distance_cm', 's2_distance_mm', 's2_status',
            'ultrasonic_connected',
        ])

    print(f"[CSV] Folder log  : {LOG_DIR}")
    print(f"[CSV] Depth log   : {os.path.basename(csv_paths['depth'])}")
    print(f"[CSV] Trajectory  : {os.path.basename(csv_paths['trajectory'])}")
    print(f"[CSV] Ultrasonic  : {os.path.basename(csv_paths['ultrasonic'])}")


def log_depth_csv():
    """Menulis satu baris data depth ke file CSV jika interval terpenuhi."""
    now = time.time()
    if now - _last_csv_write['depth'] < CSV_LOG_INTERVAL:
        return
    _last_csv_write['depth'] = now

    with data_lock:
        info = system_data['depth_info']
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            round(info['depth'], 4),
            round(info['depth_cm'], 2),
            round(info['rate'], 4),
            info['source'],
            info['mavlink_connected'],
            info['surface_pressure_hpa'],
            info['raw_pressure_hpa'],
        ]

    try:
        with csv_lock:
            with open(csv_paths['depth'], mode='a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(row)
    except Exception as e:
        print(f"[CSV] Gagal menulis depth log: {e}")


def log_trajectory_csv():
    """Menulis satu baris data trajectory ke file CSV jika interval terpenuhi."""
    now = time.time()
    if now - _last_csv_write['trajectory'] < CSV_LOG_INTERVAL:
        return
    _last_csv_write['trajectory'] = now

    with data_lock:
        info = system_data['trajectory_info']
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            info['source'],
            round(info['x'], 3),
            round(info['y'], 3),
            round(info['z'], 3),
            round(info['raw_x'], 3),
            round(info['raw_y'], 3),
            round(info['raw_z'], 3),
            round(info['origin_x'], 3),
            round(info['origin_y'], 3),
            round(info['origin_z'], 3),
            round(info['yaw'], 1),
            info['mavlink_connected'],
            info['servo1'],
            info['servo2'],
            info['servo5'],
            round(info['v_surge'], 3),
            round(info['v_sway'], 3),
        ]

    try:
        with csv_lock:
            with open(csv_paths['trajectory'], mode='a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(row)
    except Exception as e:
        print(f"[CSV] Gagal menulis trajectory log: {e}")


def log_ultrasonic_csv():
    """Menulis satu baris data ultrasonic ke file CSV jika interval terpenuhi."""
    now = time.time()
    if now - _last_csv_write['ultrasonic'] < CSV_LOG_INTERVAL:
        return
    _last_csv_write['ultrasonic'] = now

    with data_lock:
        info = system_data['ultrasonic_info']
        s1 = info['sensor_1']
        s2 = info['sensor_2']
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            info['source'],
            info['mapping_mode'],
            round(info['x'], 1),
            round(info['y'], 1),
            round(info['z'], 1),
            round(info['raw_x'], 1),
            round(info['raw_y'], 1),
            round(info['origin_x'], 1),
            round(info['origin_y'], 1),
            s1.get('distance_cm'),
            s1.get('distance_mm'),
            s1.get('status', 'N/A'),
            s2.get('distance_cm'),
            s2.get('distance_mm'),
            s2.get('status', 'N/A'),
            info['ultrasonic_connected'],
        ]

    try:
        with csv_lock:
            with open(csv_paths['ultrasonic'], mode='a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(row)
    except Exception as e:
        print(f"[CSV] Gagal menulis ultrasonic log: {e}")

# ---------------------------------------------------------------------------
# Penyimpanan Data Terpusat (Thread-Safe)
# ---------------------------------------------------------------------------
data_lock = threading.Lock()

system_data = {
    # ---- DEPTH (dari rov-depth.py via WebSocket port 5002) ----
    'depth_info': {
        'connected': False,
        'depth': 0.0,
        'depth_cm': 0.0,
        'rate': 0.0,
        'source': 'unknown',
        'mavlink_connected': False,
        'max_depth_m': 0.0,
        'max_depth_cm': 0.0,
        'surface_pressure_hpa': None,
        'raw_pressure_hpa': None,
        'last_update': 0.0,
    },

    # ---- TRAJECTORY (dari rov-trajectory2.py via HTTP port 8007) ----
    'trajectory_info': {
        'connected': False,
        'source': 'unknown',
        'x': 0.0,
        'y': 0.0,
        'z': 0.0,
        'raw_x': 0.0,
        'raw_y': 0.0,
        'raw_z': 0.0,
        'origin_x': 0.0,
        'origin_y': 0.0,
        'origin_z': 0.0,
        'yaw': 0.0,
        'mavlink_connected': False,
        'servo1': 1500,
        'servo2': 1500,
        'servo5': 1500,
        'v_surge': 0.0,
        'v_sway': 0.0,
        'last_update': 0.0,
    },

    # ---- ULTRASONIC (dari rov_ultrasonic.py via HTTP port 8007/8008) ----
    'ultrasonic_info': {
        'connected': False,
        'source': 'unknown',
        'unit': 'cm',
        'x': 0.0,
        'y': 0.0,
        'z': 0.0,
        'raw_x': 0.0,
        'raw_y': 0.0,
        'raw_z': 0.0,
        'origin_x': 0.0,
        'origin_y': 0.0,
        'origin_z': 0.0,
        'yaw': 0.0,
        'ultrasonic_connected': False,
        'mapping_mode': 'continuous',
        'sensor_1': {
            'distance_cm': None,
            'distance_mm': None,
            'status': 'N/A',
            'target_axis': 'Y',
        },
        'sensor_2': {
            'distance_cm': None,
            'distance_mm': None,
            'status': 'N/A',
            'target_axis': 'X',
        },
        'pool_size': {'width': 5.0, 'height': 5.0},
        'history_points': 0,
        'last_update': 0.0,
    },
}


# ============================================================================
# 1. WEBSOCKET CLIENT UNTUK DEPTH (PORT 5002)
# ============================================================================
def on_depth_message(ws, message):
    """Callback: setiap kali rov-depth.py push data telemetri via WebSocket."""
    try:
        data = json.loads(message)
        with data_lock:
            info = system_data['depth_info']
            info['connected'] = True
            info['last_update'] = time.time()
            # Ambil semua field yang tersedia dari payload rov-depth.py
            info['depth'] = data.get('depth', info['depth'])
            info['depth_cm'] = data.get('depth_cm', info['depth_cm'])
            info['rate'] = data.get('rate', info['rate'])
            info['source'] = data.get('source', info['source'])
            info['mavlink_connected'] = data.get('mavlink_connected', info['mavlink_connected'])
            info['max_depth_m'] = data.get('max_depth_m', info['max_depth_m'])
            info['max_depth_cm'] = data.get('max_depth_cm', info['max_depth_cm'])
            info['surface_pressure_hpa'] = data.get('surface_pressure_hpa', info['surface_pressure_hpa'])
            info['raw_pressure_hpa'] = data.get('raw_pressure_hpa', info['raw_pressure_hpa'])
    except Exception as e:
        print(f"[Depth WS] Error parsing message: {e}")
    else:
        # Catat ke CSV setelah data berhasil diperbarui
        log_depth_csv()


def on_depth_open(ws):
    print(f"[Depth WS] Terhubung ke {DEPTH_WS_URL}")


def on_depth_error(ws, error):
    print(f"[Depth WS] Error: {error}")
    with data_lock:
        system_data['depth_info']['connected'] = False


def on_depth_close(ws, close_status_code, close_msg):
    print(f"[Depth WS] Terputus (code={close_status_code}). Reconnect dalam {WS_RECONNECT_DELAY}s...")
    with data_lock:
        system_data['depth_info']['connected'] = False
    time.sleep(WS_RECONNECT_DELAY)
    start_depth_ws_client()  # Auto reconnect


def start_depth_ws_client():
    """Membuat dan menjalankan WebSocket client ke rov-depth.py (port 5002)."""
    ws = websocket.WebSocketApp(
        DEPTH_WS_URL,
        on_open=on_depth_open,
        on_message=on_depth_message,
        on_error=on_depth_error,
        on_close=on_depth_close,
    )
    ws.run_forever(reconnect=5)


# ============================================================================
# 2. HTTP POLLING CLIENT UNTUK TRAJECTORY (PORT 8007)
# ============================================================================
def trajectory_polling_worker():
    """Background thread: polling data trajectory dari rov-trajectory2.py setiap 100ms."""
    print(f"[Trajectory HTTP] Memulai polling ke {TRAJECTORY_HTTP_URL} (interval {TRAJECTORY_POLL_INTERVAL}s)")
    session = requests.Session()

    while True:
        try:
            resp = session.get(TRAJECTORY_HTTP_URL, timeout=HTTP_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                with data_lock:
                    info = system_data['trajectory_info']
                    info['connected'] = True
                    info['last_update'] = time.time()
                    info['source'] = data.get('source', info['source'])
                    info['x'] = data.get('x', info['x'])
                    info['y'] = data.get('y', info['y'])
                    info['z'] = data.get('z', info['z'])
                    info['raw_x'] = data.get('raw_x', info['raw_x'])
                    info['raw_y'] = data.get('raw_y', info['raw_y'])
                    info['raw_z'] = data.get('raw_z', info['raw_z'])
                    info['origin_x'] = data.get('origin_x', info['origin_x'])
                    info['origin_y'] = data.get('origin_y', info['origin_y'])
                    info['origin_z'] = data.get('origin_z', info['origin_z'])
                    info['yaw'] = data.get('yaw', info['yaw'])
                    info['mavlink_connected'] = data.get('mavlink_connected', info['mavlink_connected'])
                    info['servo1'] = data.get('servo1', info['servo1'])
                    info['servo2'] = data.get('servo2', info['servo2'])
                    info['servo5'] = data.get('servo5', info['servo5'])
                    info['v_surge'] = data.get('v_surge', info['v_surge'])
                    info['v_sway'] = data.get('v_sway', info['v_sway'])
                # Catat ke CSV setelah data berhasil diperbarui
                log_trajectory_csv()
            else:
                with data_lock:
                    system_data['trajectory_info']['connected'] = False

        except requests.exceptions.ConnectionError:
            with data_lock:
                system_data['trajectory_info']['connected'] = False
        except Exception as e:
            print(f"[Trajectory HTTP] Error: {e}")
            with data_lock:
                system_data['trajectory_info']['connected'] = False

        time.sleep(TRAJECTORY_POLL_INTERVAL)


# ============================================================================
# 3. HTTP POLLING CLIENT UNTUK ULTRASONIC (PORT 8007 / 8008)
# ============================================================================
def ultrasonic_polling_worker():
    """
    Background thread: polling data ultrasonic dari rov_ultrasonic.py.
    Secara otomatis mencoba port 8008 terlebih dahulu (port cadangan ultrasonic),
    lalu fallback ke 8007 jika 8008 tidak tersedia.
    """
    print(f"[Ultrasonic HTTP] Memulai polling (interval {ULTRASONIC_POLL_INTERVAL}s)")
    session = requests.Session()
    active_url = None  # URL aktif yang terakhir berhasil

    while True:
        success = False

        # Jika sudah punya URL aktif, coba URL itu dulu
        urls_to_try = [active_url] if active_url else ULTRASONIC_HTTP_URLS

        for url in urls_to_try:
            if url is None:
                continue
            try:
                resp = session.get(url, timeout=HTTP_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    # Deteksi apakah ini benar data ultrasonic (bukan trajectory MAVLink)
                    source = data.get('source', '')
                    if source == 'ultrasonic' or 'sensor_1' in data or 'ultrasonic_connected' in data:
                        active_url = url
                        with data_lock:
                            info = system_data['ultrasonic_info']
                            info['connected'] = True
                            info['last_update'] = time.time()
                            info['source'] = data.get('source', info['source'])
                            info['unit'] = data.get('unit', info['unit'])
                            info['x'] = data.get('x', info['x'])
                            info['y'] = data.get('y', info['y'])
                            info['z'] = data.get('z', info['z'])
                            info['raw_x'] = data.get('raw_x', info['raw_x'])
                            info['raw_y'] = data.get('raw_y', info['raw_y'])
                            info['raw_z'] = data.get('raw_z', info['raw_z'])
                            info['origin_x'] = data.get('origin_x', info['origin_x'])
                            info['origin_y'] = data.get('origin_y', info['origin_y'])
                            info['origin_z'] = data.get('origin_z', info['origin_z'])
                            info['yaw'] = data.get('yaw', info['yaw'])
                            info['ultrasonic_connected'] = data.get('ultrasonic_connected', info['ultrasonic_connected'])
                            info['mapping_mode'] = data.get('mapping_mode', info['mapping_mode'])
                            # Sensor 1 & 2
                            if 'sensor_1' in data:
                                info['sensor_1'] = data['sensor_1']
                            if 'sensor_2' in data:
                                info['sensor_2'] = data['sensor_2']
                            if 'pool_size' in data:
                                info['pool_size'] = data['pool_size']
                            info['history_points'] = data.get('history_points', info['history_points'])
                        success = True
                        break
            except requests.exceptions.ConnectionError:
                pass
            except Exception as e:
                print(f"[Ultrasonic HTTP] Error ({url}): {e}")

        # Jika URL aktif gagal, coba semua URL
        if not success and active_url is not None:
            active_url = None
            for url in ULTRASONIC_HTTP_URLS:
                try:
                    resp = session.get(url, timeout=HTTP_TIMEOUT)
                    if resp.status_code == 200:
                        data = resp.json()
                        source = data.get('source', '')
                        if source == 'ultrasonic' or 'sensor_1' in data or 'ultrasonic_connected' in data:
                            active_url = url
                            print(f"[Ultrasonic HTTP] Ditemukan di {url}")
                            success = True
                            break
                except Exception:
                    pass

        if not success:
            with data_lock:
                system_data['ultrasonic_info']['connected'] = False

        time.sleep(ULTRASONIC_POLL_INTERVAL)


# ============================================================================
# 4. MONITOR STATUS (Log berkala ke terminal)
# ============================================================================
def status_monitor_worker():
    """Background thread: menampilkan status koneksi semua sensor setiap 5 detik."""
    while True:
        time.sleep(5.0)
        with data_lock:
            depth_ok = system_data['depth_info']['connected']
            traj_ok = system_data['trajectory_info']['connected']
            ultra_ok = system_data['ultrasonic_info']['connected']

            depth_val = system_data['depth_info']['depth']
            traj_x = system_data['trajectory_info']['x']
            traj_y = system_data['trajectory_info']['y']
            traj_z = system_data['trajectory_info']['z']
            ultra_x = system_data['ultrasonic_info']['x']
            ultra_y = system_data['ultrasonic_info']['y']

        icon = lambda ok: "OK" if ok else "--"
        print(
            f"[Status] "
            f"Depth: {icon(depth_ok)} ({depth_val:.3f}m) | "
            f"Trajectory: {icon(traj_ok)} (X:{traj_x:+.2f} Y:{traj_y:+.2f} Z:{traj_z:.2f}) | "
            f"Ultrasonic: {icon(ultra_ok)} (X:{ultra_x:.1f}cm Y:{ultra_y:.1f}cm)"
        )


# ============================================================================
# REST API TERPUSAT UNTUK FRONTEND (PORT 5000)
# ============================================================================
@app.route('/api/all-data', methods=['GET'])
def get_all_data():
    """Frontend cukup panggil endpoint ini untuk mendapatkan SEMUA data sensor sekaligus."""
    with data_lock:
        return jsonify(system_data)


@app.route('/api/depth', methods=['GET'])
def get_depth():
    """Endpoint khusus data depth saja."""
    with data_lock:
        return jsonify(system_data['depth_info'])


@app.route('/api/trajectory', methods=['GET'])
def get_trajectory():
    """Endpoint khusus data trajectory saja."""
    with data_lock:
        return jsonify(system_data['trajectory_info'])


@app.route('/api/ultrasonic', methods=['GET'])
def get_ultrasonic():
    """Endpoint khusus data ultrasonic saja."""
    with data_lock:
        return jsonify(system_data['ultrasonic_info'])


@app.route('/api/status', methods=['GET'])
def get_status():
    """Cek status koneksi semua backend sensor."""
    with data_lock:
        now = time.time()
        depth_age = now - system_data['depth_info']['last_update']
        traj_age = now - system_data['trajectory_info']['last_update']
        ultra_age = now - system_data['ultrasonic_info']['last_update']

        return jsonify({
            'depth': {
                'connected': system_data['depth_info']['connected'],
                'last_update_age_s': round(depth_age, 1) if system_data['depth_info']['last_update'] > 0 else None,
                'backend': DEPTH_WS_URL,
            },
            'trajectory': {
                'connected': system_data['trajectory_info']['connected'],
                'last_update_age_s': round(traj_age, 1) if system_data['trajectory_info']['last_update'] > 0 else None,
                'backend': TRAJECTORY_HTTP_URL,
            },
            'ultrasonic': {
                'connected': system_data['ultrasonic_info']['connected'],
                'last_update_age_s': round(ultra_age, 1) if system_data['ultrasonic_info']['last_update'] > 0 else None,
                'backend': 'auto-detect (port 8007/8008)',
            },
        })


# ============================================================================
# ENTRYPOINT
# ============================================================================
if __name__ == '__main__':
    print("=" * 72)
    print("  DATA.PY - SERVER DATA PUSAT ROV")
    print("=" * 72)
    print(f"  REST API     : http://0.0.0.0:{DATA_SERVER_PORT}/api/all-data")
    print(f"  Depth src    : {DEPTH_WS_URL} (WebSocket)")
    print(f"  Trajectory   : {TRAJECTORY_HTTP_URL} (HTTP Polling)")
    print(f"  Ultrasonic   : auto-detect port 8007/8008 (HTTP Polling)")
    print("=" * 72)

    # 1. Thread WebSocket client ke rov-depth.py (port 5002)
    t_depth = threading.Thread(target=start_depth_ws_client, daemon=True, name="depth-ws")
    t_depth.start()

    # 2. Thread HTTP polling ke rov-trajectory2.py (port 8007)
    t_trajectory = threading.Thread(target=trajectory_polling_worker, daemon=True, name="trajectory-poll")
    t_trajectory.start()

    # 3. Thread HTTP polling ke rov_ultrasonic.py (port 8007/8008)
    t_ultrasonic = threading.Thread(target=ultrasonic_polling_worker, daemon=True, name="ultrasonic-poll")
    t_ultrasonic.start()

    # 4. Thread monitor status berkala
    t_status = threading.Thread(target=status_monitor_worker, daemon=True, name="status-monitor")
    t_status.start()

    # 5. Jalankan Flask server utama di port 5000
    print(f"\n[Data.py] Server Pusat AKTIF di http://0.0.0.0:{DATA_SERVER_PORT}")
    app.run(host='0.0.0.0', port=DATA_SERVER_PORT, threaded=True)