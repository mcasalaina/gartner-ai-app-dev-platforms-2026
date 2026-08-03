export type RunStatus =
  | 'planning'
  | 'awaiting_approval'
  | 'researching'
  | 'synthesizing'
  | 'generating_artifacts'
  | 'complete'
  | 'failed'
  | 'cancelled'

export type StageStatus = 'pending' | 'running' | 'complete' | 'failed'

export interface PlanSection {
  id: string
  title: string
  objective: string
  search_questions: string[]
  evaluation_criteria: string[]
}

export interface ResearchPlan {
  refined_request: string
  objectives: string[]
  assumptions: string[]
  methods: string[]
  evaluation_criteria: string[]
  sections: PlanSection[]
  revision: number
}

export interface WorkflowStage {
  id: string
  label: string
  actor: string
  model?: string
  status: StageStatus
  detail?: string
}

export interface Citation {
  id: string
  title: string
  url: string
  publisher?: string
  published_at?: string
  claims: string[]
}

export interface Artifact {
  name: string
  kind: string
  url: string
  content_type: string
  bytes: number
}

export interface EvaluationSummary {
  groundedness: number
  citation_completeness: number
  plan_coverage: number
  source_quality: number
  passed: boolean
}

export interface ResearchRun {
  id: string
  prompt: string
  research_depth: string
  status: RunStatus
  created_at: string
  updated_at: string
  plan?: ResearchPlan
  stages: WorkflowStage[]
  report_markdown?: string
  highlighted_chapter?: string
  citations: Citation[]
  artifacts: Artifact[]
  evaluation?: EvaluationSummary
  error?: string
}
