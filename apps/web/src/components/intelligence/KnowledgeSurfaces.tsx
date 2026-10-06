import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { BadgeCheck, Binary, BrainCircuit, Braces, ExternalLink, FileSearch, Fingerprint, GitBranch, Link2, Radar, ShieldCheck, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { evidenceBoundObjectIds, getEvidence, type EvidenceRef, type KnowledgeRelation } from '../../lib/api'
import { compactEvidenceObjectRef, evidenceProvenanceClass, evidenceProvenanceLabel, formatDate, formatLocator, formatValue, humanize } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'

export function FocusedKnowledgeGraph({
  relations,
  totalRelationCount,
  neighborhood,
  loading,
  error,
  selectedLabel,
  objectType,
  onEvidence,
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
  onOpenTarget: (objectId: string) => void
}) {
  const { text } = useI18n()
  const layers = useMemo(() => ['ALL', ...Array.from(new Set(relations.map((item) => item.target.object_type))).sort()], [relations])
  const [layer, setLayer] = useState('ALL')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [evidenceOnly, setEvidenceOnly] = useState(false)
  const semanticRelations = relations.filter((item) => (layer === 'ALL' || item.target.object_type === layer) && (!evidenceOnly || item.evidence.length > 0))
  const visible = semanticRelations.slice(0, 10)
  const selectedCandidate = relations.find((item) => item.relation_id === selectedId) ?? null
  const selected = selectedCandidate && semanticRelations.some((item) => item.relation_id === selectedCandidate.relation_id) ? selectedCandidate : null

  return (
    <section className={`relation-section graph-mode ${selected ? 'graph-focused' : ''}`}>
      <div className="section-title-row">
        <div><small>FOCUSED KNOWLEDGE GRAPH</small><strong>RELATION NEIGHBORHOOD</strong></div>
        <span>{text(`${totalRelationCount} 条 canonical edges · ${visible.length} 条可见`, `${totalRelationCount} canonical edges · ${visible.length} visible`)}</span>
      </div>
      <div className="graph-read-boundary"><span>{neighborhood.replaceAll('_', ' ')}</span>{totalRelationCount > relations.length && <b>{text(`读取窗口 ${relations.length}/${totalRelationCount}`, `read window ${relations.length}/${totalRelationCount}`)}</b>}</div>
      <div className="graph-toolbar">
        <div className="graph-layers">
          {layers.map((item) => <button key={item} className={layer === item ? 'active' : ''} onClick={() => setLayer(item)}>{item}</button>)}
        </div>
        <div className="graph-camera">
          <button className={evidenceOnly ? 'active' : ''} onClick={() => setEvidenceOnly((value) => !value)}><BadgeCheck size={11} /> {text('证据', 'EVIDENCE')}</button>
          <button onClick={() => setZoom((value) => Math.max(.78, Number((value - .1).toFixed(2))))} aria-label={text('缩小图谱', 'Zoom out')}><ZoomOut size={12} /></button>
          <span>{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((value) => Math.min(1.32, Number((value + .1).toFixed(2))))} aria-label={text('放大图谱', 'Zoom in')}><ZoomIn size={12} /></button>
          {(selected || zoom !== 1 || evidenceOnly) && <button className="graph-reset" onClick={() => { setSelectedId(null); setZoom(1); setEvidenceOnly(false) }}>{text('重置', 'RESET')}</button>}
        </div>
      </div>
      <div className="focused-graph-stage" onWheel={(event) => { if (!event.ctrlKey && !event.metaKey) return; event.preventDefault(); setZoom((value) => Math.max(.78, Math.min(1.32, Number((value + (event.deltaY < 0 ? .06 : -.06)).toFixed(2))))) }}>
        <motion.div className="graph-world" animate={{ scale: (selected ? 1.045 : 1) * zoom, x: selected ? -36 : 0 }} transition={{ type: 'spring', stiffness: 180, damping: 24 }}>
          <svg className="graph-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {visible.map((relation, index) => {
              const point = graphPoint(index, visible.length)
              const active = relation.relation_id === selectedId
              return <path key={relation.relation_id} className={selected ? active ? 'active' : 'dimmed' : ''} d={`M 50 50 Q ${(50 + point.x) / 2} ${(50 + point.y) / 2 - 4} ${point.x} ${point.y}`} />
            })}
          </svg>
          <div className="graph-core-node"><ShieldCheck size={23} /><strong>{selectedLabel}</strong><small>{objectType}</small></div>
          {visible.map((relation, index) => {
            const point = graphPoint(index, visible.length)
            const active = relation.relation_id === selectedId
            const dimmed = Boolean(selected && !active)
            return <GraphRelationNode key={relation.relation_id} relation={relation} point={point} active={active} dimmed={dimmed} onSelect={() => setSelectedId(active ? null : relation.relation_id)} />
          })}
          {loading && <div className="graph-empty">{text('解析 bounded canonical neighborhood…', 'RESOLVING BOUNDED CANONICAL NEIGHBORHOOD…')}</div>}
          {!loading && error && <div className="graph-empty error-block">{error}</div>}
          {!loading && !error && visible.length === 0 && <div className="graph-empty">{text('当前语义层没有 canonical Relation。', 'No canonical relation in this semantic layer.')}</div>}
        </motion.div>
        <span className="graph-zoom-hint">{text('CTRL / ⌘ + 滚轮 · 缩放', 'CTRL / ⌘ + WHEEL · ZOOM')}</span>

        <AnimatePresence>
          {selected && <motion.aside className="graph-relation-dossier" initial={{ opacity: 0, x: 28 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 18 }} transition={{ type: 'spring', stiffness: 230, damping: 27 }}>
            <button onClick={() => setSelectedId(null)} className="graph-dossier-close" aria-label={text('关闭关系聚焦', 'Close relation focus')}><X size={15} /></button>
            <small>CANONICAL RELATION</small>
            <strong>{humanize(selected.relation_type)}</strong>
            <RelationTargetIdentity relation={selected} />
            <div className="graph-relation-facts">
              <div><small>ORIGIN</small><strong>{selected.origin}</strong></div>
              <div><small>REVISION</small><strong>{selected.created_revision}</strong></div>
              <div><small>TARGET TYPE</small><strong>{selected.target.object_type}</strong></div>
            </div>
            <div className="graph-evidence-block"><small>EVIDENCE</small><EvidenceCapsules evidence={selected.evidence} onEvidence={onEvidence} /></div>
            <button className="graph-open-target" onClick={() => onOpenTarget(selected.target.object_id)}>{text('打开目标档案', 'OPEN TARGET DOSSIER')} <ExternalLink size={12} /></button>
            <div className="graph-coordinate mono">{selected.relation_id}</div>
          </motion.aside>}
        </AnimatePresence>
      </div>
    </section>
  )
}

