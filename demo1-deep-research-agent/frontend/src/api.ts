import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { ResearchPlan, ResearchRun } from './types'

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? 'Request failed')
  }
  return response.json()
}

export async function createRun(
  prompt: string,
  depth: string,
  files: File[],
): Promise<ResearchRun> {
  const form = new FormData()
  form.append('prompt', prompt)
  form.append('research_depth', depth)
  files.forEach((file) => form.append('files', file))
  return request<ResearchRun>('/api/runs', { method: 'POST', body: form })
}

export function getRun(runId: string): Promise<ResearchRun> {
  return request<ResearchRun>(`/api/runs/${runId}`)
}

export function savePlan(
  runId: string,
  plan: ResearchPlan,
): Promise<ResearchRun> {
  return request<ResearchRun>(`/api/runs/${runId}/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  })
}

export function approveRun(runId: string): Promise<ResearchRun> {
  return request<ResearchRun>(`/api/runs/${runId}/approve`, { method: 'POST' })
}

export function streamRun(
  runId: string,
  signal: AbortSignal,
  onEvent: () => void,
  onError: (error: Error) => void,
): void {
  void fetchEventSource(`${API_BASE}/api/runs/${runId}/events`, {
    signal,
    openWhenHidden: true,
    onmessage(message) {
      onEvent()
      if (message.event === 'stream.closed') {
        return
      }
    },
    onerror(error) {
      onError(error instanceof Error ? error : new Error('Event stream failed'))
      throw error
    },
  })
}
