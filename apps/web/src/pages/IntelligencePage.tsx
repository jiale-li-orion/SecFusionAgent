import { IntelligenceIndex } from '../components/intelligence/IntelligenceIndex'
import { ProductGlyph } from '../components/instrument/ProductGlyph'
import { SpaceHeading } from '../components/instrument/SpaceHeading'
import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  FileSearch,
  GitBranch,
  Link2,
  Search,
  ShieldCheck,
  Telescope,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  getDocumentByObject,
  getHotWorld,
  getHotWorldItem,
  getWorldStories,
  getWorldIncidentCandidates,
  getIncident,
  getIntelligenceEnrichment,
  getIntelligenceGraph,
  getKnowledgeObject,
  getVulnerability,
  listIncidents,
  searchIntelligence,
} from '../lib/api'
import { EnrichmentConstellation } from '../components/intelligence/EnrichmentConstellation'
import { ProductEnrichmentActions } from '../components/intelligence/ProductEnrichmentActions'
import { PersonalizedIntelligence } from '../components/intelligence/PersonalizedIntelligence'
import { ClaimGroup, DocumentIndexDossier, HotWorkingSetPanel, IncidentArchiveRail, IncidentDossier, IntelligenceArchiveBlueprint, ObjectFacetField } from '../components/intelligence/DossierSurfaces'
import { EvidenceInspector, FocusedKnowledgeGraph } from '../components/intelligence/KnowledgeSurfaces'
import { countEvidence, groupClaims, humanize } from '../lib/intelligencePresentation'
import { useI18n } from '../lib/i18n'
import { useAuth } from '../lib/auth'
import { AccountLoginPrompt } from '../components/auth/RequireAccount'

