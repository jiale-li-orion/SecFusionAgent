import { IntelligenceHome, type IntelligenceChannel } from '../components/intelligence/IntelligenceHome'
import '../components/intelligence/intelligence.css'
import { useDeferredValue, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  ArrowLeft,
  FileSearch,
  Search,
} from '../components/ui/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  getDocumentByObject,
  getHotWorld,
  getHotWorldItem,
  getWorldStories,
  getWorldIncidentCandidates,
  getIncident,
  getIntelligenceEnrichment,
  getKnowledgeObject,
  getVulnerability,
  listIncidents,
  searchIntelligence,
} from '../lib/api'
import { HotWorkingSetPanel, IncidentDossier, IntelligenceArchiveBlueprint } from '../components/intelligence/DossierSurfaces'
import { DossierHeading, DossierReader, type DossierView } from '../components/intelligence/DossierReader'
import { presentationTitle } from '../components/intelligence/feedPresentation'
import { EvidenceOverlay } from '../components/investigations/CaseSurfaces'
import { humanize } from '../lib/intelligencePresentation'
import { useI18n } from '../lib/i18n'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'

export function IntelligencePage() {
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
  const channel: IntelligenceChannel = ['following', 'hot', 'events', 'library'].includes(params.get('channel') ?? '') ? params.get('channel') as IntelligenceChannel : 'recommended'
  const hasSelection = Boolean(paramObject || paramIncident || paramCve || paramEvidence)
  function destination(values: Record<string, string>) { return { channel, ...(params.get('category') ? { category: params.get('category')! } : {}), ...values } }
  const [inputOverride, setInputOverride] = useState<string | null>(null)
  const [searchError, setSearchError] = useState('')
  const [searchBusy, setSearchBusy] = useState(false)
  const input = inputOverride ?? (paramIncident ? `incident:${paramIncident}` : paramObject ? `object:${paramObject}` : paramCve || paramQuery)
  const deferredInput = useDeferredValue(input.trim())
  const evidenceRef = paramEvidence
  const readingMode: DossierView = ['graph', 'evidence', 'enrichment'].includes(paramView ?? '') ? paramView as DossierView : 'dossier'
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
  const entryQuery = useQuery({ queryKey: ['intelligence-recent-sources', 18], queryFn: () => getWorldStories(18), enabled: !selectedCve && !paramObject && !paramIncident, staleTime: 30_000 })
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
  async function refreshDossier() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['knowledge-object', selectedObjectId || selectedCve] }),
      queryClient.invalidateQueries({ queryKey: ['intelligence-enrichment', obj?.object_id] }),
      queryClient.invalidateQueries({ queryKey: ['knowledge-network', obj?.object_id] }),
      queryClient.invalidateQueries({ queryKey: ['world-hot-intelligence'] }),
    ])
  }
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
  const headline = presentationTitle(incident
    ? incident.incident.current_summary || humanize(incident.incident.incident_type)
    : (typeof displayName === 'string' && displayName) || obj?.external_identifiers.cve?.[0] || obj?.canonical_key || selectedCve || selectedObjectId || text('选择一个对象', 'SELECT AN OBJECT'))

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
    if (/^CVE-\d{4}-\d+$/.test(value)) setParams(destination({ cve: value }))
    else if (incidentMatch?.[1]?.trim()) setParams(destination({ incident: incidentMatch[1].trim() }))
    else if (objectMatch?.[1]?.trim()) setParams(destination({ object: objectMatch[1].trim() }))
    else {
      setSearchBusy(true)
      try {
        const result = await searchIntelligence(raw, 12)
        if (result.items[0]) openSearchResult(result.items[0].object_id)
        else setSearchError(text('没有找到匹配内容，试试其他关键词。', 'No matching material. Try another keyword.'))
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
    setParams(destination({ object: objectId }))
  }

  function selectReadingMode(nextMode: DossierView) {
    setParams(current => {
      const next = new URLSearchParams(current)
      if (nextMode === 'dossier') next.delete('view')
      else next.set('view', nextMode)
      next.delete('evidence')
      return next
    }, { replace: true })
  }

  function openEvidence(ref: string) {
    setParams(current => { const next = new URLSearchParams(current); next.set('evidence', ref); return next }, { replace: true })
  }

  function closeEvidence() {
    setParams(current => { const next = new URLSearchParams(current); next.delete('evidence'); return next }, { replace: true })
  }

  function openMission(profile: 'VERIFY' | 'INVESTIGATE' | 'RETRIEVE') {
    const mission = new URLSearchParams()
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
      : obj?.object_type === 'Repo'
      ? text(`调查 ${headline} 的安全风险。请结合已知公告、问题记录和代码变更分析，并说明已确认的发现、来源分歧及仍待核实的问题，附上证据来源。`, `Investigate security risks in ${headline} using available advisories, issues and code changes. Explain confirmed findings, source disagreements and open questions, with citations.`)
      : obj?.object_type === 'Vulnerability'
        ? text(`调查 ${headline} 的影响范围、利用情况和修复措施，结合来源解释结论，并明确哪些问题仍缺少证据。`, `Investigate the affected scope, exploitation and remediation of ${headline}. Explain the findings with sources and identify unresolved evidence gaps.`)
        : text(`调查 ${headline} 的主要事实及关联背景。请分析来源证据、相互冲突的信息和仍待核实的问题，给出带引用的分析。`, `Investigate the key facts and context of ${headline}. Analyze supporting evidence, source conflicts and open questions in a cited report.`)
    mission.set('question', prompt)
    navigate(`/start?${mission.toString()}`)
  }

  return (
    <section className={`intel-experience ${hasSelection ? 'has-dossier' : 'intel-home'}`}>
      <header className="intel-page-heading"><div>{hasSelection && <button className="intel-back" onClick={() => { setInputOverride(null); setParams(destination({})) }}><ArrowLeft size={15}/>{text('返回情报', 'Back to intelligence')}</button>}{!hasSelection && <><span className="intel-page-kicker">SECFUSION / INTELLIGENCE</span><h1>{text('情报', 'Intelligence')}</h1><p>{text('跟进值得关注的变化，沿证据读懂它的来龙去脉。', 'Follow what matters and trace each story to its evidence.')}</p></>}</div>
        {!hasSelection && <form className="intel-search intel-discovery-search" onSubmit={submitSearch}>
          <Search size={15} />
          <Input value={input} onChange={(event) => setInputOverride(event.target.value)} aria-label={text("查找情报对象", "Find an intelligence object")} placeholder={text("论文、项目、漏洞编号或资产名称", "Paper, project, vulnerability or asset")} />
          <Button size="sm" type="submit" disabled={searchBusy}>{searchBusy ? text('检索中…', 'SEARCHING…') : text('搜索', 'Search')}</Button>
          <AnimatePresence>
            {shouldSearchKnowledge(input.trim()) && (
              <motion.div
                className="intel-object-search-results"
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
              >
                <div className="intel-object-search-head">
                  <small>{text('搜索结果', 'Search results')}</small>
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
                    <p>{text('没有找到匹配内容，试试其他关键词。', 'No matching material. Try another keyword.')}</p>
                  )}
                  {objectSearchQuery.isError && <p className="error-block">{String(objectSearchQuery.error.message)}</p>}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          {searchError && <span className="intel-search-error">{searchError}</span>}
        </form>}
      </header>

      {originSpace === 'world' && worldRef && <div className="dossier-return-link"><Button variant="ghost" size="sm" onClick={() => navigate('/')}><ArrowLeft size={14}/>{text('返回世界', 'Back to world')}</Button></div>}

      {!hasSelection && <IntelligenceHome channel={channel} onChannel={next => { setInputOverride(null); setParams({ channel: next }) }} onOpen={(objectId, evidence) => { setInputOverride(null); setParams(destination({ object: objectId, ...(evidence ? { evidence } : {}) })) }}
        stories={entryQuery.data?.items ?? []} hot={hotQuery.data?.items ?? []} hotTotal={hotQuery.data?.resident_total ?? 0} candidates={candidateQuery.data?.items ?? []} candidateTotal={candidateQuery.data?.total ?? 0}
        loading={entryQuery.isPending} hotLoading={hotQuery.isPending} candidateLoading={candidateQuery.isPending} error={entryQuery.isError ? String(entryQuery.error.message) : null} hotError={hotQuery.isError ? String(hotQuery.error.message) : null} candidateError={candidateQuery.isError ? String(candidateQuery.error.message) : null}
        onSelect={item => { if (item.object_id) openSearchResult(item.object_id); else if (item.incident_id) setParams(destination({ incident: item.incident_id })) }} onHotSelect={item => setParams(destination({ cve: item.cve_id ?? item.external_object_id, hot: `${item.source_id}:${item.external_object_id}` }))} onCandidateSelect={item => navigate(`/?${new URLSearchParams({ view: 'stories', source: 'incidents', story: `candidate:${item.candidate_id}` })}`)}
        incidents={incidentListQuery.data?.items ?? []} incidentsLoading={incidentListQuery.isPending} incidentsError={incidentListQuery.isError} onRetryIncidents={() => void incidentListQuery.refetch()} onIncident={id => setParams(destination({ incident: id }))}/>}

      {hasSelection && <motion.div className="dossier-reading-content" initial={reduceMotion ? false : { opacity:0, y:6 }} animate={{ opacity:1,y:0 }} transition={{duration:.18}}>
        {obj && <DossierReader obj={obj} headline={headline} cveId={obj.external_identifiers.cve?.[0] || selectedCve || headline} view={readingMode} onView={selectReadingMode} onEvidence={openEvidence} onMission={openMission}
          onOpenTarget={openSearchResult}
          enrichment={enrichmentQuery.data ?? null} enrichmentLoading={enrichmentQuery.isLoading} enrichmentError={enrichmentQuery.isError} retryEnrichment={() => void enrichmentQuery.refetch()} refresh={refreshDossier}
          document={documentQuery.data ?? null} documentLoading={documentQuery.isLoading} documentError={documentQuery.isError ? String(documentQuery.error.message) : null}/>}
        {incident && <><DossierHeading title={headline} kind={text('事件档案', 'Event dossier')} coordinate={incident.incident.incident_id} stats={[
          {label:text('条记录', 'records'),value:incident.incident.timeline_event_count}, {label:text('个来源', 'sources'),value:incident.incident.source_link_count}, {label:text('个独立来源', 'independent sources'),value:incident.incident.source_diversity_count},
        ]}><Button onClick={() => openMission('RETRIEVE')}><FileSearch size={15}/>{text('检索事件证据', 'Search incident evidence')}</Button></DossierHeading><IncidentDossier incident={incident} onEvidence={openEvidence}/></>}
        {knowledgeQuery.isError && !hotMatch && <div className="intel-state error-block" role="alert"><span>{text('这份档案暂时无法读取。', 'This dossier could not be loaded.')}</span><Button variant="outline" onClick={() => void knowledgeQuery.refetch()}>{text('重新读取', 'Retry')}</Button></div>}
        {!obj && hotMatch && <><HotWorkingSetPanel item={hotMatch}/><Button onClick={() => openMission('VERIFY')}>{text('核验并建立档案', 'Verify and build a dossier')}</Button></>}
        {!obj && (selectedCve || selectedObjectId) && !hotMatch && !knowledgeQuery.isError && <IntelligenceArchiveBlueprint target={selectedCve || selectedObjectId}/>}
        {paramIncident && incidentQuery.isPending && <div className="intel-state" role="status">{text('正在读取事件档案…', 'Reading incident dossier…')}</div>}
        {incidentQuery.isError && <div className="intel-state error-block" role="alert"><span>{text('事件档案暂时无法读取。', 'The event dossier could not be loaded.')}</span><Button variant="outline" onClick={() => void incidentQuery.refetch()}>{text('重新读取', 'Retry')}</Button></div>}
      </motion.div>}
      <AnimatePresence>{evidenceRef && <EvidenceOverlay key={evidenceRef} evidenceRef={evidenceRef} onClose={closeEvidence}/>}</AnimatePresence>
    </section>
  )
}

function shouldSearchKnowledge(value: string) {
  if (value.length < 2) return false
  if (/^object:/i.test(value) || /^incident:/i.test(value)) return false
  if (/^CVE-\d{4}-\d+$/i.test(value)) return false
  return true
}
