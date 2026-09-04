"""
================================================================================
ROV 3D TRAJECTORY & TELEMETRY BACKEND (DEAD RECKONING MODEL)
================================================================================

DESKRIPSI SISTEM:
Backend perantara (middleware) yang menerima telemetri MAVLink dari Pixhawk 
(melalui BlueOS di Onboard Computer / Companion) dan menyediakannya ke 
Ground Control Station (GCS / UI) melalui REST API (port 8007).

LOGIKA ESTIMASI POSISI (X, Y, Z, YAW):
1. Orientasi / Yaw (Heading):
   - Diterima dari pesan MAVLink 'ATTITUDE' (IMU/Kompas Pixhawk).
   - Dikonversi ke derajat 0 - 360° (0° = North/+Y, 90° = East/+X).

2. Sumbu Z (Kedalaman / Depth):
   - Diterima dari pesan 'GLOBAL_POSITION_INT' (relative_alt) atau 'SCALED_PRESSURE'.

3. Sumbu Horizontal X & Y (Dead Reckoning dari SERVO_OUTPUT_RAW):
   - Servo 1 & Servo 2: Kendali Maju / Mundur (Surge)
       * PWM > 1500 (+ deadband): Maju (v_surge > 0)
       * PWM < 1500 (- deadband): Mundur (v_surge < 0)
       * PWM == 1500 (rentang netral): Diam (v_surge = 0)
       * dev_surge = (dev_servo1 + dev_servo2) / 2.0
       * v_surge = dev_surge * K_SURGE (m/s)
   - Servo 5: Kendali Kanan / Kiri (Sway / Strafe)
       * PWM > 1500 (+ deadband): Geser Kanan (v_sway > 0)
       * PWM < 1500 (- deadband): Geser Kiri (v_sway < 0)
       * PWM == 1500 (rentang netral): Diam (v_sway = 0)
       * dev_sway = dev_servo5
       * v_sway = dev_sway * K_SWAY (m/s)
   - Transformasi Koordinat Body-Frame ke World-Frame Kolam berbasis Yaw:
       * dx = (v_surge * sin(yaw_rad) + v_sway * cos(yaw_rad)) * dt
       * dy = (v_surge * cos(yaw_rad) - v_sway * sin(yaw_rad)) * dt
   - Integrasi Posisi:
       * X = X + dx
       * Y = Y + dy

================================================================================
"""

import json
import logging
import math
import threading
import time
import urllib.request
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymavlink import mavutil

# Redam log akses HTTP Werkzeug yang berlebihan agar tidak memblokir console I/O
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Konfigurasi Endpoint MAVLink, Ultrasonic & Server
# ---------------------------------------------------------------------------
MAVLINK_UDP_ENDPOINT = 'udpin:0.0.0.0:14553'
ULTRASONIC_ENDPOINT = 'http://127.0.0.1:8008/api/trajectory'
HEARTBEAT_TIMEOUT_S = 10.0
RECONNECT_DELAY_S = 3.0
HTTP_PORT = 8007

# ---------------------------------------------------------------------------
# Parameter Kalibrasi Dead Reckoning (PWM -> Kecepatan m/s)
# ---------------------------------------------------------------------------
# Nilai netral PWM ESC (1500 us) dan rentang toleransi deadband
PWM_NEUTRAL = 1500
PWM_DEADBAND = 25  # Rentang (1475 - 1525 us) dianggap netral / motor diam

# Konstanta pengali kecepatan linier (meter/detik per satuan deviasi PWM)
# Contoh: deviasi +300 (PWM 1800) * 0.001 = 0.3 m/s
K_SURGE = 0.001    # Faktor kecepatan Maju / Mundur (Servo 1 & 2)
K_SWAY = 0.001     # Faktor kecepatan Kanan / Kiri (Servo 5)

app = Flask(__name__)
CORS(app)

state_lock = threading.Lock()

# Sumber data aktif ('real' untuk Pixhawk fisik, 'dummy' untuk simulasi UI)
current_source = 'real'

