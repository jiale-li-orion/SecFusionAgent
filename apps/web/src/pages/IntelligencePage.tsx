import { useDeferredValue, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  BadgeCheck,
  Binary,
  BrainCircuit,
  Braces,
  ExternalLink,
  FileSearch,
  Fingerprint,
  GitBranch,
  Link2,
  Radar,
  Search,
  ShieldCheck,
  Telescope,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  evidenceBoundObjectIds,
  getDocumentByObject,
  getEvidence,
  getHotWorld,
  getIncident,
  getIntelligenceEnrichment,
  getIntelligenceGraph,
  getKnowledgeObject,
  getVulnerability,
  listIncidents,
  searchIntelligence,
  type EvidenceRef,
  type IncidentDetail,
  type IntelligenceEnrichmentState,
  type KnowledgeClaim,
  type HotBug,
  type KnowledgeRelation,
} from '../lib/api'
import { useI18n } from '../lib/i18n'

export function IntelligencePage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [params, setParams] = useSearchParams()
  const originSpace = params.get('from')
  const worldRef = params.get('worldRef')
  const paramCve = params.get('cve') ?? ''
  const paramObject = params.get('object') ?? ''
  const paramEvidence = params.get('evidence')
  const paramIncident = params.get('incident') ?? ''
  const paramView = params.get('view')
  const [inputOverride, setInputOverride] = useState<string | null>(null)
  const [searchError, setSearchError] = useState('')
  const input = inputOverride ?? (paramIncident ? `incident:${paramIncident}` : paramObject ? `object:${paramObject}` : paramCve)
  const deferredInput = useDeferredValue(input.trim())
  const evidenceRef = paramEvidence
  const readingMode: 'dossier' | 'graph' | 'evidence' = paramEvidence || paramView === 'evidence'
    ? 'evidence'
    : paramView === 'graph'
      ? 'graph'
      : 'dossier'
  const [returnReadingMode, setReturnReadingMode] = useState<'dossier' | 'graph'>('dossier')
  const hotQuery = useQuery({ queryKey: ['world-hot-intelligence'], queryFn: () => getHotWorld(64), refetchInterval: 20_000 })
  const incidentListQuery = useQuery({ queryKey: ['incident-index'], queryFn: () => listIncidents(16), staleTime: 20_000 })
  const objectSearchQuery = useQuery({
    queryKey: ['intelligence-search', deferredInput],
    queryFn: () => searchIntelligence(deferredInput, 12),
    enabled: shouldSearchKnowledge(deferredInput),
    staleTime: 20_000,
  })
  const incidentQuery = useQuery({
    queryKey: ['incident', paramIncident],
    queryFn: () => getIncident(paramIncident),
    enabled: Boolean(paramIncident),
  })

  const fallbackCve = hotQuery.data?.items[0]?.cve_id ?? ''
  const selectedCve = paramObject || paramIncident ? '' : (paramCve || fallbackCve)
  const selectedObjectId = paramIncident ? '' : paramObject
  const hotMatch = hotQuery.data?.items.find((item) => (item.cve_id ?? item.external_object_id).toUpperCase() === selectedCve.toUpperCase()) ?? null

  const knowledgeQuery = useQuery({
    queryKey: ['knowledge-object', selectedObjectId || selectedCve],
    queryFn: () => selectedObjectId ? getKnowledgeObject(selectedObjectId) : getVulnerability(selectedCve),
    enabled: !paramIncident && Boolean(selectedObjectId || selectedCve),
  })
  const obj = knowledgeQuery.data
  const graphQuery = useQuery({
    queryKey: ['intelligence-graph', obj?.object_id],
    queryFn: () => getIntelligenceGraph(obj!.object_id, 24),
    enabled: Boolean(obj),
    staleTime: 30_000,
  })
  const enrichmentQuery = useQuery({
    queryKey: ['intelligence-enrichment', obj?.object_id],
    queryFn: () => getIntelligenceEnrichment(obj!.object_id),
    enabled: obj?.object_type === 'Vulnerability',
    staleTime: 30_000,
  })
  const documentQuery = useQuery({
    queryKey: ['product-document-by-object', obj?.object_id],
    queryFn: () => getDocumentByObject(obj!.object_id),
    enabled: Boolean(obj && (obj.object_type === 'Document' || obj.object_type === 'ResearchWork')),
    staleTime: 30_000,
  })
  const incident = incidentQuery.data
  const displayName = obj?.properties.display_name
  const headline = incident
    ? humanize(incident.incident.incident_type)
    : (typeof displayName === 'string' && displayName) || obj?.external_identifiers.cve?.[0] || obj?.canonical_key || selectedCve || selectedObjectId || text('选择一个对象', 'SELECT AN OBJECT')

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    const raw = input.trim()
    const value = raw.toUpperCase()
    if (!value) return
    const incidentMatch = raw.match(/^incident:(.+)$/i)
    const objectMatch = raw.match(/^object:(.+)$/i)
    setSearchError('')
    setInputOverride(/^CVE-\d{4}-\d+$/i.test(raw) ? value : raw)
    if (/^CVE-\d{4}-\d+$/.test(value)) setParams({ cve: value })
    else if (incidentMatch?.[1]?.trim()) setParams({ incident: incidentMatch[1].trim() })
    else if (objectMatch?.[1]?.trim()) setParams({ object: objectMatch[1].trim() })
    else if (objectSearchQuery.data?.items[0]) openSearchResult(objectSearchQuery.data.items[0].object_id)
    else setSearchError(text('当前 Knowledge World 没有匹配对象。', 'No matching object exists in the current Knowledge World.'))
  }

  function openSearchResult(objectId: string) {
    setSearchError('')
    setInputOverride(null)
    setParams({ object: objectId })
  }

  const groupedClaims = useMemo(() => groupClaims(obj?.claims ?? []), [obj?.claims])

  function selectReadingMode(nextMode: 'dossier' | 'graph' | 'evidence', evidence?: string) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (nextMode === 'dossier') next.delete('view')
      else next.set('view', nextMode)
      if (nextMode !== 'evidence') next.delete('evidence')
      else if (evidence) next.set('evidence', evidence)
      return next
    }, { replace: true })
  }

  function openEvidence(ref: string) {
    if (readingMode !== 'evidence') setReturnReadingMode(readingMode)
    selectReadingMode('evidence', ref)
  }

  function closeEvidence() {
    selectReadingMode(returnReadingMode)
  }

  function openMission(profile: 'VERIFY' | 'INVESTIGATE') {
    const mission = new URLSearchParams({ profile })
    if (selectedCve) mission.set('cve', selectedCve)
    else if (obj?.object_id) mission.set('object', obj.object_id)
    mission.set('from', 'intelligence')
    mission.set('origin', incident
      ? `incident:${incident.incident.incident_id}`
      : obj?.object_id
        ? `object:${obj.object_id}`
        : selectedCve
          ? `cve:${selectedCve}`
          : 'intelligence')
    const prompt = profile === 'VERIFY'
      ? text(`核验 ${headline} 的关键 Claims、Relations 与 Evidence 边界。`, `Verify the key Claims, Relations, and Evidence boundaries for ${headline}.`)
      : text(`调查 ${headline} 的关联证据、冲突、未知与外部上下文。`, `Investigate the related evidence, conflicts, unknowns, and external context for ${headline}.`)
    mission.set('question', prompt)
    navigate(`/start?${mission.toString()}`)
  }

  return (
    <section className={`intelligence-space intelligence-page ${obj || incident ? 'has-dossier' : 'archive-empty'}`}>
      <header className="dossier-masthead intel-heading">
        <div>
          <p>{text('让每条 Claim 都面对自己的见证者', 'CALL EVERY CLAIM TO THE WITNESS STAND')}</p>
          <h1>{text('情报', 'INTELLIGENCE')} <span>{text('档案', 'DOSSIER')}</span></h1>
          <small>{text(
            '十二维 enrichment、canonical Claims、bounded Relations 与 Evidence Inspector 在同一 dossier 展开；来源、revision、时间与 locator 保持可追溯。',
            'Twelve enrichment dimensions, canonical Claims, bounded Relations, and the Evidence Inspector share one dossier. Source, revision, time, and locator remain traceable.',
          )}</small>
        </div>
        <form className="intel-search" onSubmit={submitSearch}>
          <Search size={15} />
          <input value={input} onChange={(event) => setInputOverride(event.target.value)} placeholder="CVE-2026-… / object:<id> / incident:<id>" />
          <button type="submit">{text('打开档案', 'OPEN DOSSIER')}</button>
          <AnimatePresence>
            {shouldSearchKnowledge(input.trim()) && (
              <motion.div
                className="intel-object-search-results"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
              >
                <div className="intel-object-search-head">
                  <small>{text('KNOWLEDGE OBJECT SEARCH', 'KNOWLEDGE OBJECT SEARCH')}</small>
                  <span>{objectSearchQuery.isLoading ? text('检索中…', 'SEARCHING…') : text(`${objectSearchQuery.data?.items.length ?? 0} 个对象`, `${objectSearchQuery.data?.items.length ?? 0} objects`)}</span>
                </div>
                <div>
                  {(objectSearchQuery.data?.items ?? []).map((item) => (
                    <button type="button" key={item.object_id} onClick={() => openSearchResult(item.object_id)}>
                      <span className="intel-search-object-kind">{item.object_type}</span>
                      <div><strong>{item.label}</strong><small className="mono">{item.canonical_key}</small></div>
                      <em>REV {item.created_revision}</em>
                    </button>
                  ))}
                  {!objectSearchQuery.isLoading && !objectSearchQuery.isError && (objectSearchQuery.data?.items.length ?? 0) === 0 && (
                    <p>{text('当前 durable Knowledge 没有匹配对象。', 'No matching object in current durable Knowledge.')}</p>
                  )}
                  {objectSearchQuery.isError && <p className="error-block">{String(objectSearchQuery.error.message)}</p>}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {searchError && <span className="intel-search-error">{searchError}</span>}
        </form>
      </header>

      {originSpace === 'world' && worldRef && (
        <div className="dossier-origin">
          <div><small>WORLD → INTELLIGENCE</small><strong>{text('来自 Evidence World 的对象坐标', 'OBJECT COORDINATE FROM EVIDENCE WORLD')}</strong><span className="mono">{worldRef}</span></div>
          <button onClick={() => navigate('/')}>{text('返回 Evidence World', 'BACK TO EVIDENCE WORLD')}</button>
        </div>
      )}

      <div className={`intel-layout reading-${readingMode}`}>
        <motion.div
          key={incident?.incident.incident_id ?? obj?.object_id ?? selectedObjectId ?? selectedCve ?? 'archive'}
          className="intel-main"
          initial={reduceMotion ? false : { opacity: 0, x: 22, rotateY: -1.8, transformOrigin: 'left center' }}
          animate={{ opacity: 1, x: 0, rotateY: 0 }}
          transition={{ duration: reduceMotion ? 0 : .34, ease: [0.22, 1, 0.36, 1] }}
        >
          <article className="dossier-hero dossier-hero">
            <div className="dossier-id">
              <span className={`dossier-sigil ${incident ? 'incident' : ''}`}>{incident ? <Radar size={30} /> : <Fingerprint size={30} />}</span>
              <div>
                <small>{incident ? 'SECURITY INCIDENT / DURABLE WORLD' : `${obj?.object_type?.toUpperCase() ?? (selectedCve ? 'VULNERABILITY' : 'CANONICAL OBJECT')} / CANONICAL OBJECT`}</small>
                <strong>{headline}</strong>
                <span className="mono">{incident?.incident.incident_id ?? obj?.object_id ?? (hotMatch ? `${hotMatch.source_id} · HOT WORKING SET` : (incidentQuery.isLoading || knowledgeQuery.isLoading) ? text('解析中…', 'resolving…') : text('未加载对象', 'no object loaded'))}</span>
              </div>
            </div>
            <div className="dossier-stats">
              {incident ? (
                <>
                  <DossierStat label="TIMELINE" value={String(incident.incident.timeline_event_count)} tone="amber" />
                  <DossierStat label="SOURCES" value={String(incident.incident.source_link_count)} tone="cyan" />
                  <DossierStat label="DIVERSITY" value={String(incident.incident.source_diversity_count)} tone="lime" />
                </>
              ) : (
                <>
                  <DossierStat label={obj ? 'CLAIMS' : hotMatch ? 'LAYER' : 'CLAIMS'} value={obj ? String(obj.claims.length) : hotMatch ? 'HOT' : '—'} tone="cyan" />
                  <DossierStat label={obj ? 'RELATIONS' : hotMatch ? 'CHANGED' : 'RELATIONS'} value={obj ? String(obj.relations.length) : hotMatch ? String(hotMatch.changed_fields.length) : '—'} tone="violet" />
                  <DossierStat label={obj ? 'EVIDENCE' : hotMatch ? 'ACCESS' : 'EVIDENCE'} value={obj ? String(countEvidence(obj.claims, obj.relations)) : hotMatch ? String(Math.round(hotMatch.access_count)) : '—'} tone="lime" />
                </>
              )}
            </div>
            {obj && (
              <div className="dossier-mission-actions">
                <button onClick={() => openMission('VERIFY')}><ShieldCheck size={13} /><span>{text('核验这个对象', 'VERIFY OBJECT')}</span><em>ARGUS · VERIFY</em></button>
                <button onClick={() => openMission('INVESTIGATE')}><Telescope size={13} /><span>{text('展开调查', 'INVESTIGATE')}</span><em>ARGUS · INVESTIGATE</em></button>
              </div>
            )}
            {obj && (
              <div className="intel-reading-switch" role="tablist" aria-label={text('情报阅读视角', 'Intelligence reading view')}>
                <button role="tab" aria-selected={readingMode === 'dossier'} className={readingMode === 'dossier' ? 'active' : ''} onClick={() => { selectReadingMode('dossier'); setReturnReadingMode('dossier') }}><FileSearch size={12} /> {text('档案', 'DOSSIER')}</button>
                <button role="tab" aria-selected={readingMode === 'graph'} className={readingMode === 'graph' ? 'active' : ''} onClick={() => { selectReadingMode('graph'); setReturnReadingMode('graph') }}><GitBranch size={12} /> {text('关系图谱', 'GRAPH')}</button>
                <button role="tab" aria-selected={readingMode === 'evidence'} className={readingMode === 'evidence' ? 'active' : ''} onClick={() => selectReadingMode('evidence', evidenceRef ?? undefined)}><Link2 size={12} /> {text('证据', 'EVIDENCE')}</button>
                <motion.i layoutId="intel-reading-cursor" transition={{ type: 'spring', stiffness: 320, damping: 28 }} className={`cursor-${readingMode}`} />
              </div>
            )}
          </article>

          {incident ? (
            <IncidentDossier incident={incident} onEvidence={openEvidence} />
          ) : (
            <>
              {(!obj || obj.object_type === 'Vulnerability')
                ? <EnrichmentConstellation
                    claims={obj?.claims ?? []}
                    cveId={selectedCve || headline}
                    state={enrichmentQuery.data ?? null}
                    stateLoading={Boolean(obj && enrichmentQuery.isLoading)}
                    stateError={Boolean(obj && enrichmentQuery.isError)}
                  />
                : <ObjectFacetField obj={obj} />}
              {obj && (obj.object_type === 'Document' || obj.object_type === 'ResearchWork') && (
                <DocumentIndexDossier
                  document={documentQuery.data ?? null}
                  loading={documentQuery.isLoading}
                  error={documentQuery.isError ? String(documentQuery.error.message) : null}
                />
              )}

              {knowledgeQuery.isError && !hotMatch && <div className="intel-state error-block"><span>{String(knowledgeQuery.error.message)}</span><button className="recovery-action" onClick={() => void knowledgeQuery.refetch()}>{text('重试 Knowledge read', 'RETRY KNOWLEDGE READ')}</button></div>}
              {!selectedCve && !selectedObjectId && <IntelligenceArchiveBlueprint />}
              {!obj && hotMatch && <HotWorkingSetPanel item={hotMatch} />}
              {!obj && (selectedCve || selectedObjectId) && !hotMatch && <IntelligenceArchiveBlueprint target={selectedCve || selectedObjectId} />}

              {obj && (
                <div className="intel-reading-deck">
                  <div className="intel-section-grid">
                    {groupedClaims.map((group) => (
                      <ClaimGroup key={group.title} title={group.title} claims={group.claims} onEvidence={openEvidence} />
                    ))}
                  </div>

                  <FocusedKnowledgeGraph
                    relations={graphQuery.data?.relations ?? []}
                    totalRelationCount={graphQuery.data?.total_relation_count ?? obj.relations.length}
                    neighborhood={graphQuery.data?.neighborhood ?? 'canonical_outbound_one_hop'}
                    loading={graphQuery.isLoading}
                    error={graphQuery.isError ? String(graphQuery.error.message) : null}
                    selectedLabel={headline}
                    objectType={obj.object_type}
                    onEvidence={openEvidence}
                    onOpenTarget={(objectId) => {
                      setInputOverride(null)
                      setParams({ object: objectId })
                    }}
                  />
                </div>
              )}
            </>
          )}
          {incidentQuery.isError && <div className="intel-state error-block" role="alert"><span>{String(incidentQuery.error.message)}</span><button className="recovery-action" onClick={() => void incidentQuery.refetch()}>{text('重试 Incident read', 'RETRY INCIDENT READ')}</button></div>}
        </motion.div>

        <aside className="intel-side">
          <IncidentArchiveRail
            items={incidentListQuery.data?.items ?? []}
            loading={incidentListQuery.isLoading}
            error={incidentListQuery.isError}
            activeId={paramIncident}
            onSelect={(incidentId) => {
              setInputOverride(null)
              setParams({ incident: incidentId })
            }}
          />
          <EvidenceInspector evidenceRef={evidenceRef} onClose={closeEvidence} />
        </aside>
      </div>
    </section>
  )
}

function enrichmentStatusLabel(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'resolved') return text('已解析', 'RESOLVED')
  if (status === 'conflict') return text('冲突', 'CONFLICT')
  if (status === 'unknown') return text('明确未知', 'EXPLICIT UNKNOWN')
  if (status === 'missing') return text('缺失', 'MISSING')
  return text('状态不可用', 'STATE UNAVAILABLE')
}

