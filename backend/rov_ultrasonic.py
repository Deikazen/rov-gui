#!/usr/bin/env python3
"""
WebSocket Server Receiver (Jalankan di Laptop)
==============================================
Menerima payload JSON streaming dari Jetson Nano secara real-time.
"""

import asyncio
import json
import websockets

HOST = "0.0.0.0"  # Mendengarkan koneksi dari semua interface jaringan
PORT = 8765


def format_sensor(sensor_dict):
    dist = sensor_dict.get("distance_mm")
    status = sensor_dict.get("status", "N/A")
    if dist is None:
        return f"--- [{status}]"
    return f"{dist} mm ({dist/10:.1f} cm) [{status}]"


async def handler(websocket):
    client_ip = websocket.remote_address[0]
    print(f"\n[+] Jetson Nano terhubung dari: {client_ip}\n")
    print(f"{'Timestamp':<12} | {'Sensor 1':<30} | {'Sensor 2':<30}")
    print("-" * 78)

    try:
        async for message in websocket:
            data = json.loads(message)
            ts = data.get("timestamp", 0)
            sensors = data.get("sensors", {})

            s1_info = format_sensor(sensors.get("sensor_1", {}))
            s2_info = format_sensor(sensors.get("sensor_2", {}))

            # Cetak baris per baris secara real-time
            print(f"\r{ts:<12.3f} | {s1_info:<30} | {s2_info:<30}",
                  end="", flush=True)

    except websockets.exceptions.ConnectionClosed:
        print(f"\n[-] Koneksi dari {client_ip} terputus.")
    except Exception as e:
        print(f"\n[!] Error: {e}")


async def main():
    async with websockets.serve(handler, HOST, PORT):
        print(
            f"🚀 Server aktif di port {PORT}. Menunggu data dari Jetson Nano...")
        await asyncio.Future()  # Menjaga server tetap berjalan


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
