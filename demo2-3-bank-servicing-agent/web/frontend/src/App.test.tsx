import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const mocks = vi.hoisted(() => ({
  account: null as { name: string; username: string } | null,
  getAccessToken: vi.fn(),
  sendMessage: vi.fn(),
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
  createVoiceSession: vi.fn(),
  decideReview: vi.fn(),
  getMetrics: vi.fn(),
  getReviewQueue: vi.fn(),
  sendMessage: mocks.sendMessage,
  submitFeedback: vi.fn(),
}))

describe('Bank Servicing Agent shell', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    mocks.account = null
    vi.clearAllMocks()
  })

  it('requires sign-in before showing agent controls', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /banking answers with evidence/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in to continue/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/workspace mode/i)).not.toBeInTheDocument()
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

    const sourceList = screen.getByLabelText(/iq source activity/i)
    expect(sourceList).toHaveTextContent('Working')
    expect(screen.getAllByText('Checking…')).toHaveLength(3)
  })
})