# State data posisi & telemetri aktual
real_data = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
    'yaw': 0.0,
    'mavlink_connected': False,
    'ultrasonic_connected': False,
    'sensor_1': None,
    'sensor_2': None,
    'servo1': 1500,
    'servo2': 1500,
    'servo5': 1500,
    'v_surge': 0.0,
    'v_sway': 0.0,
}

# Data tiruan untuk pengujian tanpa robot fisik
dummy_data = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
    'yaw': 0.0,
}

# Titik offset koordinat (Origin Kalibrasi)
origin = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
}


def apply_deadband(val, neutral=PWM_NEUTRAL, deadband=PWM_DEADBAND):
    """
    Menghitung deviasi PWM terhadap nilai netral (1500 us).
    Jika nilai berada di rentang netral (neutral - deadband s/d neutral + deadband),
    hasilnya adalah 0.0 (diam).
    """
    if val <= 0:
        return 0.0
    diff = val - neutral
    if abs(diff) <= deadband:
        return 0.0
    return float(diff)


# ---------------------------------------------------------------------------
# Ultrasonic Background Worker Thread (Sinkronisasi X, Y dari port 8008)
# ---------------------------------------------------------------------------
def ultrasonic_client_worker():
    """
    Sinkronisasi instan data posisi (X, Y) dari backend rov_ultrasonic.py (port 8008).
    Menggunakan interval polling cepat (30ms) dan update independen agar posisi
    langsung ter-update seketika data sensor masuk.
    """
    last_log_state = False
    last_valid_time = 0.0

    while True:
        try:
            req = urllib.request.Request(
                ULTRASONIC_ENDPOINT,
                headers={'User-Agent': 'ROV-Trajectory-Bridge'}
            )
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                if resp.status == 200:
                    u_data = json.loads(resp.read().decode())
                    is_u_ok = u_data.get('ultrasonic_connected', False)
                    raw_x = u_data.get('raw_x')
                    raw_y = u_data.get('raw_y')

                    with state_lock:
                        if is_u_ok:
                            last_valid_time = time.time()
                            real_data['ultrasonic_connected'] = True

                            # Update X dan Y SECARA INDEPENDEN DAN INSTAN!
                            if raw_x is not None:
                                real_data['x'] = raw_x
                            if raw_y is not None:
                                real_data['y'] = raw_y

                            real_data['sensor_1'] = u_data.get('sensor_1')
                            real_data['sensor_2'] = u_data.get('sensor_2')

                            if not last_log_state:
                                print(
                                    f"[ULTRASONIC BRIDGE] Terhubung ke {ULTRASONIC_ENDPOINT}! Posisi X & Y real-time aktif.")
                                last_log_state = True
                        else:
                            if time.time() - last_valid_time > 2.0:
                                real_data['ultrasonic_connected'] = False
        except Exception:
            with state_lock:
                if time.time() - last_valid_time > 2.0:
                    if last_log_state:
                        print(
                            "[ULTRASONIC BRIDGE] Koneksi ultrasonic terputus. Fallback ke Dead Reckoning MAVLink.")
                        last_log_state = False
                    real_data['ultrasonic_connected'] = False
        time.sleep(0.03)  # 30ms (~33 Hz) respon instan tanpa lag


