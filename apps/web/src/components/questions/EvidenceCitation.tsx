import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight } from '../ui/icons'
import { getEvidence } from '../../lib/api/intelligence'
import { useI18n } from '../../lib/i18n'
import { evidenceFieldLabel } from '../../lib/intelligencePresentation'
import { readableObjectTitle } from '../../lib/source-identity'
import { SourceIdentity } from '../ui/source-identity'

/** Reads the cited version; never substitutes current object state for source evidence. */
export function EvidenceCitation({ evidenceRef, index, onOpen }: { evidenceRef: string; index: number; onOpen: (ref: string) => void }) {
  const { text } = useI18n()
  const evidence = useQuery({ queryKey: ['evidence-overlay', evidenceRef], queryFn: () => getEvidence(evidenceRef), staleTime: 60_000, retry: false })
  const item = evidence.data
  const label = item ? evidenceFieldLabel(item.target.label, text) : ''
  const title = item ? readableObjectTitle(item.observation.external_object_id, item.observation.canonical_url, item.source.source_id) : text(`证据 ${index + 1}`, `Evidence ${index + 1}`)
  return <button className="qa-source-citation" onClick={() => onOpen(evidenceRef)} title={evidenceRef}>
    <span className="qa-citation-index">{String(index + 1).padStart(2, '0')}</span>
    <span className="qa-citation-content">
      {item && <SourceIdentity source={item.source.source_id} url={item.observation.canonical_url}/>}
      <strong>{title}</strong>
      <small>{item ? label : evidence.isError ? text('摘要暂不可用，点击重试读取原始证据', 'Preview unavailable. Open to retry the source evidence.') : text('正在读取来源…', 'Loading source…')}</small>
    </span>
    <ArrowUpRight size={15}/>
  </button>
}
