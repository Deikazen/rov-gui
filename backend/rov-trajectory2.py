"""
================================================================================
ROV 3D TRAJECTORY & TELEMETRY BACKEND (DEAD RECKONING MODEL)
================================================================================

DESKRIPSI SISTEM:
Sistem ini berfungsi sebagai backend perantara (middleware) yang menerima 
telemetri MAVLink dari Pixhawk (melalui BlueOS di Onboard Computer) dan 
menyediakannya ke Ground Control Station (GCS) melalui REST API.

METODOLOGI ESTIMASI POSISI (X, Y, Z, YAW):
Karena wahana beroperasi di bawah air tanpa sensor posisi absolut eksternal 
(GPS tidak dapat menembus air dan belum menggunakan akustik DVL/USBL), sistem 
menggunakan pendekatan hybrid sensor & dead reckoning:

1. Orientasi / Yaw (Heading):
   - Diperoleh langsung dari internal IMU (Kompas + Giroskop) Pixhawk melalui 
     pesan MAVLink 'ATTITUDE'. Nilai dikonversi ke derajat (0 - 360 deg).

2. Sumbu Z (Kedalaman / Depth):
   - Diperoleh dari sensor tekanan hidrostatis eksternal (Bar30 / MS5837 via I2C) 
     yang diolah EKF ArduSub melalui pesan 'GLOBAL_POSITION_INT' (field relative_alt).

3. Sumbu Horizontal X & Y (Dead Reckoning berbasis Model Propulsi):
   - Membaca deviasi sinyal kendali PWM thruster dari pesan 'SERVO_OUTPUT_RAW'.
   - Nilai PWM (1100-1900 us) dikurangi titik netral (1500 us) dengan deadband filter.
   - Deviasi dikalikan konstanta empiris (K_SURGE & K_SWAY) untuk menghasilkan 
     estimasi kecepatan linier pada koordinat wahana (Body-Frame Velocity).
   - Kecepatan lokal ditransformasi ke koordinat global kolam (World-Frame) 
     menggunakan sudut Yaw:
         dx = (v_surge * cos(yaw) - v_sway * sin(yaw)) * dt
         dy = (v_surge * sin(yaw) + v_sway * cos(yaw)) * dt
   - Posisi diupdate secara berkala: X = X + dx, Y = Y + dy.

CATATAN PENGUJIAN & TUNING:
- Sistem ini dirancang untuk area terbatas kolam uji (10 x 10 meter) air tenang.
- Lakukan kalibrasi empiris konstanta K_SURGE dan K_SWAY jika pergeseran terlalu 
  cepat/lambat dibanding gerakan fisik ROV.
- Gunakan endpoint /api/origin/reset secara berkala untuk mereset akumulasi drift.

ARSITEKTUR DATA:
[Pixhawk FC] --(UART/USB)--> [Jetson (BlueOS)] --(UDP 14553)--> [Script Ini] 
                                                                    |
                                                            (HTTP REST :8007)
                                                                    v
                                                               [GCS / UI]
================================================================================
"""

import time
import math
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymavlink import mavutil

# ---------------------------------------------------------------------------
# Konfigurasi Endpoint MAVLink & Server
# ---------------------------------------------------------------------------
MAVLINK_UDP_ENDPOINT = 'udpin:0.0.0.0:14553'
HEARTBEAT_TIMEOUT_S = 10.0
RECONNECT_DELAY_S = 3.0
HTTP_PORT = 8007

# ---------------------------------------------------------------------------
# Parameter Kalibrasi Dead Reckoning (Kolam 10x10 m)
# ---------------------------------------------------------------------------
# Konstanta kecepatan (meter/detik per satuan deviasi PWM dari 1500)
# Nilai ini dapat disesuaikan berdasarkan kalibrasi pengujian di kolam:
K_SURGE = 0.0001   # Skala kecepatan maju/mundur (Surge)
K_SWAY = 0.0001   # Skala kecepatan geser samping (Sway/Strafe)

PWM_NEUTRAL = 1500
PWM_DEADBAND = 25  # Rentang toleransi (1475 - 1525 us) dianggap motor diam

app = Flask(__name__)
CORS(app)

state_lock = threading.Lock()

# Sumber data aktif ('real' untuk wahana fisik, 'dummy' untuk simulasi UI)
current_source = 'real'

# State data posisi & telemetri aktual
real_data = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
    'yaw': 0.0,
    'mavlink_connected': False,
}

# Data tiruan untuk pengetesan tampilan GCS tanpa robot fisik
dummy_data = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
    'yaw': 0.0,
}

