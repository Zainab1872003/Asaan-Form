
import { useEffect, useRef } from 'react';

/**
 * useFormWebSocket
 *
 * Connects to the Node.js WebSocket server.
 * Port must match your Node.js server (default 5000, not 3000).
 *
 * Usage:
 *   useFormWebSocket(userId, (fieldKey, value) => { ... });
 */
export function useFormWebSocket(userId, onFieldUpdate) {
    const wsRef = useRef(null);
    const onFieldUpdateRef = useRef(onFieldUpdate);

    // Keep the callback ref fresh without re-connecting
    useEffect(() => {
        onFieldUpdateRef.current = onFieldUpdate;
    }, [onFieldUpdate]);

    useEffect(() => {
        if (!userId) return;

        // Read port from env (Vite uses import.meta.env, CRA uses process.env)
        // Default to 5000 which is the Node.js server port
        const WS_PORT = import.meta.env?.VITE_WS_PORT || 5000;
        const WS_HOST = import.meta.env?.VITE_WS_HOST || 'localhost';
        const wsUrl = `ws://${WS_HOST}:${WS_PORT}`;

        console.log(`[WebSocket] Connecting to ${wsUrl}`);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log('[WebSocket] Connected ✅');
            ws.send(JSON.stringify({ type: 'auth', userId }));
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'auth_ok') {
                    console.log('[WebSocket] Auth confirmed');
                }
                if (data.type === 'field_update') {
                    console.log(`[WebSocket] Field update: ${data.field_key} = ${data.value}`);
                    if (onFieldUpdateRef.current) {
                        onFieldUpdateRef.current(data.field_key, data.value);
                    }
                }
            } catch (e) {
                console.error('[WebSocket] Message parse error', e);
            }
        };

        ws.onerror = (e) => console.error('[WebSocket] Error', e);
        ws.onclose = () => console.log('[WebSocket] Disconnected');

        return () => {
            ws.close();
        };
    }, [userId]);
}





