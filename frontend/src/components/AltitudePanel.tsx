import React from 'react';
import { PanelWrapper } from './PanelWrapper';

interface AltitudePanelProps {
    altitude: number;
    altPrev: number;
}

export const AltitudePanel: React.FC<AltitudePanelProps> = ({ altitude, altPrev }) => {
    const pct = Math.min(1, Math.max(0, altitude / 5.0));
    const isDanger = altitude < 0.3;
    const isWarning = altitude < 1.5;
    const colorVar = isDanger ? 'var(--red)' : isWarning ? 'var(--amber)' : 'var(--green)';

    const rate = ((altitude - altPrev) / (16 / 1000)).toFixed(2);
    const formattedRate = (parseFloat(rate) >= 0 ? '+' : '') + parseFloat(rate).toFixed(2);

    return (
        <PanelWrapper className="alt-panel" title="ALTITUDE — DEPTH SENSOR">
            <div className="alt-gauge-wrap">
                <div className="alt-gauge-track">
                    <div
                        className="alt-gauge-fill"
                        style={{ height: `${pct * 100}%`, background: colorVar }}
                    />
                </div>
                <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>0.0m</div>
            </div>
            <div className="alt-gauge-labels">
                <span>5.0</span><span>4.0</span><span>3.0</span><span>2.0</span><span>1.0</span><span>0.0</span>
            </div>
            <div className="alt-readout">
                <div className="alt-label">ALTITUDE</div>
                <div className="alt-value" style={{ color: colorVar }}>
                    {altitude.toFixed(2)}
                </div>
                <div className="alt-unit">METERS</div>
                <div className="alt-danger" style={{ opacity: isDanger ? 1 : 0 }}>
                    ⚠ DANGER ZONE
                </div>
                <div style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-muted)' }}>
                    MIN <span style={{ color: 'var(--text-main)' }}>0.20</span> | MAX <span style={{ color: 'var(--text-main)' }}>3.50</span>
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    RATE <span style={{ color: 'var(--amber)', fontFamily: 'JetBrains Mono' }}>{formattedRate}</span> m/s
                </div>
            </div>
        </PanelWrapper>
    );
};
