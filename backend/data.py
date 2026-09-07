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

try:
    import websocket  # pip install websocket-client
except ImportError:
    websocket = None
import requests   # pip install requests
from flask import Flask, jsonify, request
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
DATA_SERVER_PORT = 5000

# Endpoint backend sensor
DEPTH_WS_URL = "ws://127.0.0.1:5002"
DEPTH_HTTP_URL = "http://127.0.0.1:5001/api/telemetry"  # fallback bila WS tidak tersedia
TRAJECTORY_HTTP_URL = "http://127.0.0.1:8007/api/trajectory"
ULTRASONIC_HTTP_URLS = [
    "http://127.0.0.1:8008/api/trajectory",  # Port cadangan (jika trajectory sudah pakai 8007)
    "http://127.0.0.1:8007/api/trajectory",  # Port utama
]

# Interval polling HTTP (detik)
TRAJECTORY_POLL_INTERVAL = 0.1   # 10 Hz
ULTRASONIC_POLL_INTERVAL = 0.1   # 10 Hz
DEPTH_POLL_INTERVAL = 0.1        # 10 Hz (fallback HTTP)

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

# Satu file CSV gabungan untuk seluruh sesi dan semua sumber data.
CSV_PATH = os.path.join(LOG_DIR, 'data.csv')

# Agar file CSV tidak membengkak, data ditulis maksimal 2 Hz (setiap 0.5 detik).
CSV_LOG_INTERVAL = 0.5

# Lock khusus untuk operasi file CSV (terpisah dari data_lock agar tidak saling blokir)
csv_lock = threading.Lock()

_last_csv_write = 0.0


def init_csv_logs():
    """Siapkan satu file ``logs/data.csv`` tanpa menghapus data sesi lama."""
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                'timestamp',
                'servo1_pwm', 'servo2_pwm', 'servo3_pwm', 'servo4_pwm', 'servo5_pwm',
                'x_surge_pwm', 'y_sway_pwm', 'z_heave_pwm', 'r_yaw_pwm', 'buttons',
                'depth_sensor_m', 'depth_sensor_cm', 'depth_rate_m_s',
                'us_front_cm', 'us_front_mm', 'us_front_position_y_cm', 'us_front_status',
                'us_down_cm', 'us_down_mm', 'us_down_position_x_cm', 'us_down_status',
            ])
    print(f"[CSV] Data gabungan: {CSV_PATH}")


