// src/components/Toast.jsx
//
// M9 — in-DOM toast surface. Replaces the M8a console.warn/console.error
// pattern with a real, accessible, dismissible toast host.
//
// Architecture:
//   - Toasts live on the layers-context slice of the store.
//   - Components dispatch TOAST_PUSHED; the host dispatches TOAST_DISMISSED
//     on auto-timeout or click.
//   - `kind: 'info' | 'success' | 'error'` drives the visual style.
//   - `aria-live="polite"` so screen-readers announce errors without
//     interrupting flow (politeness is per WAI-ARIA Authoring Practices).

import { useEffect } from "react";
import { useLayers, useDispatch } from "../state/AppStore.jsx";
import { TOAST_DISMISSED } from "../state/actions.js";

const ICONS = {
    info: "ℹ️",
    success: "✅",
    error: "⚠️",
};

function ToastItem({ toast }) {
    const dispatch = useDispatch();
    useEffect(() => {
        if (!toast.ttl) return;
        const t = setTimeout(() => {
            dispatch({ type: TOAST_DISMISSED, id: toast.id });
        }, toast.ttl);
        return () => clearTimeout(t);
    }, [toast.id, toast.ttl, dispatch]);

    return (
        <div
            className={`toast toast--${toast.kind}`}
            role={toast.kind === "error" ? "alert" : "status"}
            data-testid={`toast-${toast.kind}`}
        >
            <span className="toast__icon" aria-hidden="true">
                {ICONS[toast.kind] || "•"}
            </span>
            <span className="toast__text">{toast.text}</span>
            <button
                type="button"
                className="toast__close"
                onClick={() => dispatch({ type: TOAST_DISMISSED, id: toast.id })}
                aria-label="Dismiss"
            >
                ✕
            </button>
        </div>
    );
}

export default function ToastHost() {
    const { toasts } = useLayers();
    if (!toasts || toasts.length === 0) return null;
    return (
        <div className="toast-host" aria-live="polite" aria-atomic="false">
            {toasts.map((t) => (
                <ToastItem key={t.id} toast={t} />
            ))}
        </div>
    );
}
