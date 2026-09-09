"""Jalankan seluruh backend ROV dalam satu perintah.

Tekan Ctrl+C untuk menghentikan rov-trajectory, rov-depth, dan
rov_ultrasonic sekaligus.
"""

from __future__ import annotations

import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
SERVICES = (
    ("trajectory", "rov-trajectory.py"),
    ("depth", "rov-depth.py"),
    ("ultrasonic", "rov_ultrasonic.py"),
    ("water pressure", "mavlink_pressure_listener.py"),
    ("model 3D", "model_3d.py" )
)


def port_is_ready(port: int) -> bool:
    """Return True setelah server HTTP trajectory menerima koneksi TCP."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def stop_all(processes: list[tuple[str, subprocess.Popen]]) -> None:
    """Hentikan child process tanpa meninggalkan server di background."""
    for _name, process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 5
    for _name, process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()


def start(name: str, filename: str) -> subprocess.Popen:
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / filename)],
        cwd=BASE_DIR,
        creationflags=flags,
    )
    print(f"[START] {name} (PID {process.pid})")
    return process


def main() -> int:
    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        # Trajectory memakai 8007. Tunggu sampai aktif agar ultrasonic otomatis
        # memilih port fallback 8008 dan tidak berlomba mengambil port 8007.
        trajectory = start(*SERVICES[0])
        processes.append((SERVICES[0][0], trajectory))
        for _ in range(50):
            if trajectory.poll() is not None:
                print("[ERROR] rov-trajectory.py berhenti saat startup.")
                return trajectory.returncode or 1
            if port_is_ready(8007):
                break
            time.sleep(0.1)
        else:
            print("[ERROR] rov-trajectory.py tidak membuka port 8007.")
            return 1

        for name, filename in SERVICES[1:]:
            processes.append((name, start(name, filename)))

        print("[READY] Semua service berjalan. Tekan Ctrl+C untuk berhenti.")
        while True:
            for name, process in processes:
                code = process.poll()
                if code is not None:
                    print(f"[ERROR] {name} berhenti dengan kode {code}.")
                    return code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[STOP] Menghentikan semua service...")
        return 0
    finally:
        stop_all(processes)


if __name__ == "__main__":
    raise SystemExit(main())
