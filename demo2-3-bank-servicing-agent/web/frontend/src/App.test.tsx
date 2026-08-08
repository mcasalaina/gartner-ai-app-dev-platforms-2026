import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const mocks = vi.hoisted(() => ({
  account: null as { name: string; username: string } | null,
  createVoiceSession: vi.fn(),
  getAccessToken: vi.fn(),
  sendMessage: vi.fn(),
  voiceSetMuted: vi.fn(),
  voiceCallbacks: null as {
    onState: (state: string) => void
    onTranscript: (role: 'user' | 'assistant', text: string) => void
    onAvatarStream: (stream: MediaStream) => void
    onError: (message: string) => void
  } | null,
}))

vi.mock('./auth/authContext', () => ({
  useAuth: () => ({
    account: mocks.account,
    initializing: false,
    configurationError: null,
    isReviewer: false,
    isAdmin: false,
    signIn: vi.fn(),
    signOut: vi.fn(),
    getAccessToken: mocks.getAccessToken,
  }),
}))

vi.mock('./api', () => ({
  compareModels: vi.fn(),
  createVoiceSession: mocks.createVoiceSession,
  decideReview: vi.fn(),
  getMetrics: vi.fn(),
  getReviewQueue: vi.fn(),
  sendMessage: mocks.sendMessage,
  submitFeedback: vi.fn(),
}))

vi.mock('./voice', () => ({
  VoiceCall: class {
    constructor(callbacks: NonNullable<typeof mocks.voiceCallbacks>) {
      mocks.voiceCallbacks = callbacks
    }

    connect = vi.fn().mockResolvedValue(undefined)
    close = vi.fn()
    setMuted = mocks.voiceSetMuted
  },
}))

