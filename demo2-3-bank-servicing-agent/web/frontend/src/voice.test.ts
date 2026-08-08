import { afterEach, describe, expect, it, vi } from 'vitest'
import { VoiceCall } from './voice'

describe('VoiceCall', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('authenticates with the first frame without putting the handle in the URL', async () => {
    const sent: Array<string | ArrayBufferLike | Blob | ArrayBufferView> = []
    let openedUrl = ''

    class FakeWebSocket {
      static readonly OPEN = 1
      readyState = FakeWebSocket.OPEN
      binaryType = ''
      onopen: (() => void) | null = null
      onerror: (() => void) | null = null
      onmessage: ((event: MessageEvent) => void) | null = null
      onclose: (() => void) | null = null

      constructor(url: string) {
        openedUrl = url
        socketInstances.push(this)
        queueMicrotask(() => this.onopen?.())
      }

      send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
        sent.push(data)
      }

      close() {
        this.onclose?.()
      }
    }
    const socketInstances: FakeWebSocket[] = []

    class FakeAudioContext {
      sampleRate = 48000
      destination = {}

      createMediaStreamSource() {
        return { connect: vi.fn() }
      }

      createScriptProcessor() {
        return {
          onaudioprocess: null,
          connect: vi.fn(),
          disconnect: vi.fn(),
        }
      }

      close() {
        return Promise.resolve()
      }
    }

    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    vi.stubGlobal('AudioContext', FakeAudioContext as unknown as typeof AudioContext)
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [],
        } as unknown as MediaStream),
      },
    })

    const onState = vi.fn()
    const call = new VoiceCall({
      onState,
      onTranscript: vi.fn(),
      onAvatarStream: vi.fn(),
      onError: vi.fn(),
    })
    await call.connect('wss://bank.example/api/voice/live', 'opaque-handle')

    expect(openedUrl).toBe('wss://bank.example/api/voice/live')
    expect(sent[0]).toBe('{"type":"auth","sessionHandle":"opaque-handle"}')
    socketInstances[0].onmessage?.({
      data: JSON.stringify({ type: 'ready', avatarEnabled: false, iceServers: [] }),
    } as MessageEvent)
    await vi.waitFor(() => expect(onState).toHaveBeenCalledWith('listening'))
    call.close()
  })

  it('negotiates avatar WebRTC, suppresses duplicate PCM audio, and releases media', async () => {
    const sent: Array<string | ArrayBufferLike | Blob | ArrayBufferView> = []
    const createBuffer = vi.fn(() => ({
      duration: 0.1,
      getChannelData: () => new Float32Array(2),
    }))
    const start = vi.fn()
    const inputTrack = { id: 'mic', kind: 'audio', stop: vi.fn() }
    const avatarAudio = { id: 'avatar-audio', kind: 'audio', stop: vi.fn() }
    const avatarVideo = { id: 'avatar-video', kind: 'video', stop: vi.fn() }

    class FakeMediaStream {
      tracks: Array<typeof avatarAudio | typeof avatarVideo> = []

      addTrack(track: typeof avatarAudio | typeof avatarVideo) {
        this.tracks.push(track)
      }

      getTracks() {
        return this.tracks
      }

      getAudioTracks() {
        return this.tracks.filter((track) => track.kind === 'audio')
      }
    }

    class FakeWebSocket {
      static readonly OPEN = 1
      readyState = FakeWebSocket.OPEN
      binaryType = ''
      onopen: (() => void) | null = null
      onerror: (() => void) | null = null
      onmessage: ((event: MessageEvent) => void) | null = null
      onclose: (() => void) | null = null

      constructor() {
        socketInstances.push(this)
        queueMicrotask(() => this.onopen?.())
      }

      send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
        sent.push(data)
      }

      close() {
        this.onclose?.()
      }
    }
    const socketInstances: FakeWebSocket[] = []

    class FakeAudioContext {
      sampleRate = 48000
      currentTime = 0
      destination = {}

      createMediaStreamSource() {
        return { connect: vi.fn() }
      }

      createScriptProcessor() {
        return {
          onaudioprocess: null,
          connect: vi.fn(),
          disconnect: vi.fn(),
        }
      }

      createBuffer = createBuffer

      createBufferSource() {
        return {
          buffer: null,
          connect: vi.fn(),
          start,
        }
      }

      close() {
        return Promise.resolve()
      }
    }

    class FakePeerConnection {
      configuration: RTCConfiguration
      localDescription: RTCSessionDescriptionInit | null = null
      iceGatheringState: RTCIceGatheringState = 'complete'
      connectionState: RTCPeerConnectionState = 'new'
      ontrack: ((event: RTCTrackEvent) => void) | null = null
      onconnectionstatechange: (() => void) | null = null
      addTransceiver = vi.fn()
      setRemoteDescription = vi.fn().mockResolvedValue(undefined)
      close = vi.fn()

      constructor(configuration: RTCConfiguration) {
        this.configuration = configuration
        peerInstances.push(this)
      }

      async createOffer() {
        return { type: 'offer' as const, sdp: 'client-offer' }
      }

      async setLocalDescription(description: RTCSessionDescriptionInit) {
        this.localDescription = description
      }

      addEventListener() {}
      removeEventListener() {}
    }
    const peerInstances: FakePeerConnection[] = []

    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    vi.stubGlobal('AudioContext', FakeAudioContext as unknown as typeof AudioContext)
    vi.stubGlobal('MediaStream', FakeMediaStream as unknown as typeof MediaStream)
    vi.stubGlobal('RTCPeerConnection', FakePeerConnection as unknown as typeof RTCPeerConnection)
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [inputTrack],
        } as unknown as MediaStream),
      },
    })
    const onAvatarStream = vi.fn()
    const onState = vi.fn()
    const call = new VoiceCall({
      onState,
      onTranscript: vi.fn(),
      onAvatarStream,
      onError: vi.fn(),
    })

    await call.connect('wss://bank.example/api/voice/live', 'opaque-handle')
    const socket = socketInstances[0]
    socket.onmessage?.({
      data: JSON.stringify({
        type: 'ready',
        iceServers: [{ urls: ['turn:avatar.example'] }],
      }),
    } as MessageEvent)
    await vi.waitFor(() => expect(sent).toHaveLength(2))

    const peer = peerInstances[0]
    expect(peer.configuration).toEqual({
      iceServers: [{ urls: ['turn:avatar.example'] }],
    })
    expect(peer.addTransceiver).toHaveBeenNthCalledWith(1, 'video', { direction: 'sendrecv' })
    expect(peer.addTransceiver).toHaveBeenNthCalledWith(2, 'audio', { direction: 'sendrecv' })
    const offerFrame = JSON.parse(String(sent[1]))
    expect(offerFrame.type).toBe('avatar_connect')
    expect(JSON.parse(atob(offerFrame.clientSdp))).toEqual({
      type: 'offer',
      sdp: 'client-offer',
    })

    socket.onmessage?.({ data: new Int16Array([1, 2]).buffer } as MessageEvent)
    expect(createBuffer).toHaveBeenCalledTimes(1)
    peer.ontrack?.({ track: avatarAudio } as unknown as RTCTrackEvent)
    peer.ontrack?.({ track: avatarVideo } as unknown as RTCTrackEvent)
    socket.onmessage?.({ data: new Int16Array([3, 4]).buffer } as MessageEvent)
    expect(createBuffer).toHaveBeenCalledTimes(1)
    expect(onAvatarStream).toHaveBeenCalled()
    expect(onState).toHaveBeenCalledWith('listening')

    const answer = btoa(JSON.stringify({ type: 'answer', sdp: 'server-answer' }))
    socket.onmessage?.({
      data: JSON.stringify({ type: 'avatar_answer', serverSdp: answer }),
    } as MessageEvent)
    await vi.waitFor(() => expect(peer.setRemoteDescription).toHaveBeenCalledWith({
      type: 'answer',
      sdp: 'server-answer',
    }))

    call.close()
    expect(inputTrack.stop).toHaveBeenCalled()
    expect(avatarAudio.stop).toHaveBeenCalled()
    expect(avatarVideo.stop).toHaveBeenCalled()
    expect(peer.close).toHaveBeenCalled()
  })
})