function GraphRelationNode({ relation, point, active, dimmed, onSelect }: { relation: KnowledgeRelation; point: { x: number; y: number }; active: boolean; dimmed: boolean; onSelect: () => void }) {
  const displayName = relation.target.properties.display_name
  const label = typeof displayName === 'string' ? displayName : relation.target.external_identifiers.cve?.[0] ?? relation.target.canonical_key
  return <motion.button
    className={`graph-relation-node ${active ? 'active' : ''} ${dimmed ? 'dimmed' : ''}`}
    style={{ left: `${point.x}%`, top: `${point.y}%` }}
    onClick={onSelect}
    initial={{ opacity: 0, scale: .85 }}
    animate={{ opacity: dimmed ? .15 : 1, scale: active ? 1.08 : dimmed ? .92 : 1 }}
    transition={{ type: 'spring', stiffness: 220, damping: 24 }}
  >
    <span className="graph-node-glyph"><GitBranch size={13} /></span>
    <span><small>{humanize(relation.relation_type)}</small><strong>{label}</strong><em>{relation.target.object_type}</em></span>
    {relation.evidence.length > 0 && <b>{relation.evidence.length}E</b>}
  </motion.button>
}

function RelationTargetIdentity({ relation }: { relation: KnowledgeRelation }) {
  const displayName = relation.target.properties.display_name
  const label = typeof displayName === 'string' ? displayName : relation.target.external_identifiers.cve?.[0] ?? relation.target.canonical_key
  return <div className="graph-target-identity"><span className="relation-icon"><GitBranch size={15} /></span><div><small>TARGET</small><strong>{label}</strong><span>{relation.target.object_type}</span></div></div>
}

function graphPoint(index: number, count: number) {
  const angle = -Math.PI / 2 + (index / Math.max(count, 1)) * Math.PI * 2
  const radiusX = count <= 6 ? 33 : 38
  const radiusY = count <= 6 ? 34 : 39
  return { x: 50 + Math.cos(angle) * radiusX, y: 50 + Math.sin(angle) * radiusY }
}

export function EvidenceCapsules({ evidence, onEvidence, compact = false }: { evidence: EvidenceRef[]; onEvidence: (ref: string) => void; compact?: boolean }) {
  const { text } = useI18n()
  if (evidence.length === 0) return <span className="no-evidence">{text('无 Evidence', 'NO EVIDENCE')}</span>
  return (
    <div className={`evidence-capsules ${compact ? 'compact' : ''}`}>
      {evidence.slice(0, compact ? 2 : 4).map((item) => (
        <button key={item.evidence_ref} onClick={() => onEvidence(item.evidence_ref)} title={item.source_id}>
          <BadgeCheck size={12} /> {compact ? item.source_id.slice(0, 10) : item.source_id}
        </button>
      ))}
      {evidence.length > (compact ? 2 : 4) && <span>+{evidence.length - (compact ? 2 : 4)}</span>}
    </div>
  )
}

