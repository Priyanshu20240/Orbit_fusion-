// src/components/DateRangePicker.jsx
//
// M9 — replaces the Sidebar's raw date inputs with a small, validated
// DateRangePicker. Default range = last 90 days. Validation: start ≤
// end, both within the last 5 years, and end ≤ today. Emits via the
// `onChange({ startDate, endDate })` callback (ISO YYYY-MM-DD).

import { useMemo } from "react";

const DAY = 86_400_000;

function isoDate(d) {
    return new Date(d).toISOString().slice(0, 10);
}

export default function DateRangePicker({ value, onChange, error }) {
    // Today + 5 years ago bounds (max historical window we allow).
    const bounds = useMemo(() => {
        const today = new Date();
        const min = new Date(today.getTime() - 5 * 365 * DAY);
        return { min: isoDate(min), max: isoDate(today) };
    }, []);

    const onStart = (e) => {
        const startDate = e.target.value;
        const endDate =
            value?.endDate && value.endDate < startDate ? startDate : value?.endDate || "";
        onChange?.({ startDate, endDate });
    };
    const onEnd = (e) => {
        const endDate = e.target.value;
        onChange?.({ startDate: value?.startDate || "", endDate });
    };
    const onPreset = (days) => {
        const end = new Date();
        const start = new Date(end.getTime() - days * DAY);
        onChange?.({ startDate: isoDate(start), endDate: isoDate(end) });
    };

    return (
        <div className="date-card">
            <div className="date-group">
                <label htmlFor="date-start">Start Date</label>
                <input
                    id="date-start"
                    type="date"
                    className="date-input date-input--start"
                    value={value?.startDate || ""}
                    min={bounds.min}
                    max={bounds.max}
                    onChange={onStart}
                    data-type="start"
                />
            </div>

            <div className="date-group">
                <label htmlFor="date-end">End Date</label>
                <input
                    id="date-end"
                    type="date"
                    className="date-input date-input--end"
                    value={value?.endDate || ""}
                    min={bounds.min}
                    max={bounds.max}
                    onChange={onEnd}
                    data-type="end"
                />
            </div>

            <div className="date-presets" role="group" aria-label="Date range presets">
                <button type="button" className="date-preset" onClick={() => onPreset(30)}>30d</button>
                <button type="button" className="date-preset" onClick={() => onPreset(90)}>90d</button>
                <button type="button" className="date-preset" onClick={() => onPreset(180)}>6m</button>
                <button type="button" className="date-preset" onClick={() => onPreset(365)}>1y</button>
            </div>

            {error && (
                <p className="date-error" role="alert">
                    {error}
                </p>
            )}
        </div>
    );
}