# ---------------------------------------------------------------------------
# MAVLink Background Worker Thread
# ---------------------------------------------------------------------------
def mavlink_worker():
    """Menerima dan memproses data telemetri MAVLink dari Pixhawk via UDP."""
    while True:
        master = None
        try:
            print(
                f"[MAVLINK] Mendengarkan paket UDP di {MAVLINK_UDP_ENDPOINT} ...")
            master = mavutil.mavlink_connection(MAVLINK_UDP_ENDPOINT)

            # 1. Menunggu Heartbeat valid dari Autopilot
            target_sys = 1
            target_comp = 1
            t_start = time.time()

            while True:
                hb = master.recv_match(
                    type='HEARTBEAT', blocking=True, timeout=1.0)
                if hb is not None:
                    src_sys = hb.get_srcSystem()
                    src_comp = hb.get_srcComponent()

                    # Terima pesan heartbeat dari autopilot (Component 1) atau komponen sistem
                    if src_sys != 0:
                        target_sys = src_sys
                        target_comp = src_comp
                        master.target_system = target_sys
                        master.target_component = target_comp
                        print(
                            f"[MAVLINK] Heartbeat terdeteksi -> Sys ID: {target_sys}, Comp ID: {target_comp}")
                        break

                if time.time() - t_start > HEARTBEAT_TIMEOUT_S:
                    raise Exception(
                        "Timeout menunggu heartbeat valid dari Pixhawk")

            with state_lock:
                real_data['mavlink_connected'] = True

            # 2. Request Data Stream ke Pixhawk (10 Hz)
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
            )
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 10, 1
            )
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_RAW_CONTROLLER, 10, 1
            )

            last_msg_time = time.time()
            last_servo_time = time.time()
            last_log_time = time.time()

            # 3. Looping Utama Pemrosesan Paket MAVLink
            while True:
                msg = master.recv_match(blocking=True, timeout=1.0)

                if msg:
                    last_msg_time = time.time()
                    msg_type = msg.get_type()

                    with state_lock:
                        real_data['mavlink_connected'] = True

                        # --- A. PARSING HEADING / YAW (ATTITUDE) ---
                        if msg_type == 'ATTITUDE':
                            # msg.yaw dalam radian -> konversi ke derajat (0 - 360)
                            yaw_deg = (math.degrees(msg.yaw) + 360.0) % 360.0
                            real_data['yaw'] = yaw_deg

                        # --- B. PARSING KEDALAMAN (DEPTH / SUMBU Z) ---
                        elif msg_type == 'GLOBAL_POSITION_INT':
                            if hasattr(msg, 'relative_alt'):
                                # relative_alt dalam milimeter negatif -> meter positif
                                real_data['z'] = max(
                                    0.0, -float(msg.relative_alt) / 1000.0)

                        elif msg_type == 'SCALED_PRESSURE':
                            # Fallback sensor tekanan Bar30
                            press_diff = max(0.0, msg.press_diff)
                            real_data['z'] = press_diff / 98.0665

                        # --- C. ESTIMASI POSISI X & Y (DEAD RECKONING) ---
                        elif msg_type == 'SERVO_OUTPUT_RAW':
                            now = time.time()
                            dt = now - last_servo_time
                            last_servo_time = now

                            # Proteksi lonjakan nilai dt saat thread baru aktif atau delay
                            if dt > 1.0 or dt <= 0.0:
                                dt = 0.05  # Default ~20 Hz

                            # 1. Baca nilai PWM dari Servo 1, 2, dan 5
                            s1 = int(getattr(msg, 'servo1_raw', PWM_NEUTRAL))
                            s2 = int(getattr(msg, 'servo2_raw', PWM_NEUTRAL))
                            s5 = int(getattr(msg, 'servo5_raw', PWM_NEUTRAL))

                            real_data['servo1'] = s1
                            real_data['servo2'] = s2
                            real_data['servo5'] = s5

                            # 2. Hitung deviasi PWM terhadap titik netral (1500 us) + filter deadband
                            dev_s1 = apply_deadband(s1)
                            dev_s2 = apply_deadband(s2)
                            dev_s5 = apply_deadband(s5)

                            # 3. Logika Maju / Mundur (Surge) -> Servo 1 & 2
                            #    - Nilai > 1500 : Maju (+dev_surge)
                            #    - Nilai < 1500 : Mundur (-dev_surge)
                            #    - Nilai == 1500: Netral/Diam (0)
                            dev_surge = (dev_s1 + dev_s2) / 2.0
                            # Kecepatan linier maju/mundur (m/s)
                            v_surge = dev_surge * K_SURGE

                            # 4. Logika Kanan / Kiri (Sway / Strafe) -> Servo 5
                            #    - Nilai > 1500 : Geser Kanan (+dev_sway)
                            #    - Nilai < 1500 : Geser Kiri (-dev_sway)
                            #    - Nilai == 1500: Netral/Diam (0)
                            dev_sway = dev_s5
                            # Kecepatan linier geser kanan/kiri (m/s)
                            v_sway = dev_sway * K_SWAY

                            real_data['v_surge'] = v_surge
                            real_data['v_sway'] = v_sway

                            # 5. Transformasi Kecepatan Body-Frame ke World-Frame menggunakan Yaw Pixhawk
                            #    Orientasi Kompas: 0° = North (+Y), 90° = East (+X)
                            yaw_deg = real_data['yaw']
                            yaw_rad = math.radians(yaw_deg)

                            dx = (v_surge * math.sin(yaw_rad) +
                                  v_sway * math.cos(yaw_rad)) * dt
                            dy = (v_surge * math.cos(yaw_rad) -
                                  v_sway * math.sin(yaw_rad)) * dt

                            # 6. Akumulasi pergeseran posisi X dan Y (hanya jika sensor ultrasonic tidak aktif)
                            if not real_data.get('ultrasonic_connected'):
                                real_data['x'] += dx
                                real_data['y'] += dy

                            cur_x = real_data['x']
                            cur_y = real_data['y']
                            cur_z = real_data['z']

                        # 7. Tampilkan log pergerakan ke terminal setiap 0.5 detik (di luar lock)
                        if msg_type == 'SERVO_OUTPUT_RAW':
                            now_log = time.time()
                            if now_log - last_log_time >= 0.5:
                                last_log_time = now_log
                                surge_lbl = "MAJU" if dev_surge > 0 else (
                                    "MUNDUR" if dev_surge < 0 else "DIAM")
                                sway_lbl = "KANAN" if dev_sway > 0 else (
                                    "KIRI" if dev_sway < 0 else "DIAM")
                                print(
                                    f"[DEAD RECKONING] S1:{s1} S2:{s2} S5:{s5} | "
                                    f"Surge:{surge_lbl} ({v_surge:+.2f}m/s) Sway:{sway_lbl} ({v_sway:+.2f}m/s) | "
                                    f"Yaw:{yaw_deg:05.1f}° | POS: (X:{cur_x:+.2f}m, Y:{cur_y:+.2f}m, Z:{cur_z:.2f}m)"
                                )

                # Deteksi Timeout Komunikasi MAVLink
                if time.time() - last_msg_time > 5.0:
                    print("[MAVLINK] Koneksi MAVLink terputus (timeout > 5s)...")
                    with state_lock:
                        real_data['mavlink_connected'] = False
                    break

        except Exception as e:
            print(f"[MAVLINK] Terjadi kesalahan: {e}")
            with state_lock:
                real_data['mavlink_connected'] = False
            time.sleep(RECONNECT_DELAY_S)
        finally:
            if master is not None:
                try:
                    master.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Dummy Simulation Worker Thread (20 Hz)
