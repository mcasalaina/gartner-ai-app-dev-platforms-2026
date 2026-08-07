import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface CitationPill {
  href: string
  label: string
  source: 'fabric' | 'foundry' | 'work' | 'workflow'
}

const CITATION_PILLS: Record<string, CitationPill> = {
  F: { href: '#iq-fabric', label: 'FabricIQ: Data', source: 'fabric' },
  P: { href: '#iq-foundry', label: 'FoundryIQ: Document', source: 'foundry' },
  S: { href: '#iq-foundry', label: 'FoundryIQ: Document', source: 'foundry' },
  W: { href: '#iq-work', label: 'WorkIQ: Email', source: 'work' },
  C: { href: '#iq-workflow', label: 'Agent: Workflow', source: 'workflow' },
}

const PILLS_BY_HREF = Object.fromEntries(
  Object.values(CITATION_PILLS).map((pill) => [pill.href, pill]),
)

const CITATION_SEQUENCE = /(?:[ \t]*\[[FPSWC]\d+\])+/g
const CITATION_TOKEN = /\[([FPSWC])\d+\]/g

function renderCitationPills(content: string): string {
  return content.replace(CITATION_SEQUENCE, (sequence) => {
    const pills = new Map<string, CitationPill>()
    for (const match of sequence.matchAll(CITATION_TOKEN)) {
      const pill = CITATION_PILLS[match[1]]
      pills.set(pill.href, pill)
    }

    const leadingSpace = /^[ \t]/.test(sequence) ? ' ' : ''
    const links = [...pills.values()]
      .map((pill) => `[${pill.label}](${pill.href})`)
      .join(' ')
    return `${leadingSpace}${links}`
  })
}

const MARKDOWN_COMPONENTS: Components = {
  a({ children, href, title }) {
    const pill = href ? PILLS_BY_HREF[href] : undefined
    if (pill) {
      return (
        <span
          aria-label={`${pill.label} citation`}
          className={`source-citation source-citation-${pill.source}`}
          title={`${pill.label} evidence`}
        >
          {pill.label}
        </span>
      )
    }

    return <a href={href} title={title}>{children}</a>
  },
}

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="message-content">
      <ReactMarkdown components={MARKDOWN_COMPONENTS} remarkPlugins={[remarkGfm]}>
        {renderCitationPills(content)}
      </ReactMarkdown>
    </div>
  )
}
