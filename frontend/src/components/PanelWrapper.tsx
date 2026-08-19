import React, { useState, useEffect } from 'react';

interface PanelWrapperProps {
    className?: string;
    title: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
    onLayoutChange?: () => void;
}

export const PanelWrapper: React.FC<PanelWrapperProps> = ({
    className = '',
    title,
    children,
    footer,
    onLayoutChange
}) => {
    const [isFullView, setIsFullView] = useState(false);

    const toggleFullView = () => {
        setIsFullView(prev => !prev);
    };

    useEffect(() => {
        if (isFullView) {
            document.body.classList.add('full-view-active');
        } else {
            // Check if any other panel is full view before removing
            const anyFull = document.querySelector('.panel.full-view');
            if (!anyFull) {
                document.body.classList.remove('full-view-active');
            }
        }

        const timer = setTimeout(() => {
            if (onLayoutChange) onLayoutChange();
            window.dispatchEvent(new Event('rov-layout-change'));
        }, 320);

        return () => clearTimeout(timer);
    }, [isFullView, onLayoutChange]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isFullView) {
                setIsFullView(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isFullView]);

    return (
        <div className={`panel ${className} ${isFullView ? 'full-view' : ''}`}>
            <div className="panel-header">
                <span className="panel-title">{title}</span>
                <span className="panel-actions">
                    <div className="dot"></div>
                    <button
                        type="button"
                        className="panel-expand-btn"
                        aria-label="Toggle full view"
                        title="Toggle full view"
                        onClick={toggleFullView}
                    >
                        {isFullView ? '×' : '□'}
                    </button>
                </span>
            </div>
            <div className="panel-body">{children}</div>
            {footer}
        </div>
    );
};
