import React from 'react';

interface HeaderProps {
    timeString: string;
    dateString: string;
}

export const Header: React.FC<HeaderProps> = ({ timeString, dateString }) => {
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
            <div>
                <div id="clock">{timeString}</div>
                <div id="date-display">{dateString}</div>
            </div>
        </div>
    );
};
