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
    print(" Pesan MAV   : HEARTBEAT, LOCAL_POSITION_NED, ATTITUDE")
    print(" Tekan Ctrl+C untuk menghentikan simulasi.")
    print("="*60 + "\n")

    last_print_time = 0

    try:
        while True:
            # 1. Hitung Posisi Simulasi (Pola angka 8 / Lemniscate di kolam)
            x = scale_x * math.sin(t * speed)
            y = scale_y * math.sin(t * speed * 2.0)
            z = 1.2 + 0.4 * math.sin(t * speed * 0.5)  # Kedalaman (depth) 0.8m s/d 1.6m

            # 2. Hitung Kecepatan (Derivatif dx/dt dan dy/dt)
            vx = scale_x * speed * math.cos(t * speed)
            vy = scale_y * speed * 2.0 * math.cos(t * speed * 2.0)
            vz = 0.4 * speed * 0.5 * math.cos(t * speed * 0.5)

            # 3. Hitung Sudut Sikap Kapal (Attitude: Roll, Pitch, Yaw)
            heading_rad = math.atan2(vy, vx)
            yaw_rad = (heading_rad + 2 * math.pi) % (2 * math.pi)
            roll_rad = math.sin(t * 1.2) * math.radians(4)   # Roll halus saat belok
            pitch_rad = math.cos(t * 0.8) * math.radians(3)  # Pitch halus saat naik-turun

            boot_time_ms = int(time.time() * 1000) & 0xFFFFFFFF

            # 4. Kirim Pesan HEARTBEAT (Identitas Submarine ArduSub)
            master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_SUBMARINE,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )

            # 5. Kirim Pesan LOCAL_POSITION_NED (Posisi & Kecepatan dalam koordinat lokal meter)
            # Parameter: time_boot_ms, x (m, North), y (m, East), z (m, Down), vx (m/s), vy (m/s), vz (m/s)
            master.mav.local_position_ned_send(
                boot_time_ms,
                x,
                y,
                z,
                vx,
                vy,
                vz
            )

            # 6. Kirim Pesan ATTITUDE (Roll, Pitch, Yaw dalam Radian)
            master.mav.attitude_send(
                boot_time_ms,
                roll_rad,
                pitch_rad,
                yaw_rad,
                0.0, 0.0, 0.0  # rollspeed, pitchspeed, yawspeed
            )

            # Log ke terminal setiap 0.5 detik
            if time.time() - last_print_time >= 0.5:
                yaw_deg = math.degrees(yaw_rad)
                print(f"[MAVLINK OUT -> 14553] POS: (X: {x:+.2f}m, Y: {y:+.2f}m, Z: {z:.2f}m) | HDG: {yaw_deg:05.1f}° | VEL: ({vx:+.2f}, {vy:+.2f}) m/s")
                last_print_time = time.time()

            t += interval
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[MAVLINK MOCK TRAJECTORY] Dummy sender dihentikan.")

if __name__ == '__main__':
    run_fake_trajectory_sender()
