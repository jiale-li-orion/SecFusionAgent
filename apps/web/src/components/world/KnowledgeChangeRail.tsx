import { ArrowUpRight, GitCommitHorizontal } from 'lucide-react'

import type { WorldKnowledgeChange } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

export function KnowledgeChangeRail({ changes, loading, unavailable, onOpenObject }: {
  changes: WorldKnowledgeChange[]
  loading: boolean
  unavailable: boolean
  onOpenObject: (objectId: string, changeId: string) => void
}) {
  const { text } = useI18n()
  return (
    <aside className={`world-change-rail ${unavailable ? 'unavailable' : ''}`} aria-label={text('最近知识变更', 'Recent Knowledge Changes')}>
      <header>
        <GitCommitHorizontal size={13} />
        <div><small>{text('知识变化轨', 'KNOWLEDGE CHANGE RAIL')}</small><strong>{loading ? '…' : unavailable ? '—' : changes.length}</strong></div>
        <em>{text('durable revisions', 'DURABLE REVISIONS')}</em>
      </header>
      {!loading && !unavailable && changes.length === 0 && (
        <p>{text('当前没有 durable KnowledgeChange；核心保持静默。', 'No durable KnowledgeChange is present; the core remains quiet.')}</p>
      )}
      {changes.slice(0, 3).map((change) => {
        const objectId = change.object_ids[0] ?? null
        return (
          <button
            key={change.change_id}
            type="button"
            disabled={!objectId}
            onClick={() => objectId && onOpenObject(objectId, change.change_id)}
          >
            <span>R{change.revision}</span>
            <div>
              <strong>O{change.object_ids.length} · C{change.claim_ids.length} · R{change.relation_ids.length}</strong>
              <small>{new Date(change.committed_at).toLocaleTimeString()}</small>
            </div>
            {objectId ? <ArrowUpRight size={11} /> : <i />}
          </button>
        )
      })}
      {unavailable && <p>{text('KnowledgeChange read seam 读取失败；不从 canonical write 数量反推变更。', 'KnowledgeChange read seam failed; change events are not inferred from canonical-write counts.')}</p>}
    </aside>
  )
}
