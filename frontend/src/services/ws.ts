import { ref } from 'vue'

export function useScanWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const lastMessage = ref<any>(null)
  let heartbeat: ReturnType<typeof setInterval> | null = null
  let reconnect: ReturnType<typeof setTimeout> | null = null
  let manuallyClosed = false

  function connect(token: string) {
    manuallyClosed = false
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const address = scheme + '//' + window.location.host + '/ws/scans?token=' + encodeURIComponent(token)
    ws.value = new WebSocket(address)

    ws.value.onopen = () => {
      isConnected.value = true
      if (heartbeat) clearInterval(heartbeat)
      heartbeat = setInterval(() => {
        if (ws.value && ws.value.readyState === WebSocket.OPEN) ws.value.send('ping')
      }, 30000)
    }

    ws.value.onmessage = (event) => {
      try {
        lastMessage.value = JSON.parse(event.data)
      } catch {
        lastMessage.value = event.data
      }
    }

    ws.value.onclose = () => {
      isConnected.value = false
      if (heartbeat) {
        clearInterval(heartbeat)
        heartbeat = null
      }
      if (!manuallyClosed) reconnect = setTimeout(() => connect(token), 5000)
    }
  }

  function disconnect() {
    manuallyClosed = true
    if (heartbeat) clearInterval(heartbeat)
    if (reconnect) clearTimeout(reconnect)
    heartbeat = null
    reconnect = null
    ws.value?.close()
    ws.value = null
    isConnected.value = false
  }

  return { connect, disconnect, isConnected, lastMessage }
}
