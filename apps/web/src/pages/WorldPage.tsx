import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  ArrowUpRight,
  Crosshair,
  Flame,
  Sparkles,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getHotWorld, getHotWorldItem, getWorldIncidentCandidates, getWorldKnowledgeChanges, getWorldOverview, listIncidents, type HotBug } from '../lib/api'
import { HotLens, PathLens, SourceLens, Telemetry, WorldField2D, WorldIncidentCluster, WorldLiveFlow } from '../components/world/WorldSurfaces'
import { KnowledgeChangeRail } from '../components/world/KnowledgeChangeRail'
import { hotIdentity, laneClass, laneSlug, parseHotIdentity, snapshotAge, sourceNarrative, sourceState, sources, worldLanePoints, worldWindows, type WorldWindow } from '../components/world/worldModel'
import { useI18n } from '../lib/i18n'

export function WorldPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const sourceParam = params.get('source')
  const laneParam = params.get('lane')
  const hotParam = params.get('hot')
  const reduceMotion = Boolean(useReducedMotion())
  const focusedSource = sourceParam && sources.some((source) => source.key === sourceParam) ? sourceParam : null
  const focusedLane = laneParam && Object.hasOwn(worldLanePoints, laneParam) ? laneParam : null
  const focusedHotKey = hotParam
  const focusedHotCoordinate = useMemo(() => parseHotIdentity(focusedHotKey), [focusedHotKey])
  const [locator, setLocator] = useState('')
  const [locatorError, setLocatorError] = useState('')
  const [worldWindow, setWorldWindow] = useState<WorldWindow>('1h')
  const [clockNow, setClockNow] = useState(() => Date.now())
  const [knowledgePulseRevision, setKnowledgePulseRevision] = useState<number | null>(null)
  const lastKnowledgeRevision = useRef<number | null>(null)
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const hotQuery = useQuery({ queryKey: ['world-hot'], queryFn: () => getHotWorld(6), refetchInterval: 20_000 })
  const incidentQuery = useQuery({ queryKey: ['world-incidents'], queryFn: () => listIncidents(6), refetchInterval: 30_000 })
  const incidentCandidateQuery = useQuery({ queryKey: ['world-incident-candidates'], queryFn: () => getWorldIncidentCandidates(24), refetchInterval: 20_000 })
  const knowledgeChangeQuery = useQuery({ queryKey: ['world-knowledge-changes'], queryFn: () => getWorldKnowledgeChanges(8), refetchInterval: 15_000 })
  const hotDetailQuery = useQuery({
    queryKey: ['world-hot-detail', focusedHotCoordinate?.sourceId, focusedHotCoordinate?.externalObjectId],
    queryFn: () => getHotWorldItem(focusedHotCoordinate!.sourceId, focusedHotCoordinate!.externalObjectId),
    enabled: Boolean(focusedHotCoordinate),
    refetchInterval: focusedHotCoordinate ? 20_000 : false,
    retry: false,
  })
  const snapshot = worldQuery.data
  const oneHour = snapshot?.windows['1h']
  const activeWindow = snapshot?.windows[worldWindow] ?? oneHour
  const requestedHours = worldWindow === '1h' ? 1 : worldWindow === '6h' ? 6 : worldWindow === '24h' ? 24 : 168
  const flowSeries = useMemo(() => {
    const series = snapshot?.hourly_series ?? []
    return series.slice(-Math.min(requestedHours, series.length))
  }, [requestedHours, snapshot?.hourly_series])
  const categoryHealth = useMemo(() => new Map(snapshot?.categories.map((item) => [item.category, item]) ?? []), [snapshot?.categories])
  const hotItems = useMemo(() => hotQuery.data?.items ?? [], [hotQuery.data?.items])
  const focusedHot = hotDetailQuery.data
    ?? hotItems.find((item) => hotIdentity(item) === focusedHotKey)
    ?? null
  const focusedSourceMeta = sources.find((source) => source.key === focusedSource) ?? null
  const hasFocus = Boolean(focusedSourceMeta || focusedHotKey || focusedLane)
  const snapshotFresh = snapshot ? clockNow - new Date(snapshot.generated_at).getTime() <= 120_000 : false
  const latestKnowledgeChange = knowledgeChangeQuery.data?.items[0] ?? null
  const knowledgeChangeActive = latestKnowledgeChange?.revision === knowledgePulseRevision

  useEffect(() => {
    const timer = window.setInterval(() => setClockNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!latestKnowledgeChange) return
    const nextRevision = latestKnowledgeChange.revision
    if (lastKnowledgeRevision.current === nextRevision) return
    const initialObservation = lastKnowledgeRevision.current === null
    lastKnowledgeRevision.current = nextRevision
    const age = Date.now() - new Date(latestKnowledgeChange.committed_at).getTime()
    if (initialObservation && age > 300_000) return
    setKnowledgePulseRevision(nextRevision)
    const timer = window.setTimeout(() => {
      setKnowledgePulseRevision((current) => current === nextRevision ? null : current)
    }, 6_500)
    return () => window.clearTimeout(timer)
  }, [latestKnowledgeChange])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      const nextParams = new URLSearchParams(params)
      nextParams.delete('source')
      nextParams.delete('lane')
      nextParams.delete('hot')
      setParams(nextParams, { replace: true })
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [params, setParams])

  function focusSource(key: string) {
    const next = focusedSource === key ? null : key
    const nextParams = new URLSearchParams(params)
    nextParams.delete('lane')
    nextParams.delete('hot')
    if (next) nextParams.set('source', next)
    else nextParams.delete('source')
    setParams(nextParams, { replace: true })
  }

  function openIncident(incidentId: string) {
    navigate(`/intelligence?${new URLSearchParams({ incident: incidentId, from: 'world', worldRef: `incident:${incidentId}` }).toString()}`)
  }

  function openKnowledgeObject(objectId: string, changeId: string) {
    navigate(`/intelligence?${new URLSearchParams({ object: objectId, from: 'world', worldRef: `knowledge-change:${changeId}` }).toString()}`)
  }

  function focusHot(item: HotBug) {
    const nextParams = new URLSearchParams(params)
    nextParams.delete('source')
    nextParams.delete('lane')
    const key = hotIdentity(item)
    if (focusedHotKey === key) nextParams.delete('hot')
    else nextParams.set('hot', key)
    setParams(nextParams, { replace: true })
  }

  function clearFocus() {
    const nextParams = new URLSearchParams(params)
    nextParams.delete('source')
    nextParams.delete('lane')
    nextParams.delete('hot')
    setParams(nextParams, { replace: true })
  }

  function focusLane(lane: string) {
    const nextParams = new URLSearchParams(params)
    nextParams.delete('source')
    nextParams.delete('hot')
    if (focusedLane === lane) nextParams.delete('lane')
    else nextParams.set('lane', lane)
    setParams(nextParams, { replace: true })
  }

  function locateObject(event: React.FormEvent) {
    event.preventDefault()
    const raw = locator.trim()
    if (!raw) return
    const canonical = raw.toUpperCase()
    setLocatorError('')
    if (/^CVE-\d{4}-\d+$/.test(canonical)) {
      const query = new URLSearchParams({ cve: canonical, from: 'world', worldRef: `cve:${canonical}` })
      navigate(`/intelligence?${query.toString()}`)
      return
    }
    if (/^object:/i.test(raw)) {
      const objectId = raw.replace(/^object:/i, '').trim()
      if (objectId) {
        const query = new URLSearchParams({ object: objectId, from: 'world', worldRef: `object:${objectId}` })
        navigate(`/intelligence?${query.toString()}`)
        return
      }
    }
    setLocatorError(text('请输入规范 CVE，或 object:<id>。', 'Enter a canonical CVE or object:<id>.'))
  }

  return (
    <section className="world-space">
      <header className="world-title-lockup">
        <div>
          <p>{text('八类来源发声，证据决定何者沉淀', 'EIGHT SOURCES SPEAK; EVIDENCE DECIDES WHAT ENDURES')}</p>
          <h1>{text('证据', 'EVIDENCE')} <span>{text('世界', 'WORLD')}</span></h1>
          <small>{text(
            '八类异构来源经漏洞流、开发索引、洞察语料与事件监测进入同一证据世界；Hot Layer 保留活跃对象，Evidence / Knowledge / Incident / Insight / Experience 构成持久核心。',
            'Eight heterogeneous source families enter Bug Stream, Structured Development Index, Insight Corpus, and Incident Watch. Hot Layer retains active objects while Evidence / Knowledge / Incident / Insight / Experience form the durable inner world.',
          )}</small>
        </div>

        <div className="world-hero-actions">
          <button onClick={() => navigate('/observatory')}>{text('查看运行证据', 'OPEN RUNTIME PROOF')} <ArrowUpRight size={13} /></button>
          <button className="launch" onClick={() => navigate('/start')}><Sparkles size={13} /> {text('发起调查', 'START INVESTIGATION')}</button>
        </div>
      </header>

      <form className="world-locator" onSubmit={locateObject}>
        <Search size={15} />
        <input
          value={locator}
          onChange={(event) => setLocator(event.target.value)}
          placeholder={text('定位 CVE / object:id', 'LOCATE CVE / object:id')}
        />
        <button type="submit">{text('打开档案', 'OPEN')}</button>
        {locatorError && <span>{locatorError}</span>}
      </form>

      <div className="world-status-strip">
        <div className="world-telemetry">
          <div className="world-time-lens">
            {worldWindows.map((window) => <button key={window} className={worldWindow === window ? 'active' : ''} onClick={() => setWorldWindow(window)}>{window === '168h' ? '7d' : window}</button>)}
          </div>
          <Telemetry label="SOURCE HEALTH" value={snapshot ? `${snapshot.source_health.healthy}/${snapshot.source_health.healthy + snapshot.source_health.degraded + snapshot.source_health.blocked}` : '—'} detail={snapshot ? text(`${(snapshot.healthy_rate * 100).toFixed(1)}% 健康`, `${(snapshot.healthy_rate * 100).toFixed(1)}% healthy`) : worldQuery.isError ? text('不可用', 'unavailable') : text('解析中', 'resolving')} tone="lime" />
          <Telemetry label={`FRESH CHANGES · ${worldWindow === '168h' ? '7D' : worldWindow.toUpperCase()}`} value={activeWindow ? String(activeWindow.fresh_external_changes) : '—'} detail={activeWindow ? text(`${activeWindow.observations} 条 observations`, `${activeWindow.observations} observations`) : text('运行快照', 'operational snapshot')} tone="cyan" />
          <Telemetry label={`CANONICAL WRITES · ${worldWindow === '168h' ? '7D' : worldWindow.toUpperCase()}`} value={activeWindow ? String(activeWindow.canonical_writes) : '—'} detail={activeWindow ? `${activeWindow.backfill_observations} backfill` : text('运行快照', 'operational snapshot')} tone="violet" />
          <Telemetry label="SNAPSHOT AGE" value={snapshot ? snapshotAge(snapshot.generated_at) : '—'} detail={snapshot ? new Date(snapshot.generated_at).toLocaleString() : text('等待 truth source', 'loading truth source')} tone="blue" />
        </div>
        <WorldIncidentCluster
          compact
          incidents={incidentQuery.data?.items ?? []}
          candidates={incidentCandidateQuery.data?.items ?? []}
          candidateTotal={incidentCandidateQuery.data?.total ?? 0}
          signalTotal={incidentCandidateQuery.data?.total_signals ?? 0}
          multiSourceCandidates={incidentCandidateQuery.data?.multi_source_candidates ?? 0}
          anchoredCandidates={incidentCandidateQuery.data?.anchored_candidates ?? 0}
          loading={incidentQuery.isLoading}
          candidateLoading={incidentCandidateQuery.isLoading}
          unavailable={incidentQuery.isError}
          candidateUnavailable={incidentCandidateQuery.isError}
          onOpen={openIncident}
        />
      </div>

      <div className={`world-stage ${hasFocus ? 'has-focus' : ''} ${focusedSource ? 'focus-source' : ''} ${focusedHotKey ? 'focus-hot' : ''} ${focusedLane ? 'focus-lane' : ''}`}>
        {snapshot && !snapshotFresh && (
          <div className="world-freeze-state">
            <span />
            <div><small>{text('冻结快照', 'FROZEN SNAPSHOT')}</small><strong>{text('运行快照已陈旧；交互保留，活动动画停止。', 'Operational snapshot is stale; inspection remains available while activity motion is frozen.')}</strong></div>
            <em>{snapshotAge(snapshot.generated_at)} · {new Date(snapshot.generated_at).toLocaleString()}</em>
          </div>
        )}
        <div className="world-overview-grid">
          <section className="world-source-panel">
            <div className="world-panel-head"><div><small>SOURCE FAMILIES</small><strong>{text('八类来源', 'EIGHT SOURCE FAMILIES')}</strong></div><span>{snapshot?.categories.length ?? 0}</span></div>
            <div className="processing-lanes" aria-label="Category route projections">
              {Object.keys(worldLanePoints).map((lane) => (
                <button type="button" key={lane} className={`${laneSlug(lane)} ${laneClass(focusedSourceMeta, focusedLane, lane)}`} onClick={() => focusLane(lane)}>
                  {lane === 'ASSET OBSERVATION' ? 'ASSET / ON-DEMAND' : lane}
                </button>
              ))}
            </div>
            <div className="world-source-list">
              {sources.map(({ key, label, labelZh, sub, icon: Icon }, index) => {
                const health = categoryHealth.get(key)
                const selected = focusedSource === key
                const belongsToLane = !focusedLane || sourceNarrative[key].lane === focusedLane
                const dimmed = Boolean((focusedSource && !selected) || focusedHot || !belongsToLane)
                const state = sourceState(health)
                return (
                  <motion.button
                    key={key}
                    className={`source-beacon state-${state} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
                    onClick={() => focusSource(key)}
                    animate={{ opacity: dimmed ? .38 : 1 }}
                    transition={{ duration: .16 }}
                  >
                    <span className="source-beacon-glyph"><Icon size={16} /></span>
                    <span className="source-beacon-copy">
                      <small>{String(index + 1).padStart(2, '0')} · {state.toUpperCase()}</small>
                      <strong>{text(labelZh, label)}</strong>
                      <em>{health ? `${health.healthy} healthy · ${health.degraded} degraded · ${health.blocked} blocked` : sub}</em>
                    </span>
                  </motion.button>
                )
              })}
            </div>
          </section>

          <section className="world-core-panel">
            <div className="world-panel-head"><div><small>DURABLE INNER WORLD</small><strong>EVIDENCE CORE</strong></div><span>{latestKnowledgeChange ? `REV ${latestKnowledgeChange.revision}` : 'NO WRITE'}</span></div>
            <div className="world-core-visual">
              <WorldField2D freshChanges={oneHour?.fresh_external_changes ?? 0} backfillObservations={oneHour?.backfill_observations ?? 0} canonicalWrites={oneHour?.canonical_writes ?? 0} knowledgeChangeActive={knowledgeChangeActive} />
              <div className="world-core-summary">
                <div className="durable-core-label">
                  <small>DURABLE INNER WORLD</small>
                  <strong>EVIDENCE CORE</strong>
                  <span>Evidence · Knowledge · Incident · Insight · Experience</span>
                  {latestKnowledgeChange ? (
                    <>
                      <b className="world-change-coordinate mono">REV {latestKnowledgeChange.revision} · O{latestKnowledgeChange.object_ids.length} · C{latestKnowledgeChange.claim_ids.length} · R{latestKnowledgeChange.relation_ids.length}</b>
                      <em className="world-change-cause mono">{latestKnowledgeChange.cause_processing_run_id ? `PROC ${latestKnowledgeChange.cause_processing_run_id.slice(0, 12)}` : 'PROC —'}</em>
                    </>
                  ) : <b className="world-change-coordinate unavailable">{knowledgeChangeQuery.isError ? 'KNOWLEDGE CHANGE UNAVAILABLE' : 'NO DURABLE KNOWLEDGE CHANGE'}</b>}
                </div>
                <div className="world-core-kpis">
                  <div><small>{text('新增变化', 'FRESH CHANGES')}</small><strong>{oneHour?.fresh_external_changes ?? '—'}</strong><span>1H</span></div>
                  <div><small>{text('回填观测', 'BACKFILL')}</small><strong>{oneHour?.backfill_observations ?? '—'}</strong><span>1H</span></div>
                  <div><small>{text('规范写入', 'CANONICAL WRITES')}</small><strong>{oneHour?.canonical_writes ?? '—'}</strong><span>1H</span></div>
                </div>
              </div>
            </div>
            <div className="world-semantic-legend">
              <span><i className="fresh" />{text('1h 新增变化', '1h fresh changes')}</span>
              <span><i className="ghost" />{text('1h 回填', '1h backfill')}</span>
              <span><i className="write" />{text('1h canonical writes', '1h canonical writes')}</span>
              <span><i className="degraded" />{text('来源健康', 'source health')}</span>
            </div>
            {!hasFocus && <div className="world-focus-hint"><Crosshair size={12} /> {text('选择来源、路径或热点对象查看证据', 'SELECT A SOURCE, ROUTE, OR HOT OBJECT TO INSPECT')}</div>}
          </section>

          <aside className="world-activity-panel">
            <section className="world-hot-panel">
              <div className="world-panel-head"><div><small>HOT WORKING SET</small><strong>{text('热点对象', 'HOT OBJECTS')}</strong></div><span>{hotItems.length}</span></div>
              <div className="world-hot-list">
                {hotItems.slice(0, 5).map((item) => {
                  const identity = item.cve_id ?? item.external_object_id
                  const selected = focusedHotKey === hotIdentity(item)
                  return <button key={hotIdentity(item)} className={selected ? 'selected' : ''} onClick={() => focusHot(item)}><span><Flame size={13} /><strong>{identity}</strong></span><small>{item.changed_fields.length} changes · {item.source_id}</small></button>
                })}
                {!hotQuery.isLoading && !hotQuery.isError && hotItems.length === 0 && <p>{text('当前没有热点对象。', 'No hot objects right now.')}</p>}
              </div>
              {hotQuery.isError && <div className="world-hot-fault"><ShieldAlert size={14} /><strong>{text('Hot Layer 当前不可读', 'HOT LAYER UNAVAILABLE')}</strong><button className="recovery-action" onClick={() => void hotQuery.refetch()}>{text('重试', 'RETRY')}</button></div>}
            </section>
            <KnowledgeChangeRail changes={knowledgeChangeQuery.data?.items ?? []} loading={knowledgeChangeQuery.isLoading} unavailable={knowledgeChangeQuery.isError} onOpenObject={openKnowledgeObject} />
          </aside>
        </div>

        <AnimatePresence>
          {hasFocus && (
            <motion.aside
              className={`world-lens ${focusedHotKey ? 'lens-hot-focus' : 'lens-source-focus'}`}
              initial={{ opacity: 0, x: 48, clipPath: 'inset(0 0 0 18%)' }}
              animate={{ opacity: 1, x: 0, clipPath: 'inset(0 0 0 0%)' }}
              exit={{ opacity: 0, x: 28, clipPath: 'inset(0 0 0 12%)' }}
              transition={{ type: 'spring', stiffness: 240, damping: 27 }}
            >
              <button className="world-lens-close" onClick={clearFocus} aria-label={text('关闭聚焦镜片', 'Close focus lens')}><X size={15} /></button>
              {focusedHot ? (
                <HotLens item={focusedHot} onInspect={() => {
                  const target = focusedHot.cve_id ?? focusedHot.external_object_id
                  const query = new URLSearchParams({ cve: target, from: 'world', worldRef: `hot:${focusedHot.source_id}:${focusedHot.external_object_id}` })
                  navigate(`/intelligence?${query.toString()}`)
                }} />
              ) : focusedHotKey ? (
                <div className="lens-stack hot-detail-state">
                  <div className="lens-index">HOT WORKING SET / DIRECT READ</div>
                  <div className="lens-title"><span><Flame size={18} /></span><div><small>{text('对象坐标', 'OBJECT COORDINATE')}</small><strong>{focusedHotKey}</strong></div></div>
                  {hotDetailQuery.isLoading
                    ? <p>{text('正在从 Redis Hot Layer 恢复该对象…', 'Resolving this object directly from the Redis Hot Layer…')}</p>
                    : <p className="error-block">{text('当前 Hot Layer 中找不到该对象，或 detail read seam 不可用。', 'This object is absent from the current Hot Layer or the detail read seam is unavailable.')}</p>}
                  <button className="recovery-action" onClick={() => void hotDetailQuery.refetch()}>{text('重试 Hot detail', 'RETRY HOT DETAIL')}</button>
                </div>
              ) : focusedSourceMeta ? (
                <SourceLens
                  source={focusedSourceMeta}
                  health={categoryHealth.get(focusedSourceMeta.key)}
                  series={snapshot?.category_hourly_series?.[focusedSourceMeta.key] ?? []}
                  sourceDetails={snapshot?.sources.filter((item) => item.measurement_category === focusedSourceMeta.key) ?? []}
                />
              ) : focusedLane ? (
                <PathLens lane={focusedLane} snapshot={snapshot ?? null} />
              ) : null}
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      <WorldLiveFlow series={flowSeries.slice(-12)} requestedWindow={worldWindow} totalAvailable={snapshot?.hourly_series?.length ?? 0} />
    </section>
  )
}
