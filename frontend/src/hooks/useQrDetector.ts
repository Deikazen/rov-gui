import { useEffect, useRef, useState } from "react";

/**
 * Bentuk data yang dikirim oleh qr_proxy.py lewat /ws/qr/status
 * (lihat qrCode_detector.py -> latest_qr_status)
 */
interface QrStatus {
  detected: boolean;
  data: string | null;
  rect: { x: number; y: number; w: number; h: number } | null;
  quality: number;
  scan_count: number;
  last_seen_ms_ago: number | null;
  timestamp: number;
  jetson_reachable: boolean;
}

// Satu entri riwayat QR yang berhasil di-decode.
export interface QrHistoryEntry {
  data: string;
  quality: number;
  timestamp: number; // epoch detik, dari Jetson
}

// Ambil dari .env: VITE_QR_WS_URL (lihat frontend/.env.example)
// Fallback ke localhost:8091 kalau env belum di-set.
const QR_WS_URL =
  (import.meta.env.VITE_QR_WS_URL as string | undefined) ??
  "ws://localhost:8091/ws/qr/status";

const RECONNECT_DELAY_MS = 2000;
// Batas jumlah riwayat yang disimpan di memori browser, biar tidak
// membengkak kalau ROV jalan lama dan scan berkali-kali.
const MAX_HISTORY = 100;

export function useQrDetector() {
  // side default "INVALID" -> match logic isValid di QrPanel (side !== 'INVALID')
  const [side, setSide] = useState<string>("INVALID");
  const [scanCount, setScanCount] = useState<number>(0);
  const [confidence, setConfidence] = useState<string>("0.0%");
  const [connected, setConnected] = useState<boolean>(false); // status koneksi ke qr_proxy
  const [jetsonReachable, setJetsonReachable] = useState<boolean>(false); // status koneksi proxy -> Jetson
  // Link/data QR TERAKHIR yang berhasil di-decode -> TIDAK di-reset ke null
  // saat QR hilang dari frame kamera. Dipakai sebagai fallback/ringkasan cepat.
  const [lastData, setLastData] = useState<string | null>(null);
  // Riwayat SEMUA QR yang pernah berhasil terdeteksi (bukan cuma yang terakhir),
  // terbaru di index 0. Ini yang ditampilkan tombol "Lihat Link QR".
  const [history, setHistory] = useState<QrHistoryEntry[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Simpan data QR terakhir yang SUDAH dicatat ke history, supaya tidak
  // mencatat entri duplikat berulang-ulang selagi QR yang sama masih
  // terus terlihat kamera pada beberapa pesan berturut-turut.
  const lastRecordedRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;

      const ws = new WebSocket(QR_WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        console.log("[QR] Terhubung ke qr_proxy:", QR_WS_URL);
      };

      ws.onmessage = (event) => {
        try {
          const status: QrStatus = JSON.parse(event.data);

          setJetsonReachable(status.jetson_reachable);

          if (status.detected && status.data) {
            // QR CODE TERDETEKSI -> langsung tampil, tanpa perlu trigger manual apapun
            setSide(status.data);
            setConfidence(`${status.quality.toFixed(1)}%`);
            setLastData(status.data);

            // Catat ke history setiap kali ini deteksi BARU (beda dari yang
            // sebelumnya dicatat) -> supaya scan berulang untuk QR yang sama
            // yang masih terus terlihat kamera tidak numpuk jadi banyak baris
            // duplikat pada satu "kemunculan" yang sama.
            if (status.data !== lastRecordedRef.current) {
              lastRecordedRef.current = status.data;
              setHistory((prev) => {
                const entry: QrHistoryEntry = {
                  data: status.data as string,
                  quality: status.quality,
                  timestamp: status.timestamp,
                };
                const next = [entry, ...prev];
                return next.length > MAX_HISTORY ? next.slice(0, MAX_HISTORY) : next;
              });
            }
          } else {
            setSide("INVALID");
            setConfidence("0.0%");
            // QR sudah tidak terlihat -> reset penanda "terakhir dicatat" supaya
            // kalau QR yang SAMA muncul lagi nanti (kemunculan baru), tetap
            // dicatat sebagai entri history yang baru.
            lastRecordedRef.current = null;
          }

          setScanCount(status.scan_count ?? 0);
        } catch (err) {
          console.warn("[QR] Gagal parse pesan dari qr_proxy:", err);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!cancelled) {
          reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onerror = () => {
        // onclose akan tetap terpanggil setelah ini, biarkan reconnect logic di onclose yang jalan
        ws.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return { side, scanCount, confidence, connected, jetsonReachable, lastData, history };
}