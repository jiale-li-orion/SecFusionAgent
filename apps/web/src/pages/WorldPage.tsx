import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
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
import { getHotWorld, getHotWorldItem, getWorldOverview, listIncidents, type HotBug } from '../lib/api'
import { HotCrystal, HotLens, PathLens, SourceLens, Telemetry, WorldField2D, WorldIncidentCluster, WorldIngressFlow, WorldLiveFlow } from '../components/world/WorldSurfaces'
import { hotIdentity, laneClass, laneSlug, parseHotIdentity, snapshotAge, sourceNarrative, sourceState, sources, supportsWebGL, worldLanePoints, worldWindows, type WorldWindow } from '../components/world/worldModel'
import { useI18n } from '../lib/i18n'

const WorldField3D = lazy(() => import('../components/world/WorldField3D').then((module) => ({ default: module.WorldField3D })))

export function WorldPage() {
  const { text } = useI18n()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const sourceParam = params.get('source')
  const laneParam = params.get('lane')
  const hotParam = params.get('hot')
  const reduceMotion = Boolean(useReducedMotion())
  const webglAvailable = useMemo(() => supportsWebGL(), [])
  const focusedSource = sourceParam && sources.some((source) => source.key === sourceParam) ? sourceParam : null
  const focusedLane = laneParam && Object.hasOwn(worldLanePoints, laneParam) ? laneParam : null
  const focusedHotKey = hotParam
  const focusedHotCoordinate = useMemo(() => parseHotIdentity(focusedHotKey), [focusedHotKey])
  const [locator, setLocator] = useState('')
  const [locatorError, setLocatorError] = useState('')
  const [worldWindow, setWorldWindow] = useState<WorldWindow>('1h')
  const [clockNow, setClockNow] = useState(() => Date.now())
  const [compactViewport, setCompactViewport] = useState(() => typeof window !== 'undefined' && window.matchMedia('(max-width: 860px), (max-height: 680px)').matches)
  const [world3DReady, setWorld3DReady] = useState(false)
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const hotQuery = useQuery({ queryKey: ['world-hot'], queryFn: () => getHotWorld(6), refetchInterval: 20_000 })
  const incidentQuery = useQuery({ queryKey: ['world-incidents'], queryFn: () => listIncidents(6), refetchInterval: 30_000 })
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
  const categoryActivityMap = useMemo(() => Object.fromEntries(sources.map((source) => {
    const latest = snapshot?.category_hourly_series?.[source.key]?.at(-1)
    return [source.key, {
      fresh: Number(latest?.fresh_external_changes ?? 0),
      backfill: Number(latest?.backfill_observations ?? 0),
      runs: Number(latest?.scheduled_runs ?? 0),
      observations: Number(latest?.observations ?? 0),
      successRate: typeof latest?.scheduled_run_success_rate === 'number' ? latest.scheduled_run_success_rate : null,
      providerFailure: typeof latest?.provider_boundary_failure_rate === 'number' ? latest.provider_boundary_failure_rate : null,
      runtimeFailure: typeof latest?.runtime_owned_failure_rate === 'number' ? latest.runtime_owned_failure_rate : null,
    }]
  })), [snapshot?.category_hourly_series])
  const hotItems = useMemo(() => hotQuery.data?.items ?? [], [hotQuery.data?.items])
  const focusedHot = hotDetailQuery.data
    ?? hotItems.find((item) => hotIdentity(item) === focusedHotKey)
    ?? null
  const focusedSourceMeta = sources.find((source) => source.key === focusedSource) ?? null
  const hasFocus = Boolean(focusedSourceMeta || focusedHotKey || focusedLane)
  const snapshotFresh = snapshot ? clockNow - new Date(snapshot.generated_at).getTime() <= 120_000 : false

  useEffect(() => {
    const timer = window.setInterval(() => setClockNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (reduceMotion || !webglAvailable || compactViewport) return
    const timer = window.setTimeout(() => setWorld3DReady(true), 650)
    return () => window.clearTimeout(timer)
  }, [compactViewport, reduceMotion, webglAvailable])

  useEffect(() => {
    const query = window.matchMedia('(max-width: 860px), (max-height: 680px)')
    const onChange = () => setCompactViewport(query.matches)
    onChange()
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

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

        <WorldIncidentCluster
          incidents={incidentQuery.data?.items ?? []}
          loading={incidentQuery.isLoading}
          unavailable={incidentQuery.isError}
          onOpen={openIncident}
        />
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

      <div className={`world-stage ${hasFocus ? 'has-focus' : ''} ${focusedSource ? 'focus-source' : ''} ${focusedHotKey ? 'focus-hot' : ''} ${focusedLane ? 'focus-lane' : ''}`}>
        {snapshot && !snapshotFresh && (
          <div className="world-freeze-state">
            <span />
            <div><small>{text('冻结快照', 'FROZEN SNAPSHOT')}</small><strong>{text('运行快照已陈旧；交互保留，活动动画停止。', 'Operational snapshot is stale; inspection remains available while activity motion is frozen.')}</strong></div>
            <em>{snapshotAge(snapshot.generated_at)} · {new Date(snapshot.generated_at).toLocaleString()}</em>
          </div>
        )}
        {!reduceMotion && webglAvailable && !compactViewport && world3DReady ? (
          <Suspense fallback={<WorldField2D freshChanges={oneHour?.fresh_external_changes ?? 0} backfillObservations={oneHour?.backfill_observations ?? 0} canonicalWrites={oneHour?.canonical_writes ?? 0} />}>
            <WorldField3D
              categories={snapshot?.categories ?? []}
              categoryActivity={categoryActivityMap}
              freshChanges={oneHour?.fresh_external_changes ?? 0}
              backfillObservations={oneHour?.backfill_observations ?? 0}
              canonicalWrites={oneHour?.canonical_writes ?? 0}
              incidents={incidentQuery.data?.items ?? []}
              focusedSource={focusedSource}
              focusedLane={focusedLane}
              focusedHot={Boolean(focusedHot)}
              reduceMotion={!snapshotFresh}
              onSourceFocus={focusSource}
              onIncidentOpen={openIncident}
            />
          </Suspense>
        ) : (
          <WorldField2D
            freshChanges={oneHour?.fresh_external_changes ?? 0}
            backfillObservations={oneHour?.backfill_observations ?? 0}
            canonicalWrites={oneHour?.canonical_writes ?? 0}
          />
        )}

        <div className="world-depth-mask" />
        <div className="world-coordinate north">N / SOURCE TAXONOMY</div>
        <div className="world-coordinate west">M1 · MONITORING</div>
        <div className="world-coordinate east">M2 · EVIDENCE</div>

        <div className="durable-core-label">
          <small>DURABLE INNER WORLD</small>
          <strong>EVIDENCE CORE</strong>
          <span>Evidence · Knowledge · Incident · Insight · Experience</span>
          <i className={oneHour?.canonical_writes ? 'active' : ''} />
        </div>

        <div className="processing-lanes" aria-label="Category route projections">
          {Object.keys(worldLanePoints).map((lane) => (
            <button
              type="button"
              key={lane}
              className={`${laneSlug(lane)} ${laneClass(focusedSourceMeta, focusedLane, lane)}`}
              onClick={() => focusLane(lane)}
            >
              {lane === 'ASSET OBSERVATION' ? 'ASSET OBSERVATION / ON-DEMAND' : lane}
            </button>
          ))}
        </div>

        <WorldIngressFlow snapshot={snapshot} focusedSource={focusedSource} focusedLane={focusedLane} focusedHot={Boolean(focusedHot)} reduceMotion={reduceMotion} />

        {sources.map(({ key, label, labelZh, sub, icon: Icon, x, y }, index) => {
          const health = categoryHealth.get(key)
          const selected = focusedSource === key
          const belongsToLane = !focusedLane || sourceNarrative[key].lane === focusedLane
          const dimmed = Boolean((focusedSource && !selected) || focusedHot || !belongsToLane)
          const state = sourceState(health)
          return (
            <motion.button
              key={key}
              className={`source-beacon state-${state} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
              style={{ left: `${x}%`, top: `${y}%` }}
              onClick={() => focusSource(key)}
              initial={{ opacity: 0, scale: .88 }}
              animate={{ opacity: dimmed ? .22 : 1, scale: selected ? 1.08 : 1 }}
              transition={{ delay: reduceMotion ? 0 : index * .035, duration: .2 }}
            >
              <span className="source-beacon-glyph"><Icon size={15} /></span>
              <span className="source-beacon-copy">
                <small>{String(index + 1).padStart(2, '0')} / {state.toUpperCase()}</small>
                <strong>{text(labelZh, label)}</strong>
                <em>{health ? `${health.healthy}H · ${health.degraded}D · ${health.blocked}B` : sub}</em>
              </span>
              <i />
            </motion.button>
          )
        })}

        <div className="hot-field" aria-label="Hot Bug working set">
          <div className="hot-field-label">
            <Flame size={12} />
            <span>{text('热点工作集', 'HOT WORKING SET')}</span>
            <small>{hotQuery.isLoading ? text('连接中', 'CONNECTING') : hotQuery.isError ? text('不可用', 'UNAVAILABLE') : text(`${hotItems.length} 个对象`, `${hotItems.length} OBJECTS`)}</small>
          </div>
          {hotItems.slice(0, 5).map((item, index) => (
            <HotCrystal
              key={hotIdentity(item)}
              item={item}
              index={index}
              selected={focusedHotKey === hotIdentity(item)}
              dimmed={Boolean(focusedSource || (focusedHotKey && focusedHotKey !== hotIdentity(item)))}
              reduceMotion={reduceMotion}
              onOpen={() => focusHot(item)}
            />
          ))}
          {hotQuery.isError && (
            <div className="world-hot-fault">
              <ShieldAlert size={14} />
              <div><small>{text('HOT 读取降级', 'HOT READ SEAM DEGRADED')}</small><strong>{text('Redis Hot Layer 当前不可读；Evidence Core 与 source monitoring 继续可用。', 'Redis Hot Layer is unreadable; Evidence Core and source monitoring remain available.')}</strong></div>
              <button className="recovery-action" onClick={() => void hotQuery.refetch()}>{text('重试 Hot read', 'RETRY HOT READ')}</button>
            </div>
          )}
        </div>

        <AnimatePresence>
          {focusedHot && (
            <motion.div
              className="world-hot-corridor"
              initial={{ opacity: 0, scaleX: .72 }}
              animate={{ opacity: 1, scaleX: 1 }}
              exit={{ opacity: 0, scaleX: .8 }}
              transition={{ duration: .28, ease: [0.22, 1, 0.36, 1] }}
              aria-hidden="true"
            >
              <svg viewBox="0 0 100 40" preserveAspectRatio="none">
                <path d="M 2 22 C 28 20, 44 18, 61 12 C 72 8, 82 9, 98 15" />
                <path className="echo" d="M 3 25 C 30 23, 49 21, 64 16 C 78 12, 87 13, 98 18" />
              </svg>
              <span>CORE → HOT WORKING OBJECT</span>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="world-semantic-legend">
          <span><i className="fresh" />{text('粒子密度 = 1h fresh changes', 'particle density = 1h fresh changes')}</span>
          <span><i className="ghost" />{text('幽灵轨迹 = 1h backfill', 'ghost transit = 1h backfill')}</span>
          <span><i className="write" />{text('核心波纹 = 1h canonical writes', 'core ripple = 1h canonical writes')}</span>
          <span><i className="degraded" />{text('节点健康色 = source health 聚合', 'node health color = source health aggregate')}</span>
          <span><i className="provider-failure" />{text('琥珀 halo = provider-boundary failure rate', 'amber halo = provider-boundary failure rate')}</span>
          <span><i className="runtime-failure" />{text('珊瑚 halo = runtime-owned failure rate', 'coral halo = runtime-owned failure rate')}</span>
        </div>

        {!hasFocus && <div className="world-focus-hint"><Crosshair size={12} /> {text('聚焦来源 / Hot Object', 'FOCUS SOURCE / HOT OBJECT')}</div>}

        {!hasFocus && (
          <motion.button
            className="world-start-portal"
            onClick={() => navigate('/start')}
            whileHover={reduceMotion ? undefined : { scale: 1.045 }}
            whileTap={reduceMotion ? undefined : { scale: .98 }}
          >
            <span className="world-start-ring"><Sparkles size={17} /></span>
            <div><small>{text('任务入口', 'MISSION ENTRY')}</small><strong>START</strong><em>{text('选择 ExecutionProfile', 'CHOOSE EXECUTION PROFILE')}</em></div>
          </motion.button>
        )}

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

      <div className="world-telemetry">
        <div className="world-time-lens">
          {worldWindows.map((window) => <button key={window} className={worldWindow === window ? 'active' : ''} onClick={() => setWorldWindow(window)}>{window === '168h' ? '7d' : window}</button>)}
        </div>
        <Telemetry label="SOURCE HEALTH" value={snapshot ? `${snapshot.source_health.healthy}/${snapshot.source_health.healthy + snapshot.source_health.degraded + snapshot.source_health.blocked}` : '—'} detail={snapshot ? text(`${(snapshot.healthy_rate * 100).toFixed(1)}% 健康`, `${(snapshot.healthy_rate * 100).toFixed(1)}% healthy`) : worldQuery.isError ? text('不可用', 'unavailable') : text('解析中', 'resolving')} tone="lime" />
        <Telemetry label={`FRESH CHANGES · ${worldWindow === '168h' ? '7D' : worldWindow.toUpperCase()}`} value={activeWindow ? String(activeWindow.fresh_external_changes) : '—'} detail={activeWindow ? text(`${activeWindow.observations} 条 observations`, `${activeWindow.observations} observations`) : text('运行快照', 'operational snapshot')} tone="cyan" />
        <Telemetry label={`CANONICAL WRITES · ${worldWindow === '168h' ? '7D' : worldWindow.toUpperCase()}`} value={activeWindow ? String(activeWindow.canonical_writes) : '—'} detail={activeWindow ? `${activeWindow.backfill_observations} backfill` : text('运行快照', 'operational snapshot')} tone="violet" />
        <Telemetry label="QUEUE / EXEC P95" value={activeWindow?.queue_delay_p95_seconds != null && activeWindow?.execution_p95_seconds != null ? `${activeWindow.queue_delay_p95_seconds.toFixed(1)} / ${activeWindow.execution_p95_seconds.toFixed(1)}s` : '—'} detail={activeWindow?.scheduled_run_success_rate != null ? text(`${(activeWindow.scheduled_run_success_rate * 100).toFixed(1)}% 调度成功`, `${(activeWindow.scheduled_run_success_rate * 100).toFixed(1)}% scheduled success`) : text('不可评估', 'not evaluable')} tone="amber" />
        <Telemetry label="SNAPSHOT AGE" value={snapshot ? snapshotAge(snapshot.generated_at) : '—'} detail={snapshot ? new Date(snapshot.generated_at).toLocaleString() : text('等待 truth source', 'loading truth source')} tone="blue" />
      </div>
      <WorldLiveFlow series={flowSeries.slice(-12)} requestedWindow={worldWindow} totalAvailable={snapshot?.hourly_series?.length ?? 0} />
    </section>
  )
}
