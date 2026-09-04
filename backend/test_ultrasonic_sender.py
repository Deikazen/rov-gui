#!/usr/bin/env python3
"""
================================================================================
TEST ULTRASONIC SENDER (MOCK JETSON NANO STREAMER)
================================================================================
Deskripsi:
Simulator pengirim data sensor ultrasonic dari Jetson Nano ke rov_ultrasonic.py
melalui WebSocket (ws://localhost:8765).

Menguji:
1. Tahap 1: Pengujian nilai diskrit dari catatan tangan (20260902_143750.jpg):
   - S1 = 500 cm -> Y = 1.0 m, S2 = 500 cm -> X = 1.0 m
   - S1 = 400 cm -> Y = 2.0 m, S2 = 400 cm -> X = 2.0 m
   - S1 = 300 cm -> Y = 3.0 m, S2 = 300 cm -> X = 3.0 m
   - S1 = 200 cm -> Y = 4.0 m, S2 = 200 cm -> X = 4.0 m
   - S1 = 100 cm -> Y = 5.0 m, S2 = 100 cm -> X = 5.0 m
2. Tahap 2: Simulasi pergerakan halus (smooth trajectory) di dalam kolam 5x5 meter.
================================================================================
"""

import asyncio
import json
import math
import sys
import time
import websockets

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WS_URI = "ws://127.0.0.1:8765"


async def run_sender():
    print(f"[*] Menghubungkan ke server WebSocket di {WS_URI} ...")
    try:
        async with websockets.connect(WS_URI) as ws:
            print("[+] Berhasil terhubung ke rov_ultrasonic.py!")
            print("\n" + "=" * 70)
            print(" TAHAP 1: PENGUJIAN 5 TITIK DISKRIT SESUAI CATATAN GAMBAR")
            print("=" * 70)

            # S1 (Y) dan S2 (X) dalam milimeter (5000mm = 500cm, dst.)
            discrete_test_cases = [
                (5000, 5000, "Expect: X = 100cm, Y = 100cm"),
                (4000, 4000, "Expect: X = 200cm, Y = 200cm"),
                (3000, 3000, "Expect: X = 300cm, Y = 300cm"),
                (2000, 2000, "Expect: X = 400cm, Y = 400cm"),
                (1000, 1000, "Expect: X = 500cm, Y = 500cm"),
                (3000, 5000, "Expect: X = 100cm, Y = 300cm"),
                (1000, 2000, "Expect: X = 400cm, Y = 500cm"),
            ]

            for s1_mm, s2_mm, desc in discrete_test_cases:
                payload = {
                    "timestamp": time.time(),
                    "sensors": {
                        "sensor_1": {"distance_mm": s1_mm, "status": "VALID"},
                        "sensor_2": {"distance_mm": s2_mm, "status": "VALID"},
                    },
                }
                await ws.send(json.dumps(payload))
                print(f"[TEST DISKRIT] S1={s1_mm//10}cm, S2={s2_mm//10}cm -> {desc}")
                await asyncio.sleep(1.5)

            print("\n" + "=" * 70)
            print(" TAHAP 2: SIMULASI TRAJECTORY KONTINU (5x5 METER)")
            print(" Tekan Ctrl+C untuk menghentikan.")
            print("=" * 70)

            t = 0.0
            dt = 0.1  # 10 Hz
            while True:
                # Gerakan lingkaran di dalam kolam 5x5m (tengah di 2.5m, radius 1.8m)
                # x_rov = 2.5 + 1.8 * cos(t)  -> [0.7m .. 4.3m]
                # y_rov = 2.5 + 1.8 * sin(t)  -> [0.7m .. 4.3m]
                x_rov = 2.5 + 1.8 * math.cos(t * 0.5)
                y_rov = 2.5 + 1.8 * math.sin(t * 0.5)

                # Dari rumus catatan: Pos = 6.0 - (S_cm / 100)
                # Maka: S_cm = (6.0 - Pos) * 100
                s2_cm = max(100.0, min(500.0, (6.0 - x_rov) * 100.0))
                s1_cm = max(100.0, min(500.0, (6.0 - y_rov) * 100.0))

                s1_mm = int(s1_cm * 10)
                s2_mm = int(s2_cm * 10)

                payload = {
                    "timestamp": time.time(),
                    "sensors": {
                        "sensor_1": {"distance_mm": s1_mm, "status": "VALID"},
                        "sensor_2": {"distance_mm": s2_mm, "status": "VALID"},
                    },
                }
                await ws.send(json.dumps(payload))
                t += dt
                await asyncio.sleep(dt)

    except ConnectionRefusedError:
        print(f"[!] Gagal terhubung ke {WS_URI}. Pastikan rov_ultrasonic.py sudah berjalan!")
    except Exception as e:
        print(f"[!] Terjadi error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(run_sender())
    except KeyboardInterrupt:
        print("\n[!] Simulasi sender dihentikan.")
