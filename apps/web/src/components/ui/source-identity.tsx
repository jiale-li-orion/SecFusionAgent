import github from '../../assets/sources/github.svg'
import arxiv from '../../assets/sources/arxiv.svg'
import anthropic from '../../assets/sources/anthropic.svg'
import huggingface from '../../assets/sources/huggingface.svg'
import owasp from '../../assets/sources/owasp.svg'
import cisco from '../../assets/sources/cisco.svg'
import paloalto from '../../assets/sources/paloaltonetworks.svg'
import { sourceIdentity } from '../../lib/source-identity'
import './source-identity.css'

const marks: Record<string, string> = { github, arxiv, anthropic, huggingface, owasp, cisco, paloalto }

/** Locally hosted publisher marks. Unknown sources retain their own readable identity. */
export function SourceIdentity({ source, url, compact = false }: { source?: string | null; url?: string | null; compact?: boolean }) {
  const identity = sourceIdentity(source, url)
  const mark = marks[identity.key]
  return <span className={`source-identity ${compact ? 'is-compact' : ''}`}>
    <span className={`source-avatar source-${identity.key}`} aria-hidden="true">{mark ? <img src={mark} alt="" width={20} height={20}/> : identity.initials}</span>
    {!compact && <span className="source-identity-name">{identity.name}</span>}
  </span>
}
