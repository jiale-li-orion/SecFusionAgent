import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import {
  ArrowUpRight,
  Boxes,
  Bug,
  Building2,
  Code2,
  Crosshair,
  FileBadge,
  Flame,
  GraduationCap,
  RadioTower,
  ShieldAlert,
  Sparkles,
  Search,
  X,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { getHotWorld, getHotWorldItem, getWorldOverview, type HotBug, type WorldOverview } from '../lib/api'
import { useI18n } from '../lib/i18n'

const WorldField3D = lazy(() => import('../components/world/WorldField3D').then((module) => ({ default: module.WorldField3D })))

const sources = [
  { key: 'vulnerability', label: 'VULNERABILITY', labelZh: '漏洞', sub: 'CVE · NVD · KEV', icon: Bug, x: 4.5, y: 20 },
  { key: 'development', label: 'DEVELOPMENT', labelZh: '开发', sub: 'Git · Package · Release', icon: Code2, x: 4.5, y: 30 },
  { key: 'academic', label: 'ACADEMIC', labelZh: '学术', sub: 'Paper · Preprint', icon: GraduationCap, x: 4.5, y: 40 },
  { key: 'vendor', label: 'VENDOR', labelZh: '厂商', sub: 'Advisory · PSIRT', icon: Building2, x: 4.5, y: 50 },
  { key: 'independent', label: 'INDEPENDENT', labelZh: '独立情报', sub: 'OSINT · Analysis', icon: RadioTower, x: 4.5, y: 60 },
  { key: 'normative', label: 'NORMATIVE', labelZh: '规范', sub: 'Standard · Regulation', icon: FileBadge, x: 4.5, y: 70 },
  { key: 'assets', label: 'ASSETS', labelZh: '资产', sub: 'Exposure · Inventory', icon: Boxes, x: 4.5, y: 80 },
  { key: 'incidents', label: 'INCIDENTS', labelZh: '事件', sub: 'Report · Signal', icon: ShieldAlert, x: 4.5, y: 90 },
]

const worldWindows = ['1h', '6h', '24h', '168h'] as const
type WorldWindow = (typeof worldWindows)[number]

const worldLanePoints: Record<string, { x: number; y: number }> = {
  'BUG STREAM': { x: 34, y: 34 },
  'DEVELOPMENT INDEX': { x: 37, y: 43 },
  'INSIGHT CORPUS': { x: 38, y: 53 },
  'INCIDENT WATCH': { x: 36, y: 64 },
  'ASSET OBSERVATION': { x: 40, y: 73 },
}

const sourceNarrative: Record<string, { lane: string; role: string; roleZh: string; summary: string; summaryZh: string }> = {
  vulnerability: { lane: 'BUG STREAM', role: 'deterministic + canonical identity', roleZh: '确定性抽取 + 规范身份', summary: 'CVE / NVD / KEV form the vulnerability spine and feed normalized security facts into the durable world.', summaryZh: 'CVE / NVD / KEV 构成漏洞主干，规范化安全事实持续进入 durable world。' },
  development: { lane: 'DEVELOPMENT INDEX', role: 'graph + fix intelligence', roleZh: '关系图谱 + 修复情报', summary: 'Repository, release and package evidence expands fix, version and development relationships.', summaryZh: '仓库、Release 与 Package 证据扩展修复、版本和开发关系。' },
  academic: { lane: 'INSIGHT CORPUS', role: 'semantic enrichment', roleZh: '语义增强', summary: 'Papers and research signals add analytical context without overriding authoritative source facts.', summaryZh: '论文与研究信号补充分析上下文，同时保留权威来源的事实边界。' },
  vendor: { lane: 'BUG STREAM', role: 'primary advisory authority', roleZh: '一手厂商权威', summary: 'Vendor advisories provide product, remediation and fix-boundary evidence with source authority kept visible.', summaryZh: '厂商通告提供产品、修复与 fix boundary 证据，并保留来源权威性。' },
  independent: { lane: 'INSIGHT CORPUS', role: 'secondary analysis', roleZh: '独立二手分析', summary: 'Independent analysis contributes supporting observations and cross-source context.', summaryZh: '独立分析提供辅助观察与跨来源上下文。' },
  normative: { lane: 'INSIGHT CORPUS', role: 'standards / normative context', roleZh: '标准 / 规范上下文', summary: 'Standards and normative documents contribute constrained policy and technical context.', summaryZh: '标准与规范文档补充受约束的政策和技术上下文。' },
  assets: { lane: 'ASSET OBSERVATION', role: 'applicability / exposure', roleZh: '适用性 / 暴露面', summary: 'Observed assets bind canonical product/version facts to deployment applicability through an on-demand side path.', summaryZh: '资产观测把规范化产品/版本事实绑定到真实部署适用性与暴露面。' },
  incidents: { lane: 'INCIDENT WATCH', role: 'signal → candidate → durable incident', roleZh: '信号 → 候选 → 持久事件', summary: 'Incident signals remain provisional until evidence is strong enough to enter the durable Incident world.', summaryZh: '事件信号先保持候选态，证据满足强锚点条件后进入 durable Incident。' },
}

function shortDateTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString([], { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function SourceMiniTrend({ series }: { series: Array<Record<string, number | string | null>> }) {
  const { text } = useI18n()
  const values = series.map((item) => Number(item.fresh_external_changes ?? 0))
  const max = Math.max(...values, 1)
  const points = values.map((value, index) => {
    const x = values.length <= 1 ? 0 : index / (values.length - 1) * 100
    const y = 36 - Math.min(value / max, 1) * 30
    return `${x},${y}`
  }).join(' ')
  return (
    <div className="source-mini-trend">
      <div><small>{text('新增贡献', 'FRESH CONTRIBUTION')}</small><span>{series.length ? text(`${series.length} 个小时样本`, `${series.length} hourly samples`) : text('当前类别没有样本', 'no category samples')}</span></div>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" x2="100" y1="36" y2="36" />
        {series.length > 0 && <polyline points={points} />}
      </svg>
    </div>
  )
}

function categorySeriesSummary(series: Array<Record<string, number | string | null>>) {
  const fresh = series.reduce((sum, item) => sum + Number(item.fresh_external_changes ?? 0), 0)
  const runs = series.reduce((sum, item) => sum + Number(item.scheduled_runs ?? 0), 0)
  const average = (key: string) => {
    const values = series.map((item) => item[key]).filter((value): value is number => typeof value === 'number')
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  }
  return {
    fresh,
    runs,
    success: average('scheduled_run_success_rate'),
    providerFailure: average('provider_boundary_failure_rate'),
    runtimeFailure: average('runtime_owned_failure_rate'),
  }
}

const hotSlots = [
  { left: '78%', top: '27%' },
  { left: '78%', top: '39%' },
  { left: '78%', top: '51%' },
  { left: '78%', top: '63%' },
  { left: '78%', top: '75%' },
]

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
              focusedSource={focusedSource}
              focusedLane={focusedLane}
              focusedHot={Boolean(focusedHot)}
              reduceMotion={!snapshotFresh}
              onSourceFocus={focusSource}
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

function WorldIngressFlow({ snapshot, focusedSource, focusedLane, focusedHot, reduceMotion }: { snapshot: WorldOverview | null | undefined; focusedSource: string | null; focusedLane: string | null; focusedHot: boolean; reduceMotion: boolean }) {
  const categoryHealth = new Map((snapshot?.categories ?? []).map((item) => [item.category, item]))
  const laneNames = Object.keys(worldLanePoints)
  return (
    <svg className={`world-ingress-flow ${focusedHot ? 'dimmed' : ''}`} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <g className="world-lane-trunks">
        {laneNames.map((lane) => {
          const point = worldLanePoints[lane]
          const laneActive = sources.some((source) => sourceNarrative[source.key].lane === lane && categoryActivity(snapshot?.category_hourly_series?.[source.key] ?? []).active)
          const selected = focusedLane === lane
          const dimmed = Boolean(focusedLane && !selected)
          return <motion.path key={lane} className={`${laneActive ? 'active' : ''} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`} d={`M ${point.x} ${point.y} C ${point.x + 6} ${point.y}, 45 50, 50 50`} animate={reduceMotion || !laneActive ? undefined : { strokeDashoffset: [0, -18] }} transition={{ duration: 1.8, repeat: Infinity, ease: 'linear' }} />
        })}
      </g>
      <g className="world-source-ingress">
        {sources.map((source) => {
          const lane = sourceNarrative[source.key].lane
          const point = worldLanePoints[lane]
          const health = categoryHealth.get(source.key)
          const state = sourceState(health ? { healthy: health.healthy, degraded: health.degraded, blocked: health.blocked } : undefined)
          const activity = categoryActivity(snapshot?.category_hourly_series?.[source.key] ?? [])
          const selected = focusedSource === source.key
          const laneSelected = focusedLane === lane
          const dimmed = Boolean((focusedSource && !selected) || (focusedLane && !laneSelected))
          return (
            <g key={source.key} className={`state-${state} ${activity.active ? 'active' : ''} ${selected || laneSelected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}>
              <motion.path d={`M 20 ${source.y} C 26 ${source.y}, 29 ${point.y}, ${point.x} ${point.y}`} animate={reduceMotion || !activity.active ? undefined : { strokeDashoffset: [0, -14] }} transition={{ duration: activity.fresh > 0 ? 1.15 : 2.1, repeat: Infinity, ease: 'linear' }} />
              <circle cx={point.x} cy={point.y} r={selected || laneSelected ? 1.1 : .65} />
            </g>
          )
        })}
      </g>
    </svg>
  )
}

function categoryActivity(series: Array<Record<string, number | string | null>>) {
  const latest = series.at(-1)
  const fresh = Number(latest?.fresh_external_changes ?? 0)
  const runs = Number(latest?.scheduled_runs ?? 0)
  const observations = Number(latest?.observations ?? 0)
  return { fresh, runs, observations, active: fresh > 0 || runs > 0 || observations > 0 }
}

function supportsWebGL() {
  if (typeof document === 'undefined') return false
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'))
  } catch {
    return false
  }
}

function WorldField2D({ freshChanges, backfillObservations, canonicalWrites }: { freshChanges: number; backfillObservations: number; canonicalWrites: number }) {
  const freshRadius = Math.min(31, 20 + Math.log10(freshChanges + 1) * 3.2)
  const backfillRadius = Math.min(38, 27 + Math.log10(backfillObservations + 1) * 2.8)
  const writeEnergy = Math.min(1, Math.log10(canonicalWrites + 1) / 2.5)
  return (
    <div className="world-2d-fallback" aria-hidden="true">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none">
        <ellipse className="grid-ring outer" cx="50" cy="50" rx="35" ry="31" />
        <ellipse className="grid-ring middle" cx="50" cy="50" rx="27" ry="24" />
        <ellipse className="grid-ring inner" cx="50" cy="50" rx="18" ry="16" />
        <circle className="backfill-ring" cx="50" cy="50" r={backfillRadius / 2} />
        <circle className="fresh-ring" cx="50" cy="50" r={freshRadius / 2} />
        <polygon className="core-plane outer" points="50,39 58,44 60,53 54,61 45,60 40,53 42,44" />
        <polygon className="core-plane inner" points="50,43 55,46 56,52 52,57 46,56 44,52 45,46" style={{ opacity: .36 + writeEnergy * .44 }} />
        {canonicalWrites > 0 && <circle className="write-ring" cx="50" cy="50" r="13" />}
      </svg>
      <div className="world-2d-readout"><span>{freshChanges} fresh</span><span>{backfillObservations} backfill</span><span>{canonicalWrites} writes</span></div>
    </div>
  )
}

function WorldLiveFlow({ series, requestedWindow, totalAvailable }: { series: Array<Record<string, number | string | null>>; requestedWindow: '1h' | '6h' | '24h' | '168h'; totalAvailable: number }) {
  const { text } = useI18n()
  return (
    <section className="world-live-flow">
      <div className="world-live-flow-head">
        <div><small>LIVE EVIDENCE FLOW</small><strong>{text('近期运行样本', 'RECENT OPERATIONAL SAMPLES')}</strong></div>
        <span>{text(`${series.length} 个可见样本 · 共 ${totalAvailable} 个 · ${requestedWindow === '168h' ? '7d' : requestedWindow}`, `${series.length} visible · ${totalAvailable} available · ${requestedWindow === '168h' ? '7d' : requestedWindow}`)}</span>
      </div>
      <div className="world-live-flow-track">
        {series.map((item, index) => {
          const fresh = Number(item.fresh_external_changes ?? 0)
          const writes = Number(item.canonical_writes ?? 0)
          const observations = Number(item.observations ?? 0)
          const stamp = String(item.hour ?? item.timestamp ?? item.generated_at ?? '')
          return (
            <div key={stamp + '-' + index} className="world-flow-sample">
              <i style={{ height: Math.max(12, Math.min(58, Math.log10(fresh + 1) * 18)) + 'px' }} />
              <div><small>{stamp ? new Date(stamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'T-' + (series.length - index)}</small><strong>{text(`${fresh} 条新增`, `${fresh} fresh`)}</strong><span>{text(`${writes} 次写入 · ${observations} 条观测`, `${writes} writes · ${observations} obs`)}</span></div>
            </div>
          )
        })}
        {series.length === 0 && <div className="world-flow-empty">{text('等待运行样本', 'AWAITING OPERATIONAL SAMPLES')}</div>}
      </div>
    </section>
  )
}

function HotCrystal({
  item,
  index,
  selected,
  dimmed,
  reduceMotion,
  onOpen,
}: {
  item: HotBug
  index: number
  selected: boolean
  dimmed: boolean
  reduceMotion: boolean
  onOpen: () => void
}) {
  const { text } = useI18n()
  const slot = hotSlots[index % hotSlots.length]
  const identity = item.cve_id ?? item.external_object_id
  const critical = item.priority_signals.includes('critical_severity')
  const primarySignal = critical ? text('严重等级', 'CRITICAL SEVERITY') : item.priority_signals[0]?.replaceAll('_', ' ').toUpperCase() ?? text('热点', 'HOT')
  const changeBand = item.changed_fields.length >= 8 ? 'major' : item.changed_fields.length >= 3 ? 'material' : item.changed_fields.length > 0 ? 'minor' : 'stable'
  const signalClasses = item.priority_signals.map((value) => `signal-${hotSignalSlug(value)}`).join(' ')

  return (
    <motion.button
      className={`hot-crystal change-${changeBand} ${signalClasses} ${critical ? 'priority-critical' : ''} ${item.active ? 'is-active' : ''} ${item.pinned ? 'is-pinned' : ''} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
      style={slot}
      onClick={onOpen}
      animate={{
        opacity: dimmed ? .18 : 1,
        scale: selected ? 1.11 : dimmed ? .94 : 1,
        y: 0,
      }}
      transition={{ opacity: { duration: .2 }, scale: { duration: .2 }, y: { duration: reduceMotion ? 0 : .2 } }}
    >
      <span className="hot-crystal-cut" />
      <small>{primarySignal}</small>
      <strong>{identity}</strong>
      <em>{item.cvss_score != null ? `CVSS ${item.cvss_score.toFixed(1)} · ${item.cvss_severity ?? ''}` : item.source_id}</em>
      {item.changed_fields.length > 0 && <span className="hot-change-count">Δ {item.changed_fields.length}</span>}
      {item.access_count > 0 && <span className="hot-access-count">{text('读取', 'READ')} {formatHotCount(item.access_count)}</span>}
      {item.pinned && <span className="hot-pin-state">{text('已固定', 'PINNED')}</span>}
      {(item.active || item.pinned) && <span className="hot-orbit" />}
    </motion.button>
  )
}

function hotSignalSlug(value: string) { return value.toLowerCase().replace(/[^a-z0-9]+/g, '-') }
function formatHotCount(value: number) { return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k` : String(Math.round(value)) }

function SourceLens({
  source,
  health,
  series,
  sourceDetails,
}: {
  source: (typeof sources)[number]
  health: { healthy: number; degraded: number; blocked: number } | undefined
  series: Array<Record<string, number | string | null>>
  sourceDetails: WorldOverview['sources']
}) {
  const { text } = useI18n()
  const [focusedProviderId, setFocusedProviderId] = useState<string | null>(null)
  const narrative = sourceNarrative[source.key]
  const total = health ? health.healthy + health.degraded + health.blocked : 0
  const Icon = source.icon
  const summary = categorySeriesSummary(series.slice(-6))
  const focusedProvider = sourceDetails.find((item) => item.source_id === focusedProviderId) ?? null

  return (
    <div className="lens-stack">
      <div className="lens-index">{text('来源星图', 'SOURCE CONSTELLATION')} / {source.key.toUpperCase()}</div>
      <div className="lens-title"><span><Icon size={18} /></span><div><small>{source.sub}</small><strong>{text(source.labelZh, source.label)}</strong></div></div>
      <p>{text(narrative.summaryZh, narrative.summary)}</p>
      <div className="lens-facts">
        <LensFact label={text('类别路径', 'CATEGORY ROUTE')} value={narrative.lane} />
        <LensFact label={text('世界角色', 'WORLD ROLE')} value={text(narrative.roleZh, narrative.role)} />
        <LensFact label={text('健康度', 'HEALTH')} value={health ? text(`${health.healthy}/${total} 健康`, `${health.healthy}/${total} healthy`) : text('快照不可用', 'snapshot unavailable')} />
        <LensFact label={text('新增 · 6H', 'FRESH · 6H')} value={String(summary.fresh)} />
        <LensFact label={text('运行 · 6H', 'RUNS · 6H')} value={String(summary.runs)} />
        <LensFact label={text('运行成功率', 'RUN SUCCESS')} value={summary.success == null ? '—' : `${(summary.success * 100).toFixed(1)}%`} />
      </div>
      <SourceMiniTrend series={series.slice(-12)} />
      <div className="lens-failure-balance">
        <div><small>{text('Provider 失败', 'PROVIDER FAIL')}</small><strong>{summary.providerFailure == null ? '—' : `${(summary.providerFailure * 100).toFixed(1)}%`}</strong></div>
        <div><small>{text('Runtime 失败', 'RUNTIME FAIL')}</small><strong>{summary.runtimeFailure == null ? '—' : `${(summary.runtimeFailure * 100).toFixed(1)}%`}</strong></div>
      </div>
      <div className="source-provider-list">
        <div className="source-provider-head"><small>{text('PROVIDER / 调度状态', 'PROVIDERS / SCHEDULE STATE')}</small><span>{sourceDetails.length}</span></div>
        {sourceDetails.slice(0, 8).map((item) => (
          <button
            type="button"
            key={item.source_id}
            className={`source-provider-row state-${item.health} ${focusedProviderId === item.source_id ? 'selected' : ''}`}
            onClick={() => setFocusedProviderId((current) => current === item.source_id ? null : item.source_id)}
          >
            <i />
            <div>
              <strong>{item.source_id}</strong>
              <small>{item.latest_scheduled_status ?? text('无调度状态', 'no scheduled status')}</small>
            </div>
            <div className="source-provider-time">
              <span>{item.last_success_at ? text(`最近 ${shortDateTime(item.last_success_at)}`, `last ${shortDateTime(item.last_success_at)}`) : text('暂无成功记录', 'no success recorded')}</span>
              <em>{item.next_due_at ? text(`下次 ${shortDateTime(item.next_due_at)}`, `due ${shortDateTime(item.next_due_at)}`) : text('无下次调度时间', 'no due time')}</em>
            </div>
            {(item.consecutive_failures > 0 || item.latest_error_code || item.overdue || item.backfill_pending) && (
              <div className="source-provider-alert">
                {item.consecutive_failures > 0 && <span>{text(`${item.consecutive_failures} 次失败`, `${item.consecutive_failures} failures`)}</span>}
                {item.latest_error_code && <span>{item.latest_error_code}</span>}
                {item.overdue && <span>{text('已逾期', 'OVERDUE')}</span>}
                {item.backfill_pending && <span>{text('待回填', 'BACKFILL')}</span>}
              </div>
            )}
          </button>
        ))}
        {sourceDetails.length === 0 && <div className="source-provider-empty">{text('当前快照没有 source-level 调度记录。', 'No source-level schedule rows in current snapshot.')}</div>}
      </div>
      <AnimatePresence mode="wait">
        {focusedProvider && (
          <motion.section
            key={focusedProvider.source_id}
            className={`source-provider-focus state-${focusedProvider.health}`}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
          >
            <div className="source-provider-focus-head">
              <div><small>{text('运行来源', 'RUNTIME SOURCE')}</small><strong>{focusedProvider.source_id}</strong></div>
              <span>{focusedProvider.health}</span>
            </div>
            <div className="source-provider-focus-grid">
              <LensFact label={text('最近成功', 'LAST SUCCESS')} value={focusedProvider.last_success_at ? shortDateTime(focusedProvider.last_success_at) : '—'} />
              <LensFact label={text('下次调度', 'NEXT DUE')} value={focusedProvider.next_due_at ? shortDateTime(focusedProvider.next_due_at) : '—'} />
              <LensFact label={text('调度状态', 'SCHEDULE')} value={focusedProvider.latest_scheduled_status ?? text('未解析', 'unresolved')} />
              <LensFact label={text('连续失败', 'FAILURES')} value={String(focusedProvider.consecutive_failures)} />
              <LensFact label={text('退避至', 'BACKOFF')} value={focusedProvider.backoff_until ? shortDateTime(focusedProvider.backoff_until) : '—'} />
              <LensFact label={text('错误码', 'ERROR')} value={focusedProvider.latest_error_code ?? text('无', 'none')} />
            </div>
            <div className="source-provider-flags">
              {focusedProvider.overdue && <span>{text('已逾期', 'OVERDUE')}</span>}
              {focusedProvider.backfill_pending && <span>{text('待回填', 'BACKFILL PENDING')}</span>}
              {!focusedProvider.overdue && !focusedProvider.backfill_pending && <span>{text('无活动调度告警', 'NO ACTIVE SCHEDULER FLAG')}</span>}
            </div>
          </motion.section>
        )}
      </AnimatePresence>
      {health && total > 0 && (
        <div className="lens-health">
          <span className="healthy" style={{ width: `${health.healthy / total * 100}%` }} />
          <span className="degraded" style={{ width: `${health.degraded / total * 100}%` }} />
          <span className="blocked" style={{ width: `${health.blocked / total * 100}%` }} />
        </div>
      )}
      <div className="lens-coordinate mono">{source.key} / operational category</div>
    </div>
  )
}

function PathLens({ lane, snapshot }: { lane: string; snapshot: WorldOverview | null }) {
  const { text } = useI18n()
  const categories = sources.filter((source) => sourceNarrative[source.key].lane === lane)
  const categoryKeys = new Set(categories.map((source) => source.key))
  const providers = (snapshot?.sources ?? []).filter((source) => categoryKeys.has(source.measurement_category))
  const health = providers.reduce((acc, source) => {
    if (source.health === 'healthy') acc.healthy += 1
    else if (source.health === 'degraded') acc.degraded += 1
    else if (source.health === 'blocked') acc.blocked += 1
    return acc
  }, { healthy: 0, degraded: 0, blocked: 0 })
  const summaries = categories.map((source) => categorySeriesSummary((snapshot?.category_hourly_series?.[source.key] ?? []).slice(-6)))
  const fresh = summaries.reduce((sum, item) => sum + item.fresh, 0)
  const runs = summaries.reduce((sum, item) => sum + item.runs, 0)
  const failures = providers.filter((provider) => provider.health !== 'healthy')

  return (
    <div className="lens-stack path-lens">
      <div className="lens-index">{text('类别路径 / 运行叠加', 'CATEGORY ROUTE / RUNTIME OVERLAY')}</div>
      <div className="path-lens-title">
        <div><small>{text('类别路径', 'CATEGORY ROUTE')}</small><strong>{lane}</strong></div>
        <span>{text(`${categories.length} 类来源 · ${providers.length} 个 provider`, `${categories.length} categories · ${providers.length} sources`)}</span>
      </div>
      <p>{text(
        '这一视角使用产品 taxonomy 的类别→路径映射，再叠加近六小时运行量和 source health；它不声称某一次 execution 选择了未记录的处理路径。',
        'This view applies the product taxonomy category-to-route mapping, then overlays six-hour activity and source health; it does not claim an unrecorded per-execution path selection.',
      )}</p>
      <div className="lens-facts">
        <LensFact label={text('来源类别', 'CATEGORIES')} value={categories.map((item) => text(item.labelZh, item.label)).join(' · ')} />
        <LensFact label={text('新增 · 6H', 'FRESH · 6H')} value={String(fresh)} />
        <LensFact label={text('运行 · 6H', 'RUNS · 6H')} value={String(runs)} />
        <LensFact label={text('健康度', 'HEALTH')} value={`${health.healthy}H · ${health.degraded}D · ${health.blocked}B`} />
      </div>
      <div className="path-category-map">
        {categories.map((source) => {
          const state = snapshot?.categories.find((item) => item.category === source.key)
          const activity = categoryActivity(snapshot?.category_hourly_series?.[source.key] ?? [])
          return (
            <div key={source.key}>
              <span className={`state-${sourceState(state)}`} />
              <div><small>{source.sub}</small><strong>{text(source.labelZh, source.label)}</strong></div>
              <em>{text(`${activity.fresh} 新增 · ${activity.runs} 运行`, `${activity.fresh} fresh · ${activity.runs} runs`)}</em>
            </div>
          )
        })}
      </div>
      <div className="path-failure-field">
        <div><small>{text('当前边界', 'CURRENT BOUNDARY')}</small><strong>{failures.length ? text(`${failures.length} 个来源需要注意`, `${failures.length} sources require attention`) : text('无 degraded / blocked 来源', 'NO DEGRADED / BLOCKED SOURCES')}</strong></div>
        {failures.slice(0, 6).map((provider) => (
          <div key={provider.source_id} className={`state-${provider.health}`}>
            <span>{provider.source_id}</span>
            <b>{provider.latest_error_code ?? provider.latest_scheduled_status ?? provider.health}</b>
          </div>
        ))}
      </div>
      <div className="lens-coordinate mono">{lane.toLowerCase().replaceAll(' ', '-')} / taxonomy-map + runtime-overlay</div>
    </div>
  )
}

function HotLens({ item, onInspect }: { item: HotBug; onInspect: () => void }) {
  const { text } = useI18n()
  const signal = item.priority_signals.includes('critical_severity') ? text('严重等级', 'CRITICAL SEVERITY') : item.priority_signals[0]?.replaceAll('_', ' ').toUpperCase() ?? text('热点', 'HOT')
  return (
    <div className="lens-stack">
      <div className="lens-index">{text('HOT 工作集 / REDIS 读取边界', 'HOT WORKING SET / REDIS READ SEAM')}</div>
      <div className="lens-title"><span><Flame size={18} /></span><div><small>{signal}</small><strong>{item.cve_id ?? item.external_object_id}</strong></div></div>
      <p>{item.description ?? item.title ?? text('当前 Hot Bug 投影来自真实读取，不填充演示内容。', 'Current Hot Bug projection. No demo content substituted.')}</p>
      <div className="lens-facts two">
        <LensFact label={text('来源', 'SOURCE')} value={item.source_id} />
        <LensFact label={text('版本', 'REVISION')} value={item.external_revision ?? text('内容版本', 'content revision')} />
        <LensFact label="CVSS" value={item.cvss_score != null ? `${item.cvss_score.toFixed(1)} ${item.cvss_severity ?? ''}` : '—'} />
        <LensFact label="TTL" value={item.ttl_seconds != null ? `${Math.max(0, Math.round(item.ttl_seconds / 60))} min` : item.pinned ? text('已固定', 'pinned') : '—'} />
        <LensFact label={text('读取次数', 'ACCESS')} value={item.access_count > 0 ? formatHotCount(item.access_count) : '0'} />
        <LensFact label={text('工作状态', 'WORKING STATE')} value={[item.active ? text('活动', 'active') : null, item.pinned ? text('已固定', 'pinned') : null].filter(Boolean).join(' · ') || text('被动', 'passive')} />
      </div>
      <div className="lens-signal"><small>{text('变化字段', 'CHANGED FIELDS')}</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : text('无已报告字段', 'none reported')}</span></div>
      <div className="lens-signal"><small>{text('优先级信号', 'PRIORITY SIGNALS')}</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : text('无已报告信号', 'none reported')}</span></div>
      <button className="lens-primary" onClick={onInspect}>{text('打开情报档案', 'OPEN INTELLIGENCE DOSSIER')} <ArrowUpRight size={13} /></button>
      <div className="lens-coordinate mono">{item.source_id}:{item.external_object_id}</div>
    </div>
  )
}

function LensFact({ label, value }: { label: string; value: string }) {
  return <div><small>{label}</small><strong>{value}</strong></div>
}

function Telemetry({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return <div className={`telemetry-readout tone-${tone}`}><small>{label}</small><strong>{value}</strong><span>{detail}</span></div>
}

function sourceState(health: { healthy: number; degraded: number; blocked: number } | undefined) {
  if (!health) return 'unknown'
  const total = health.healthy + health.degraded + health.blocked
  if (total > 0 && health.blocked === total) return 'blocked'
  if (health.degraded > 0 || health.blocked > 0) return 'degraded'
  if (health.healthy > 0) return 'healthy'
  return 'unknown'
}

function laneClass(source: (typeof sources)[number] | null, focusedLane: string | null, lane: string) {
  if (focusedLane) return focusedLane === lane ? 'active selected' : 'dimmed'
  if (!source) return ''
  return sourceNarrative[source.key]?.lane === lane ? 'active' : 'dimmed'
}

function laneSlug(lane: string) {
  if (lane === 'BUG STREAM') return 'lane-bug'
  if (lane === 'DEVELOPMENT INDEX') return 'lane-development'
  if (lane === 'INSIGHT CORPUS') return 'lane-insight'
  if (lane === 'INCIDENT WATCH') return 'lane-incident'
  return 'lane-assets'
}

function hotIdentity(item: HotBug) {
  return `${item.source_id}:${item.external_object_id}`
}

function parseHotIdentity(value: string | null) {
  if (!value) return null
  const separator = value.indexOf(':')
  if (separator <= 0 || separator >= value.length - 1) return null
  return {
    sourceId: value.slice(0, separator),
    externalObjectId: value.slice(separator + 1),
  }
}

function snapshotAge(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}
