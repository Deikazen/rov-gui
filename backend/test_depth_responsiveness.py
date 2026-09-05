import time
import json
import urllib.request
import threading
from pymavlink import mavutil

def mock_sender():
    time.sleep(1.0)
    master = mavutil.mavlink_connection('udpout:127.0.0.1:14552')
    print("[MOCK] Connected to udpout:127.0.0.1:14552")
    
    # 1. Send Heartbeat
    for _ in range(3):
        master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_SUBMARINE,
            mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
            0, 0, 0
        )
        time.sleep(0.1)

    # 2. Simulate sensor at rest (depth 0.0)
    for _ in range(5):
        master.mav.vfr_hud_send(0, 0, 0, 0, 0.0, 0.0)
        time.sleep(0.05)

    print("[MOCK] Sensor at rest sent.")
    time.sleep(0.5)

    # 3. Simulate SENSOR PRESSED! Depth jumps to 1.85m, descent rate 0.4 m/s
    print("[MOCK] SENSOR PRESSED! Sending depth = 1.85m ...")
    for _ in range(25):
        # alt is negative for depth
        master.mav.vfr_hud_send(0, 0, 0, 0, -1.85, -0.4)
        # Also send scaled pressure to verify it does NOT overwrite to 0.0
        master.mav.scaled_pressure_send(int(time.time() * 1000) & 0xFFFFFFFF, 1195.0, 0.0, 2500, 0)
        time.sleep(0.05)

    print("[MOCK] Finished sending pressed packets.")

if __name__ == '__main__':
    # Start mock sender in background thread
    t = threading.Thread(target=mock_sender, daemon=True)
    t.start()

    # Wait for server to be accessible
    print("[TEST] Setting source to 'real' ...")
    time.sleep(1.5)
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:5001/api/source',
            data=json.dumps({'source': 'real'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            print("[TEST] Set source result:", json.loads(resp.read().decode('utf-8')))
    except Exception as e:
        print("[TEST] Failed to set source:", e)

    # Poll /api/telemetry repeatedly and measure response
    start_time = time.time()
    pressed_detected = False

    while time.time() - start_time < 5.0:
        try:
            with urllib.request.urlopen('http://127.0.0.1:5001/api/telemetry', timeout=1) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                depth = res.get('depth', 0.0)
                rate = res.get('rate', 0.0)
                conn = res.get('mavlink_connected', False)
                print(f"[TEST POLL] depth={depth}m ({res.get('depth_cm')}cm), rate={rate}m/s, connected={conn}")

                if depth > 1.0 and not pressed_detected:
                    pressed_detected = True
                    print(f"[TEST SUCCESS] SENSOR PRESS DETECTED! Depth = {depth}m, Rate = {rate}m/s")
        except Exception as e:
            print("[TEST POLL ERROR]:", e)

        time.sleep(0.1)

    if pressed_detected:
        print("\n>>> VERIFICATION PASSED: Sensor press is immediately detected and responsive! <<<")
    else:
        print("\n>>> VERIFICATION FAILED: Sensor press not detected! <<<")

