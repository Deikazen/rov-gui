import React, { useState } from 'react';
import { PanelWrapper } from './PanelWrapper';
import type { QrHistoryEntry } from '../hooks/useQrDetector';

interface QrPanelProps {
    side: string;
    scanCount: number;
    confidence: string;
    // Riwayat SEMUA QR yang pernah berhasil terdeteksi, terbaru di index 0.
    history: QrHistoryEntry[];
}

// Cek apakah teks hasil decode QR berupa URL yang bisa dibuka langsung.
function isUrl(text: string): boolean {
    try {
        const url = new URL(text);
        return url.protocol === 'http:' || url.protocol === 'https:';
    } catch {
        return false;
    }
}

function formatTime(epochSeconds: number): string {
    if (!epochSeconds) return '--:--:--';
    return new Date(epochSeconds * 1000).toLocaleTimeString('id-ID', { hour12: false });
}

export const QrPanel: React.FC<QrPanelProps> = ({ side, scanCount, confidence, history }) => {
    const isValid = side !== 'INVALID';
    const hasHistory = history.length > 0;
    const pattern = [1, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0];

    // Kontrol tampilan di dalam panel: "live" (default) <-> "link" (riwayat semua scan)
    const [view, setView] = useState<'live' | 'link'>('live');

    const btnStyle = (enabled: boolean): React.CSSProperties => ({
        marginTop: '8px',
        width: '100%',
        padding: '6px 10px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.03em',
        textTransform: 'uppercase',
        borderRadius: '6px',
        border: '1px solid var(--green)',
        background: enabled ? 'var(--green)' : 'transparent',
        color: enabled ? '#0a0a0a' : 'var(--text-muted)',
        cursor: enabled ? 'pointer' : 'not-allowed',
        opacity: enabled ? 1 : 0.5,
        transition: 'opacity 0.2s ease',
    });

    if (view === 'link') {
        // Tampilan riwayat: TIDAK pindah halaman/tab, cuma ganti isi panel.
        return (
            <PanelWrapper className="qr-panel" title="QR CODE DETECTOR">
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '8px', textAlign: 'center' }}>
                    RIWAYAT QR TERDETEKSI ({history.length})
                </div>

                {hasHistory ? (
                    <div
                        style={{
                            maxHeight: '180px',
                            overflowY: 'auto',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '6px',
                            paddingRight: '2px',
                        }}
                    >
                        {history.map((entry, i) => (
                            <div
                                key={`${entry.timestamp}-${i}`}
                                style={{
                                    border: '1px solid rgba(255,255,255,0.08)',
                                    borderRadius: '6px',
                                    padding: '6px 8px',
                                    fontSize: '11px',
                                }}
                            >
                                <div style={{ color: 'var(--text-muted)', fontSize: '10px', marginBottom: '2px' }}>
                                    #{history.length - i} · {formatTime(entry.timestamp)} · {entry.quality.toFixed(1)}%
                                </div>
                                {isUrl(entry.data) ? (
                                    <a
                                        href={entry.data}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            display: 'block',
                                            wordBreak: 'break-all',
                                            color: 'var(--green)',
                                            fontFamily: 'monospace',
                                            textDecoration: 'underline',
                                        }}
                                    >
                                        {entry.data}
                                    </a>
                                ) : (
                                    <div style={{ wordBreak: 'break-all', color: 'var(--green)', fontFamily: 'monospace' }}>
                                        {entry.data}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', padding: '12px 0' }}>
                        Belum ada QR yang pernah berhasil terdeteksi.
                    </div>
                )}

                <button
                    type="button"
                    className="qr-back-btn"
                    onClick={() => setView('live')}
                    style={btnStyle(true)}
                >
                    Kembali
                </button>
            </PanelWrapper>
        );
    }

    return (
        <PanelWrapper className="qr-panel" title="QR CODE DETECTOR">
            <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginBottom: '2px' }}>DETECTED SIDE</div>
                <div className="qr-side-label" style={{ color: isValid ? 'var(--green)' : 'var(--red)' }}>
                    {side}
                </div>
            </div>
            <div className={`qr-valid-badge ${isValid ? 'valid' : 'invalid'}`}>
                {isValid ? 'VALID' : 'INVALID'}
            </div>
            <div className="qr-anim-box">
                <div className="qr-inner-grid">
                    {pattern.map((v, i) => (
                        <div key={i} className={v ? 'qr-cell' : ''} />
                    ))}
                </div>
            </div>
            <div className="qr-info-row">
                <div>SCAN: <span>{String(scanCount).padStart(4, '0')}</span></div>
                <div>CONF: <span>{confidence}</span></div>
            </div>

            <button
                type="button"
                className="qr-view-link-btn"
                onClick={() => setView('link')}
                disabled={!hasHistory}
                title={
                    hasHistory
                        ? `Lihat ${history.length} riwayat QR yang berhasil terdeteksi dari Camera 01`
                        : 'Belum ada QR yang pernah berhasil terdeteksi'
                }
                style={btnStyle(hasHistory)}
            >
                Lihat Link QR
            </button>
        </PanelWrapper>
    );
};
