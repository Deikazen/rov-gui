import time
import math
from pymavlink import mavutil

def run_fake_trajectory_sender():
    # Kirim data UDP MAVLink ke localhost:14553 (sesuai endpoint di rov-trajectory.py)
    target_address = 'udpout:127.0.0.1:14553'
    print(f"[MAVLINK MOCK TRAJECTORY] Menghubungkan dan mengirim paket MAVLink ke {target_address}...")
    
    try:
        master = mavutil.mavlink_connection(target_address)
    except Exception as e:
        print(f"[ERROR] Gagal membuat koneksi sender: {e}")
        return

    t = 0.0
    hz = 20  # 20 Hz (interval 50ms)
    interval = 1.0 / hz
    speed = 0.25  # kecepatan siklus lintasan (rad/s)
    scale_x = 3.5 # rentang pergerakan sumbu X dalam meter (-3.5m s/d +3.5m)
    scale_y = 2.0 # rentang pergerakan sumbu Y dalam meter (-2.0m s/d +2.0m)

    print("\n" + "="*60)
    print(" [MAVLINK MOCK TRAJECTORY SENDER AKTIF]")
    print(" Target Port : localhost:14553 (rov-trajectory.py)")
    print(" Update Rate : 20 Hz (50 ms)")
    print(" Pesan MAV   : HEARTBEAT, ATTITUDE, SERVO_OUTPUT_RAW, GLOBAL_POSITION_INT")
    print(" Tekan Ctrl+C untuk menghentikan simulasi.")
    print("="*60 + "\n")

    last_print_time = 0

    try:
        while True:
            # 1. Hitung Posisi & Kecepatan Simulasi
            x = scale_x * math.sin(t * speed)
            y = scale_y * math.sin(t * speed * 2.0)
            z = 1.2 + 0.4 * math.sin(t * speed * 0.5)  # Kedalaman (depth)

            vx = scale_x * speed * math.cos(t * speed)
            vy = scale_y * speed * 2.0 * math.cos(t * speed * 2.0)

            # 2. Hitung Sudut Heading & Attitude
            heading_rad = math.atan2(vy, vx)
            yaw_rad = (heading_rad + 2 * math.pi) % (2 * math.pi)
            roll_rad = math.sin(t * 1.2) * math.radians(4)
            pitch_rad = math.cos(t * 0.8) * math.radians(3)

            # 3. Simulasi PWM Servo 1, 2 (Maju/Mundur), dan 5 (Kanan/Kiri)
            # v_surge simulasi (maju ~ PWM 1750, mundur ~ PWM 1250)
            v_linear = math.hypot(vx, vy)
            # Servo 1 & 2: Maju ketika nilai PWM > 1500
            pwm_surge = int(1500 + 250 * math.sin(t * speed))
            # Servo 5: Kanan (>1500) / Kiri (<1500)
            pwm_sway = int(1500 + 200 * math.cos(t * speed * 1.5))

            boot_time_ms = int(time.time() * 1000) & 0xFFFFFFFF
            time_usec = int(time.time() * 1e6) & 0xFFFFFFFFFFFFFFFF

            # 4. Kirim Pesan HEARTBEAT (Submarine ArduSub)
            master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_SUBMARINE,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )

            # 5. Kirim Pesan ATTITUDE (Roll, Pitch, Yaw)
            master.mav.attitude_send(
                boot_time_ms,
                roll_rad,
                pitch_rad,
                yaw_rad,
                0.0, 0.0, 0.0
            )

            # 6. Kirim Pesan SERVO_OUTPUT_RAW (Servo 1, 2 untuk maju/mundur, Servo 5 untuk kanan/kiri)
            master.mav.servo_output_raw_send(
                time_usec,
                0,             # port
                pwm_surge,     # servo1_raw (Maju/Mundur)
                pwm_surge,     # servo2_raw (Maju/Mundur)
                1500,          # servo3_raw
                1500,          # servo4_raw
                pwm_sway,      # servo5_raw (Kanan/Kiri)
                1500,          # servo6_raw
                1500,          # servo7_raw
                1500           # servo8_raw
            )

            # 7. Kirim Pesan GLOBAL_POSITION_INT (Kedalaman / relative_alt)
            master.mav.global_position_int_send(
                boot_time_ms,
                0, 0, 0,
                int(-z * 1000), # relative_alt dalam mm negatif
                int(vx * 100),
                int(vy * 100),
                0,
                int(math.degrees(yaw_rad) * 100)
            )

            # Log ke terminal setiap 0.5 detik
            if time.time() - last_print_time >= 0.5:
                yaw_deg = math.degrees(yaw_rad)
                print(f"[MAVLINK OUT -> 14553] S1/S2 (Surge): {pwm_surge}us | S5 (Sway): {pwm_sway}us | HDG: {yaw_deg:05.1f}° | Z: {z:.2f}m")
                last_print_time = time.time()

            t += interval
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[MAVLINK MOCK TRAJECTORY] Dummy sender dihentikan.")

if __name__ == '__main__':
    run_fake_trajectory_sender()