# ---------------------------------------------------------------------------
def dummy_worker():
    """Menghasilkan pergerakan koordinat dummy berbentuk lintasan angka 8 untuk simulasi UI."""
    t0 = time.time()
    while True:
        t = time.time() - t0
        speed = 0.22
        scale_x = 3.0
        scale_y = 2.0

        x = scale_x * math.sin(t * speed)
        y = scale_y * math.sin(t * speed * 2.0)
        z = 1.0 + 0.3 * math.sin(t * speed * 0.5)

        dx = scale_x * speed * math.cos(t * speed)
        dy = scale_y * speed * 2.0 * math.cos(t * speed * 2.0)
        yaw_rad = math.atan2(dy, dx)
        yaw_deg = (math.degrees(yaw_rad) + 360.0) % 360.0

        with state_lock:
            dummy_data['x'] = x
            dummy_data['y'] = y
            dummy_data['z'] = z
            dummy_data['yaw'] = yaw_deg

        time.sleep(0.05)


# ---------------------------------------------------------------------------
# API Routes (Untuk Konsumsi Frontend GCS)
# ---------------------------------------------------------------------------
@app.route('/api/trajectory', methods=['GET'])
def get_telemetry():
    """Mengembalikan data koordinat relatif, data mentah, servo status, dan koneksi."""
    with state_lock:
        source = current_source
        if source == 'real':
            raw_x, raw_y, raw_z = real_data['x'], real_data['y'], real_data['z']
            yaw = real_data['yaw']
            connected = real_data['mavlink_connected']
            s1 = real_data['servo1']
            s2 = real_data['servo2']
            s5 = real_data['servo5']
            v_surge = real_data['v_surge']
            v_sway = real_data['v_sway']
        else:
            raw_x, raw_y, raw_z = dummy_data['x'], dummy_data['y'], dummy_data['z']
            yaw = dummy_data['yaw']
            connected = real_data['mavlink_connected']
            s1, s2, s5 = 1500, 1500, 1500
            v_surge, v_sway = 0.0, 0.0

        rel_x = raw_x - origin['x']
        rel_y = raw_y - origin['y']
        rel_z = raw_z - origin['z']

        return jsonify({
            'source': source,
            'x': round(rel_x, 3),
            'y': round(rel_y, 3),
            'z': round(rel_z, 3),
            'raw_x': round(raw_x, 3),
            'raw_y': round(raw_y, 3),
            'raw_z': round(raw_z, 3),
            'origin_x': round(origin['x'], 3),
            'origin_y': round(origin['y'], 3),
            'origin_z': round(origin['z'], 3),
            'yaw': round(yaw, 1),
            'mavlink_connected': connected,
            'ultrasonic_connected': real_data.get('ultrasonic_connected', False),
            'sensor_1': real_data.get('sensor_1'),
            'sensor_2': real_data.get('sensor_2'),
            'servo1': s1,
            'servo2': s2,
            'servo5': s5,
            'v_surge': round(v_surge, 3),
            'v_sway': round(v_sway, 3),
        })


