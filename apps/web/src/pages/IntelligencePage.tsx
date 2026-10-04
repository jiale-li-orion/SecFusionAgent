import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import {
  ArrowUpRight,
  BadgeCheck,
  Binary,
  Braces,
  ExternalLink,
  FileSearch,
  Fingerprint,
  GitBranch,
  Link2,
  Radar,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import {
  getEvidence,
  getHotWorld,
  getVulnerability,
  type EvidenceRef,
  type KnowledgeClaim,
  type HotBug,
  type KnowledgeRelation,
} from '../lib/api'

export function IntelligencePage() {
  const [params, setParams] = useSearchParams()
  const paramCve = params.get('cve') ?? ''
  const [input, setInput] = useState(paramCve)
  const [evidenceRef, setEvidenceRef] = useState<string | null>(null)
  const hotQuery = useQuery({ queryKey: ['world-hot-intelligence'], queryFn: () => getHotWorld(64), refetchInterval: 20_000 })
  const fallbackCve = hotQuery.data?.items[0]?.cve_id ?? ''
  const selectedCve = paramCve || fallbackCve
  const hotMatch = hotQuery.data?.items.find((item) => (item.cve_id ?? item.external_object_id).toUpperCase() === selectedCve.toUpperCase()) ?? null

  useEffect(() => {
    if (paramCve) setInput(paramCve)
  }, [paramCve])

  const knowledgeQuery = useQuery({
    queryKey: ['vulnerability', selectedCve],
    queryFn: () => getVulnerability(selectedCve),
    enabled: Boolean(selectedCve),
  })
  const obj = knowledgeQuery.data
  const headline = selectedCve || 'SELECT A VULNERABILITY'

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    const value = input.trim().toUpperCase()
    if (!value) return
    setEvidenceRef(null)
    setParams({ cve: value })
  }

  const groupedClaims = useMemo(() => groupClaims(obj?.claims ?? []), [obj?.claims])

  return (
    <section className="page intelligence-page">
      <div className="page-heading intel-heading">
        <div>
          <p className="eyebrow">CANONICAL KNOWLEDGE · EVIDENCE ADJACENT · BOUNDED GRAPH</p>
          <h1>INTELLIGENCE DOSSIER</h1>
          <p className="lede">事实、关系和来源在同一观察面里展开；任何 Evidence capsule 都可以回到真实 Observation。</p>
        </div>
        <form className="intel-search" onSubmit={submitSearch}>
          <Search size={15} />
          <input value={input} onChange={(event) => setInput(event.target.value)} placeholder="CVE-2026-…" />
          <button type="submit">INSPECT</button>
        </form>
      </div>

      <div className="intel-layout">
        <div className="intel-main">
          <article className="dossier-hero panel-glass">
            <div className="dossier-id">
              <span className="dossier-sigil"><Fingerprint size={30} /></span>
              <div>
                <small>VULNERABILITY / CANONICAL OBJECT</small>
                <strong>{headline}</strong>
                <span className="mono">{obj?.object_id ?? (hotMatch ? `${hotMatch.source_id} · HOT WORKING SET` : knowledgeQuery.isLoading ? 'resolving…' : 'no object loaded')}</span>
              </div>
            </div>
            <div className="dossier-stats">
              <DossierStat label={obj ? 'CLAIMS' : hotMatch ? 'LAYER' : 'CLAIMS'} value={obj ? String(obj.claims.length) : hotMatch ? 'HOT' : '—'} tone="cyan" />
              <DossierStat label={obj ? 'RELATIONS' : hotMatch ? 'CHANGED' : 'RELATIONS'} value={obj ? String(obj.relations.length) : hotMatch ? String(hotMatch.changed_fields.length) : '—'} tone="violet" />
              <DossierStat label={obj ? 'EVIDENCE' : hotMatch ? 'ACCESS' : 'EVIDENCE'} value={obj ? String(countEvidence(obj.claims, obj.relations)) : hotMatch ? String(Math.round(hotMatch.access_count)) : '—'} tone="lime" />
            </div>
          </article>

          {knowledgeQuery.isError && !hotMatch && <div className="intel-state error-block">{String(knowledgeQuery.error.message)}</div>}
          {!selectedCve && <div className="intel-state panel-glass">从 WORLD 选择 Hot CVE，或输入 CVE ID。</div>}
          {!obj && hotMatch && <HotWorkingSetPanel item={hotMatch} />}

          {obj && (
            <>
              <div className="intel-section-grid">
                {groupedClaims.map((group) => (
                  <ClaimGroup key={group.title} title={group.title} claims={group.claims} onEvidence={setEvidenceRef} />
                ))}
              </div>

              <section className="relation-section panel-glass">
                <div className="section-title-row">
                  <div><small>FOCUSED KNOWLEDGE GRAPH</small><strong>RELATION NEIGHBORHOOD</strong></div>
                  <span>{obj.relations.length} canonical edges</span>
                </div>
                <div className="relation-stage">
                  <div className="relation-core"><ShieldCheck size={24} /><strong>{selectedCve}</strong></div>
                  <div className="relation-list">
                    {obj.relations.slice(0, 18).map((relation, index) => (
                      <RelationCard key={relation.relation_id} relation={relation} index={index} onEvidence={setEvidenceRef} />
                    ))}
                    {obj.relations.length === 0 && <div className="empty-state">No current canonical relations.</div>}
                  </div>
                </div>
              </section>
            </>
          )}
        </div>

        <aside className="intel-side">
          <EvidenceInspector evidenceRef={evidenceRef} onClose={() => setEvidenceRef(null)} />
        </aside>
      </div>
    </section>
  )
}

