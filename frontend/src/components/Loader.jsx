import React, { useEffect, useState } from 'react';

const Loader = ({ isLoading }) => {
    const [shouldRender, setShouldRender] = useState(isLoading);

    useEffect(() => {
        if (isLoading) {
            setShouldRender(true);
        } else {
            // Delay unmounting for fade-out animation
            const timer = setTimeout(() => {
                setShouldRender(false);
            }, 600);
            return () => clearTimeout(timer);
        }
    }, [isLoading]);

    if (!shouldRender) return null;

    return (
        <div className="loader-screen" style={{ opacity: isLoading ? 1 : 0 }}>
            <div className="orbit-container">
                {/* Replaced image with a CSS-styled placeholder if no image exists, 
                    or use a generic satellite emoji for now as requested 'replace with your image path' */}
                <div className="logo" style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '4rem',
                    background: '#0f172a',
                    color: 'white'
                }}>
                    🛰️
                </div>

                <div className="orbit orbit-1"></div>
                <div className="orbit orbit-2"></div>
                <div className="orbit orbit-3"></div>
            </div>

            <p className="loading-text">Loading satellite data...</p>
        </div>
    );
};

export default Loader;