function enrichmentStatusExplanation(status: EnrichmentVisualStatus, text: (zh: string, en: string) => string) {
  if (status === 'unknown') return text('权威查询或成功 operator 已明确返回未知；这与尚未获取证据不同。', 'An authoritative lookup or successful operator explicitly returned unknown; this differs from missing evidence.')
  if (status === 'missing') return text('当前 world revision 没有满足该维度 completion predicate 的 canonical fact。', 'No canonical fact satisfies this dimension completion predicate at the current world revision.')
  if (status === 'conflict') return text('当前 canonical facts 形成互不相容的值或适用性状态，冲突被保留。', 'Current canonical facts contain incompatible values or applicability states; the conflict is preserved.')
  if (status === 'resolved') return text('当前 world revision 已有满足 completion predicate 的 canonical fact。', 'A canonical fact satisfies the completion predicate at the current world revision.')
  return text('权威 enrichment state read 当前不可用；页面不从可见 Claim 数量推断状态。', 'The authoritative enrichment-state read is unavailable; the UI does not infer status from visible claim count.')
}

function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

function shouldSearchKnowledge(value: string) {
  if (value.length < 2) return false
  if (/^object:/i.test(value) || /^incident:/i.test(value)) return false
  if (/^CVE-\d{4}-\d+$/i.test(value)) return false
  return true
}