def log_data_csv():
    """Simpan satu snapshot gabungan ke ``data.csv``."""
    global _last_csv_write
    now = time.time()
    if now - _last_csv_write < CSV_LOG_INTERVAL:
        return
    _last_csv_write = now

    with data_lock:
        rov = system_data['rov_data']
        trajectory = system_data['trajectory_info']
        depth = system_data['depth_info']
        ultrasonic = system_data['ultrasonic_info']
        s1 = ultrasonic['sensor_1']
        s2 = ultrasonic['sensor_2']
        s1_cm = s1.get('distance_cm')
        s2_cm = s2.get('distance_cm')
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            trajectory['servo1'], trajectory['servo2'], trajectory['servo3'],
            trajectory['servo4'], trajectory['servo5'],
            rov['actuator']['x'], rov['actuator']['y'], rov['actuator']['z'],
            rov['actuator']['r'], rov['trigger']['buttons'],
            depth['depth'], depth['depth_cm'], depth['rate'],
            s1_cm, s1.get('distance_mm'), _ultrasonic_position_cm(s1_cm), s1.get('status', 'N/A'),
            s2_cm, s2.get('distance_mm'), _ultrasonic_position_cm(s2_cm), s2.get('status', 'N/A'),
        ]

    try:
        with csv_lock:
            with open(CSV_PATH, mode='a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(row)
    except OSError as e:
        print(f"[CSV] Gagal menulis data.csv: {e}")

# ---------------------------------------------------------------------------
# Penyimpanan Data Terpusat (Thread-Safe)
# ---------------------------------------------------------------------------
data_lock = threading.Lock()

system_data = {
    # ---- FORMAT TELEMETRI ROV UTAMA ----
    # Nilai PWM selalu dibatasi pada 1100--1900.  Nilai 1500 berarti netral.
    # Data ini diperbarui dari backend lain melalui fungsi sync_* di bawah.
    'rov_data': {
        'actuator': {
            'x': 1500,  # surge: maju/mundur
            'y': 1500,  # sway: kiri/kanan
            'z': 1500,  # heave: naik/turun
            'r': 1500,  # yaw: putar kiri/kanan
        },
        'trigger': {
            'buttons': 0,  # bitmask tombol gamepad
        },
        'sensor': {
            'depth_sensor': None,  # meter, dari Pixhawk
            'us_front': None,      # meter, ultrasonik depan
            'us_down': None,       # meter, ultrasonik bawah
        },
        'last_update': 0.0,
    },
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
        'servo3': 1500,
        'servo4': 1500,
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


def _pwm(value, default=1500):
    """Normalisasi satu nilai aktuator menjadi PWM aman (1100--1900)."""
    try:
        return max(1100, min(1900, int(value)))
    except (TypeError, ValueError):
        return default


def _distance_to_m(value, unit='cm'):
    """Konversi jarak ultrasonik ke meter; None tetap menandakan data belum ada."""
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value / 1000.0 if unit == 'mm' else value / 100.0 if unit == 'cm' else value


def _ultrasonic_position_cm(distance_cm):
    """Rumus continuous dari rov_ultrasonic.py: posisi = 600 - jarak(cm)."""
    try:
        distance_cm = float(distance_cm)
    except (TypeError, ValueError):
        return None
    return round(600.0 - distance_cm, 1) if distance_cm > 0 else None


def _distance_to_cm(value, unit='cm'):
    """Konversi jarak ke cm untuk format CSV/rov_ultrasonic.py."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if unit == 'mm':
        return round(value / 10.0, 2)
    if unit == 'm':
        return round(value * 100.0, 2)
    return round(value, 2)


def sync_control_data(payload):
    """Ambil kontrol dari payload backend tanpa mencampurnya dengan koordinat posisi.

    Sumber dapat mengirim ``actuator``/``trigger`` atau field datar
    ``pwm_x``, ``pwm_y``, ``pwm_z``, ``pwm_r``, dan ``buttons``.
    """
    actuator = payload.get('actuator', {}) if isinstance(payload, dict) else {}
    trigger = payload.get('trigger', {}) if isinstance(payload, dict) else {}
    if not isinstance(actuator, dict):
        actuator = {}
    if not isinstance(trigger, dict):
        trigger = {}

    with data_lock:
        target = system_data['rov_data']
        for axis in ('x', 'y', 'z', 'r'):
            value = actuator.get(axis, payload.get(f'pwm_{axis}'))
            if value is not None:
                target['actuator'][axis] = _pwm(value, target['actuator'][axis])

        buttons = trigger.get('buttons', payload.get('buttons'))
        if buttons is not None:
            try:
                target['trigger']['buttons'] = max(0, int(buttons))
            except (TypeError, ValueError):
                pass

        # Pengirim simulator atau backend MAVLink dapat meneruskan PWM mentah
        # servo 1--5 supaya data.csv selalu merekam lima kanal tersebut.
        trajectory = system_data['trajectory_info']
        for channel in range(1, 6):
            key = f'servo{channel}'
            if key in payload:
                trajectory[key] = _pwm(payload[key], trajectory[key])
        target['last_update'] = time.time()


def sync_depth_sensor(depth_m):
    with data_lock:
        system_data['rov_data']['sensor']['depth_sensor'] = _distance_to_m(depth_m, 'm')
        system_data['rov_data']['last_update'] = time.time()


def sync_ultrasonic_sensors(sensor_1, sensor_2):
    """Petakan sensor_1=depan dan sensor_2=bawah dari rov_ultrasonic.py.

    Kedua sumber dapat mengirim ``distance_m``, ``distance_cm``, atau
    ``distance_mm``. Ubah pemetaan ini bila kabel sensor fisik ditukar.
    """
    def as_m(sensor):
        if not isinstance(sensor, dict):
            return None
        for field, unit in (('distance_m', 'm'), ('distance_cm', 'cm'), ('distance_mm', 'mm')):
            if field in sensor:
                return _distance_to_m(sensor[field], unit)
        return None

    with data_lock:
        target = system_data['rov_data']['sensor']
        target['us_front'] = as_m(sensor_1)
        target['us_down'] = as_m(sensor_2)
        system_data['rov_data']['last_update'] = time.time()


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
        # depth dari rov-depth.py sudah dalam satuan meter
        sync_depth_sensor(data.get('depth'))
        sync_control_data(data)
    except Exception as e:
        print(f"[Depth WS] Error parsing message: {e}")
    else:
        # Catat ke CSV setelah data berhasil diperbarui
        log_data_csv()


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
    if websocket is None:
        print("[Depth WS] websocket-client belum terpasang; depth WebSocket dilewati.")
        return
    ws = websocket.WebSocketApp(
        DEPTH_WS_URL,
        on_open=on_depth_open,
        on_message=on_depth_message,
        on_error=on_depth_error,
        on_close=on_depth_close,
    )
    ws.run_forever(reconnect=5)


def depth_http_polling_worker():
    """Fallback HTTP untuk rov-depth.py atau simulator tanpa WebSocket."""
    session = requests.Session()
    while True:
        try:
            response = session.get(DEPTH_HTTP_URL, timeout=HTTP_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                with data_lock:
                    info = system_data['depth_info']
                    info['connected'] = True
                    info['last_update'] = time.time()
                    info['depth'] = data.get('depth', info['depth'])
                    info['depth_cm'] = data.get('depth_cm', info['depth_cm'])
                    info['rate'] = data.get('rate', info['rate'])
                    info['source'] = data.get('source', info['source'])
                    info['mavlink_connected'] = data.get('mavlink_connected', info['mavlink_connected'])
                sync_depth_sensor(data.get('depth'))
                log_data_csv()
        except (requests.exceptions.RequestException, ValueError):
            pass
        time.sleep(DEPTH_POLL_INTERVAL)


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
                    info['servo3'] = data.get('servo3', info['servo3'])
                    info['servo4'] = data.get('servo4', info['servo4'])
                    info['servo5'] = data.get('servo5', info['servo5'])
                    info['v_surge'] = data.get('v_surge', info['v_surge'])
                    info['v_sway'] = data.get('v_sway', info['v_sway'])
                # rov-trajectory2.py menyediakan PWM surge di servo 1/2 dan
                # PWM sway di servo 5. Z/R tetap nilai terakhir sampai sumber
                # kontrol mengirim pwm_z/pwm_r atau objek actuator.
                surge = (_pwm(data.get('servo1')) + _pwm(data.get('servo2'))) / 2
                sync_control_data({
                    'pwm_x': surge,
                    'pwm_y': data.get('servo5', 1500),
                    'pwm_z': data.get('servo3'),
                    'pwm_r': data.get('servo4'),
                    'buttons': data.get('buttons'),
                    'actuator': data.get('actuator', {}),
                    'trigger': data.get('trigger', {}),
                })
                # Catat ke CSV setelah data berhasil diperbarui
                log_data_csv()
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
                        # Konvensi payload saat ini: sensor_1=depan,
                        # sensor_2=bawah. Semua nilai yang dipublikasikan
                        # data.py dinormalisasi ke meter.
                        sync_ultrasonic_sensors(
                            data.get('sensor_1'), data.get('sensor_2')
                        )
                        sync_control_data(data)
                        log_data_csv()
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


@app.route('/api/data', methods=['GET'])
def get_rov_data():
    """Format ringkas untuk kontrol dan evaluasi kondisi ROV.

    ``x/y/z/r`` adalah PWM (1100--1900), ``buttons`` adalah bitmask, dan
    semua jarak sensor menggunakan meter.
    """
    with data_lock:
        rov = system_data['rov_data']
        return jsonify({
            **rov['actuator'],
            **rov['trigger'],
            **rov['sensor'],
            'unit': {
                'actuator': 'pwm_us',
                'depth_sensor': 'm',
                'us_front': 'm',
                'us_down': 'm',
            },
            'last_update': rov['last_update'],
        })


@app.route('/api/control', methods=['POST'])
def receive_control():
    """Terima data kontrol dari file/backend gamepad lain.

    Contoh payload: {"actuator":{"x":1600,"y":1500,"z":1500,"r":1400},
    "trigger":{"buttons":1}}. Field datar ``pwm_x`` s.d. ``pwm_r`` juga
    didukung agar mudah dipakai oleh pengirim MAVLink yang sudah ada.
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'payload JSON object diperlukan'}), 400
    sync_control_data(payload)
    return get_rov_data()


