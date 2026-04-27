export function createWebSocket(token: string, onMessage: (data: any) => void) {
    // Prefer explicit WS base, then API base, then window origin
    const rawBase = import.meta.env.VITE_WS_BASE || import.meta.env.VITE_API_BASE_URL || window.location.origin
    const base = String(rawBase).replace(/^http/, 'ws')
    const url = `${base}/ws?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)

    ws.onopen = () => {
        // send a simple ping to keep the connection active
        try { ws.send('open') } catch (e) { }
    }

    ws.onmessage = (ev) => {
        try {
            const data = JSON.parse(ev.data)
            onMessage(data)
        } catch (e) {
            // ignore parse errors
        }
    }

    ws.onclose = () => {
        // no-op; caller may implement reconnect
    }

    ws.onerror = () => {
        // no-op
    }

    return ws
}
