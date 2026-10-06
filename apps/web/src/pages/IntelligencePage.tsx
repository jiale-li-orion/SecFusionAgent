import { useDeferredValue, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  FileSearch,
  Fingerprint,
  GitBranch,
  Link2,
  Radar,
  Search,
  ShieldCheck,
  Telescope,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  getDocumentByObject,
  getHotWorld,
  getIncident,
  getIntelligenceEnrichment,
  getIntelligenceGraph,
  getKnowledgeObject,
  getVulnerability,
  listIncidents,
  searchIntelligence,
} from '../lib/api'
import { EnrichmentConstellation } from '../components/intelligence/EnrichmentConstellation'
import { ClaimGroup, DocumentIndexDossier, HotWorkingSetPanel, IncidentArchiveRail, IncidentDossier, IntelligenceArchiveBlueprint, ObjectFacetField } from '../components/intelligence/DossierSurfaces'
import { EvidenceInspector, FocusedKnowledgeGraph } from '../components/intelligence/KnowledgeSurfaces'
import { countEvidence, groupClaims, humanize } from '../lib/intelligencePresentation'
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

function shouldSearchKnowledge(value: string) {
  if (value.length < 2) return false
  if (/^object:/i.test(value) || /^incident:/i.test(value)) return false
  if (/^CVE-\d{4}-\d+$/i.test(value)) return false
  return true
}

function DossierStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return <div className={`dossier-stat tone-${tone}`}><small>{label}</small><strong>{value}</strong></div>
}
