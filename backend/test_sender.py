import time
import math
from pymavlink import mavutil

def run_fake_mavlink_sender():
    # Kirim data UDP MAVLink ke localhost:14770 (sesuai port di model_3d.py)
    target_address = 'udpout:127.0.0.1:14770'
    print(f"[MAVLINK MOCK] Mengirim sinyal MAVLink tiruan ke {target_address}...")
    
    try:
        master = mavutil.mavlink_connection(target_address)
    except Exception as e:
        print(f"[ERROR] Gagal membuat koneksi sender: {e}")
        return

    t = 0.0
    hz = 20  # 20 Hz (50ms interval)
    interval = 1.0 / hz

    print("[MAVLINK MOCK] Dummy Pixhawk aktif! Tekan Ctrl+C untuk menghentikan.")

    try:
        while True:
            # Simulasi gerakan rotasi tiruan (Roll: -30°..30°, Pitch: -20°..20°, Yaw: 0°..360°)
            roll_rad = math.sin(t * 1.5) * math.radians(25)
            pitch_rad = math.cos(t * 1.0) * math.radians(15)
            yaw_rad = (t * 0.3) % (2 * math.pi)

            boot_time_ms = int(time.time() * 1000) & 0xFFFFFFFF

            # 1. Kirim Heartbeat (seakan-akan dari ROV Submarine ArduSub)
            master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_SUBMARINE,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )

            # 2. Kirim Pesan ATTITUDE (Roll, Pitch, Yaw dalam Radian)
            master.mav.attitude_send(
                boot_time_ms,
                roll_rad,
                pitch_rad,
                yaw_rad,
                0.0, 0.0, 0.0  # rollspeed, pitchspeed, yawspeed
            )

            t += interval
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n[MAVLINK MOCK] Dummy sender dihentikan.")

if __name__ == '__main__':
    run_fake_mavlink_sender()
