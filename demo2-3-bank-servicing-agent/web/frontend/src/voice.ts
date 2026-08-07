export interface VoiceCallbacks {
  onState: (state: 'connecting' | 'connected' | 'ended') => void
  onTranscript: (role: 'user' | 'assistant', text: string) => void
  onError: (message: string) => void
}

export class VoiceCall {
  private readonly callbacks: VoiceCallbacks
  private socket: WebSocket | null = null
  private inputContext: AudioContext | null = null
  private outputContext: AudioContext | null = null
  private stream: MediaStream | null = null
  private processor: ScriptProcessorNode | null = null
  private nextPlaybackAt = 0

  constructor(callbacks: VoiceCallbacks) {
    this.callbacks = callbacks
  }

  async connect(websocketUrl: string, handle: string): Promise<void> {
    this.callbacks.onState('connecting')
    const socket = new WebSocket(websocketUrl)
    socket.binaryType = 'arraybuffer'
    this.socket = socket

    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'auth', sessionHandle: handle }))
        this.callbacks.onState('connected')
        resolve()
      }
      socket.onerror = () => reject(new Error('Unable to connect the voice session.'))
    })

    socket.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        this.playPcm16(event.data)
        return
      }
      try {
        const message = JSON.parse(String(event.data)) as {
          type: string
          role?: 'user' | 'assistant'
          text?: string
          message?: string
        }
        if (message.type === 'transcript' && message.role && message.text) {
          this.callbacks.onTranscript(message.role, message.text)
        } else if (message.type === 'error') {
          this.callbacks.onError(message.message ?? 'Voice session failed.')
        }
      } catch {
        this.callbacks.onError('Voice session returned an invalid control message.')
      }
    }
    socket.onclose = () => {
      this.stopAudio()
      this.callbacks.onState('ended')
    }
    await this.startCapture()
  }

  close(): void {
    this.stopAudio()
    this.socket?.close(1000, 'User ended the call')
    this.socket = null
    this.callbacks.onState('ended')
  }

  private async startCapture(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
    this.inputContext = new AudioContext()
    const source = this.inputContext.createMediaStreamSource(this.stream)
    this.processor = this.inputContext.createScriptProcessor(4096, 1, 1)
    this.processor.onaudioprocess = (event) => {
      if (this.socket?.readyState !== WebSocket.OPEN) return
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

  private stopAudio(): void {
    this.processor?.disconnect()
    this.processor = null
    for (const track of this.stream?.getTracks() ?? []) track.stop()
    this.stream = null
    void this.inputContext?.close()
    void this.outputContext?.close()
    this.inputContext = null
    this.outputContext = null
    this.nextPlaybackAt = 0
  }
}