@app.route('/api/origin/calibrate', methods=['POST'])
@app.route('/api/calibrate', methods=['POST'])
def calibrate_origin():
    """Mengatur posisi wahana saat ini sebagai titik origin (0, 0, 0)."""
    with state_lock:
        if current_source == 'real':
            origin['x'] = real_data['x']
            origin['y'] = real_data['y']
            origin['z'] = real_data['z']
        else:
            origin['x'] = dummy_data['x']
            origin['y'] = dummy_data['y']
            origin['z'] = dummy_data['z']

        return jsonify({
            'status': 'ok',
            'message': 'Titik origin berhasil diset ke posisi saat ini',
            'origin': {
                'x': round(origin['x'], 3),
                'y': round(origin['y'], 3),
                'z': round(origin['z'], 3),
            }
        })


@app.route('/api/origin/reset', methods=['POST'])
def reset_origin():
    """Mereset titik origin dan menghapus akumulasi perhitungan koordinat posisi."""
    with state_lock:
        origin['x'] = 0.0
        origin['y'] = 0.0
        origin['z'] = 0.0
        real_data['x'] = 0.0
        real_data['y'] = 0.0

        return jsonify({
            'status': 'ok',
            'message': 'Origin dan akumulasi koordinat di-reset ke default (0, 0, 0)',
            'origin': {'x': 0.0, 'y': 0.0, 'z': 0.0}
        })


@app.route('/api/source', methods=['POST'])
def set_source():
    """Mengganti mode sumber data antara 'real' (wahana asli) atau 'dummy' (simulasi)."""
    global current_source
    payload = request.get_json(silent=True) or {}
    requested = payload.get('source')

    if requested not in ('real', 'dummy'):
        return jsonify({'error': 'source harus bernilai "real" atau "dummy"'}), 400

    with state_lock:
        current_source = requested

    return jsonify({'status': 'ok', 'source': current_source})


# ---------------------------------------------------------------------------
# Entrypoint Aplikasi
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    mav_thread = threading.Thread(target=mavlink_worker, daemon=True)
    dummy_thread = threading.Thread(target=dummy_worker, daemon=True)
    ultrasonic_thread = threading.Thread(
        target=ultrasonic_client_worker, daemon=True)
    mav_thread.start()
    dummy_thread.start()
    ultrasonic_thread.start()

    print(
        f"[ROV TRAJECTORY] Server Backend aktif pada http://127.0.0.1:{HTTP_PORT}")
    app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, threaded=True)