function evidenceProvenanceClass(role: string, sourceClass: string) {
  const value = (role + ' ' + sourceClass).toLowerCase()
  if (/authority|primary|official|vendor/.test(value)) return 'provenance-authority'
  if (/forensic|incident|telemetry|asset/.test(value)) return 'provenance-forensic'
  if (/reference|normative|academic|research/.test(value)) return 'provenance-reference'
  if (/signal|independent|osint/.test(value)) return 'provenance-signal'
  return 'provenance-general'
}

function evidenceProvenanceLabel(role: string, sourceClass: string) {
  const cls = evidenceProvenanceClass(role, sourceClass)
  if (cls === 'provenance-authority') return 'AUTHORITATIVE TESTIMONY'
  if (cls === 'provenance-forensic') return 'FORENSIC OBSERVATION'
  if (cls === 'provenance-reference') return 'REFERENCE RECORD'
  if (cls === 'provenance-signal') return 'CORROBORATING SIGNAL'
  return 'EVIDENCE RECORD'
}

function IncidentDossier({ incident, onEvidence }: { incident: IncidentDetail; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const watchEntries = Object.entries(incident.incident.watch_state)
  return (
    <section className="incident-dossier">
      <div className="incident-state">
        <div className="incident-state-copy">
          <small>DURABLE INCIDENT / REV {incident.incident.current_revision}</small>
          <strong>{incident.incident.current_summary ?? text('当前 Incident 尚无摘要。', 'No current Incident summary.')}</strong>
          <p>{text(
            `该 Incident 由 ${humanize(incident.incident.promotion_reason)} 提升进入 durable world；生命周期为 ${incident.incident.lifecycle}。`,
            `Promoted into the durable world by ${humanize(incident.incident.promotion_reason)}; lifecycle is ${incident.incident.lifecycle}.`,
          )}</p>
        </div>
        <div className="incident-state-facts">
          <div><small>LIFECYCLE</small><strong>{incident.incident.lifecycle}</strong></div>
          <div><small>PROMOTION</small><strong>{humanize(incident.incident.promotion_reason)}</strong></div>
          <div><small>CANDIDATE</small><strong className="mono">{incident.incident.candidate_id}</strong></div>
          <div><small>UPDATED</small><strong>{formatDate(incident.incident.updated_at)}</strong></div>
        </div>
        {watchEntries.length > 0 && (
          <div className="incident-watch">
            <small>WATCH STATE</small>
            <div>{watchEntries.map(([key, value]) => <span key={key}><b>{humanize(key)}</b>{formatValue(value)}</span>)}</div>
          </div>
        )}
      </div>

      <div className="incident-reading">
        <section className="incident-timeline">
          <div className="incident-section-head">
            <div><small>INCIDENT TIMELINE</small><strong>{text('事件演进', 'EVENT EVOLUTION')}</strong></div>
            <span>{incident.timeline.length} durable events</span>
          </div>
          <div className="incident-timeline-track">
            {incident.timeline.map((event, index) => (
              <article key={event.event_id} className="incident-event">
                <div className="incident-event-coordinate"><span>{String(index + 1).padStart(2, '0')}</span><i /></div>
                <div className="incident-event-body">
                  <div><small>{event.source_role} · REV {event.created_revision}</small><strong>{humanize(event.event_type)}</strong><time>{formatDate(event.event_time)}</time></div>
                  <p>{event.summary}</p>
                  <div className="incident-event-refs">
                    {event.evidence_refs.map((ref) => ref.startsWith('evidence:')
                      ? <button key={ref} onClick={() => onEvidence(ref)}><BadgeCheck size={11} /> EVIDENCE</button>
                      : <span key={ref} title={ref}>{typedRefLabel(ref)}</span>)}
                    {event.claim_refs.map((ref) => <span key={ref} title={ref}>CLAIM</span>)}
                    {event.supersedes_event_id && <span title={event.supersedes_event_id}>SUPERSEDES</span>}
                  </div>
                </div>
              </article>
            ))}
            {incident.timeline.length === 0 && <div className="incident-empty">{text('durable timeline 当前为空。', 'Durable timeline is empty.')}</div>}
          </div>
        </section>

        <aside className="incident-sources">
          <div className="incident-section-head">
            <div><small>SOURCE CORROBORATION</small><strong>{text('来源独立性', 'SOURCE DIVERSITY')}</strong></div>
            <span>{incident.incident.source_diversity_count} independent keys</span>
          </div>
          <div className="incident-source-list">
            {incident.sources.map((source) => (
              <article key={source.source_link_id}>
                <span className={`incident-source-role role-${source.source_role}`} />
                <div><small>{source.source_role} · {source.source_family}</small><strong>{source.source_id}</strong><em>{source.upstream_source ?? text('直接来源', 'direct source')}</em></div>
                <div><small>INDEPENDENCE KEY</small><strong className="mono">{source.independence_key}</strong><span>rev {source.created_revision}</span></div>
              </article>
            ))}
            {incident.sources.length === 0 && <div className="incident-empty">{text('当前没有 durable source link。', 'No durable source links.')}</div>}
          </div>
        </aside>
      </div>
    </section>
  )
}

function typedRefLabel(ref: string) {
  const prefix = ref.split(':', 1)[0] || 'ref'
  return prefix.replaceAll('-', ' ').toUpperCase()
}

function IncidentArchiveRail({
  items,
  loading,
  error,
  activeId,
  onSelect,
}: {
  items: Awaited<ReturnType<typeof listIncidents>>['items']
  loading: boolean
  error: boolean
  activeId: string
  onSelect: (incidentId: string) => void
}) {
  const { text } = useI18n()
  return (
    <section className="incident-archive-rail">
      <div className="incident-archive-head">
        <div><small>DURABLE INCIDENTS</small><strong>{text('事件档案', 'INCIDENT ARCHIVE')}</strong></div>
        <span>{items.length}</span>
      </div>
      {loading ? (
        <div className="incident-archive-state">{text('解析 Incident 索引…', 'RESOLVING INCIDENT INDEX…')}</div>
      ) : error ? (
        <div className="incident-archive-state error-block" role="alert">{text('Incident read 当前不可用。', 'Incident read is unavailable.')}</div>
      ) : items.length === 0 ? (
        <div className="incident-archive-state">
          <Radar size={18} />
          <strong>{text('当前 durable Incident 为 0', '0 DURABLE INCIDENTS')}</strong>
          <span>{text('Incident promotion 持久化真实 row 后，这里自动出现 timeline-first dossier。', 'A timeline-first dossier appears here when Incident promotion persists a real row.')}</span>
        </div>
      ) : (
        <div className="incident-archive-list">
          {items.map((item) => (
            <button key={item.incident_id} className={item.incident_id === activeId ? 'active' : ''} onClick={() => onSelect(item.incident_id)}>
              <span className={`incident-archive-state-dot state-${item.lifecycle}`} />
              <div><small>{humanize(item.incident_type)}</small><strong>{item.current_summary ?? item.incident_id}</strong><em>{item.timeline_event_count} events · {item.source_diversity_count} independent</em></div>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

function IntelligenceArchiveBlueprint({ target }: { target?: string }) {
  const { text } = useI18n()
  const groups = ['IDENTITY & SEVERITY', 'AFFECTED & FIX', 'EXPLOIT & LIKELIHOOD', 'SOURCE & TIMELINE']
  const nodes = [
    { x: 18, y: 28, label: 'Product / Version' },
    { x: 81, y: 25, label: 'Advisory / Fix' },
    { x: 77, y: 72, label: 'Incident / Exploit' },
    { x: 22, y: 74, label: 'Research / Asset' },
  ]
  return (
    <section className="intel-blueprint">
      <div className="intel-blueprint-claims">
        {groups.map((group, index) => (
          <div key={group}>
            <span>{String(index + 1).padStart(2, '0')}</span>
            <small>{text('CLAIM 分组', 'CLAIM GROUP')}</small>
            <strong>{group}</strong>
            <i />
            <i />
          </div>
        ))}
      </div>
      <div className="intel-blueprint-graph">
        <div className="instrument-section-head">
          <div><small>{text('聚焦知识图谱', 'FOCUSED KNOWLEDGE GRAPH')}</small><strong>{text('关系邻域', 'RELATION NEIGHBORHOOD')}</strong></div>
          <span>{text('目标解析后显示 canonical edges', 'canonical edges appear here when target resolves')}</span>
        </div>
        <div className="intel-blueprint-graph-stage">
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {nodes.map((node) => <path key={node.label} d={`M 50 50 Q 50 42 ${node.x} ${node.y}`} />)}
          </svg>
          <div className="intel-blueprint-core">
            <Fingerprint size={22} />
            <strong>{target ?? 'CANONICAL OBJECT'}</strong>
            <small>VULNERABILITY</small>
          </div>
          {nodes.map((node) => (
            <div
              key={node.label}
              className="intel-blueprint-node"
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
            >
              <GitBranch size={12} />
              <span><small>{text('关系槽位', 'RELATION SLOT')}</small><strong>{node.label}</strong></span>
            </div>
          ))}
          <div className="intel-blueprint-caption">TARGET → CLAIM → RELATION → EVIDENCE</div>
        </div>
      </div>
    </section>
  )
}

function HotWorkingSetPanel({ item }: { item: HotBug }) {
  const { text } = useI18n()
  return (
    <section className="hot-dossier">
      <div className="hot-dossier-head">
        <div>
          <small>{text('HOT WORKING SET · 尚未 promotion', 'HOT WORKING SET · NOT YET PROMOTED')}</small>
          <strong>{item.cve_id ?? item.external_object_id}</strong>
          <p>{text(
            '对象已被 Data Plane 捕获并进入 Redis Hot Layer；canonical Knowledge 等待 promotion / retention policy 推进至 Evidence Core。',
            'The Data Plane has captured this object into the Redis Hot Layer. Canonical Knowledge remains pending until promotion / retention policy advances it into the Evidence Core.',
          )}</p>
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
      {item.title && <div className="hot-text"><small>{text('标题', 'TITLE')}</small><strong>{item.title}</strong></div>}
      {item.description && <div className="hot-text"><small>{text('描述', 'DESCRIPTION')}</small><p>{item.description}</p></div>}
      <div className="hot-signal-row">
        <div><small>{text('变化字段', 'CHANGED FIELDS')}</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : text('无', 'none')}</span></div>
        <div><small>{text('优先级信号', 'PRIORITY SIGNALS')}</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : text('无', 'none')}</span></div>
      </div>
    </section>
  )
}

function HotFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="hot-fact"><small>{label}</small><strong className={mono ? 'mono' : ''}>{value}</strong></div>
}

function ObjectFacetField({ obj }: { obj: Awaited<ReturnType<typeof getKnowledgeObject>> }) {
  const { text } = useI18n()
  const identifiers = Object.entries(obj.external_identifiers)
  const properties = Object.entries(obj.properties).filter(([, value]) => value != null).slice(0, 10)
  return (
    <section className="object-facet-field">
      <div className="enrichment-head">
        <div><small>{text('规范对象切面', 'CANONICAL OBJECT FACETS')}</small><strong>{obj.object_type.toUpperCase()}</strong></div>
        <span>{text(`${identifiers.length} 个 identifier namespace · ${properties.length} 个可见属性`, `${identifiers.length} identifier namespaces · ${properties.length} visible properties`)}</span>
      </div>
      <div className="object-facet-body">
        <div className="object-identifier-field">
          {identifiers.map(([namespace, values]) => (
            <div key={namespace}><small>{namespace}</small><strong>{values.join(' · ')}</strong></div>
          ))}
          {identifiers.length === 0 && <div><small>IDENTIFIERS</small><strong>{text('无持久化标识', 'none persisted')}</strong></div>}
        </div>
        <div className="object-property-field">
          {properties.map(([key, value]) => (
            <div key={key}><small>{humanize(key)}</small><strong>{formatValue(value)}</strong></div>
          ))}
        </div>
      </div>
    </section>
  )
}

function DocumentIndexDossier({
  document,
  loading,
  error,
}: {
  document: Awaited<ReturnType<typeof getDocumentByObject>> | null
  loading: boolean
  error: string | null
}) {
  const { text } = useI18n()
  if (loading) {
    return <section className="document-index-dossier is-loading"><FileSearch size={18} /><span>{text('解析文档索引…', 'RESOLVING DOCUMENT INDEX…')}</span></section>
  }
  if (error || !document) {
    return <section className="document-index-dossier is-error"><FileSearch size={18} /><span>{error ?? text('文档索引不可用', 'Document index unavailable')}</span></section>
  }
  const revision = document.current_revision
  const indexed = Object.entries(document.index_status_counts).sort((a, b) => b[1] - a[1])
  return (
    <section className="document-index-dossier">
      <div className="document-index-head">
        <div>
          <small>MANAGED DOCUMENT / INDEX PROVENANCE</small>
          <strong>{revision?.title ?? document.external_object_id}</strong>
          <span className="mono">{document.document_id}</span>
        </div>
        <div>
          <small>{text('来源', 'SOURCE')}</small>
          <strong>{document.source_id}</strong>
          <span>{revision ? `${revision.parser_name}@${revision.parser_version}` : text('无 revision', 'no revision')}</span>
        </div>
      </div>
      <div className="document-index-measures">
        <div><small>CHUNKS</small><strong>{document.chunk_count}</strong><span>{text('正文不在 Product read 中暴露', 'content withheld from Product read')}</span></div>
        <div><small>EMBEDDED</small><strong>{document.embedded_chunk_count}</strong><span>{document.embedding_models.join(' · ') || text('未记录 embedding model', 'no embedding model recorded')}</span></div>
        <div><small>INDEX STATE</small><strong>{indexed.map(([status, count]) => `${count} ${status}`).join(' · ') || '—'}</strong><span>{text('持久 chunk 状态', 'persisted chunk state')}</span></div>
        <div><small>SECTIONS</small><strong>{document.sections.length}</strong><span>{document.sections.slice(0, 3).join(' · ') || '—'}</span></div>
      </div>
      <div className="document-index-provenance">
        <div>
          <small>CURRENT REVISION</small>
          <strong className="mono">{revision?.document_revision_id ?? '—'}</strong>
          <span>{revision?.external_revision ?? revision?.content_hash.slice(0, 16) ?? '—'}</span>
        </div>
        <div>
          <small>OBSERVATION</small>
          <strong className="mono">{revision?.observation_id ?? '—'}</strong>
          <span>{revision?.updated_at ? formatDate(revision.updated_at) : revision?.created_at ? formatDate(revision.created_at) : '—'}</span>
        </div>
        <div>
          <small>INSIGHT CANDIDATE</small>
          <strong>{document.insight?.promotion_state ?? '—'}</strong>
          <span>{document.insight ? `${humanize(document.insight.change_type)} · ${humanize(document.insight.evidence_maturity)}` : text('未持久化 InsightCandidate', 'no persisted InsightCandidate')}</span>
        </div>
      </div>
      {document.canonical_url && <a className="document-canonical-link" href={document.canonical_url} target="_blank" rel="noreferrer">{text('打开规范文档来源', 'OPEN CANONICAL DOCUMENT SOURCE')} <ExternalLink size={12} /></a>}
    </section>
  )
}

const enrichmentDimensions = [
  { key: 'identity', label: 'IDENTITY', test: /title|description|status|assigner|identifier|cve/i },
  { key: 'severity', label: 'SEVERITY', test: /cvss|severity|score/i },
  { key: 'weakness', label: 'WEAKNESS', test: /weakness|cwe/i },
  { key: 'product_package', label: 'PRODUCT / PACKAGE', test: /product|package|vendor|component/i },
  { key: 'version_applicability', label: 'VERSION APPLICABILITY', test: /version|affected|not_affected|fixed|under_investigation|applicab/i },
  { key: 'fix_remediation', label: 'FIX / REMEDIATION', test: /fix|remediation|patch|upgrade|commit/i },
  { key: 'exploit_state', label: 'EXPLOIT STATE', test: /exploit|kev|poc|weapon/i },
  { key: 'exploit_likelihood', label: 'EXPLOIT LIKELIHOOD', test: /epss|likelihood|probab/i },
  { key: 'advisory_reference', label: 'ADVISORY / REFERENCE', test: /advisory|reference|url|bulletin/i },
  { key: 'asset_exposure', label: 'ASSET EXPOSURE', test: /asset|exposure|internet|deployment/i },
  { key: 'research_paper', label: 'RESEARCH / PAPER', test: /research|paper|academic|publication/i },
  { key: 'incident_context', label: 'INCIDENT CONTEXT', test: /incident|campaign|attack|observed_in_the_wild/i },
] as const

type EnrichmentVisualStatus = IntelligenceEnrichmentState['dimensions'][number]['status'] | 'unavailable'

function EnrichmentConstellation({ claims, cveId, state, stateLoading, stateError }: { claims: KnowledgeClaim[]; cveId: string; state: IntelligenceEnrichmentState | null; stateLoading: boolean; stateError: boolean }) {
  const { text } = useI18n()
  const [focusedDimension, setFocusedDimension] = useState<string | null>(null)
  const stateByDimension = new Map(state?.dimensions.map((item) => [item.dimension, item]) ?? [])
  const dimensions = enrichmentDimensions.map((dimension, index) => {
    const matchedClaims = claims.filter((claim) => dimension.test.test(claim.predicate))
    const authoritativeState = stateByDimension.get(dimension.key)
    const status: EnrichmentVisualStatus = authoritativeState?.status ?? 'unavailable'
    const angle = -Math.PI / 2 + (index / enrichmentDimensions.length) * Math.PI * 2
    return {
      ...dimension,
      status,
      authoritativeState,
      matchedClaims,
      x: 50 + Math.cos(angle) * 40,
      y: 50 + Math.sin(angle) * 37,
    }
  })
  const counts = dimensions.reduce<Record<EnrichmentVisualStatus, number>>((acc, item) => {
    acc[item.status] += 1
    return acc
  }, { resolved: 0, conflict: 0, unknown: 0, missing: 0, unavailable: 0 })
  const focused = dimensions.find((item) => item.key === focusedDimension) ?? null

  return (
    <section className={`enrichment-constellation ${focused ? 'dimension-focused' : ''}`}>
      <div className="enrichment-head">
        <div><small>ENRICHMENT-V1</small><strong>12-DIMENSION EVIDENCE CONSTELLATION</strong></div>
        <span>{stateLoading
          ? text('解析权威 enrichment state…', 'resolving authoritative enrichment state…')
          : stateError || !state
            ? text('四态 read 不可用 · 不从 Claim 数量推断', 'four-state read unavailable · claim counts are not used as status')
            : `${counts.resolved} resolved · ${counts.conflict} conflict · ${counts.unknown} unknown · ${counts.missing} missing`}</span>
      </div>
      <div className="enrichment-orbit">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {dimensions.map((item) => (
            <line
              key={item.key}
              className={`status-${item.status}`}
              x1="50"
              y1="50"
              x2={item.x}
              y2={item.y}
            />
          ))}
        </svg>
        <button className="enrichment-core" onClick={() => setFocusedDimension(null)}>
          <small>CANONICAL</small>
          <strong>{focused ? focused.label : cveId}</strong>
          <span>{focused ? enrichmentStatusLabel(focused.status, text) : state ? `WORLD REV ${state.world_revision}` : text(`${claims.length} 条可见 Claims`, `${claims.length} visible claims`)}</span>
        </button>
        {dimensions.map((item, index) => (
          <motion.button
            key={item.key}
            className={`enrichment-dimension status-${item.status} ${focusedDimension === item.key ? 'selected' : ''} ${focused && focusedDimension !== item.key ? 'dimmed' : ''}`}
            style={{ left: `${item.x}%`, top: `${item.y}%` }}
            onClick={() => setFocusedDimension((current) => current === item.key ? null : item.key)}
            initial={{ opacity: 0, scale: .82 }}
            animate={{ opacity: focused && focusedDimension !== item.key ? .18 : 1, scale: focusedDimension === item.key ? 1.08 : 1 }}
            transition={{ delay: index * .025 }}
          >
            <span>{String(index + 1).padStart(2, '0')}</span>
            <strong>{item.label}</strong>
            <small>{enrichmentStatusLabel(item.status, text)}</small>
          </motion.button>
        ))}
        <AnimatePresence>
          {focused && (
            <motion.aside
              className="enrichment-dimension-lens"
              initial={{ opacity: 0, x: 18 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 12 }}
            >
              <small>{focused.key.toUpperCase()} / ENRICHMENT DIMENSION</small>
              <strong>{focused.label}</strong>
              <span>{enrichmentStatusLabel(focused.status, text)} · {focused.authoritativeState ? `REV ${focused.authoritativeState.world_revision}` : 'STATE UNAVAILABLE'}</span>
              <div>
                {focused.matchedClaims.slice(0, 4).map((claim) => (
                  <p key={claim.claim_id}><b>{humanize(claim.predicate)}</b>{formatValue(claim.value)}</p>
                ))}
                {focused.matchedClaims.length === 0 && <p><b>{enrichmentStatusLabel(focused.status, text)}</b>{enrichmentStatusExplanation(focused.status, text)}</p>}
                {focused.authoritativeState?.conflict_refs.length ? <p><b>CONFLICT REFS</b>{focused.authoritativeState.conflict_refs.join(' · ')}</p> : null}
                {focused.authoritativeState?.attempted_operator_refs.length ? <p><b>ATTEMPTED OPERATORS</b>{focused.authoritativeState.attempted_operator_refs.join(' · ')}</p> : null}
                {focused.authoritativeState?.blocked_attempt_refs.length ? <p><b>BLOCKED ATTEMPTS</b>{focused.authoritativeState.blocked_attempt_refs.join(' · ')}</p> : null}
              </div>
              <em>{text('再次点击该维度以退出聚焦', 'CLICK DIMENSION AGAIN TO RELEASE FOCUS')}</em>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>
    </section>
  )
}

function ClaimGroup({ title, claims, onEvidence }: { title: string; claims: KnowledgeClaim[]; onEvidence: (ref: string) => void }) {
  return (
    <article className="claim-group">
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

function FocusedKnowledgeGraph({
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

function EvidenceCapsules({ evidence, onEvidence, compact = false }: { evidence: EvidenceRef[]; onEvidence: (ref: string) => void; compact?: boolean }) {
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

function EvidenceInspector({ evidenceRef, onClose }: { evidenceRef: string | null; onClose: () => void }) {
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
