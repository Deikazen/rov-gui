import React, { useState, useEffect, useRef } from 'react';

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
    const [customHeight, setCustomHeight] = useState<number | null>(null);
    const [isResizing, setIsResizing] = useState(false);

    const panelRef = useRef<HTMLDivElement | null>(null);
    const isResizingRef = useRef(false);
    const startPosRef = useRef({ y: 0, initialH: 0 });

    const toggleFullView = () => {
        setIsFullView(prev => !prev);
    };

    // Listen to Global Reset Layout Event
    useEffect(() => {
        const handleGlobalReset = () => {
            setIsFullView(false);
            setCustomHeight(null);
        };
        window.addEventListener('rov-reset-layout', handleGlobalReset);
        return () => window.removeEventListener('rov-reset-layout', handleGlobalReset);
    }, []);

    const startResize = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        isResizingRef.current = true;
        setIsResizing(true);
        const initialH = panelRef.current?.offsetHeight || 260;
        startPosRef.current = {
            y: e.clientY,
            initialH
        };

        const handleMouseMove = (moveEvent: MouseEvent) => {
            if (!isResizingRef.current) return;
            const deltaY = moveEvent.clientY - startPosRef.current.y;
            const newHeight = Math.max(160, Math.min(850, startPosRef.current.initialH + deltaY));
            setCustomHeight(newHeight);
            window.dispatchEvent(new Event('rov-layout-change'));
        };

        const handleMouseUp = () => {
            isResizingRef.current = false;
            setIsResizing(false);
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
            if (onLayoutChange) onLayoutChange();
            window.dispatchEvent(new Event('rov-layout-change'));
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
    };

    useEffect(() => {
        if (isFullView) {
            document.body.classList.add('full-view-active');
        } else {
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

    const panelStyle: React.CSSProperties = {};
    if (!isFullView && customHeight !== null) {
        panelStyle.height = `${customHeight}px`;
        panelStyle.minHeight = `${customHeight}px`;
        panelStyle.flex = 'none';
    }

    return (
        <div
            ref={panelRef}
            className={`panel ${className} ${isFullView ? 'full-view' : ''} ${isResizing ? 'is-resizing' : ''}`}
            style={panelStyle}
        >
            <div className="panel-header">
                <span className="panel-title">{title}</span>
                <span className="panel-actions">
                    <div className="dot" />
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

            {/* Handle Drag Resize Tinggi Card di Garis Bawah Card */}
            {!isFullView && (
                <div
                    className="panel-resize-handle"
                    onMouseDown={startResize}
                    title="Klik dan tarik ke atas/bawah untuk mengatur tinggi card ini"
                >
                    <span className="resize-grip-bar" />
                </div>
            )}
        </div>
    );
};
