export type VoiceState =
  | 'connecting'
  | 'listening'
  | 'speaking'
  | 'reconnecting'
  | 'failed'
  | 'ended'

export interface VoiceCallbacks {
  onState: (state: VoiceState) => void
  onTranscript: (role: 'user' | 'assistant', text: string) => void
  onAvatarStream: (stream: MediaStream) => void
  onError: (message: string) => void
}

interface VoiceControlMessage {
  type: string
  role?: 'user' | 'assistant'
  text?: string
  message?: string
  state?: 'listening' | 'speaking'
  avatarEnabled?: boolean
  iceServers?: RTCIceServer[]
  serverSdp?: string
}

export class VoiceCall {
  private readonly callbacks: VoiceCallbacks
  private socket: WebSocket | null = null
  private inputContext: AudioContext | null = null
  private outputContext: AudioContext | null = null
  private stream: MediaStream | null = null
  private processor: ScriptProcessorNode | null = null
  private peer: RTCPeerConnection | null = null
  private avatarStream: MediaStream | null = null
  private nextPlaybackAt = 0
  private muted = false

  constructor(callbacks: VoiceCallbacks) {
    this.callbacks = callbacks
  }

  async connect(websocketUrl: string, handle: string): Promise<void> {
    this.callbacks.onState('connecting')
    const socket = new WebSocket(websocketUrl)
    socket.binaryType = 'arraybuffer'
    this.socket = socket

    socket.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        if (!this.avatarStream?.getAudioTracks().length) this.playPcm16(event.data)
        return
      }
      void this.handleControlMessage(String(event.data))
    }
    socket.onclose = () => {
      if (this.socket !== socket) return
      this.socket = null
      this.stopMedia()
      this.callbacks.onState('ended')
    }

    try {
      await new Promise<void>((resolve, reject) => {
        socket.onopen = () => {
          socket.send(JSON.stringify({ type: 'auth', sessionHandle: handle }))
          resolve()
        }
        socket.onerror = () => reject(new Error('Unable to connect the avatar session.'))
      })
      await this.startCapture()
    } catch (reason) {
      if (this.socket === socket) this.socket = null
      this.stopMedia()
      socket.close()
      throw reason
    }
  }

  close(): void {
    this.stopMedia()
    const socket = this.socket
    this.socket = null
    socket?.close(1000, 'User ended the call')
    this.callbacks.onState('ended')
  }

  setMuted(muted: boolean): void {
    this.muted = muted
    for (const track of this.stream?.getAudioTracks() ?? []) {
      track.enabled = !muted
    }
  }

  private async handleControlMessage(data: string): Promise<void> {
    try {
      const message = JSON.parse(data) as VoiceControlMessage
      if (message.type === 'ready') {
        if (message.avatarEnabled === false) {
          this.callbacks.onState('listening')
        } else {
          await this.connectAvatar(message.iceServers ?? [])
        }
      } else if (message.type === 'avatar_answer' && message.serverSdp) {
        await this.acceptAvatarAnswer(message.serverSdp)
      } else if (message.type === 'state' && message.state) {
        this.callbacks.onState(message.state)
      } else if (message.type === 'transcript' && message.role && message.text) {
        this.callbacks.onTranscript(message.role, message.text)
      } else if (message.type === 'error') {
        this.fail(message.message ?? 'Avatar session failed.')
      }
    } catch (reason) {
      this.fail(reason instanceof Error ? reason.message : 'Avatar session returned invalid data.')
    }
  }

  private async connectAvatar(iceServers: RTCIceServer[]): Promise<void> {
    const peer = new RTCPeerConnection({ iceServers })
    this.peer = peer
    peer.addTransceiver('video', { direction: 'sendrecv' })
    peer.addTransceiver('audio', { direction: 'sendrecv' })
    peer.ontrack = (event) => {
      this.avatarStream ??= new MediaStream()
      if (!this.avatarStream.getTracks().some((track) => track.id === event.track.id)) {
        this.avatarStream.addTrack(event.track)
      }
      this.callbacks.onAvatarStream(this.avatarStream)
      if (event.track.kind === 'video') this.callbacks.onState('listening')
    }
    peer.onconnectionstatechange = () => {
      if (peer.connectionState === 'connected') {
        this.callbacks.onState('listening')
      } else if (peer.connectionState === 'disconnected') {
        this.callbacks.onState('reconnecting')
      } else if (peer.connectionState === 'failed') {
        this.fail('The avatar media connection failed.')
      }
    }

    const offer = await peer.createOffer()
    await peer.setLocalDescription(offer)
    await waitForUsableIceCandidates(peer)
    if (!peer.localDescription) throw new Error('The avatar offer could not be created.')
    this.socket?.send(JSON.stringify({
      type: 'avatar_connect',
      clientSdp: btoa(JSON.stringify(peer.localDescription)),
    }))
  }

  private async acceptAvatarAnswer(encodedAnswer: string): Promise<void> {
    if (!this.peer) throw new Error('The avatar answer arrived before the media connection.')
    const answer = JSON.parse(atob(encodedAnswer)) as RTCSessionDescriptionInit
    await this.peer.setRemoteDescription(answer)
  }

  private async startCapture(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
    this.setMuted(this.muted)
    this.inputContext = new AudioContext()
    const source = this.inputContext.createMediaStreamSource(this.stream)
    this.processor = this.inputContext.createScriptProcessor(4096, 1, 1)
    this.processor.onaudioprocess = (event) => {
      if (this.muted || this.socket?.readyState !== WebSocket.OPEN) return
      const samples = event.inputBuffer.getChannelData(0)
      const ratio = this.inputContext!.sampleRate / 16000
      const outputLength = Math.floor(samples.length / ratio)
      const pcm = new Int16Array(outputLength)
      for (let index = 0; index < outputLength; index += 1) {
        const sample = Math.max(-1, Math.min(1, samples[Math.floor(index * ratio)]))
        pcm[index] = sample < 0 ? sample * 32768 : sample * 32767
      }
      this.socket.send(pcm.buffer)
    }
    source.connect(this.processor)
    this.processor.connect(this.inputContext.destination)
  }

  private playPcm16(data: ArrayBuffer): void {
    this.outputContext ??= new AudioContext({ sampleRate: 24000 })
    const sourceData = new Int16Array(data)
    const buffer = this.outputContext.createBuffer(1, sourceData.length, 24000)
    const channel = buffer.getChannelData(0)
    for (let index = 0; index < sourceData.length; index += 1) {
      channel[index] = sourceData[index] / 32768
    }
    const source = this.outputContext.createBufferSource()
    source.buffer = buffer
    source.connect(this.outputContext.destination)
    const startAt = Math.max(this.outputContext.currentTime, this.nextPlaybackAt)
    source.start(startAt)
    this.nextPlaybackAt = startAt + buffer.duration
  }

  private fail(message: string): void {
    this.callbacks.onError(message)
    this.callbacks.onState('failed')
    this.stopMedia()
    const socket = this.socket
    this.socket = null
    socket?.close(1011, 'Avatar session failed')
  }

  private stopMedia(): void {
    this.processor?.disconnect()
    this.processor = null
    for (const track of this.stream?.getTracks() ?? []) track.stop()
    for (const track of this.avatarStream?.getTracks() ?? []) track.stop()
    this.stream = null
    this.avatarStream = null
    this.peer?.close()
    this.peer = null
    void this.inputContext?.close()
    void this.outputContext?.close()
    this.inputContext = null
    this.outputContext = null
    this.nextPlaybackAt = 0
    this.muted = false
  }
}

