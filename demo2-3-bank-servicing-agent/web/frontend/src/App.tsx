import { useEffect, useMemo, useRef, useState } from 'react'
import {
  compareModels,
  createVoiceSession,
  decideReview,
  getMetrics,
  getReviewQueue,
  sendMessage,
  submitFeedback,
} from './api'
import { useAuth } from './auth/authContext'
import { MarkdownMessage } from './MarkdownMessage'
import type {
  AvatarTone,
  ChatMessage,
  DemoMode,
  GroundingSource,
  ModelComparison,
  QualityMetrics,
  ReviewDraft,
  WorkspaceView,
} from './types'
import { VoiceCall, type VoiceState } from './voice'
import './App.css'

const MODE_COPY: Record<DemoMode, { title: string; description: string; prompt: string }> = {
  service_discovery: {
    title: 'Explore bank services',
    description: 'Grounded service guidance, cited research, approved images, and a multilingual avatar.',
    prompt: "Maria Garcia called about a $35 ATM fee on her checking account ending in 1013. Is the fee eligible for a refund, does anyone need to approve it, and have I received a recent message from Maria about the issue?",
  },
  customer_servicing: {
    title: 'Manage your banking',
    description: 'Customer-scoped account guidance and a controlled account-opening workflow.',
    prompt: 'I want to open a checking account. What information and identity checks do you need from me, and what happens before the account is opened?',
  },
}

const INITIAL_METRICS: QualityMetrics = {
  comprehensiveness: null,
  accuracy: null,
  latencyP50Ms: null,
  estimatedCostUsd: null,
}

const GROUNDING_SOURCES: GroundingSource[] = ['Fabric IQ', 'Foundry IQ', 'Work IQ']
const VOICE_STATE_LABELS: Record<'idle' | Exclude<VoiceState, 'ended'>, string> = {
  idle: 'Avatar ready',
  connecting: 'Avatar connecting',
  listening: 'Avatar listening',
  speaking: 'Avatar speaking',
  reconnecting: 'Avatar reconnecting',
  failed: 'Avatar unavailable',
}
type SourceActivityStatus = 'idle' | 'checking' | 'queried' | 'returned' | 'error'
type SourceActivity = Record<GroundingSource, SourceActivityStatus>

const SOURCE_DETAILS: Record<GroundingSource, string> = {
  'Fabric IQ': 'Customer and account data',
  'Foundry IQ': 'Policy documents',
  'Work IQ': 'Email and work context',
}

const SOURCE_STATUS_LABELS: Record<SourceActivityStatus, string> = {
  idle: 'Ready',
  checking: 'Checking…',
  queried: 'Queried',
  returned: 'Returned',
  error: 'Request failed',
}

function sourceActivity(status: SourceActivityStatus): SourceActivity {
  return {
    'Fabric IQ': status,
    'Foundry IQ': status,
    'Work IQ': status,
  }
}

function sourceActivityFromMessage(message: ChatMessage): SourceActivity {
  const activity = sourceActivity('idle')
  for (const source of GROUNDING_SOURCES) {
    if (message.groundingSources?.includes(source)) {
      activity[source] = 'returned'
    } else if (message.queriedSources?.includes(source)) {
      activity[source] = 'queried'
    }
  }
  return activity
}

function score(value: number | null, digits = 2): string {
  return value === null ? 'Not available' : value.toFixed(digits)
}

function newMessage(role: ChatMessage['role'], content: string): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    createdAt: new Date().toISOString(),
  }
}

function avatarDestination(text: string): DemoMode | null {
  const normalized = text.toLocaleLowerCase()
  if (/\b(open|application|kyc|identity|verify|dispute|fee|statement|abrir|solicitud|identidad|verificar|disputa|tarifa|estado de cuenta)\b/.test(normalized)) {
    return 'customer_servicing'
  }
  if (/\b(compare|service|product|rate|feature|offering|benefit|comparar|servicio|producto|tasa|opción|beneficio)\b/.test(normalized)) {
    return 'service_discovery'
  }
  return null
}