@app.route('/api/sensor', methods=['POST'])
def receive_sensor():
    """Terima pembaruan sensor langsung dari file pembaca sensor bila diperlukan."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({'error': 'payload JSON object diperlukan'}), 400
    with data_lock:
        sensor = system_data['rov_data']['sensor']
        if 'depth_sensor' in payload:
            depth_m = _distance_to_m(payload['depth_sensor'], 'm')
            sensor['depth_sensor'] = depth_m
            depth_info = system_data['depth_info']
            depth_info['connected'] = True
            depth_info['source'] = payload.get('source', 'simulator')
            depth_info['depth'] = depth_m if depth_m is not None else depth_info['depth']
            depth_info['depth_cm'] = round(depth_m * 100.0, 2) if depth_m is not None else depth_info['depth_cm']
            depth_info['rate'] = payload.get('depth_rate_m_s', depth_info['rate'])
            depth_info['last_update'] = time.time()

        ultrasonic = system_data['ultrasonic_info']
        ultrasonic['source'] = payload.get('source', ultrasonic['source'])
        ultrasonic['connected'] = True
        ultrasonic['ultrasonic_connected'] = True
        if 'us_front' in payload:
            unit = payload.get('us_front_unit', 'm')
            front_cm = _distance_to_cm(payload['us_front'], unit)
            sensor['us_front'] = _distance_to_m(payload['us_front'], unit)
            ultrasonic['sensor_1'] = {
                'distance_cm': front_cm,
                'distance_mm': round(front_cm * 10.0, 1) if front_cm is not None else None,
                'status': payload.get('us_front_status', 'VALID'),
                'target_axis': 'Y',
            }
            if front_cm is not None:
                ultrasonic['raw_y'] = _ultrasonic_position_cm(front_cm)
                ultrasonic['y'] = ultrasonic['raw_y']
        if 'us_down' in payload:
            unit = payload.get('us_down_unit', 'm')
            down_cm = _distance_to_cm(payload['us_down'], unit)
            sensor['us_down'] = _distance_to_m(payload['us_down'], unit)
            ultrasonic['sensor_2'] = {
                'distance_cm': down_cm,
                'distance_mm': round(down_cm * 10.0, 1) if down_cm is not None else None,
                'status': payload.get('us_down_status', 'VALID'),
                'target_axis': 'X',
            }
            if down_cm is not None:
                ultrasonic['raw_x'] = _ultrasonic_position_cm(down_cm)
                ultrasonic['x'] = ultrasonic['raw_x']
        ultrasonic['last_update'] = time.time()
        system_data['rov_data']['last_update'] = time.time()
    log_data_csv()
    return get_rov_data()


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
    print(f"  Depth src    : {DEPTH_WS_URL} (WebSocket), fallback {DEPTH_HTTP_URL}")
    print(f"  Trajectory   : {TRAJECTORY_HTTP_URL} (HTTP Polling)")
    print(f"  Ultrasonic   : auto-detect port 8007/8008 (HTTP Polling)")
    print("=" * 72)

    init_csv_logs()

    # 1. Thread WebSocket client ke rov-depth.py (port 5002)
    t_depth = threading.Thread(target=start_depth_ws_client, daemon=True, name="depth-ws")
    t_depth.start()

    t_depth_http = threading.Thread(target=depth_http_polling_worker, daemon=True, name="depth-http-poll")
    t_depth_http.start()

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