export function IntelligencePage() {
  const auth = useAuth()
  const { text } = useI18n()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const reduceMotion = Boolean(useReducedMotion())
  const [params, setParams] = useSearchParams()
  const originSpace = params.get('from')
  const worldRef = params.get('worldRef')
  const paramQuery = params.get('q') ?? ''
  const paramCve = params.get('cve') ?? ''
  const paramObject = params.get('object') ?? ''
  const paramEvidence = params.get('evidence')
  const paramIncident = params.get('incident') ?? ''
  const paramView = params.get('view')
  const [inputOverride, setInputOverride] = useState<string | null>(null)
  const [searchError, setSearchError] = useState('')
  const [searchBusy, setSearchBusy] = useState(false)
  const input = inputOverride ?? (paramIncident ? `incident:${paramIncident}` : paramObject ? `object:${paramObject}` : paramCve || paramQuery)
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
  const candidateQuery = useQuery({ queryKey: ['world-incident-candidates', 32], queryFn: () => getWorldIncidentCandidates(32), staleTime: 20_000 })
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

  const selectedCve = paramObject || paramIncident || paramQuery ? '' : paramCve
  const entryQuery = useQuery({ queryKey: ['intelligence-recent-sources'], queryFn: () => getWorldStories(18), enabled: !selectedCve && !paramObject && !paramIncident, staleTime: 30_000 })
  const selectedObjectId = paramIncident ? '' : paramObject
  const hotCoordinate = params.get('hot')?.split(':')
  const hotDetail = useQuery({ queryKey: ['intelligence-hot-detail', ...(hotCoordinate ?? [])], queryFn: () => getHotWorldItem(hotCoordinate![0], hotCoordinate!.slice(1).join(':')), enabled: Boolean(hotCoordinate && hotCoordinate.length > 1), retry: false })
  const hotMatch = hotDetail.data ?? hotQuery.data?.items.find((item) => (item.cve_id ?? item.external_object_id).toUpperCase() === selectedCve.toUpperCase()) ?? null

  const knowledgeQuery = useQuery({
    queryKey: ['knowledge-object', selectedObjectId || selectedCve],
    queryFn: () => selectedObjectId ? getKnowledgeObject(selectedObjectId) : getVulnerability(selectedCve),
    enabled: !paramIncident && Boolean(selectedObjectId || selectedCve),
  })
  const obj = knowledgeQuery.data
  const refreshDossier = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['knowledge-object', selectedObjectId || selectedCve] }),
      queryClient.invalidateQueries({ queryKey: ['intelligence-enrichment', obj?.object_id] }),
      queryClient.invalidateQueries({ queryKey: ['intelligence-graph', obj?.object_id] }),
      queryClient.invalidateQueries({ queryKey: ['world-hot-intelligence'] }),
    ])
  }, [queryClient, selectedObjectId, selectedCve, obj?.object_id])
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
  const displayName = documentQuery.data?.current_revision?.title ?? [obj?.properties.display_name, obj?.properties.title, obj?.properties.full_name, obj?.properties.name, obj?.properties.ip].find((v) => typeof v === 'string' && v)
  const headline = incident
    ? humanize(incident.incident.incident_type)
    : (typeof displayName === 'string' && displayName) || obj?.external_identifiers.cve?.[0] || obj?.canonical_key || selectedCve || selectedObjectId || text('选择一个对象', 'SELECT AN OBJECT')

  async function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    if (searchBusy) return
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
    else {
      setSearchBusy(true)
      try {
        const result = await searchIntelligence(raw, 12)
        if (result.items[0]) openSearchResult(result.items[0].object_id)
        else setSearchError(text('当前 Knowledge World 没有匹配对象。', 'No matching object exists in the current Knowledge World.'))
      } catch (error) {
        setSearchError(error instanceof Error ? error.message : text('情报检索暂不可用。', 'Intelligence search is unavailable.'))
      } finally {
        setSearchBusy(false)
      }
    }
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

  function openMission(profile: 'VERIFY' | 'INVESTIGATE' | 'RETRIEVE') {
    const mission = new URLSearchParams({ profile })
    if (selectedCve) mission.set('cve', selectedCve)
    else if (obj?.object_id) mission.set('object', obj.object_id)
    mission.set('from', 'intelligence')
    mission.set('targetLabel', headline)
    mission.set('origin', incident
      ? `incident:${incident.incident.incident_id}`
      : obj?.object_id
        ? `object:${obj.object_id}`
        : selectedCve
          ? `cve:${selectedCve}`
          : 'intelligence')
    const prompt = profile === 'RETRIEVE'
      ? text(`围绕事件「${headline}」检索现有证据：已确认什么、来源是什么、还有哪些未知或相互冲突的信息？`, `Search existing evidence about “${headline}”: what is confirmed, which sources support it, and what remains unknown or conflicting?`)
      : profile === 'VERIFY'
      ? text(`核验 ${headline} 的关键事实，列出来源和仍待确认的问题。`, `Verify the key Claims, Relations, and Evidence boundaries for ${headline}.`)
      : text(`调查 ${headline} 的关联证据、冲突、未知与外部上下文。`, `Investigate the related evidence, conflicts, unknowns, and external context for ${headline}.`)
    mission.set('question', prompt)
    navigate(`/start?${mission.toString()}`)
  }

  return (
    <section className={`intelligence-space studio-intelligence intelligence-page ${obj || incident ? 'has-dossier' : 'archive-empty'}`}>
      <SpaceHeading index="02" eyebrow="INTELLIGENCE / KNOWLEDGE" title={text('情报档案', 'Intelligence, in context.')} description={text('从原文进入对象，从关系回到证据。', 'Read the source. Explore the relations. Return to the evidence.')}>
        <form className="intel-search" onSubmit={submitSearch}>
          <Search size={15} />
          <input value={input} onChange={(event) => setInputOverride(event.target.value)} aria-label={text("查找情报对象", "Find an intelligence object")} placeholder={text("论文、项目、漏洞编号或资产名称", "Paper, project, vulnerability or asset")} />
          <button type="submit" disabled={searchBusy}>{searchBusy ? text('检索中…', 'SEARCHING…') : text('打开档案', 'OPEN DOSSIER')}</button>
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
                      <div><strong>{item.label}</strong></div>

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
      </SpaceHeading>

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
          {(obj || incident || selectedCve || selectedObjectId) && <article className="dossier-hero">
            <div className="dossier-id">
              <span className={`dossier-sigil ${incident ? 'incident' : ''}`}><ProductGlyph kind={incident ? 'incidents' : obj?.object_type === 'Vulnerability' ? 'vulnerability' : obj?.object_type === 'ResearchWork' || obj?.object_type === 'Document' ? 'academic' : obj?.object_type === 'Repo' ? 'development' : 'assets'} size={30}/></span>
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
            {(obj || hotMatch?.cve_id || incident) && (
              <div className="dossier-mission-actions">
                {incident ? <button onClick={() => openMission('RETRIEVE')}><FileSearch size={13} /><span>{text('围绕事件检索证据', 'Search evidence for this incident')}</span><em>ORACLE · RETRIEVE</em></button> : <><button onClick={() => openMission('VERIFY')}><ShieldCheck size={13} /><span>{text(hotMatch && !obj ? '核验这个 Hot CVE' : '核验这个对象', hotMatch && !obj ? 'VERIFY THIS HOT CVE' : 'VERIFY OBJECT')}</span><em>ARGUS · VERIFY</em></button><button onClick={() => openMission('INVESTIGATE')}><Telescope size={13} /><span>{text('展开调查', 'INVESTIGATE')}</span><em>ARGUS · INVESTIGATE</em></button></>}
              </div>
            )}
            {incident && <p className="incident-mission-boundary">{text('事件档案为检索提供问题上下文；回答只依据实际检索到的证据，不会自动将事件绑定为核验目标。', 'The incident frames the search question. The answer relies on retrieved evidence; this is not a target-bound verification.')}</p>}
            {obj && (
              <div className="intel-reading-switch" role="tablist" aria-label={text('情报阅读视角', 'Intelligence reading view')}>
                <button role="tab" aria-selected={readingMode === 'dossier'} className={readingMode === 'dossier' ? 'active' : ''} onClick={() => { selectReadingMode('dossier'); setReturnReadingMode('dossier') }}><FileSearch size={12} /> {text('档案', 'DOSSIER')}</button>
                <button role="tab" aria-selected={readingMode === 'graph'} className={readingMode === 'graph' ? 'active' : ''} onClick={() => { selectReadingMode('graph'); setReturnReadingMode('graph') }}><GitBranch size={12} /> {text('关系图谱', 'GRAPH')}</button>
                <button role="tab" aria-selected={readingMode === 'evidence'} className={readingMode === 'evidence' ? 'active' : ''} onClick={() => selectReadingMode('evidence', evidenceRef ?? undefined)}><Link2 size={12} /> {text('证据', 'EVIDENCE')}</button>
                <motion.i layoutId="intel-reading-cursor" transition={{ type: 'spring', stiffness: 320, damping: 28 }} className={`cursor-${readingMode}`} />
              </div>
            )}
          </article>}

          {incident ? (
            <IncidentDossier incident={incident} onEvidence={openEvidence} />
          ) : (
            <>
              {readingMode === 'dossier' && (
                <>
                  {obj && (obj.object_type === 'Document' || obj.object_type === 'ResearchWork') && (
                    <DocumentIndexDossier
                      document={documentQuery.data ?? null}
                      loading={documentQuery.isLoading}
                      error={documentQuery.isError ? String(documentQuery.error.message) : null}
                    />
                  )}
                  {obj?.object_type === 'Vulnerability'
                    ? <><EnrichmentConstellation
                        claims={obj?.claims ?? []}
                        relations={obj.relations}
                        onEvidence={openEvidence}
                        cveId={selectedCve || headline}
                        state={enrichmentQuery.data ?? null}
                        stateLoading={Boolean(obj && enrichmentQuery.isLoading)}
                        stateError={Boolean(obj && enrichmentQuery.isError)}
                      />{auth.authenticated
                        ? <ProductEnrichmentActions objectId={obj.object_id} cveId={obj.external_identifiers.cve?.[0] || selectedCve || headline} state={enrichmentQuery.data ?? null} onChanged={refreshDossier} />
                        : <AccountLoginPrompt title={text('继续补全这份漏洞档案', 'Continue enriching this vulnerability')} description={text('登录后可选择缺失维度，跟踪补全结果。', 'Sign in to select missing dimensions and track enrichment results.')} />}</>
                    : obj ? <ObjectFacetField obj={obj} /> : null}
                </>
              )}

              {knowledgeQuery.isError && !hotMatch && <div className="intel-state error-block"><span>{String(knowledgeQuery.error.message)}</span><button className="recovery-action" onClick={() => void knowledgeQuery.refetch()}>{text('重试 Knowledge read', 'RETRY KNOWLEDGE READ')}</button></div>}
              {!selectedCve && !selectedObjectId && !paramIncident && <><IntelligenceIndex stories={entryQuery.data?.items ?? []} hot={hotQuery.data?.items ?? []} hotTotal={hotQuery.data?.resident_total ?? 0} candidates={candidateQuery.data?.items ?? []} candidateTotal={candidateQuery.data?.total ?? 0} loading={entryQuery.isPending} hotLoading={hotQuery.isPending} candidateLoading={candidateQuery.isPending} error={entryQuery.isError ? String(entryQuery.error.message) : null} hotError={hotQuery.isError ? String(hotQuery.error.message) : null} candidateError={candidateQuery.isError ? String(candidateQuery.error.message) : null} onSelect={item => { if (item.object_id) openSearchResult(item.object_id); else if (item.incident_id) setParams({ incident: item.incident_id }) }} onHotSelect={item => { const cve = item.cve_id ?? item.external_object_id; setParams({ cve, hot: `${item.source_id}:${item.external_object_id}` }) }} onCandidateSelect={item => navigate(`/?${new URLSearchParams({ view: 'stories', source: 'incidents', story: `candidate:${item.candidate_id}` })}`)} />{auth.authenticated ? <PersonalizedIntelligence /> : <AccountLoginPrompt title={text('找到与你有关的情报', 'Find intelligence relevant to you')} description={text('登录后保存关注的技术与对象，查看带有来源的推荐。', 'Sign in to save technologies and objects you follow, and see recommendations with their sources.')} />}</>}
              {!obj && hotMatch && <HotWorkingSetPanel item={hotMatch} />}
              {!obj && (selectedCve || selectedObjectId) && !hotMatch && !knowledgeQuery.isError && <IntelligenceArchiveBlueprint target={selectedCve || selectedObjectId} />}

              {obj && (
                <div className="intel-reading-deck">
                  <div className="intel-section-grid">
                    {groupedClaims.map((group) => (
                      <ClaimGroup key={group.title} title={group.title} claims={group.claims} onEvidence={openEvidence} />
                    ))}
                  </div>

                  {readingMode === 'graph' && <FocusedKnowledgeGraph
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
                  />}
                </div>
              )}
            </>
          )}
          {paramIncident && incidentQuery.isPending && <div className="intel-state" role="status">{text('正在读取事件档案与来源时间线…', 'Reading incident dossier and source timeline…')}</div>}
          {incidentQuery.isError && <div className="intel-state error-block" role="alert"><span>{String(incidentQuery.error.message)}</span><button className="recovery-action" onClick={() => void incidentQuery.refetch()}>{text('重试 Incident read', 'RETRY INCIDENT READ')}</button></div>}
        </motion.div>

        {(readingMode === 'evidence' || Boolean(paramIncident) || incidentListQuery.isError || (incidentListQuery.data?.items.length ?? 0) > 0) && <aside className="intel-side">
          <IncidentArchiveRail
            items={incidentListQuery.data?.items ?? []}
            loading={incidentListQuery.isLoading}
            error={incidentListQuery.isError}
            onRetry={() => void incidentListQuery.refetch()}
            activeId={paramIncident}
            onSelect={(incidentId) => {
              setInputOverride(null)
              setParams({ incident: incidentId })
            }}
          />
          {readingMode === 'evidence' && <EvidenceInspector evidenceRef={evidenceRef} onClose={closeEvidence} />}
        </aside>}
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