export function EvidenceInspector({ evidenceRef, onClose }: { evidenceRef: string | null; onClose: () => void }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['evidence', evidenceRef], queryFn: () => getEvidence(evidenceRef!), enabled: Boolean(evidenceRef) })
  const item = query.data
  const objectIds = item ? evidenceBoundObjectIds(item) : []
  return (
    <div className={`evidence-inspector ${evidenceRef ? 'active' : ''}`}>
      <div className="inspector-head">
        <div><small>EVIDENCE INSPECTOR</small><strong>{item?.source.source_id ?? text('选择 Evidence', 'Select evidence')}</strong></div>
        {evidenceRef && <button onClick={onClose} aria-label={text('关闭证据镜片', 'Close evidence inspector')}><X size={16} /></button>}
      </div>
      <AnimatePresence mode="wait">
        {!evidenceRef ? (
          <motion.div key="empty" className="inspector-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <FileSearch size={36} strokeWidth={1.3} />
            <strong>{text('证据站在事实旁边', 'EVIDENCE STAYS BESIDE THE CLAIM')}</strong>
            <p>{text('点击 dossier 或 relation 上的 Evidence capsule，展开来源、版本、时间与 locator。', 'Open an Evidence capsule beside a dossier fact or Relation to inspect source, revision, time, and locator.')}</p>
          </motion.div>
        ) : query.isLoading ? (
          <motion.div key="loading" className="inspector-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><Radar size={30} /> {text('解析 Evidence…', 'resolving evidence…')}</motion.div>
        ) : query.isError ? (
          <motion.div key="error" className="inspector-empty error-block" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{String(query.error.message)}</motion.div>
        ) : item ? (
          <motion.div key={item.evidence_ref} className={'inspector-body evidence-manuscript ' + evidenceProvenanceClass(item.source.source_role, item.source.source_class)} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}>
            <div className="evidence-provenance-stamp">
              <small>PROVENANCE</small>
              <strong>{evidenceProvenanceLabel(item.source.source_role, item.source.source_class)}</strong>
              <span>{item.source.source_role} · {item.source.source_class}</span>
            </div>
            <div className="evidence-authority">
              <span className="signal-icon lime"><ShieldCheck size={17} /></span>
              <div><small>{item.source.source_role} / {item.source.source_class}</small><strong>{item.source.source_id}</strong><span>{item.source.source_family}</span></div>
            </div>
            <InspectorBlock icon={Link2} label="BOUND TO" value={`${item.target.target_kind} · ${item.target.label}`} detail={formatValue(item.target.detail.value ?? item.target.detail)} />
            <InspectorBlock icon={Binary} label="SOURCE REVISION" value={item.observation.external_revision ?? 'content-addressed'} detail={item.observation.external_object_id} mono />
            <InspectorBlock icon={Braces} label="LOCATOR" value={formatLocator(item.locator)} detail={`observed ${formatDate(item.observation.observed_at)}`} mono />
            {item.artifact && <InspectorBlock icon={Fingerprint} label="IMMUTABLE ARTIFACT" value={item.artifact.media_type} detail={`${item.artifact.trust_class} · ${item.artifact.content_hash.slice(0, 14)}…`} mono />}
            <div className="authority-scope">
              <small>AUTHORITY SCOPE</small>
              <div>{item.source.authority_scope.length ? item.source.authority_scope.map((scope) => <span key={scope}>{scope}</span>) : <span>{text('未指定', 'unspecified')}</span>}</div>
            </div>
            {objectIds.length > 0 && <div className="evidence-object-links"><small>{text('绑定对象', 'BOUND OBJECTS')}</small><div>{objectIds.map((objectId, index) => <button key={objectId} onClick={() => navigate(`/intelligence?object=${encodeURIComponent(objectId)}&from=evidence`)}><BrainCircuit size={11} /> {index === 0 ? text('打开主体档案', 'OPEN SUBJECT DOSSIER') : text('打开关系对象', 'OPEN RELATED OBJECT')}<span className="mono">{compactEvidenceObjectRef(objectId)}</span></button>)}</div></div>}
            {item.observation.canonical_url && <a className="source-link" href={item.observation.canonical_url} target="_blank" rel="noreferrer">{text('打开规范来源', 'OPEN CANONICAL SOURCE')} <ExternalLink size={13} /></a>}
            <div className="evidence-ref mono">{item.evidence_ref}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

function InspectorBlock({ icon: Icon, label, value, detail, mono = false }: { icon: typeof Link2; label: string; value: string; detail: string; mono?: boolean }) {
  return <div className="inspector-block"><Icon size={15} /><div><small>{label}</small><strong className={mono ? 'mono' : ''}>{value}</strong><span className={mono ? 'mono' : ''}>{detail}</span></div></div>
}
