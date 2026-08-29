import asyncio
import json
import math
import time
from pymavlink import mavutil
import websockets

MAVLINK_UDP_PORT = 'udpin:0.0.0.0:14770'
TIMEOUT_THRESHOLD = 5.0  # Detik tanpa data sebelum dianggap MAVLink terputus

connected_clients = set()
pixhawk_link = None


async def handler(websocket, path=None):
    connected_clients.add(websocket)
    print(f'[WS CLIENT] Client terhubung dari: {websocket.remote_address}')
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f'[WS CLIENT] Client {websocket.remote_address} terputus.')


def create_mavlink_connection():
    """Mencoba mengikat socket UDP MAVLink."""
    try:
        link = mavutil.mavlink_connection(MAVLINK_UDP_PORT)
        print(
            f'[MAVLINK] Socket UDP terikat pada {MAVLINK_UDP_PORT}. Menunggu'
            ' stream...'
























        )
        return link
    except Exception as e:
        print(f'[ERROR] Gagal mengikat socket MAVLink UDP: {e}')
        return None


async def read_pixhawk_telemetry():
    global pixhawk_link

    last_print_time = 0
    last_heartbeat_send_time = 0
    last_stream_req_time = 0
    last_rx_time = time.monotonic()
    is_connected = False

    # Inisialisasi awal koneksi
    pixhawk_link = create_mavlink_connection()

    while True:
        current_time = time.monotonic()

        # -------------------------------------------------------------------
        # 1. PENANGANAN RECONNECTION & TIMEOUT (Jika data terhenti > 5 detik)
        # -------------------------------------------------------------------
        if pixhawk_link is None or (
            current_time - last_rx_time > TIMEOUT_THRESHOLD
        ):
            if is_connected or pixhawk_link is None:
                print(
                    f'[WARNING] MAVLink Timeout / Terputus (>{TIMEOUT_THRESHOLD}s tanpa'
                    ' data). Mencoba reconnect...'
                )
                is_connected = False

                # Tutup socket lama secara bersih
                if pixhawk_link:
                    try:
                        pixhawk_link.close()
                    except Exception:
                        pass
                    pixhawk_link = None

                # Informasikan seluruh client WebSocket bahwa MAVLink Offline
                if connected_clients:
                    status_payload = json.dumps(
                        {'type': 'status', 'mavlink_online': False}
                    )
                    await asyncio.gather(
                        *[c.send(status_payload) for c in connected_clients],
                        return_exceptions=True,
                    )

            # Percobaan Re-inisialisasi
            pixhawk_link = create_mavlink_connection()
            last_rx_time = current_time  # Reset timer untuk cooldown
            # Jeda 2 detik sebelum perulangan berikutnya
            await asyncio.sleep(2.0)
            continue

        # -------------------------------------------------------------------
        # 2. KIRIM HEARTBEAT BERKALA (Setiap 1 detik)
        # -------------------------------------------------------------------
        if current_time - last_heartbeat_send_time >= 1.0:
            try:
                pixhawk_link.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0,
                    0,
                    0,
                )
                last_heartbeat_send_time = current_time
            except Exception as e:
                print(f'[ERROR] Gagal mengirim heartbeat: {e}')

        # -------------------------------------------------------------------
        # 3. REQUEST DATA STREAM BERKALA (Setiap 5 detik)
        # -------------------------------------------------------------------
        if current_time - last_stream_req_time >= 5.0:
            try:
                tgt_sys = (
                    pixhawk_link.target_system if pixhawk_link.target_system else 1
                )
                tgt_comp = (
                    pixhawk_link.target_component if pixhawk_link.target_component else 1
                )

                pixhawk_link.mav.request_data_stream_send(
                    tgt_sys, tgt_comp, mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 20, 1
                )
                last_stream_req_time = current_time
            except Exception as e:
                print(f'[ERROR] Gagal request data stream: {e}')

        # -------------------------------------------------------------------
        # 4. MEMBACA & MENGOSONGKAN BUFFER DATA MAVLINK
        # -------------------------------------------------------------------
        try:
            while True:
                msg = pixhawk_link.recv_match(blocking=False)
                if not msg:
                    break  # Buffer kosong

                # Update timestamp paket data masuk
                last_rx_time = current_time

                # Jika sebelumnya offline dan sekarang data mulai masuk kembali
                if not is_connected:
                    is_connected = True
                    print('[SUCCESS] MAVLink terhubung kembali! Data stream aktif.')
                    if connected_clients:
                        status_payload = json.dumps(
                            {'type': 'status', 'mavlink_online': True}
                        )
                        await asyncio.gather(
                            *[c.send(status_payload)
                              for c in connected_clients],
                            return_exceptions=True,
                        )

                msg_type = msg.get_type()

                if msg_type == 'HEARTBEAT':
                    pixhawk_link.target_system = msg.get_srcSystem()
                    pixhawk_link.target_component = msg.get_srcComponent()

                elif msg_type == 'ATTITUDE':
                    roll_deg = math.degrees(msg.roll)
                    pitch_deg = math.degrees(msg.pitch)
                    yaw_deg = (math.degrees(msg.yaw) + 360) % 360

                    if current_time - last_print_time >= 0.5:
                        print(
                            f'[MAVLINK] Roll: {roll_deg:.2f}° | Pitch: {pitch_deg:.2f}° |'
                            f' Yaw: {yaw_deg:.2f}°'
                        )
                        last_print_time = current_time

                    if connected_clients:
                        telemetry_data = {
                            'type': 'telemetry',
                            'roll': round(roll_deg, 2),
                            'pitch': round(pitch_deg, 2),
                            'yaw': round(yaw_deg, 2),
                        }
                        payload = json.dumps(telemetry_data)
                        await asyncio.gather(
                            *[c.send(payload) for c in connected_clients],
                            return_exceptions=True,
                        )

        except Exception as e:
            print(f'[WARNING] Error pembacaan socket MAVLink: {e}')

        await asyncio.sleep(0.001)


async def main():
    async with websockets.serve(handler, '0.0.0.0', 8082):
        print('[SERVER ACTIVE] Telemetry Bridge ROV aktif di ws://0.0.0.0:8082')
        await read_pixhawk_telemetry()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n[STOP] Telemetry Bridge dimatikan.')
