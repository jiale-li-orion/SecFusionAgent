import { useState } from 'react'
import type { EvidenceRef } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import { SourceIdentity } from '../ui/source-identity'
import { sourceIdentity } from '../../lib/source-identity'
import { Button } from '../ui/button'

export function EvidenceCapsules({
  evidence,
  onEvidence,
  compact = false,
}: {
  evidence: EvidenceRef[]
  onEvidence: (ref: string) => void
  compact?: boolean
}) {
  const { text } = useI18n()
  const [expanded, setExpanded] = useState(false)
  if (evidence.length === 0) return <span className="no-evidence">{text('尚无关联证据', 'No linked evidence')}</span>
  const limit = compact ? 2 : 4
  return (
    <div className={`evidence-capsules ${compact ? 'compact' : ''}`}>
      {(expanded ? evidence : evidence.slice(0, limit)).map((item) => (
        <Button
          variant="outline"
          size="sm"
          key={item.evidence_ref}
          onClick={() => onEvidence(item.evidence_ref)}
          title={text(
            `查看 ${sourceIdentity(item.source_id, item.canonical_url).name} 的证据`,
            `Read evidence from ${sourceIdentity(item.source_id, item.canonical_url).name}`,
          )}
        >
          <SourceIdentity source={item.source_id} url={item.canonical_url} />
        </Button>
      ))}
      {evidence.length > limit && (
        <button type="button" className="evidence-expand" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
          {expanded ? text('收起', 'Show less') : text(`查看其余 ${evidence.length - limit} 条`, `View ${evidence.length - limit} more`)}
        </button>
      )}
    </div>
  )
}
