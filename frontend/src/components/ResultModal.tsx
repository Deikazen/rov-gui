import React from 'react';
import type { LogSample } from '../types/telemetry';

interface ResultModalProps {
    isOpen: boolean;
    title: string;
    logData: LogSample[];
    screenshotUrl?: string;
    screenshotFilename?: string;
    onClose: () => void;
}

export const ResultModal: React.FC<ResultModalProps> = ({
    isOpen,
    title,
    logData,
    screenshotUrl,
    screenshotFilename,
    onClose
}) => {
    if (!isOpen) return null;

    const latest = logData.length > 0 ? logData[logData.length - 1] : null;
    const first = logData.length > 0 ? logData[0] : null;
    const duration = latest && first ? Math.max(0, Math.round((Date.parse(latest.timestamp) - Date.parse(first.timestamp)) / 1000)) : 0;
    const preview = logData.slice(-8).reverse();

    const handleDownloadScreenshot = () => {
        if (!screenshotUrl || !screenshotFilename) return;
        const a = document.createElement('a');
        a.href = screenshotUrl;
        a.download = screenshotFilename;
        a.click();
    };

    return (
        <div className={`result-modal ${isOpen ? 'open' : ''}`} aria-hidden={!isOpen}>
            <div className="result-dialog">
                <div className="result-header">
                    <div className="result-title">{title}</div>
                    <button className="result-close" type="button" onClick={onClose}>×</button>
                </div>
                <div className="result-body">
                    {screenshotUrl ? (
                        <>
                            <img className="result-preview-img" src={screenshotUrl} alt="Screenshot preview" />
                            <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
                                <span>{screenshotFilename}</span>
                                <button className="action-btn" onClick={handleDownloadScreenshot}>Download</button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="result-summary">
                                <div className="result-stat">
                                    <label>SAMPLES</label>
                                    <span>{logData.length}</span>
                                </div>
                                <div className="result-stat">
                                    <label>DURATION</label>
                                    <span>{duration}s</span>
                                </div>
                                <div className="result-stat">
                                    <label>DEPTH</label>
                                    <span>{latest ? latest.altitude : '0.00'}m</span>
                                </div>
                                <div className="result-stat">
                                    <label>YAW</label>
                                    <span>{latest ? latest.yaw : '0.00'}°</span>
                                </div>
                            </div>
                            <table className="result-table">
                                <thead>
                                    <tr>
                                        <th>TIME</th>
                                        <th>ALT</th>
                                        <th>ROLL</th>
                                        <th>PITCH</th>
                                        <th>YAW</th>
                                        <th>QR</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {preview.map((r, i) => (
                                        <tr key={i}>
                                            <td>{new Date(r.timestamp).toLocaleTimeString()}</td>
                                            <td>{r.altitude}</td>
                                            <td>{r.roll}</td>
                                            <td>{r.pitch}</td>
                                            <td>{r.yaw}</td>
                                            <td>{r.qrSide}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
