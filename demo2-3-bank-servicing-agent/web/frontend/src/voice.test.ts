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
        queueMicrotask(() => this.onopen?.())
      }

      send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
        sent.push(data)
      }

      close() {
        this.onclose?.()
      }
    }

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

    const call = new VoiceCall({
      onState: vi.fn(),
      onTranscript: vi.fn(),
      onError: vi.fn(),
    })
    await call.connect('wss://bank.example/api/voice/live', 'opaque-handle')

    expect(openedUrl).toBe('wss://bank.example/api/voice/live')
    expect(sent[0]).toBe('{"type":"auth","sessionHandle":"opaque-handle"}')
    call.close()
  })
})
