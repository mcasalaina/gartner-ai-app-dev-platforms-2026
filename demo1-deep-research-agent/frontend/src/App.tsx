import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowDown,
  ArrowRight,
  Check,
  CircleAlert,
  Download,
  FileAudio,
  FileChartColumn,
  FileText,
  Globe2,
  Image,
  LoaderCircle,
  Pause,
  Search,
  Sparkles,
  Upload,
  Users,
  AudioLines,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import {
  API_BASE,
  approveRun,
  createRun,
  getRun,
  savePlan,
  streamRun,
} from './api'
import type {
  PlanSection,
  ResearchPlan,
  ResearchRun,
  StageStatus,
} from './types'
import './App.css'

const BANK_PROMPT = `Design the strategy and operating model for a new investment bank located near the Texas Stock Exchange in Dallas. The bank will offer retail and commercial checking, savings, retirement, investment, and advisory services across the United States, Europe, and China. Research the market opportunity, exchange landscape, regulatory obligations, customer needs, fraud and KYC controls, technology platform, and prioritized service portfolio. Produce an evidence-backed executive recommendation with citations.`

const capabilities = [
  ['PLAN', 'GPT-5.4 MINI'],
  ['RESEARCH', 'GPT-5.4 MINI'],
  ['GROUND', 'WEB IQ'],
  ['CREATE', 'FLUX 1.1 PRO'],
  ['NARRATE', 'AZURE SPEECH'],
  ['OBSERVE', 'APP INSIGHTS'],
]

const stageGlyph: Record<string, typeof Search> = {
  plan: Sparkles,
  approval: Pause,
  research: Users,
  review: Search,
  synthesis: FileText,
  artifacts: AudioLines,
}

function StatusMark({ status }: { status: StageStatus }) {
  if (status === 'running') return <LoaderCircle className="spin" size={17} />
  if (status === 'complete') return <Check size={17} />
  if (status === 'failed') return <CircleAlert size={17} />
  return <span className="pending-dot" />
}