function Header() {
  const { account, signIn, signOut, configurationError } = useAuth()
  const [error, setError] = useState<string | null>(null)

  async function handleSignIn() {
    setError(null)
    try {
      await signIn()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed.')
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">BS</div>
          <div>
            <p className="brand-name">Bank Servicing Agent</p>
            <p className="brand-subtitle">Microsoft Foundry · Gartner Demos 2 through 4</p>
          </div>
        </div>
        <div className="topbar-actions">
          {account ? (
            <>
              <span className="muted">{account.name ?? account.username}</span>
              <button className="button" type="button" onClick={() => void signOut()}>
                Sign out
              </button>
            </>
          ) : (
            <button
              className="button button-primary"
              type="button"
              disabled={Boolean(configurationError)}
              onClick={() => void handleSignIn()}
            >
              Sign in to continue
            </button>
          )}
        </div>
      </header>
      {(error || configurationError) && (
        <div className="error-banner" role="alert">{error ?? configurationError}</div>
      )}
    </>
  )
}

function Landing() {
  return (
    <main className="landing">
      <section>
        <p className="eyebrow">Secure, grounded banking assistance</p>
        <h1>Banking answers with evidence.</h1>
        <p className="landing-copy">
          Discover services, speak with a photorealistic multilingual avatar, and prepare
          a checking account application. Sign-in is required before the agent can access
          any experience or customer-scoped data.
        </p>
        <div className="chip-row">
          <span className="chip">gpt-5.4-mini</span>
          <span className="chip">Foundry IQ</span>
          <span className="chip">Voice Live</span>
          <span className="chip">Photo avatar</span>
        </div>
      </section>
      <section className="capability-grid" aria-label="Capabilities">
        <article className="capability-card">
          <h2>Explore services</h2>
          <p>Detailed text, approved images, generated media, and citations to approved research.</p>
        </article>
        <article className="capability-card">
          <h2>Customer servicing</h2>
          <p>Identity-scoped account and investment guidance with explicit KYC confirmation.</p>
        </article>
        <article className="capability-card">
          <h2>Built-in controls</h2>
          <p>Bank-domain guardrails, salary DLP, quality gates, human review, and feedback.</p>
        </article>
        <article className="capability-card">
          <h2>Talking avatar</h2>
          <p>Photorealistic, multilingual guidance with synchronized speech and safe menu navigation.</p>
        </article>
      </section>
    </main>
  )
}

function ConversationWorkspace({
  mode,
  onSourceActivity,
  onNavigate,
}: {
  mode: DemoMode
  onSourceActivity: (activity: SourceActivity) => void
  onNavigate: (destination: DemoMode) => void
}) {
  const { getAccessToken } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string>()
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [voiceState, setVoiceState] = useState<'idle' | Exclude<VoiceState, 'ended'>>('idle')
  const [voiceMuted, setVoiceMuted] = useState(false)
  const [hasAvatarStream, setHasAvatarStream] = useState(false)
  const [mediaBlocked, setMediaBlocked] = useState(false)
  const [tone, setTone] = useState<AvatarTone>('professional')
  const [navigationNotice, setNavigationNotice] = useState<string | null>(null)
  const voiceRef = useRef<VoiceCall | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const modeRef = useRef(mode)
  modeRef.current = mode
  const copy = MODE_COPY[mode]

  useEffect(() => {
    setConversationId(undefined)
    setDraft('')
    setError(null)
    onSourceActivity(sourceActivity('idle'))
  }, [mode, onSourceActivity])

  useEffect(() => () => {
    voiceRef.current?.close()
    voiceRef.current = null
  }, [])

  async function submit(content: string) {
    const trimmed = content.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError(null)
    let sourceRequestStarted = false
    try {
      const token = await getAccessToken()
      sourceRequestStarted = true
      onSourceActivity(sourceActivity('checking'))
      setMessages((current) => [...current, newMessage('user', trimmed)])
      setDraft('')
      const response = await sendMessage(token, mode, trimmed, conversationId)
      setConversationId(response.conversationId)
      setMessages((current) => [...current, response.message])
      onSourceActivity(sourceActivityFromMessage(response.message))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The request failed.')
      onSourceActivity(sourceActivity(sourceRequestStarted ? 'error' : 'idle'))
    } finally {
      setBusy(false)
    }
  }

  function clearVoiceMedia() {
    setVoiceMuted(false)
    setHasAvatarStream(false)
    setMediaBlocked(false)
    if (videoRef.current) videoRef.current.srcObject = null
  }

  function endVoice() {
    voiceRef.current?.close()
    voiceRef.current = null
    clearVoiceMedia()
    setVoiceState('idle')
  }

  function toggleMicrophone() {
    const nextMuted = !voiceMuted
    voiceRef.current?.setMuted(nextMuted)
    setVoiceMuted(nextMuted)
  }

  async function startVoice() {
    if (voiceRef.current || voiceState === 'connecting') return
    setError(null)
    clearVoiceMedia()
    setVoiceState('connecting')
    try {
      const token = await getAccessToken()
      const session = await createVoiceSession(token, tone)
      const call = new VoiceCall({
        onState: (state) => {
          setVoiceState(state === 'ended' ? 'idle' : state)
          if (state === 'ended' || state === 'failed') {
            voiceRef.current = null
            clearVoiceMedia()
          }
        },
        onTranscript: (role, text) => {
          setMessages((current) => [...current, newMessage(role, text)])
          if (role !== 'user') return
          const destination = avatarDestination(text)
          if (!destination || destination === modeRef.current) return
          onNavigate(destination)
          setNavigationNotice(
            destination === 'service_discovery'
              ? 'Avatar opened Explore services for this topic.'
              : 'Avatar opened Customer servicing for this topic.',
          )
        },
        onAvatarStream: (stream) => {
          if (!videoRef.current) return
          videoRef.current.srcObject = stream
          setHasAvatarStream(true)
          setMediaBlocked(false)
          void videoRef.current.play().catch(() => {
            setMediaBlocked(true)
          })
        },
        onError: (message) => {
          setError(message)
        },
      })
      voiceRef.current = call
      await call.connect(session.websocketUrl, session.handle)
    } catch (reason) {
      voiceRef.current = null
      setVoiceState('idle')
      setError(reason instanceof Error ? reason.message : 'Voice session failed.')
    }
  }

  function resumeAvatarMedia() {
    if (!videoRef.current) return
    void videoRef.current.play().then(() => {
      setMediaBlocked(false)
    }).catch(() => {
      setError('Your browser blocked avatar playback. Check this site\'s media permissions.')
    })
  }

  const voiceActive = voiceState !== 'idle'

  async function recordFeedback(messageId: string, sentiment: 'positive' | 'negative') {
    try {
      const token = await getAccessToken()
      await submitFeedback(token, messageId, sentiment)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Feedback could not be recorded.')
    }
  }

  return (
    <section className="panel conversation-panel">
      <div className="panel-header">
        <div>
          <h2>{copy.title}</h2>
          <p>{copy.description}</p>
        </div>
        <div className={`voice-status voice-${voiceState} ${voiceState === 'listening' || voiceState === 'speaking' ? 'voice-active' : ''}`}>
          <span className="status-dot" aria-hidden="true" />
          {VOICE_STATE_LABELS[voiceState]}
        </div>
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {navigationNotice && (
        <div className="navigation-banner" role="status">
          {navigationNotice}
          <button type="button" onClick={() => setNavigationNotice(null)}>Dismiss</button>
        </div>
      )}
      <div className={`conversation-body ${voiceActive ? 'conversation-body-avatar' : ''}`}>
        {voiceActive && (
          <section className={`avatar-session avatar-${voiceState}`} aria-label="Avatar call">
            <div className="avatar-visual">
              <video
                ref={videoRef}
                className={hasAvatarStream ? 'avatar-video avatar-video-visible' : 'avatar-video'}
                autoPlay
                playsInline
                aria-label="Talking banking avatar"
                onPlaying={() => setMediaBlocked(false)}
              />
              {!hasAvatarStream && (
                <div className="avatar-placeholder">
                  <span aria-hidden="true">A</span>
                  <strong>{voiceState === 'failed' ? 'Avatar could not connect' : 'Preparing the Avatar'}</strong>
                  <small>{VOICE_STATE_LABELS[voiceState]}</small>
                </div>
              )}
            </div>
            <div className="avatar-call-bar">
              <div>
                <span className="avatar-call-label">Live avatar</span>
                <strong>{voiceMuted ? 'Microphone muted' : VOICE_STATE_LABELS[voiceState]}</strong>
              </div>
              <div className="avatar-call-actions">
                {mediaBlocked && (
                  <button className="button" type="button" onClick={resumeAvatarMedia}>
                    Play avatar
                  </button>
                )}
                {voiceState === 'failed' ? (
                  <button className="button button-primary" type="button" onClick={() => void startVoice()}>
                    Retry
                  </button>
                ) : (
                  <button
                    className={`button ${voiceMuted ? 'button-mute-active' : ''}`}
                    type="button"
                    aria-pressed={voiceMuted}
                    onClick={toggleMicrophone}
                  >
                    {voiceMuted ? 'Unmute microphone' : 'Mute microphone'}
                  </button>
                )}
                <button className="button button-danger" type="button" onClick={endVoice}>
                  End avatar
                </button>
              </div>
            </div>
          </section>
        )}
        <div className="conversation" aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="avatar-intro">
                <span className="avatar-monogram" aria-hidden="true">A</span>
                <div>
                  <strong>Meet the Avatar</strong>
                  <p>Talk naturally in any language, or use text chat below.</p>
                </div>
              </div>
              <p className="eyebrow">Suggested question</p>
              <h3>Start with a natural question</h3>
              <p className="suggested-question">{copy.prompt}</p>
              <button className="button" type="button" onClick={() => void submit(copy.prompt)}>
                Try this question
              </button>
            </div>
          ) : (
            messages.map((message) => (
              <article
                className={`message message-${message.role}`}
                key={message.id}
                aria-label={`${message.role} message`}
              >
                <div className="message-meta">
                  <strong>{message.role === 'assistant' ? 'Bank Servicing Agent' : 'You'}</strong>
                  <span>{new Date(message.createdAt).toLocaleTimeString()}</span>
                </div>
                {message.role === 'assistant'
                  ? <MarkdownMessage content={message.content} />
                  : <p className="message-plain">{message.content}</p>}
                {message.citations?.some((citation) => citation.url) ? (
                  <div className="reference-links" aria-label="Linked source documents">
                    <span>Linked sources</span>
                    {message.citations.filter((citation) => citation.url).map((citation) => (
                      <a className="reference-link" href={citation.url} key={citation.id}>
                        {citation.title}
                      </a>
                    ))}
                  </div>
                ) : null}
                {message.role === 'assistant' && (
                  <div className="button-row">
                    <button className="button button-quiet" type="button" onClick={() => void recordFeedback(message.id, 'positive')}>
                      Helpful
                    </button>
                    <button className="button button-quiet" type="button" onClick={() => void recordFeedback(message.id, 'negative')}>
                      Needs work
                    </button>
                  </div>
                )}
              </article>
            ))
          )}
        </div>
      </div>
      <div className="composer">
        <label className="composer-label" htmlFor="message">Message the agent</label>
        <textarea
          id="message"
          value={draft}
          disabled={busy}
          placeholder="Ask about a bank service or customer task"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              void submit(draft)
            }
          }}
        />
        <div className="composer-actions">
          <div className="voice-launch-controls">
            <label className="tone-control">
              <span>Avatar tone</span>
              <select
                aria-label="Avatar tone"
                value={tone}
                disabled={voiceActive}
                onChange={(event) => setTone(event.target.value as AvatarTone)}
              >
                <option value="professional">Professional</option>
                <option value="warm">Warm</option>
                <option value="energetic">Energetic</option>
              </select>
            </label>
            {!voiceActive && (
              <button className="button button-avatar" type="button" onClick={() => void startVoice()}>
                Talk with Avatar
              </button>
            )}
          </div>
          <button className="button button-primary" type="button" disabled={busy || !draft.trim()} onClick={() => void submit(draft)}>
            {busy ? 'Checking sources…' : 'Send'}
          </button>
        </div>
      </div>
    </section>
  )
}

