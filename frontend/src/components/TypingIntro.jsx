import React, { useState, useEffect } from 'react';

const TypingIntro = ({ onComplete }) => {
    const fullText = "ASTRAVISION";
    const subtitleText = "Multi-Satellite Data Fusion Dashboard";

    const [text, setText] = useState('');
    const [showSubtitle, setShowSubtitle] = useState(false);
    const [showButton, setShowButton] = useState(false);
    const [isFadingOut, setIsFadingOut] = useState(false);

    useEffect(() => {
        let index = 0;
        const typingInterval = setInterval(() => {
            if (index <= fullText.length) {
                setText(fullText.slice(0, index));
                index++;
            } else {
                clearInterval(typingInterval);
                setTimeout(() => setShowSubtitle(true), 300);
                setTimeout(() => setShowButton(true), 1000);
            }
        }, 150); // Typing speed

        return () => clearInterval(typingInterval);
    }, []);

    const handleEnter = () => {
        setIsFadingOut(true);
        setTimeout(() => {
            onComplete();
        }, 800); // Match CSS transition duration
    };

    return (
        <div className={`typing-intro ${isFadingOut ? 'fade-out' : ''}`}>
            <div className="typing-container">
                <div className="typing-wrapper">
                    <h1 className="typing-text">
                        {text}
                        <span className="cursor"></span>
                    </h1>
                </div>

                <p className={`intro-subtitle ${showSubtitle ? 'visible' : ''}`}>
                    {subtitleText}
                </p>

                <button
                    className={`btn btn-primary enter-btn ${showButton ? 'visible' : ''}`}
                    onClick={handleEnter}
                >
                    ENTER DASHBOARD
                </button>
            </div>
        </div>
    );
};

export default TypingIntro;