function App() {
  const [prompt, setPrompt] = useState(BANK_PROMPT)
  const [depth, setDepth] = useState('executive')
  const [files, setFiles] = useState<File[]>([])
  const [run, setRun] = useState<ResearchRun>()
  const [planDraft, setPlanDraft] = useState<ResearchPlan>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const workspaceRef = useRef<HTMLElement>(null)

  const refresh = useCallback(async (runId: string) => {
    const current = await getRun(runId)
    setRun(current)
    if (current.plan && current.status === 'awaiting_approval') {
      setPlanDraft((existing) => existing ?? current.plan)
    }
  }, [])

  useEffect(() => {
    if (!run?.id) return
    const controller = new AbortController()
    streamRun(
      run.id,
      controller.signal,
      () => void refresh(run.id),
      (streamError) => setError(streamError.message),
    )
    return () => controller.abort()
  }, [run?.id, refresh])

  const startResearch = async () => {
    setBusy(true)
    setError(undefined)
    try {
      const created = await createRun(prompt, depth, files)
      setRun(created)
      setTimeout(() => workspaceRef.current?.scrollIntoView({ behavior: 'smooth' }), 80)
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : 'Unable to start run')
    } finally {
      setBusy(false)
    }
  }

  const updateSection = (
    index: number,
    field: keyof Pick<PlanSection, 'title' | 'objective'>,
    value: string,
  ) => {
    if (!planDraft) return
    const sections = planDraft.sections.map((section, sectionIndex) =>
      sectionIndex === index ? { ...section, [field]: value } : section,
    )
    setPlanDraft({ ...planDraft, sections })
  }

  const approve = async () => {
    if (!run || !planDraft) return
    setBusy(true)
    setError(undefined)
    try {
      await savePlan(run.id, planDraft)
      setRun(await approveRun(run.id))
    } catch (approvalError) {
      setError(
        approvalError instanceof Error ? approvalError.message : 'Approval failed',
      )
    } finally {
      setBusy(false)
    }
  }

  const progress = useMemo(() => {
    if (!run) return 0
    return Math.round(
      (run.stages.filter((stage) => stage.status === 'complete').length /
        run.stages.length) *
        100,
    )
  }, [run])

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top">
          <span className="brand-mark">G</span>
          <span>GARTNER DEEP RESEARCH DEMO</span>
        </a>
        <div className="header-meta">
          <span>DEEP RESEARCH SYSTEM</span>
          <span className="live-dot">LIVE FOUNDRY</span>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="eyebrow">
          <span>GARTNER DEMO 01</span>
          <ArrowDown size={15} />
        </div>
        <div className="hero-grid">
          <div className="hero-copy">
            <h1>
              Research at
              <br />
              the speed of
              <br />
              <em>conviction.</em>
            </h1>
            <p>
              A multi-agent strategy council that plans, investigates, challenges,
              and synthesizes the evidence your next decision demands.
            </p>
          </div>
          <div className="research-form">
            <div className="form-kicker">
              <span>01</span>
              <span>DEFINE THE MANDATE</span>
            </div>
            <label htmlFor="prompt">Research brief</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={9}
            />
            <div className="form-row">
              <label>
                Depth
                <select value={depth} onChange={(event) => setDepth(event.target.value)}>
                  <option value="executive">Executive</option>
                  <option value="comprehensive">Comprehensive</option>
                </select>
              </label>
              <label className="upload-control">
                <Upload size={17} />
                Add evidence
                <input
                  type="file"
                  accept=".pdf,.csv,.png,.jpg,.jpeg"
                  multiple
                  onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
                />
              </label>
            </div>
            {files.length > 0 && (
              <div className="file-list">{files.map((file) => file.name).join(' · ')}</div>
            )}
            <button
              className="primary-button"
              disabled={busy || prompt.length < 40}
              onClick={startResearch}
            >
              {busy ? <LoaderCircle className="spin" /> : <Sparkles />}
              Commission research
              <ArrowRight />
            </button>
            {error && <div className="error-banner">{error}</div>}
          </div>
        </div>
      </section>

      <section className="capability-rail" aria-label="Foundry capabilities">
        {capabilities.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>

      {run && (
        <section className="workspace" ref={workspaceRef}>
          <div className="workspace-head">
            <div>
              <span className="section-number">02</span>
              <span className="section-label">LIVE RESEARCH ROOM</span>
            </div>
            <div className="run-progress">
              <span>{run.status.replaceAll('_', ' ')}</span>
              <strong>{progress}%</strong>
            </div>
          </div>

          <div className="workspace-grid">
            <aside className="timeline-panel">
              <div className="panel-title">
                <span>COUNCIL ACTIVITY</span>
                <span>{run.id.slice(0, 8)}</span>
              </div>
              <div className="timeline">
                {run.stages.map((stage) => {
                  const Icon = stageGlyph[stage.id] ?? Search
                  return (
                    <div className={`stage ${stage.status}`} key={stage.id}>
                      <div className="stage-icon">
                        <Icon size={18} />
                      </div>
                      <div>
                        <div className="stage-line">
                          <strong>{stage.label}</strong>
                          <StatusMark status={stage.status} />
                        </div>
                        <span>{stage.actor}</span>
                        {stage.model && <small>{stage.model}</small>}
                        {stage.detail && <p>{stage.detail}</p>}
                      </div>
                    </div>
                  )
                })}
              </div>
            </aside>

            <div className="content-panel">
              {run.status === 'failed' ? (
                <div className="working-state failed-state">
                  <CircleAlert size={54} strokeWidth={1.2} />
                  <span>STAGE FAILURE PRESERVED</span>
                  <h2>The run stopped safely.</h2>
                  <p>{run.error}</p>
                </div>
              ) : run.status === 'awaiting_approval' && planDraft ? (
                <PlanEditor
                  plan={planDraft}
                  busy={busy}
                  onUpdate={updateSection}
                  onApprove={approve}
                />
              ) : run.report_markdown ? (
                <ReportView run={run} />
              ) : (
                <div className="working-state">
                  <Globe2 size={54} strokeWidth={1.2} />
                  <span>LIVE ORCHESTRATION</span>
                  <h2>The council is working.</h2>
                  <p>
                    Every status change reflects a real Foundry agent, model, or tool
                    call. Completed stages remain available if a later service fails.
                  </p>
                  <div className="activity-meter">
                    <span style={{ width: `${Math.max(progress, 7)}%` }} />
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      <footer>
        <span>MICROSOFT FOUNDRY × GARTNER 2026</span>
        <span>DECISION INTELLIGENCE, GROUNDED.</span>
      </footer>
    </main>
  )
}

function PlanEditor({
  plan,
  busy,
  onUpdate,
  onApprove,
}: {
  plan: ResearchPlan
  busy: boolean
  onUpdate: (
    index: number,
    field: keyof Pick<PlanSection, 'title' | 'objective'>,
    value: string,
  ) => void
  onApprove: () => void
}) {
  return (
    <div className="plan-editor">
      <div className="content-kicker">
        <span>HUMAN CHECKPOINT</span>
        <span>REV {plan.revision}</span>
      </div>
      <h2>Challenge the plan before the agents search.</h2>
      <p className="refined-request">{plan.refined_request}</p>
      <div className="plan-sections">
        {plan.sections.map((section, index) => (
          <article key={section.id}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <div>
              <input
                value={section.title}
                aria-label={`Section ${index + 1} title`}
                onChange={(event) => onUpdate(index, 'title', event.target.value)}
              />
              <textarea
                value={section.objective}
                aria-label={`Section ${index + 1} objective`}
                onChange={(event) => onUpdate(index, 'objective', event.target.value)}
              />
              <small>{section.search_questions.length} live search questions</small>
            </div>
          </article>
        ))}
      </div>
      <button className="approve-button" disabled={busy} onClick={onApprove}>
        <Check />
        Approve and launch council
        <ArrowRight />
      </button>
    </div>
  )
}

function ReportView({ run }: { run: ResearchRun }) {
  const reportArtifact = run.artifacts.find((artifact) => artifact.kind === 'report')
  const audioArtifact = run.artifacts.find((artifact) => artifact.kind === 'audio')
  const imageArtifact = run.artifacts.find((artifact) => artifact.kind === 'image')
  const chartArtifact = run.artifacts.find((artifact) => artifact.kind === 'chart')

  return (
    <div className="report-view">
      <div className="content-kicker">
        <span>EXECUTIVE OUTPUT</span>
        <span>{run.citations.length} SOURCES</span>
      </div>
      <div className="report-actions">
        <div>
          <h2>Global bank strategy</h2>
          <p>Live research, reconciled and citation-checked.</p>
        </div>
        {reportArtifact && (
          <a href={`${API_BASE}${reportArtifact.url}`} className="download-button">
            <Download size={18} />
            PDF
          </a>
        )}
      </div>

      {imageArtifact && (
        <img
          className="report-hero"
          src={`${API_BASE}${imageArtifact.url}`}
          alt="Generated visual for the proposed global bank"
        />
      )}

      {run.evaluation && (
        <div className="score-grid">
          {Object.entries(run.evaluation)
            .filter(([name]) => name !== 'passed')
            .map(([name, value]) => (
              <div key={name}>
                <strong>{Math.round(Number(value) * 100)}</strong>
                <span>{name.replaceAll('_', ' ')}</span>
              </div>
            ))}
        </div>
      )}

      <article className="markdown-report">
        <ReactMarkdown>{run.report_markdown}</ReactMarkdown>
      </article>

      {run.highlighted_chapter && (
        <section className="highlight-chapter">
          <span>HIGHLIGHTED CHAPTER</span>
          <h2>Recommended banking services</h2>
          {chartArtifact && (
            <img src={`${API_BASE}${chartArtifact.url}`} alt="Priority service scores" />
          )}
          <ReactMarkdown>{run.highlighted_chapter}</ReactMarkdown>
          {audioArtifact && (
            <div className="audio-card">
              <FileAudio />
              <div>
                <strong>Listen to the chapter</strong>
                <span>Azure Speech · neural narration</span>
              </div>
              <audio controls src={`${API_BASE}${audioArtifact.url}`} />
            </div>
          )}
        </section>
      )}

      <section className="source-list">
        <div className="content-kicker">
          <span>SOURCE REGISTER</span>
          <span>WEB IQ</span>
        </div>
        {run.citations.map((citation) => (
          <a href={citation.url} target="_blank" rel="noreferrer" key={citation.id}>
            <span>{citation.id}</span>
            <div>
              <strong>{citation.title}</strong>
              <small>{citation.publisher ?? new URL(citation.url).hostname}</small>
            </div>
            <ArrowRight size={18} />
          </a>
        ))}
      </section>

      {run.artifacts.length > 0 && (
        <div className="artifact-strip">
          {run.artifacts.map((artifact) => {
            const Icon =
              artifact.kind === 'image'
                ? Image
                : artifact.kind === 'chart'
                  ? FileChartColumn
                  : artifact.kind === 'audio'
                    ? FileAudio
                    : FileText
            return (
              <a href={`${API_BASE}${artifact.url}`} key={artifact.name}>
                <Icon />
                <span>{artifact.name}</span>
                <small>{Math.ceil(artifact.bytes / 1024)} KB</small>
              </a>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default App
