import type {
  ChatResponse,
  DemoMode,
  ModelComparison,
  QualityMetrics,
  ReviewDraft,
  VoiceSession,
} from './types'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''

interface VoiceHandleResponse {
  sessionHandle: string
  agentSessionId: string
  expiresAt: string
}

function voiceWebsocketUrl(): string {
  const base = apiBase || window.location.origin
  const url = new URL('/api/voice/live', base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

async function request<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(body.detail ?? `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export function sendMessage(
  token: string,
  mode: DemoMode,
  content: string,
  conversationId?: string,
): Promise<ChatResponse> {
  return request<ChatResponse>('/api/chat', token, {
    method: 'POST',
    body: JSON.stringify({ mode, content, conversationId }),
  })
}

export function createVoiceSession(
  token: string,
  mode: DemoMode,
): Promise<VoiceSession> {
  return request<VoiceHandleResponse>('/api/voice/handles', token, {
    method: 'POST',
    headers: {
      'x-client-demo-mode': mode,
    },
    body: JSON.stringify({ clientContext: 'web' }),
  }).then((response) => ({
    handle: response.sessionHandle,
    agentSessionId: response.agentSessionId,
    expiresAt: response.expiresAt,
    websocketUrl: voiceWebsocketUrl(),
  }))
}

export function submitFeedback(
  token: string,
  messageId: string,
  sentiment: 'positive' | 'negative',
): Promise<void> {
  return request<void>('/api/feedback', token, {
    method: 'POST',
    body: JSON.stringify({ messageId, sentiment }),
  })
}

export function getMetrics(token: string): Promise<QualityMetrics> {
  return request<QualityMetrics>('/api/admin/metrics', token)
}

export function getReviewQueue(token: string): Promise<ReviewDraft[]> {
  return request<ReviewDraft[]>('/api/admin/content/reviews', token)
}

export function decideReview(
  token: string,
  draftId: string,
  decision: 'approve' | 'reject',
): Promise<ReviewDraft> {
  return request<ReviewDraft>(`/api/admin/content/reviews/${draftId}/${decision}`, token, {
    method: 'POST',
  })
}

export function compareModels(
  token: string,
  prompt: string,
): Promise<ModelComparison[]> {
  return request<ModelComparison[]>('/api/admin/evaluations/compare', token, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}
