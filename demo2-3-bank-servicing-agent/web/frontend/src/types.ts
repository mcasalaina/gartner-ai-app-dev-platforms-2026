export type DemoMode = 'service_discovery' | 'customer_servicing'
export type WorkspaceView = DemoMode | 'quality_admin'
export type GroundingSource = 'Fabric IQ' | 'Foundry IQ' | 'Work IQ'

export interface Citation {
  id: string
  title: string
  url?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  citations?: Citation[]
  queriedSources?: GroundingSource[]
  groundingSources?: GroundingSource[]
  traceId?: string
}

export interface ChatResponse {
  message: ChatMessage
  conversationId: string
  quality: {
    passed: boolean
    repaired: boolean
    citationCount: number
  }
}

export interface VoiceSession {
  handle: string
  websocketUrl: string
  agentSessionId: string
  expiresAt: string
}

export interface QualityMetrics {
  comprehensiveness: number | null
  accuracy: number | null
  latencyP50Ms: number | null
  estimatedCostUsd: number | null
}

export interface ReviewDraft {
  id: string
  title: string
  status: 'pending_review' | 'approved' | 'rejected' | 'published'
  version: number
  summary: string
}

export interface ModelComparison {
  model: string
  output: string
  rubricScore: number | null
  assertScore: number | null
  latencyMs: number
  estimatedCostUsd: number | null
}
