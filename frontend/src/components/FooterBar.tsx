import React from 'react';

interface FooterBarProps {
    mode: 'MANUAL' | 'AUTONOMOUS';
    emergencyActive: boolean;
    connected: boolean;
    logging: boolean;
    hasLogData: boolean;
    theme: 'dark' | 'light';
    depth: number;
    onResetLayout?: () => void;
    onToggleMode: () => void;
    onToggleEmergency: () => void;
    onToggleLogging: () => void;
    onToggleTheme: () => void;
    onScreenshot: () => void;
    onDownloadCSV: () => void;
}

export const FooterBar: React.FC<FooterBarProps> = ({
    mode,
    emergencyActive,
    connected,
    logging,
    hasLogData,
    theme,
    depth,
    onResetLayout,
    onToggleMode,
    onToggleEmergency,
    onToggleLogging,
    onToggleTheme,
    onScreenshot,
    onDownloadCSV
}) => {
    const isAuto = mode === 'AUTONOMOUS';

    return (
        <div id="footer">
            <div className="footer-item">
                <span className="footer-label">MODE</span>
                <button
                    className={`mode-toggle ${isAuto ? 'auto' : ''}`}
                    id="mode-toggle"
                    type="button"
                    onClick={onToggleMode}
                    aria-pressed={isAuto}
                >
                    <span className="mode-switch" aria-hidden="true" />
                    <span className="mode-text" id="mode-label">{mode}</span>
                </button>
            </div>

            <div className="footer-divider" />

            <div className="footer-item">
                <button
                    className={`action-btn emergency-btn ${emergencyActive ? 'active' : ''}`}
                    id="btn-emergency"
                    type="button"
                    onClick={onToggleEmergency}
                >
                    {emergencyActive ? 'Emergency Active' : 'Emergency'}
                </button>
            </div>

            <div className="footer-divider" />

            <div className="footer-item">
                <span className="footer-label">LINK</span>
                <div className={`conn-dot ${connected ? 'connected' : 'disconnected'}`} id="conn-dot" />
                <span id="conn-label" style={{ fontWeight: 500, color: connected ? 'var(--green)' : 'var(--red)' }}>
                    {connected ? 'CONNECTED' : 'DISCONNECTED'}
                </span>
            </div>

            <div className="footer-divider" />

            <div className="footer-item">
                <span className="footer-label">SENSORS</span>
                <div className={`sensor-badge ${connected ? 'sensor-ok' : 'sensor-err'}`}>
                    {connected ? 'DEPTH OK' : 'DEPTH ERR'}
                </div>
                <div className={`sensor-badge ${connected ? 'sensor-ok' : 'sensor-err'}`}>
                    {connected ? 'IMU OK' : 'IMU ERR'}
                </div>
                <div className={`sensor-badge ${connected ? 'sensor-ok' : 'sensor-err'}`}>
                    {connected ? 'CAM OK' : 'CAM ERR'}
                </div>
            </div>

            <div className="footer-divider" />

            <div className="footer-item">
                <span className="footer-label">LOG</span>
                <div className="rec-indicator">
                    <div className={`rec-dot ${logging ? 'active' : 'inactive'}`} />
                    <span style={{ color: logging || emergencyActive ? 'var(--red)' : 'var(--text-muted)' }}>
                        {logging ? 'RECORDING' : emergencyActive ? 'EMERGENCY READY' : 'STANDBY'}
                    </span>
                </div>
                <button
                    className={`action-btn ${logging ? 'active' : ''}`}
                    id="btn-log"
                    onClick={onToggleLogging}
                >
                    {logging ? 'Stop Log' : 'Start Log'}
                </button>
            </div>

            <div className="footer-divider" />

            <div className="footer-item" style={{ marginLeft: 'auto' }}>
                <button
                    className="action-btn"
                    onClick={onResetLayout}
                    title="Reset semua ukuran card tampilan dan zoom kamera ke setelan awal"
                >
                    ↺ Reset Layout
                </button>
                <button className="action-btn theme-toggle" id="btn-theme" onClick={onToggleTheme}>
                    {theme === 'light' ? 'Dark' : 'Light'}
                </button>
                <button className="action-btn" onClick={onScreenshot}>
                    Screenshot
                </button>
                {hasLogData && !logging && (
                    <button className="action-btn" id="btn-csv" style={{ marginLeft: '4px' }} onClick={onDownloadCSV}>
                        Download CSV
                    </button>
                )}
            </div>

            <div className="footer-item" style={{ fontSize: '11px', color: 'var(--text-muted)', flexDirection: 'column', alignItems: 'flex-end' }}>
                <span style={{ marginTop: '2px' }}>
                    DEPTH: <span style={{ color: 'var(--blue)', fontFamily: 'JetBrains Mono' }}>{depth.toFixed(2)}</span>m | TEMP: <span style={{ color: 'var(--amber)', fontFamily: 'JetBrains Mono' }}>24.7°C</span>
                </span>
            </div>
        </div>
    );
};