function HotWorkingSetPanel({ item }: { item: HotBug }) {
  return (
    <section className="hot-dossier panel-glass">
      <div className="hot-dossier-head">
        <div>
          <small>HOT WORKING SET · NOT YET PROMOTED</small>
          <strong>{item.cve_id ?? item.external_object_id}</strong>
          <p>这个对象已经被 Data Plane 捕获并进入 Redis Hot Layer，但当前 durable Knowledge 中还没有 canonical object。它会保持 Hot 状态，直到 promotion / retention policy 把它推进 Evidence Core。</p>
        </div>
        <span className={`hot-status ${item.pinned ? 'pinned' : item.active ? 'active' : ''}`}>{item.pinned ? 'PINNED' : item.active ? 'ACTIVE' : 'HOT'}</span>
      </div>
      <div className="hot-dossier-grid">
        <HotFact label="SOURCE" value={item.source_id} />
        <HotFact label="REVISION" value={item.external_revision ?? 'content revision'} mono />
        <HotFact label="CVSS" value={item.cvss_score != null ? `${item.cvss_score.toFixed(1)} ${item.cvss_severity ?? ''}` : '—'} />
        <HotFact label="STATUS" value={item.status ?? '—'} />
        <HotFact label="TTL" value={item.ttl_seconds != null ? `${Math.round(item.ttl_seconds / 60)} min` : item.pinned ? 'persisted' : '—'} />
        <HotFact label="FETCHED" value={formatDate(item.fetched_at)} />
      </div>
      {item.title && <div className="hot-text"><small>TITLE</small><strong>{item.title}</strong></div>}
      {item.description && <div className="hot-text"><small>DESCRIPTION</small><p>{item.description}</p></div>}
      <div className="hot-signal-row">
        <div><small>CHANGED FIELDS</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : 'none'}</span></div>
        <div><small>PRIORITY SIGNALS</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : 'none'}</span></div>
      </div>
    </section>
  )
}

function HotFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="hot-fact"><small>{label}</small><strong className={mono ? 'mono' : ''}>{value}</strong></div>
}

function ClaimGroup({ title, claims, onEvidence }: { title: string; claims: KnowledgeClaim[]; onEvidence: (ref: string) => void }) {
  return (
    <article className="claim-group panel-glass">
      <div className="claim-group-title"><span>{title}</span><b>{claims.length}</b></div>
      <div className="claim-list">
        {claims.map((claim) => (
          <div key={claim.claim_id} className="claim-row">
            <div className="claim-copy">
              <small>{humanize(claim.predicate)}</small>
              <strong>{formatValue(claim.value)}</strong>
              <span className="mono">rev {claim.created_revision} · {claim.origin}</span>
            </div>
            <EvidenceCapsules evidence={claim.evidence} onEvidence={onEvidence} />
          </div>
        ))}
      </div>
    </article>
  )
}

