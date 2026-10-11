import { useState } from 'react'
import { ArrowUpRight, ChevronLeft, ChevronRight, GitBranch, X } from 'lucide-react'
import type { EvidenceRef, KnowledgeRelation } from '../../lib/api'
import { evidenceFieldLabel, formatValue } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'
import { SourceIdentity } from '../ui/source-identity'
import { sourceIdentity } from '../../lib/source-identity'
import { Button } from '../ui/button'
import './relation-map.css'

export function FocusedKnowledgeGraph({
  relations,
  totalRelationCount,
  neighborhood,
  loading,
  error,
  selectedLabel,
  objectType,
  onEvidence,
  onLoadMore,
  onOpenTarget,
}: {
  relations: KnowledgeRelation[]
  totalRelationCount: number
  neighborhood: string
  loading: boolean
  error: string | null
  selectedLabel: string
  objectType: string
  onEvidence: (ref: string) => void
  onLoadMore?: () => void
  onOpenTarget: (id: string) => void
}) {
  const { text } = useI18n()
  const [layer, setLayer] = useState('all')
  const [page, setPage] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const layers = [...new Set(relations.map((relation) => relation.target.object_type))].sort()
  const filtered = relations.filter((relation) => layer === 'all' || relation.target.object_type === layer)
  const currentPage = Math.min(page, Math.max(0, Math.ceil(filtered.length / 6) - 1))
  const visible = filtered.slice(currentPage * 6, currentPage * 6 + 6)
  const selected = filtered.find((relation) => relation.relation_id === selectedId)
  function changeLayer(next: string) {
    setLayer(next)
    setPage(0)
    setSelectedId(null)
  }
  return (
    <section className="relation-map">
      <header className="relation-map-heading">
        <div>
          <h2>{text('从对象到关联证据', 'Connections backed by evidence')}</h2>
          <p>
            {text(
              `${totalRelationCount} 条已保留的关系。选择一个节点，查看关联与来源。`,
              `${totalRelationCount} retained relations. Select a node to explore its connection and sources.`,
            )}
          </p>
        </div>
      </header>
      <div className="relation-map-filters">
        <Button
          variant={layer === 'all' ? 'secondary' : 'ghost'}
          size="sm"
          aria-pressed={layer === 'all'}
          onClick={() => changeLayer('all')}
        >
          {text('全部关系', 'All relations')}
        </Button>
        {layers.map((kind) => (
          <Button
            key={kind}
            variant={layer === kind ? 'secondary' : 'ghost'}
            size="sm"
            aria-pressed={layer === kind}
            onClick={() => changeLayer(kind)}
          >
            {objectTypeLabel(kind, text)}
          </Button>
        ))}
      </div>
      {loading ? (
        <div className="relation-map-empty" role="status">
          {text('正在读取关系…', 'Reading relations…')}
        </div>
      ) : error ? (
        <div className="relation-map-empty" role="alert">
          {text('关系暂时无法读取。', 'Relations could not be loaded.')}
          <span>{error}</span>
        </div>
      ) : visible.length ? (
        <>
          <div className="relation-map-scroll">
            <div className="relation-map-canvas">
              <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                {visible.map((relation, index) => {
                  const point = relationPoint(index)
                  return (
                    <path
                      key={relation.relation_id}
                      className={selectedId === relation.relation_id ? 'is-active' : ''}
                      d={`M 50 50 C ${point.x === 16 ? 29 : 71} 50, ${point.x === 16 ? 37 : 63} ${point.y}, ${point.x} ${point.y}`}
                    />
                  )
                })}
              </svg>
              <div className="relation-map-center">
                <span>
                  <GitBranch size={18} />
                  {objectTypeLabel(objectType, text)}
                </span>
                <strong title={selectedLabel}>{selectedLabel}</strong>
              </div>
              {visible.map((relation, index) => {
                const point = relationPoint(index)
                return (
                  <button
                    key={relation.relation_id}
                    className={`relation-map-node ${selectedId === relation.relation_id ? 'is-selected' : ''}`}
                    style={{ left: `${point.x}%`, top: `${point.y}%` }}
                    onClick={() => setSelectedId((current) => (current === relation.relation_id ? null : relation.relation_id))}
                    aria-pressed={selectedId === relation.relation_id}
                  >
                    <small>{evidenceFieldLabel(relation.relation_type, text)}</small>
                    <strong title={relationTitle(relation)}>{relationTitle(relation)}</strong>
                    <span>
                      {objectTypeLabel(relation.target.object_type, text)}
                      <b>
                        {relation.evidence.length} {text('证据', 'refs')}
                      </b>
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
          <div className="relation-map-pagination">
            <span>
              {text(
                `第 ${currentPage * 6 + 1}–${currentPage * 6 + visible.length} 条 · 已读取 ${relations.length}/${totalRelationCount}`,
                `${currentPage * 6 + 1}–${currentPage * 6 + visible.length} · ${relations.length}/${totalRelationCount} loaded`,
              )}
            </span>
            <div>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={currentPage === 0}
                onClick={() => {
                  setPage(currentPage - 1)
                  setSelectedId(null)
                }}
                aria-label={text('上一组关系', 'Previous relations')}
              >
                <ChevronLeft size={15} />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={(currentPage + 1) * 6 >= filtered.length}
                onClick={() => {
                  setPage(currentPage + 1)
                  setSelectedId(null)
                }}
                aria-label={text('下一组关系', 'Next relations')}
              >
                <ChevronRight size={15} />
              </Button>
              {totalRelationCount > relations.length && onLoadMore && (
                <Button variant="outline" size="sm" onClick={onLoadMore}>
                  {text('读取更多', 'Read more')}
                </Button>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="relation-map-empty">
          <GitBranch size={24} />
          <p>{text('这个分类下还没有已保留的关系。', 'No retained relations in this category.')}</p>
        </div>
      )}
      {selected && (
        <section className="relation-map-detail">
          <header>
            <div>
              <small>{evidenceFieldLabel(selected.relation_type, text)}</small>
              <h3>{relationTitle(selected)}</h3>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setSelectedId(null)}
              aria-label={text('收起关系详情', 'Close relation details')}
            >
              <X size={16} />
            </Button>
          </header>
          {Object.keys(selected.qualifier).length > 0 && (
            <dl>
              {Object.entries(selected.qualifier).map(([key, value]) => (
                <div key={key}>
                  <dt>{evidenceFieldLabel(key, text)}</dt>
                  <dd>{formatValue(value)}</dd>
                </div>
              ))}
            </dl>
          )}
          <div className="relation-map-detail-actions">
            <EvidenceCapsules evidence={selected.evidence} onEvidence={onEvidence} />
            <Button variant="outline" size="sm" onClick={() => onOpenTarget(selected.target.object_id)}>
              {text('打开关联档案', 'Open related dossier')}
              <ArrowUpRight size={14} />
            </Button>
          </div>
          <details>
            <summary>{text('关系记录详情', 'Relation record')}</summary>
            <p>
              {selected.origin} · {text('修订', 'Revision')} {selected.created_revision}
            </p>
            <code>{selected.relation_id}</code>
            <code>{selected.target.canonical_key}</code>
          </details>
        </section>
      )}
      <details className="relation-map-ledger">
        <summary>{text('完整关系清单与读取范围', 'All loaded relations and reading scope')}</summary>
        <p>
          {text(
            '仅包含当前对象向外的一跳关系，不代表全量图谱。',
            'Shows outbound, one-hop relations from this object, not the entire graph.',
          )}
          <code>{neighborhood}</code>
        </p>
        {filtered.map((relation) => (
          <article key={relation.relation_id}>
            <div>
              <small>{evidenceFieldLabel(relation.relation_type, text)}</small>
              <strong>{relationTitle(relation)}</strong>
              <EvidenceCapsules evidence={relation.evidence} onEvidence={onEvidence} compact />
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => onOpenTarget(relation.target.object_id)}
              aria-label={text('打开关联档案', 'Open related dossier')}
            >
              <ArrowUpRight size={15} />
            </Button>
          </article>
        ))}
      </details>
    </section>
  )
}

function relationPoint(index: number) {
  return { x: index < 3 ? 16 : 84, y: 20 + (index % 3) * 30 }
}
function relationTitle(relation: KnowledgeRelation) {
  const props = relation.target.properties
  for (const key of ['display_name', 'title', 'full_name', 'name', 'ghsa_id', 'cwe_id', 'ip']) {
    const value = props[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  if (typeof props.product === 'string') return [props.vendor, props.product].filter(Boolean).join(' · ').replaceAll('_', ' ')
  const identifier = Object.values(relation.target.external_identifiers).flat()[0]
  if (identifier) return identifier
  if (typeof props.url === 'string') {
    try {
      const url = new URL(props.url)
      return `${url.hostname}${decodeURIComponent(url.pathname).replaceAll('-', ' ')}`
    } catch {
      /* Fall back to the canonical key. */
    }
  }
  return relation.target.canonical_key
}
function objectTypeLabel(kind: string, text: (zh: string, en: string) => string) {
  const labels: Record<string, [string, string]> = {
    Vulnerability: ['漏洞', 'Vulnerability'],
    Product: ['产品', 'Product'],
    Weakness: ['漏洞类型', 'Weakness'],
    Document: ['文档', 'Document'],
    ExploitArtifact: ['利用材料', 'Exploitation material'],
    Repo: ['代码仓库', 'Repository'],
    ResearchWork: ['研究', 'Research'],
    InternetAsset: ['互联网资产', 'Internet asset'],
    Package: ['软件包', 'Package'],
    SoftwareVersion: ['软件版本', 'Software version'],
  }
  return labels[kind] ? text(...labels[kind]) : kind
}

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
