"""Menerima tekanan tangki ballast dari BATTERY_STATUS Battery 2 melalui MAVLink UDP.

BlueOS harus mengirim MAVLink ke alamat/port lokal ini, misalnya:
    UDP Client -> <IP komputer ini>:14554

Jalankan:
    python mavlink_pressure_listener.py
atau:
    python mavlink_pressure_listener.py --endpoint udpin:0.0.0.0:14554
"""

import argparse
import time

from pymavlink import mavutil

DEFAULT_ENDPOINT = "udpin:0.0.0.0:14554"
BATTERY_2_ID = 1
INVALID_VOLTAGE = 0xFFFF


def pressure_from_message(message):
    """Kembalikan tekanan BAR dari frame Battery 2, atau None jika tidak valid."""
    if message.get_type() != "BATTERY_STATUS" or message.id != BATTERY_2_ID:
        return None

    voltages = message.voltages
    if not voltages or len(voltages) == 0:
        return None

    raw_value = voltages[0]
    
    # MAVLink menggunakan UINT16_MAX (65535) untuk nilai yang tidak diketahui.
    if raw_value in (None, INVALID_VOLTAGE):
        return None

    # 1. Dapatkan pembacaan dasar dari konversi MAVLink (milivolt ke nilai dasar)
    calculated_value = float(raw_value) / 1000.0
    
    # 2. Kalibrasi Hardware Offset untuk memaksa udara bebas menjadi 0 BAR.
    # Dikompensasi langsung dari sisa kelebihan 1.104 BAR dan dikali 10.0 untuk skala BAR penuh.
    pressure_bar = (calculated_value - 1.104) * 10.0
    
    # Batasi agar noise fluktuasi negatif tipis di udara bebas tetap terbaca 0.0
    if pressure_bar < 0:
        pressure_bar = 0.0
        
    return pressure_bar


def listen(endpoint):
    """Dengarkan stream MAVLink selamanya dan cetak tekanan tangki ballast Battery 2."""
    while True:
        connection = None
        try:
            print(f"Mendengarkan MAVLink di {endpoint} ...")
            connection = mavutil.mavlink_connection(endpoint)

            while True:
                message = connection.recv_match(type="BATTERY_STATUS", blocking=True)
                if message is None:
                    continue

                pressure_bar = pressure_from_message(message)
                if pressure_bar is not None:
                    print(f"Tekanan Tangki Ballast (Battery 2, id=1): {pressure_bar:.3f} BAR")
        except KeyboardInterrupt:
            print("\nListener dihentikan.")
            return
        except Exception as error:
            print(f"Error MAVLink: {error}. Mencoba menyambung ulang dalam 2 detik...")
            time.sleep(2)
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass


def main():
    parser = argparse.ArgumentParser(
        description="Tampilkan tekanan tangki ballast (BAR) dari BATTERY_STATUS id=1."
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Endpoint pymavlink untuk UDP input (default: {DEFAULT_ENDPOINT})",
    )
    arguments = parser.parse_args()
    listen(arguments.endpoint)


if __name__ == "__main__":
    main()