"""Simulator input untuk tiga backend asli ROV.

Alur yang dipakai:
    simulate_rov_data.py -> rov-depth.py / rov-trajectory2.py / rov_ultrasonic.py
                         -> data.py -> logs/data.csv

Simulator mengirim MAVLink UDP ke port 14552 (depth) dan 14553 (trajectory),
serta WebSocket ke port 8765 (ultrasonik). Ia tidak mengirim ke data.py.
"""

import argparse
import asyncio
import json
import math
import random
import threading
import time

import websockets
from pymavlink import mavutil


PWM_NEUTRAL = 1500
state_lock = threading.Lock()
state = {'x_cm': 300.0, 'y_cm': 160.0, 'depth_m': .7, 'yaw_rad': 0.0,
         'servo1': 1500, 'servo2': 1500, 'servo3': 1500, 'servo4': 1500, 'servo5': 1500}


def clamp(value, low, high):
    return max(low, min(high, value))


def pwm(command):
    return int(clamp(PWM_NEUTRAL + command + random.gauss(0, 3), 1100, 1900))


def update_state(elapsed, dt):
    """Gerak misi dan noise kecil, menyerupai perubahan data ROV nyata."""
    phase = elapsed % 48.0
    surge = sway = heave = yaw_command = 0.0
    if phase < 12:
        surge = 210.0
    elif phase < 20:
        surge, yaw_command = 150.0, 130.0
    elif phase < 30:
        sway, heave = 160.0 * math.sin((phase - 20) * .7), 75.0
    elif phase < 39:
        surge, heave = -170.0, -90.0
    else:
        yaw_command = 35.0 * math.sin(phase * 1.3)

    s1, s2 = pwm(surge + yaw_command * .1), pwm(surge - yaw_command * .1)
    s3, s4, s5 = pwm(heave), pwm(yaw_command), pwm(sway)
    with state_lock:
        state['x_cm'] = clamp(state['x_cm'] + (s5 - PWM_NEUTRAL) * .010 * dt, 70, 530)
        state['y_cm'] = clamp(state['y_cm'] + ((s1 + s2) / 2 - PWM_NEUTRAL) * .012 * dt, 70, 530)
        state['depth_m'] = clamp(state['depth_m'] + (s3 - PWM_NEUTRAL) * .0008 * dt, .15, 5.5)
        state['yaw_rad'] = (state['yaw_rad'] + (s4 - PWM_NEUTRAL) * .0009 * dt) % (2 * math.pi)
        state.update({'servo1': s1, 'servo2': s2, 'servo3': s3, 'servo4': s4, 'servo5': s5})


def snapshot():
    with state_lock:
        return dict(state)


def send_mavlink(rate):
    """Kirim data seperti Pixhawk: depth ke 14552, trajectory/PWM ke 14553."""
    depth_link = mavutil.mavlink_connection('udpout:127.0.0.1:14552')
    trajectory_link = mavutil.mavlink_connection('udpout:127.0.0.1:14553')
    interval = 1.0 / rate
    started = previous = time.monotonic()
    while True:
        now = time.monotonic()
        update_state(now - started, max(.001, now - previous))
        previous = now
        data = snapshot()
        boot_ms = int(time.time() * 1000) & 0xFFFFFFFF
        time_us = int(time.time() * 1e6) & 0xFFFFFFFFFFFFFFFF

        for link in (depth_link, trajectory_link):
            link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_SUBMARINE,
                                    mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA, 0, 0, 0)

        # Bar30: tekanan permukaan + kenaikan 98.0665 hPa untuk setiap meter.
        pressure_hpa = 1013.25 + data['depth_m'] * 98.0665 + random.gauss(0, .35)
        depth_link.mav.scaled_pressure_send(boot_ms, pressure_hpa, 0.0, 2500, 0)

        trajectory_link.mav.attitude_send(boot_ms, 0.0, 0.0, data['yaw_rad'], 0.0, 0.0, 0.0)
        trajectory_link.mav.servo_output_raw_send(
            time_us, 0, data['servo1'], data['servo2'], data['servo3'], data['servo4'],
            data['servo5'], 1500, 1500, 1500)
        trajectory_link.mav.global_position_int_send(
            boot_ms, 0, 0, 0, int(-data['depth_m'] * 1000), 0, 0, 0,
            int(math.degrees(data['yaw_rad']) * 100))
        time.sleep(max(0, interval - (time.monotonic() - now)))


async def send_ultrasonic(rate):
    """Kirim format Jetson Nano ke server WebSocket rov_ultrasonic.py."""
    interval = 1.0 / rate
    while True:
        try:
            async with websockets.connect('ws://127.0.0.1:8765') as ws:
                print('[SIM] Terhubung ke rov_ultrasonic.py (port 8765).')
                while True:
                    data = snapshot()
                    # Invers rumus rov_ultrasonic.py: posisi = 600 - jarak_cm.
                    s1_cm = clamp(600.0 - data['y_cm'] + random.gauss(0, 1.2), 1, 599)
                    s2_cm = clamp(600.0 - data['x_cm'] + random.gauss(0, 1.2), 1, 599)
                    await ws.send(json.dumps({'timestamp': time.time(), 'sensors': {
                        'sensor_1': {'distance_mm': round(s1_cm * 10, 1), 'status': 'VALID'},
                        'sensor_2': {'distance_mm': round(s2_cm * 10, 1), 'status': 'VALID'},
                    }}))
                    await asyncio.sleep(interval)
        except (OSError, websockets.exceptions.WebSocketException):
            print('[SIM] Menunggu rov_ultrasonic.py di port 8765...')
            await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description='Kirim telemetri simulasi ke tiga backend ROV')
    parser.add_argument('--rate', type=float, default=10.0, help='laju data (Hz)')
    args = parser.parse_args()
    if args.rate <= 0:
        parser.error('--rate harus lebih dari 0')
    threading.Thread(target=send_mavlink, args=(args.rate,), daemon=True, name='mavlink-sim').start()
    print('[SIM] Mengirim MAVLink ke rov-depth.py:14552 dan rov-trajectory2.py:14553.')
    print('[SIM] Jalankan ketiga backend asli, lalu data.py, di terminal terpisah.')
    try:
        asyncio.run(send_ultrasonic(args.rate))
    except KeyboardInterrupt:
        print('\n[SIM] Simulasi dihentikan.')


if __name__ == '__main__':
    main()
