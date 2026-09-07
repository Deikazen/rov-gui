import json
import threading
import time
import websocket # pip install websocket-client
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Tempat penyimpanan data terpusat
system_data = {
    'depth_info': {},
    'trajectory_info': {}
}

# ==========================================
# WEBSOCKET CLIENT UNTUK DEPTH (PORT 5002)
# ==========================================
def on_depth_message(ws, message):
    # Setiap kali rov-depth.py nge-push data, otomatis masuk ke sini
    try:
        data = json.loads(message)
        system_data['depth_info'] = data
        # print("Update Depth:", data['depth']) # Hapus komen ini jika ingin melihat di terminal
    except Exception as e:
        print("Error parsing depth:", e)

def on_depth_error(ws, error):
    print("[WS Depth] Error:", error)

def on_depth_close(ws, close_status_code, close_msg):
    print("[WS Depth] Terputus. Mencoba koneksi ulang...")
    time.sleep(3)
    start_depth_ws_client() # Auto reconnect jika putus

def start_depth_ws_client():
    # Konek ke WebSocket Server milik rov-depth.py di port 5002
    ws_url = "ws://127.0.0.1:5002"
    ws = websocket.WebSocketApp(
        ws_url,
        on_message=on_depth_message,
        on_error=on_depth_error,
        on_close=on_depth_close
    )
    # Jalankan terus menerus
    ws.run_forever()




# ==========================================
# REST API TERPUSAT UNTUK FRONTEND
# ==========================================
@app.route('/api/all-data', methods=['GET'])
def get_all_data():
    """Frontend (React/HTML) cukup tembak endpoint ini untuk dapat SEMUA data"""
    return jsonify(system_data)

if __name__ == '__main__':
    # 1. Jalankan koneksi WebSocket ke rov-depth.py di background thread
    t_depth = threading.Thread(target=start_depth_ws_client, daemon=True)
    t_depth.start()   
    # 2. Jalankan server Flask data.py di port 5000
    print("[Data.py] Menjalankan Server Pusat di http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True)