describe('Bank Servicing Agent shell', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    mocks.account = null
    mocks.voiceCallbacks = null
    vi.clearAllMocks()
  })

  it('requires sign-in before showing agent controls', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /banking answers with evidence/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in to continue/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/workspace mode/i)).not.toBeInTheDocument()
  })

  it('offers the standard multilingual talking avatar after sign-in', () => {
    mocks.account = { name: 'Marco', username: 'marco@example.com' }

    render(<App />)

    expect(screen.getByRole('button', { name: 'Talk with Avatar' })).toBeInTheDocument()
    expect(screen.getByLabelText('Avatar tone')).toHaveValue('professional')
    expect(screen.getByText('Meet the Avatar')).toBeInTheDocument()
    expect(screen.getByText('Alloy Multilingual')).toBeInTheDocument()
  })

  it('mutes and restores the microphone without ending the avatar session', async () => {
    mocks.account = { name: 'Marco', username: 'marco@example.com' }
    mocks.getAccessToken.mockResolvedValue('access-token')
    mocks.createVoiceSession.mockResolvedValue({
      handle: 'opaque-handle',
      websocketUrl: 'wss://bank.example/api/voice/live',
      expiresAt: '2026-08-04T20:02:00Z',
    })

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'Talk with Avatar' }))
    await vi.waitFor(() => expect(mocks.voiceCallbacks).not.toBeNull())
    act(() => {
      mocks.voiceCallbacks?.onState('listening')
    })

    fireEvent.click(screen.getByRole('button', { name: 'Mute microphone' }))
    expect(mocks.voiceSetMuted).toHaveBeenCalledWith(true)
    expect(screen.getByRole('button', { name: 'Unmute microphone' })).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(screen.getByRole('button', { name: 'Unmute microphone' }))
    expect(mocks.voiceSetMuted).toHaveBeenLastCalledWith(false)
    expect(screen.getByRole('button', { name: 'Mute microphone' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('applies the selected tone and navigates only from finalized user speech', async () => {
    mocks.account = { name: 'Marco', username: 'marco@example.com' }
    mocks.getAccessToken.mockResolvedValue('access-token')
    mocks.createVoiceSession.mockResolvedValue({
      handle: 'opaque-handle',
      websocketUrl: 'wss://bank.example/api/voice/live',
      expiresAt: '2026-08-04T20:02:00Z',
    })

    render(<App />)
    fireEvent.change(screen.getByLabelText('Avatar tone'), { target: { value: 'warm' } })
    fireEvent.click(screen.getByRole('button', { name: 'Talk with Avatar' }))

    await vi.waitFor(() => {
      expect(mocks.createVoiceSession).toHaveBeenCalledWith('access-token', 'warm')
    })
    await vi.waitFor(() => expect(mocks.voiceCallbacks).not.toBeNull())
    act(() => {
      mocks.voiceCallbacks?.onTranscript('assistant', 'You can verify your identity here.')
    })
    expect(screen.getByRole('button', { name: 'Customer servicing' })).not.toHaveClass('mode-tab-active')

    act(() => {
      mocks.voiceCallbacks?.onTranscript('user', 'Quiero verificar mi identidad.')
    })
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Avatar opened Customer servicing for this topic.',
    )
    expect(screen.getByRole('button', { name: 'Customer servicing' })).toHaveClass('mode-tab-active')
    expect(screen.getByText('Quiero verificar mi identidad.')).toBeInTheDocument()

    act(() => {
      mocks.voiceCallbacks?.onTranscript('user', 'Take me back to compare banking products.')
    })
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Avatar opened Explore services for this topic.',
    )
    expect(screen.getByRole('button', { name: 'Explore services' })).toHaveClass('mode-tab-active')
    expect(screen.getByText('Quiero verificar mi identidad.')).toBeInTheDocument()
    expect(screen.getByText('Take me back to compare banking products.')).toBeInTheDocument()
  })

  it('shows the grounding services used by an assistant response', async () => {
    mocks.account = { name: 'Marco', username: 'marco@example.com' }
    mocks.getAccessToken.mockResolvedValue('access-token')
    mocks.sendMessage.mockResolvedValue({
      conversationId: 'conversation-1',
      quality: { passed: true, repaired: false, citationCount: 1 },
      message: {
        id: 'response-1',
        role: 'assistant',
        content: '## Grounded answer\n\n- Fabric account evidence [F1][F2]\n- Policy evidence [P1]\n- Work context [W1]',
        createdAt: '2026-08-04T20:00:00Z',
        citations: [{ id: 'source-1', title: 'Unlinked source' }],
        queriedSources: ['Fabric IQ', 'Foundry IQ', 'Work IQ'],
        groundingSources: ['Fabric IQ', 'Foundry IQ'],
        traceId: 'response-1',
      },
    })

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /try this question/i }))

    const sourceList = await screen.findByLabelText(/iq source activity/i)
    expect(sourceList).toHaveTextContent('Fabric IQCustomer and account dataReturned')
    expect(sourceList).toHaveTextContent('Foundry IQPolicy documentsReturned')
    expect(sourceList).toHaveTextContent('Work IQEmail and work contextQueried')

    expect(await screen.findByRole('heading', { name: 'Grounded answer' })).toBeInTheDocument()
    expect(screen.getAllByText('FabricIQ: Data')).toHaveLength(1)
    expect(screen.getByText('FoundryIQ: Document')).toBeInTheDocument()
    expect(screen.getByText('WorkIQ: Email')).toBeInTheDocument()
    expect(screen.queryByText(/\[F1\]|\[P1\]|\[W1\]/)).not.toBeInTheDocument()
    expect(screen.queryByText('Unlinked source')).not.toBeInTheDocument()

    const iqHeading = screen.getByRole('heading', { name: 'Live IQ grounding' })
    const runtimeHeading = screen.getByRole('heading', { name: 'Runtime' })
    expect(iqHeading.compareDocumentPosition(runtimeHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('shows source checks in the right rail while a response is pending', async () => {
    mocks.account = { name: 'Marco', username: 'marco@example.com' }
    mocks.getAccessToken.mockResolvedValue('access-token')
    mocks.sendMessage.mockReturnValue(new Promise(() => undefined))

    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /try this question/i }))

    await screen.findByText('Working')
    const sourceList = screen.getByLabelText(/iq source activity/i)
    expect(sourceList).toHaveTextContent('Working')
    expect(screen.getAllByText('Checking…')).toHaveLength(3)
  })
})