function AdminWorkspace({ isAdmin }: { isAdmin: boolean }) {
  const { getAccessToken } = useAuth()
  const [metrics, setMetrics] = useState(INITIAL_METRICS)
  const [reviews, setReviews] = useState<ReviewDraft[]>([])
  const [comparison, setComparison] = useState<ModelComparison[]>([])
  const [prompt, setPrompt] = useState('Explain the eligibility rules for reversing an overdraft fee.')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    void getAccessToken()
      .then(async (token) => Promise.all([getMetrics(token), getReviewQueue(token)]))
      .then(([nextMetrics, nextReviews]) => {
        if (active) {
          setMetrics(nextMetrics)
          setReviews(nextReviews)
        }
      })
      .catch((reason) => active && setError(reason instanceof Error ? reason.message : 'Admin data failed.'))
    return () => {
      active = false
    }
  }, [getAccessToken])

  async function review(draftId: string, decision: 'approve' | 'reject') {
    try {
      const token = await getAccessToken()
      const updated = await decideReview(token, draftId, decision)
      setReviews((current) => current.map((item) => item.id === updated.id ? updated : item))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Review action failed.')
    }
  }

  async function runComparison() {
    setBusy(true)
    setError(null)
    try {
      const token = await getAccessToken()
      setComparison(await compareModels(token, prompt))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Model comparison failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="notice-banner">
        Rubric evaluators and Agent Optimizer are preview. ASSERT is beta. Deterministic gates remain independently enforced.
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="metrics-grid">
        <Metric label="Comprehensiveness" value={metrics.comprehensiveness === null ? 'Not available' : `${Math.round(metrics.comprehensiveness * 100)}%`} />
        <Metric label="Accuracy" value={metrics.accuracy === null ? 'Not available' : `${Math.round(metrics.accuracy * 100)}%`} />
        <Metric label="P50 response" value={metrics.latencyP50Ms === null ? 'Not available' : `${metrics.latencyP50Ms} ms`} />
        <Metric label="Estimated cost" value={metrics.estimatedCostUsd === null ? 'Not available' : `$${metrics.estimatedCostUsd.toFixed(3)}`} />
      </div>
      <div className="admin-grid">
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Service description review</h2>
              <p>Only approved versions are published to Foundry IQ.</p>
            </div>
          </div>
          <div className="conversation">
            {reviews.length === 0 ? <p className="muted">No drafts are awaiting review.</p> : reviews.map((draft) => (
              <article className="review-card" key={draft.id}>
                <h3>{draft.title}</h3>
                <p>{draft.summary}</p>
                <div className="chip-row">
                  <span className="chip">v{draft.version}</span>
                  <span className="chip">{draft.status}</span>
                </div>
                {draft.status === 'pending_review' && (
                  <div className="button-row">
                    <button className="button button-primary" type="button" onClick={() => void review(draft.id, 'approve')}>Approve</button>
                    <button className="button button-danger" type="button" onClick={() => void review(draft.id, 'reject')}>Reject</button>
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
        {isAdmin ? <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Multiple-model evaluation lab</h2>
              <p>Customer traffic always uses gpt-5.4-mini.</p>
            </div>
          </div>
          <div className="composer">
            <label htmlFor="comparison-prompt"><strong>Evaluation prompt</strong></label>
            <textarea id="comparison-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            <div className="composer-actions">
              <span className="muted">Rubric + ASSERT scoring</span>
              <button className="button button-primary" type="button" disabled={busy || !prompt.trim()} onClick={() => void runComparison()}>
                {busy ? 'Running…' : 'Compare models'}
              </button>
            </div>
          </div>
          {comparison.length > 0 && (
            <div className="ab-grid">
              {comparison.map((result) => (
                <article className="ab-card" key={result.model}>
                  <h3>{result.model}</h3>
                  <p className="model-output">{result.output}</p>
                  <dl className="status-list">
                    <div className="status-row"><dt>Rubric</dt><dd>{score(result.rubricScore)}</dd></div>
                    <div className="status-row"><dt>ASSERT</dt><dd>{score(result.assertScore)}</dd></div>
                    <div className="status-row"><dt>Latency</dt><dd>{result.latencyMs} ms</dd></div>
                    <div className="status-row"><dt>Cost</dt><dd>{result.estimatedCostUsd === null ? 'Not available' : `$${score(result.estimatedCostUsd, 3)}`}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </section> : (
          <section className="panel">
            <h2>Multiple-model evaluation lab</h2>
            <p className="muted">Administrator access is required to run model comparisons.</p>
          </section>
        )}
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <article className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
    </article>
  )
}

function SourceActivityPanel({ activity }: { activity: SourceActivity }) {
  const checking = GROUNDING_SOURCES.some((source) => activity[source] === 'checking')

  return (
    <section className="panel source-activity-panel" aria-label="IQ source activity" aria-live="polite">
      <div className="source-panel-header">
        <div>
          <h2>Live IQ grounding</h2>
          <p>Trusted runtime evidence</p>
        </div>
        {checking && <span className="live-indicator">Working</span>}
      </div>
      <div className="source-activity-list">
        {GROUNDING_SOURCES.map((source) => {
          const status = activity[source]
          return (
            <div className={`source-activity-row source-status-${status}`} key={source}>
              <span className="source-indicator" aria-hidden="true" />
              <span className="source-identity">
                <strong>{source}</strong>
                <span>{SOURCE_DETAILS[source]}</span>
              </span>
              <span className="source-state">{SOURCE_STATUS_LABELS[status]}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function AuthenticatedWorkspace() {
  const { account, isReviewer, isAdmin } = useAuth()
  const [view, setView] = useState<WorkspaceView>('service_discovery')
  const [sourceActivityState, setSourceActivityState] = useState<SourceActivity>(
    () => sourceActivity('idle'),
  )
  const mode = view === 'customer_servicing' ? 'customer_servicing' : 'service_discovery'
  const roleLabel = useMemo(
    () => isAdmin ? 'Administrator access' : isReviewer ? 'Reviewer access' : 'Customer access',
    [isAdmin, isReviewer],
  )

  return (
    <main className="workspace">
      <div className="main-column">
        <nav className="mode-tabs" aria-label="Workspace mode">
          <button className={`mode-tab ${view === 'service_discovery' ? 'mode-tab-active' : ''}`} type="button" onClick={() => setView('service_discovery')}>Explore services</button>
          <button className={`mode-tab ${view === 'customer_servicing' ? 'mode-tab-active' : ''}`} type="button" onClick={() => setView('customer_servicing')}>Customer servicing</button>
          {isReviewer && <button className={`mode-tab ${view === 'quality_admin' ? 'mode-tab-active' : ''}`} type="button" onClick={() => setView('quality_admin')}>Quality & review</button>}
        </nav>
        {view === 'quality_admin'
          ? <AdminWorkspace isAdmin={isAdmin} />
          : (
            <ConversationWorkspace
              mode={mode}
              onSourceActivity={setSourceActivityState}
              onNavigate={setView}
            />
          )}
      </div>
      <aside className="sidebar">
        <section className="panel">
          <h2>Session security</h2>
          <dl className="status-list">
            <div className="status-row"><dt>Signed in</dt><dd>{account?.name ?? account?.username}</dd></div>
            <div className="status-row"><dt>Access</dt><dd>{roleLabel}</dd></div>
            <div className="status-row"><dt>Identity</dt><dd>On behalf of you</dd></div>
          </dl>
        </section>
        <SourceActivityPanel activity={sourceActivityState} />
        <section className="panel">
          <h2>Runtime</h2>
          <dl className="status-list">
            <div className="status-row"><dt>Model</dt><dd>gpt-5.4-mini</dd></div>
            <div className="status-row"><dt>Avatar</dt><dd>Photo avatar</dd></div>
            <div className="status-row"><dt>Voice</dt><dd>Alloy Multilingual</dd></div>
            <div className="status-row"><dt>Grounding</dt><dd>Fabric IQ + Foundry IQ + Work IQ</dd></div>
            <div className="status-row"><dt>Controls</dt><dd className="chip chip-success">Active</dd></div>
          </dl>
          <p className="footer-note">Salary DLP and bank-domain gates run before downstream tools.</p>
        </section>
      </aside>
    </main>
  )
}

function App() {
  const { account, initializing } = useAuth()
  return (
    <div className="app-shell">
      <Header />
      {initializing ? <main className="landing"><p>Initializing secure sign-in…</p></main> : account ? <AuthenticatedWorkspace /> : <Landing />}
    </div>
  )
}

export default App
