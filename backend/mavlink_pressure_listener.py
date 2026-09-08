#!/usr/bin/env python3
"""Menerima tekanan dari BATTERY_STATUS Battery 2 melalui MAVLink UDP.

BlueOS harus mengirim MAVLink ke alamat/port lokal ini, misalnya:
    UDP Client -> <IP komputer ini>:14550

Jalankan:
    python mavlink_pressure_listener.py
atau:
    python mavlink_pressure_listener.py --endpoint udpin:0.0.0.0:14552

Catatan: field ``voltages`` dalam BATTERY_STATUS secara formal bertipe uint16
(umumnya millivolt). Skrip ini sengaja mencetak ``voltages[0]`` langsung sebagai
BAR, sesuai konfigurasi ArduSub/BlueOS pada sistem ini yang telah mengalibrasi
nilai Battery 2 menjadi tekanan BAR sebelum dikirim.
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
    if not voltages:
        return None

    pressure_bar = voltages[0]
    # MAVLink menggunakan UINT16_MAX untuk sebuah voltage yang tidak diketahui.
    if pressure_bar in (None, INVALID_VOLTAGE):
        return None

    return float(pressure_bar)


def listen(endpoint):
    """Dengarkan stream MAVLink selamanya dan cetak tekanan Battery 2."""
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
                    print(f"Tekanan (Battery 2, id=1): {pressure_bar:.3f} BAR")
        except KeyboardInterrupt:
            print("\nListener dihentikan.")
            return
        except Exception as error:
            # Jangan biarkan satu frame/koneksi rusak menghentikan pembacaan stream.
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
        description="Tampilkan tekanan BAR dari BATTERY_STATUS id=1 (Battery 2)."
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
