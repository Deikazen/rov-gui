import React from 'react';
import { PanelWrapper } from './PanelWrapper';

interface QrPanelProps {
    side: string;
    scanCount: number;
    confidence: string;
}

export const QrPanel: React.FC<QrPanelProps> = ({ side, scanCount, confidence }) => {
    const isValid = side !== 'INVALID';
    const pattern = [1, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0];

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
        </PanelWrapper>
    );
};
