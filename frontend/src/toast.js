// src/toast.js
//
// Tiny helper so any module (Sidebar, Map, etc.) can push a toast onto
// the layers context without holding a reference to dispatch. The
// sequence counter is module-scoped so duplicate text doesn't pile up
// (the reducer also de-dupes, but the counter guarantees unique ids).

import { TOAST_PUSHED } from "./state/actions.js";

let _seq = 0;

export function pushToast(dispatch, kind, text, ttl = 5000) {
    if (!dispatch) return;
    dispatch({
        type: TOAST_PUSHED,
        toast: { id: `t-${++_seq}`, kind, text, ttl },
    });
}
