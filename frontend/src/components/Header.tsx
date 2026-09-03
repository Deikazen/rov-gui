import React from 'react';

interface HeaderProps {
    timeString: string;
    dateString: string;
    onResetLayout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ timeString, dateString, onResetLayout }) => {
    return (
        <div id="top-bar">
            <div className="team-identity">
                <div className="team-logo">
                    <img src="./SAGARA.jpeg" className="team-logo-img" alt="Team SAGARA Logo" />
                </div>
                <div className="team-info">
                    <div className="team-name">TEAM SAGARA</div>
                    <div className="uni-name">INSTITUT TEKNOLOGI NASIONAL BANDUNG</div>
                </div>
            </div>

            <div className="header-center-actions">
                <button
                    type="button"
                    className="btn-reset-global"
                    onClick={onResetLayout}
                    title="Reset semua ukuran card tampilan dan zoom kamera ke setelan awal"
                >
                    <span className="reset-icon">↺</span> RESET SETELAN AWAL
                </button>
            </div>

            <div className="header-clock-area">
                <div id="clock">{timeString}</div>
                <div id="date-display">{dateString}</div>
            </div>
        </div>
    );
};
