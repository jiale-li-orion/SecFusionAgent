import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getWorldKnowledgeChanges, getWorldStories, getHotWorldItem, getHotWorld, getWorldOverview, getWorldFormation, getWorldIncidentCandidates, type WorldIncidentCandidate, type WorldStory } from '../lib/api/world'
import { WorldScene } from '../components/world/WorldScene'
import { useI18n } from '../lib/i18n'
import { projectHot } from '../lib/worldHotPresentation'

export function WorldPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [hotPage, setHotPage] = useState(0)
  const hotPageSize = 24
  const query = useQuery({ queryKey: ['world-stories', 'facts-v2'], queryFn: () => getWorldStories(12), refetchInterval: 60_000 })
  const hotCoordinate = params.get('hot')?.split(':')
  const hot = useQuery({
    queryKey: ['world-hot-detail', ...(hotCoordinate ?? [])],
    queryFn: () => getHotWorldItem(hotCoordinate![0], hotCoordinate!.slice(1).join(':')),
    enabled: Boolean(hotCoordinate?.length && hotCoordinate.length > 1), retry: false,
  })
  const workingSet = useQuery({ queryKey: ['world-working-set', hotPage], queryFn: () => getHotWorld(hotPageSize, hotPage * hotPageSize),
    refetchInterval: 30_000 })
  const candidateSet = useQuery({ queryKey: ['world-incident-candidates', 32], queryFn: () => getWorldIncidentCandidates(32), refetchInterval: 30_000 })
  const overview = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const formation = useQuery({ queryKey: ['world-formation'], queryFn: getWorldFormation, refetchInterval: 15_000 })
  const changes = useQuery({ queryKey: ['world-knowledge-changes'], queryFn: () => getWorldKnowledgeChanges(6), refetchInterval: 15_000 })
  const hotStory = hot.data ? projectHot(hot.data) : null
  const hotStories = (workingSet.data?.items ?? []).map(projectHot)
  const stories = [ ...(query.data?.items ?? []), ...hotStories, ...(candidateSet.data?.items ?? []).map(projectCandidate) ]
  if (hotStory && !stories.some(s => s.story_id === hotStory.story_id)) stories.push(hotStory)

  function focus(story: WorldStory) {
    const next = new URLSearchParams({ story: story.story_id })
    if (story.kind === 'HotVulnerability') next.set('hot', story.story_id.slice(4))
    if (params.get('view')) next.set('view', params.get('view')!)
    setParams(next, { replace: true })
  }
  function openHotFromAtlas(story: WorldStory) {
    setParams(new URLSearchParams({ view: 'hot', story: story.story_id, hot: story.story_id.slice(4) }), { replace: true })
  }
  function open(story: WorldStory) {
    const context = { from: 'world', worldRef: story.story_id }
    if (story.incident_id) navigate(`/intelligence?${new URLSearchParams({ ...context, incident: story.incident_id })}`)
    else if (story.object_id) navigate(`/intelligence?${new URLSearchParams({ ...context, object: story.object_id })}`)
    else if (story.kind === 'HotVulnerability') navigate(`/intelligence?${new URLSearchParams({ ...context, cve: String(story.facts.cve_id ?? story.facts.external_object_id), hot: story.story_id.slice(4) })}`)
  }
  function investigate(story: WorldStory) {
    const incidentWithoutTarget = Boolean(story.incident_id && !story.object_id)
    const next = new URLSearchParams({ profile: incidentWithoutTarget ? 'RETRIEVE' : 'INVESTIGATE', from: 'world', origin: story.story_id, targetLabel: story.headline,
      question: incidentWithoutTarget
        ? text(`围绕事件「${story.headline}」检索现有证据、来源、冲突与未知。`, `Search existing evidence, sources, conflicts and unknowns for “${story.headline}”.`)
        : text(`调查「${story.headline}」的安全机制、影响范围与证据。`, `Investigate the mechanism, impact and evidence of “${story.headline}”.`) })
    if (story.object_id) next.set('object', story.object_id)
    if (story.incident_id) next.set('incident', story.incident_id)
    if (story.kind === 'HotVulnerability' && typeof story.facts.cve_id === 'string') next.set('cve', story.facts.cve_id)
    navigate(`/start?${next}`)
  }
  return <WorldScene stories={stories} hotStories={hotStories} focusedId={params.get('story') ?? hotStory?.story_id ?? null}
    region={params.get('source')} onRegion={source => { setParams(current => { const next = new URLSearchParams(current); if (source) next.set('source', source); else next.delete('source'); return next }, { replace: true }) }}
    onHotRetry={() => void workingSet.refetch()} view={params.get('view') ?? (hotCoordinate ? 'hot' : 'stories')} onView={view => { const next = new URLSearchParams(params); next.set('view', view); next.delete('story'); next.delete('hot'); next.delete('source'); setParams(next, { replace: true }) }}
    changes={changes.data?.items ?? []} overview={overview.data} overviewFailed={overview.isError} onOverviewRetry={() => void overview.refetch()} formation={formation.data} formationFailed={formation.isError} onFormationRetry={() => void formation.refetch()} hotTotal={workingSet.data?.resident_total} hotFailed={workingSet.isError} hotPending={workingSet.isPending} hotPage={hotPage} hotPageSize={hotPageSize}
    onHotPage={page => { setHotPage(page); setParams(current => { const next = new URLSearchParams(current); next.delete('story'); next.delete('hot'); return next }, { replace: true }) }}
    pending={query.isPending} failed={query.isError} candidatePending={candidateSet.isPending} candidateFailed={candidateSet.isError}
    onFocus={focus} onHotFromAtlas={openHotFromAtlas} onOpen={open} onInvestigate={investigate} onRetry={() => void query.refetch()}
    onCandidateRetry={() => void candidateSet.refetch()} />
}

function projectCandidate(item: WorldIncidentCandidate): WorldStory {
  return {
    story_id: `candidate:${item.candidate_id}`, category: 'incidents', kind: 'IncidentCandidate',
    headline: item.headline, excerpt: item.summary, excerpt_origin: item.summary ? 'source_field' : null,
    happened_at: item.published_at ?? item.observed_at, observed_at: item.observed_at,
    published_at: item.published_at, source_id: item.source_id, source_name: item.source_name ?? item.source_id,
    object_id: null, incident_id: null, external_ref: item.canonical_url, evidence: null,
    facts: { candidate_id: item.candidate_id, signal_id: item.signal_id, source_role: item.source_role, signal_count: item.signal_count,
      independent_source_count: item.independent_source_count, anchor_count: item.anchor_count,
      promotion_state: item.promotion_state, unresolved_question_count: item.unresolved_question_count },
  }
}