# Titik offset koordinat (Origin)
origin = {
    'x': 0.0,
    'y': 0.0,
    'z': 0.0,
}


# ---------------------------------------------------------------------------
# MAVLink Background Worker Thread
# ---------------------------------------------------------------------------
def mavlink_worker():
    """Menerima dan memproses data telemetri dari Pixhawk via UDP bridge BlueOS."""
    while True:
        master = None
        try:
            print(
                f"[MAVLINK] Mendengarkan paket UDP di {MAVLINK_UDP_ENDPOINT} ...")
            master = mavutil.mavlink_connection(MAVLINK_UDP_ENDPOINT)

            # 1. Menunggu Heartbeat valid dari Autopilot (Component ID == 1)
            target_sys = 1
            target_comp = 1
            t_start = time.time()

            while True:
                hb = master.recv_match(
                    type='HEARTBEAT', blocking=True, timeout=1.0)
                print('HEARBEAT diterima')
                if hb is not None:
                    src_sys = hb.get_srcSystem()
                    src_comp = hb.get_srcComponent()

                    if src_comp == 1 and src_sys != 0:
                        target_sys = src_sys
                        target_comp = src_comp
                        master.target_system = target_sys
                        master.target_component = target_comp
                        print(
                            f"[MAVLINK] Autopilot terdeteksi -> Sys ID: {target_sys}, Comp ID: {target_comp}")
                        break

                if time.time() - t_start > HEARTBEAT_TIMEOUT_S:
                    raise Exception(
                        "Timeout menunggu heartbeat valid dari Pixhawk")

            with state_lock:
                real_data['mavlink_connected'] = True

            # 2. Request Data Stream (10 Hz) dari Pixhawk
            master.mav.request_data_stream_send(
                target_sys, target_comp,
                mavutil.mavlink.MAV_DATA_STREAM_POSITION, 10, 1
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

            # 3. Looping Utama Pemrosesan Paket
            while True:
                msg = master.recv_match(blocking=True, timeout=1.0)

                if msg:
                    last_msg_time = time.time()
                    msg_type = msg.get_type()

                    with state_lock:
                        real_data['mavlink_connected'] = True

                        # --- A. PARSING ATTITUDE (HEADING / YAW) ---
                        if msg_type == 'ATTITUDE':
                            yaw_deg = (math.degrees(msg.yaw) + 360.0) % 360.0
                            real_data['yaw'] = yaw_deg

                        # --- B. PARSING KEDALAMAN (DEPTH / SUMBU Z) ---
                        elif msg_type == 'GLOBAL_POSITION_INT':
                            if hasattr(msg, 'relative_alt'):
                                # relative_alt dalam milimeter negatif -> meter positif
                                real_data['z'] = max(
                                    0.0, -float(msg.relative_alt) / 1000.0)

                        # --- C. ESTIMASI POSISI X & Y (DEAD RECKONING) ---
                        elif msg_type == 'SERVO_OUTPUT_RAW':
                            now = time.time()
                            dt = now - last_servo_time
                            last_servo_time = now

                            # Proteksi lonjakan dt jika thread sempat terhenti
                            if dt > 1.0:
                                dt = 0.1

                            # Baca kanal PWM output motor
                            s1 = getattr(msg, 'servo1_raw', 0)
                            s2 = getattr(msg, 'servo2_raw', 0)
                            s3 = getattr(msg, 'servo3_raw', 0)
                            s4 = getattr(msg, 'servo4_raw', 0)
                            print(f'servo 1={s1}')
                            print(f'servo 2={s2}')
                            print(f'servo 3={s3}')
                            print(f'servo 4={s4}')

                            if s1 > 1500:
                                print('Maju')
                            elif s1 < 1500:
                                print('mundur')

                # Deteksi Timeout Komunikasi
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
    """Menghasilkan pergerakan koordinat dummy berbentuk lintasan angka 8."""
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
    """Mengembalikan data koordinat relatif, data mentah, dan status koneksi."""
    with state_lock:
        source = current_source
        if source == 'real':
            raw_x, raw_y, raw_z = real_data['x'], real_data['y'], real_data['z']
            yaw = real_data['yaw']
            connected = real_data['mavlink_connected']
        else:
            raw_x, raw_y, raw_z = dummy_data['x'], dummy_data['y'], dummy_data['z']
            yaw = dummy_data['yaw']
            connected = real_data['mavlink_connected']

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
    mav_thread.start()
    dummy_thread.start()

    print(
        f"[ROV TRAJECTORY] Server Backend aktif pada http://127.0.0.1:{HTTP_PORT}")
    app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, threaded=True)