async function waitForUsableIceCandidates(peer: RTCPeerConnection): Promise<void> {
  if (peer.iceGatheringState === 'complete') return
  await new Promise<void>((resolve, reject) => {
    let hasCandidate = peer.localDescription?.sdp?.includes('a=candidate:') ?? false
    let settleTimer: number | null = null
    const timeout = window.setTimeout(() => {
      cleanup()
      if (hasCandidate) {
        resolve()
      } else {
        reject(new Error('The avatar media connection could not find a network route.'))
      }
    }, 8_000)
    const cleanup = () => {
      window.clearTimeout(timeout)
      if (settleTimer !== null) window.clearTimeout(settleTimer)
      peer.removeEventListener('icegatheringstatechange', onStateChange)
      peer.removeEventListener('icecandidate', onCandidate)
    }
    const finish = () => {
      cleanup()
      resolve()
    }
    const onStateChange = () => {
      if (peer.iceGatheringState !== 'complete') return
      finish()
    }
    const onCandidate = (event: RTCPeerConnectionIceEvent) => {
      if (!event.candidate) {
        finish()
        return
      }
      hasCandidate = true
      if (event.candidate.type !== 'relay') return
      if (settleTimer !== null) window.clearTimeout(settleTimer)
      settleTimer = window.setTimeout(finish, 250)
    }
    peer.addEventListener('icegatheringstatechange', onStateChange)
    peer.addEventListener('icecandidate', onCandidate)
  })
}