function RelationCard({ relation, index, onEvidence }: { relation: KnowledgeRelation; index: number; onEvidence: (ref: string) => void }) {
  const displayName = relation.target.properties.display_name
  const label = typeof displayName === 'string' ? displayName : relation.target.external_identifiers.cve?.[0] ?? relation.target.canonical_key
  return (
    <motion.article className="relation-card" initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(index * .025, .3) }}>
      <span className="relation-icon"><GitBranch size={15} /></span>
      <div className="relation-copy">
        <small>{relation.relation_type}</small>
        <strong>{label}</strong>
        <span>{relation.target.object_type}</span>
      </div>
      <EvidenceCapsules evidence={relation.evidence} onEvidence={onEvidence} compact />
    </motion.article>
  )
}

function EvidenceCapsules({ evidence, onEvidence, compact = false }: { evidence: EvidenceRef[]; onEvidence: (ref: string) => void; compact?: boolean }) {
  if (evidence.length === 0) return <span className="no-evidence">NO EVIDENCE</span>
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

function EvidenceInspector({ evidenceRef, onClose }: { evidenceRef: string | null; onClose: () => void }) {
  const query = useQuery({ queryKey: ['evidence', evidenceRef], queryFn: () => getEvidence(evidenceRef!), enabled: Boolean(evidenceRef) })
  const item = query.data
  return (
    <div className={`evidence-inspector panel-glass ${evidenceRef ? 'active' : ''}`}>
      <div className="inspector-head">
        <div><small>EVIDENCE INSPECTOR</small><strong>{item?.source.source_id ?? 'Select evidence'}</strong></div>
        {evidenceRef && <button onClick={onClose} aria-label="Close evidence inspector"><X size={16} /></button>}
      </div>
      <AnimatePresence mode="wait">
        {!evidenceRef ? (
          <motion.div key="empty" className="inspector-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <FileSearch size={36} strokeWidth={1.3} />
            <strong>证据不会藏在脚注里</strong>
            <p>点击 dossier 或 relation 上的 Evidence capsule，检查来源、版本、时间和 locator。</p>
          </motion.div>
        ) : query.isLoading ? (
          <motion.div key="loading" className="inspector-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}><Radar size={30} /> resolving evidence…</motion.div>
        ) : query.isError ? (
          <motion.div key="error" className="inspector-empty error-block" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{String(query.error.message)}</motion.div>
        ) : item ? (
          <motion.div key={item.evidence_ref} className="inspector-body" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}>
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
              <div>{item.source.authority_scope.length ? item.source.authority_scope.map((scope) => <span key={scope}>{scope}</span>) : <span>unspecified</span>}</div>
            </div>
            {item.observation.canonical_url && <a className="source-link" href={item.observation.canonical_url} target="_blank" rel="noreferrer">OPEN CANONICAL SOURCE <ExternalLink size={13} /></a>}
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

function DossierStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className={`dossier-stat tone-${tone}`}><small>{label}</small><strong>{value}</strong></div>
}

function countEvidence(claims: KnowledgeClaim[], relations: KnowledgeRelation[]) {
  return new Set([...claims.flatMap((item) => item.evidence.map((e) => e.evidence_ref)), ...relations.flatMap((item) => item.evidence.map((e) => e.evidence_ref))]).size
}

function groupClaims(claims: KnowledgeClaim[]) {
  const groups = [
    { title: 'IDENTITY & SEVERITY', test: /status|title|description|cvss|severity|weakness|cwe/i },
    { title: 'AFFECTED & FIX', test: /affected|product|package|version|fix|remediation/i },
    { title: 'EXPLOIT & LIKELIHOOD', test: /exploit|epss|kev|poc|likelihood/i },
    { title: 'SOURCE & TIMELINE', test: /published|modified|assigner|reference|advisory/i },
  ]
  const assigned = new Set<string>()
  const result = groups.map((group) => {
    const items = claims.filter((claim) => group.test.test(claim.predicate))
    items.forEach((claim) => assigned.add(claim.claim_id))
    return { title: group.title, claims: items }
  }).filter((group) => group.claims.length)
  const other = claims.filter((claim) => !assigned.has(claim.claim_id))
  if (other.length) result.push({ title: 'OTHER CANONICAL FACTS', claims: other })
  return result
}

function humanize(value: string) { return value.replaceAll('_', ' ').replaceAll('-', ' ').toUpperCase() }
function formatDate(value: string) { return new Date(value).toLocaleString() }
function formatLocator(value: Record<string, unknown>) { return Object.entries(value).map(([key, val]) => `${key}=${formatValue(val)}`).join(' · ') || 'root' }
function formatValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.map(formatValue).join(' · ')
  try { return JSON.stringify(value) } catch { return String(value) }
}
