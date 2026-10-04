import { useEffect, useMemo, useState } from 'react'
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
  X,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { WorldField3D } from '../components/world/WorldField3D'
import { getHotWorld, getWorldOverview, type HotBug } from '../lib/api'

const sources = [
  { key: 'vulnerability', label: 'VULNERABILITY', sub: 'CVE · NVD · KEV', icon: Bug, x: 12, y: 26 },
  { key: 'development', label: 'DEVELOPMENT', sub: 'Git · Package · Release', icon: Code2, x: 31, y: 12 },
  { key: 'academic', label: 'ACADEMIC', sub: 'Paper · Preprint', icon: GraduationCap, x: 59, y: 10 },
  { key: 'vendor', label: 'VENDOR', sub: 'Advisory · PSIRT', icon: Building2, x: 84, y: 25 },
  { key: 'independent', label: 'INDEPENDENT', sub: 'OSINT · Analysis', icon: RadioTower, x: 87, y: 69 },
  { key: 'normative', label: 'NORMATIVE', sub: 'Standard · Regulation', icon: FileBadge, x: 64, y: 85 },
  { key: 'assets', label: 'ASSETS', sub: 'Exposure · Inventory', icon: Boxes, x: 35, y: 86 },
  { key: 'incidents', label: 'INCIDENTS', sub: 'Report · Signal', icon: ShieldAlert, x: 11, y: 68 },
]

const sourceNarrative: Record<string, { lane: string; role: string; summary: string }> = {
  vulnerability: { lane: 'BUG STREAM', role: 'deterministic + canonical identity', summary: 'CVE / NVD / KEV form the vulnerability spine and feed normalized security facts into the durable world.' },
  development: { lane: 'DEVELOPMENT INDEX', role: 'graph + fix intelligence', summary: 'Repository, release and package evidence expands fix, version and development relationships.' },
  academic: { lane: 'INSIGHT CORPUS', role: 'semantic enrichment', summary: 'Papers and research signals add analytical context without overriding authoritative source facts.' },
  vendor: { lane: 'BUG STREAM', role: 'primary advisory authority', summary: 'Vendor advisories provide product, remediation and fix-boundary evidence with source authority kept visible.' },
  independent: { lane: 'INSIGHT CORPUS', role: 'secondary analysis', summary: 'Independent analysis contributes supporting observations and cross-source context.' },
  normative: { lane: 'INSIGHT CORPUS', role: 'standards / normative context', summary: 'Standards and normative documents contribute constrained policy and technical context.' },
  assets: { lane: 'ASSET OBSERVATION', role: 'applicability / exposure', summary: 'Observed assets bind canonical product/version facts to deployment applicability through an on-demand side path.' },
  incidents: { lane: 'INCIDENT WATCH', role: 'signal → candidate → durable incident', summary: 'Incident signals remain provisional until evidence is strong enough to enter the durable Incident world.' },
}

const hotSlots = [
  { left: '27%', top: '45%' },
  { left: '73%', top: '43%' },
  { left: '64%', top: '66%' },
  { left: '38%', top: '69%' },
  { left: '52%', top: '30%' },
]

export function WorldPage() {
  const navigate = useNavigate()
  const reduceMotion = Boolean(useReducedMotion())
  const [focusedSource, setFocusedSource] = useState<string | null>(null)
  const [focusedHotKey, setFocusedHotKey] = useState<string | null>(null)
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const hotQuery = useQuery({ queryKey: ['world-hot'], queryFn: () => getHotWorld(6), refetchInterval: 20_000 })
  const snapshot = worldQuery.data
  const oneHour = snapshot?.windows['1h']
  const categoryHealth = useMemo(() => new Map(snapshot?.categories.map((item) => [item.category, item]) ?? []), [snapshot?.categories])
  const hotItems = useMemo(() => hotQuery.data?.items ?? [], [hotQuery.data?.items])
  const focusedHot = useMemo(() => hotItems.find((item) => hotIdentity(item) === focusedHotKey) ?? null, [hotItems, focusedHotKey])
  const focusedSourceMeta = sources.find((source) => source.key === focusedSource) ?? null
  const hasFocus = Boolean(focusedSourceMeta || focusedHot)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') clearFocus()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  function focusSource(key: string) {
    setFocusedHotKey(null)
    setFocusedSource((current) => current === key ? null : key)
  }

  function focusHot(item: HotBug) {
    setFocusedSource(null)
    const key = hotIdentity(item)
    setFocusedHotKey((current) => current === key ? null : key)
  }

  function clearFocus() {
    setFocusedSource(null)
    setFocusedHotKey(null)
  }

  return (
    <section className="world-space-v3">
      <header className="world-hero-v3">
        <div>
          <p>CONTINUOUS EVIDENCE FORMATION / M1 → M3</p>
          <h1>EVIDENCE <span>WORLD</span></h1>
          <small>八类异构来源进入真实 processing path，形成 Hot working set、Evidence、Knowledge、Incident、Insight 与 Experience。</small>
        </div>
        <div className="world-hero-actions-v3">
          <button onClick={() => navigate('/observatory')}>LIVE RUNTIME <ArrowUpRight size={13} /></button>
          <button className="launch" onClick={() => navigate('/start')}><Sparkles size={13} /> START ANALYSIS</button>
        </div>
      </header>

      <div className={`world-stage-v3 ${hasFocus ? 'has-focus' : ''}`}>
        <WorldField3D
          categories={snapshot?.categories ?? []}
          freshChanges={oneHour?.fresh_external_changes ?? 0}
          backfillObservations={oneHour?.backfill_observations ?? 0}
          canonicalWrites={oneHour?.canonical_writes ?? 0}
          focusedSource={focusedSource}
          reduceMotion={reduceMotion}
          onSourceFocus={focusSource}
        />

        <div className="world-depth-mask-v3" />
        <div className="world-coordinate-v3 north">N / SOURCE TAXONOMY</div>
        <div className="world-coordinate-v3 west">M1 · MONITORING</div>
        <div className="world-coordinate-v3 east">M2 · EVIDENCE</div>

        <div className="durable-core-label-v3">
          <small>DURABLE INNER WORLD</small>
          <strong>EVIDENCE CORE</strong>
          <span>Evidence · Knowledge · Incident · Insight · Experience</span>
          <i className={oneHour?.canonical_writes ? 'active' : ''} />
        </div>

        <div className="processing-lanes-v3" aria-label="Processing paths">
          <span className={laneClass(focusedSourceMeta, 'BUG STREAM')}>BUG STREAM</span>
          <span className={laneClass(focusedSourceMeta, 'DEVELOPMENT INDEX')}>DEVELOPMENT INDEX</span>
          <span className={laneClass(focusedSourceMeta, 'INSIGHT CORPUS')}>INSIGHT CORPUS</span>
          <span className={laneClass(focusedSourceMeta, 'INCIDENT WATCH')}>INCIDENT WATCH</span>
          <span className={laneClass(focusedSourceMeta, 'ASSET OBSERVATION')}>ASSET OBSERVATION / ON-DEMAND</span>
        </div>

        {sources.map(({ key, label, sub, icon: Icon, x, y }, index) => {
          const health = categoryHealth.get(key)
          const selected = focusedSource === key
          const dimmed = Boolean((focusedSource && !selected) || focusedHot)
          const state = sourceState(health)
          return (
            <motion.button
              key={key}
              className={`source-beacon-v3 state-${state} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
              style={{ left: `${x}%`, top: `${y}%` }}
              onClick={() => focusSource(key)}
              initial={{ opacity: 0, scale: .88 }}
              animate={{ opacity: dimmed ? .22 : 1, scale: selected ? 1.08 : 1 }}
              transition={{ delay: reduceMotion ? 0 : index * .035, duration: .2 }}
            >
              <span className="source-beacon-glyph-v3"><Icon size={15} /></span>
              <span className="source-beacon-copy-v3">
                <small>{String(index + 1).padStart(2, '0')} / {state.toUpperCase()}</small>
                <strong>{label}</strong>
                <em>{health ? `${health.healthy}H · ${health.degraded}D · ${health.blocked}B` : sub}</em>
              </span>
              <i />
            </motion.button>
          )
        })}

        <div className="hot-field-v3" aria-label="Hot Bug working set">
          <div className="hot-field-label-v3">
            <Flame size={12} />
            <span>HOT WORKING SET</span>
            <small>{hotQuery.isLoading ? 'CONNECTING' : hotQuery.isError ? 'UNAVAILABLE' : `${hotItems.length} OBJECTS`}</small>
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
        </div>

        <div className="world-semantic-legend-v3">
          <span><i className="fresh" />particle density = 1h fresh changes</span>
          <span><i className="ghost" />ghost transit = 1h backfill</span>
          <span><i className="write" />core ripple = 1h canonical writes</span>
          <span><i className="degraded" />amber = category has degraded sources</span>
        </div>

        {!hasFocus && <div className="world-focus-hint-v3"><Crosshair size={12} /> FOCUS SOURCE / HOT OBJECT</div>}

        <AnimatePresence>
          {hasFocus && (
            <motion.aside
              className="world-lens-v3"
              initial={{ opacity: 0, x: 48, clipPath: 'inset(0 0 0 18%)' }}
              animate={{ opacity: 1, x: 0, clipPath: 'inset(0 0 0 0%)' }}
              exit={{ opacity: 0, x: 28, clipPath: 'inset(0 0 0 12%)' }}
              transition={{ type: 'spring', stiffness: 240, damping: 27 }}
            >
              <button className="world-lens-close-v3" onClick={clearFocus} aria-label="Close focus lens"><X size={15} /></button>
              {focusedHot ? (
                <HotLens item={focusedHot} onInspect={() => navigate(`/intelligence?cve=${encodeURIComponent(focusedHot.cve_id ?? focusedHot.external_object_id)}`)} />
              ) : focusedSourceMeta ? (
                <SourceLens source={focusedSourceMeta} health={categoryHealth.get(focusedSourceMeta.key)} />
              ) : null}
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      <div className="world-telemetry-v3">
        <Telemetry label="SOURCE HEALTH" value={snapshot ? `${snapshot.source_health.healthy}/${snapshot.source_health.healthy + snapshot.source_health.degraded + snapshot.source_health.blocked}` : '—'} detail={snapshot ? `${(snapshot.healthy_rate * 100).toFixed(1)}% healthy` : worldQuery.isError ? 'unavailable' : 'resolving'} tone="lime" />
        <Telemetry label="FRESH CHANGES · 1H" value={oneHour ? String(oneHour.fresh_external_changes) : '—'} detail={oneHour ? `${oneHour.observations} observations` : 'operational snapshot'} tone="cyan" />
        <Telemetry label="CANONICAL WRITES · 1H" value={oneHour ? String(oneHour.canonical_writes) : '—'} detail={oneHour ? `${oneHour.backfill_observations} backfill` : 'operational snapshot'} tone="violet" />
        <Telemetry label="QUEUE / EXEC P95" value={oneHour?.queue_delay_p95_seconds != null && oneHour?.execution_p95_seconds != null ? `${oneHour.queue_delay_p95_seconds.toFixed(1)} / ${oneHour.execution_p95_seconds.toFixed(1)}s` : '—'} detail={oneHour?.scheduled_run_success_rate != null ? `${(oneHour.scheduled_run_success_rate * 100).toFixed(1)}% scheduled success` : 'not evaluable'} tone="amber" />
        <Telemetry label="SNAPSHOT AGE" value={snapshot ? snapshotAge(snapshot.generated_at) : '—'} detail={snapshot ? new Date(snapshot.generated_at).toLocaleString() : 'loading truth source'} tone="blue" />
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
  const slot = hotSlots[index % hotSlots.length]
  const identity = item.cve_id ?? item.external_object_id
  const state = item.pinned ? 'pinned' : item.active ? 'active' : item.priority_signals.includes('critical_severity') ? 'critical' : 'hot'
  const signal = item.pinned ? 'PINNED' : item.active ? 'ACTIVE' : item.priority_signals[0]?.replaceAll('_', ' ') ?? 'HOT'

  return (
    <motion.button
      className={`hot-crystal-v3 state-${state} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
      style={slot}
      onClick={onOpen}
      animate={{
        opacity: dimmed ? .18 : 1,
        scale: selected ? 1.11 : dimmed ? .94 : 1,
        y: reduceMotion || selected ? 0 : [0, -5, 0],
      }}
      transition={{ opacity: { duration: .2 }, scale: { duration: .2 }, y: { duration: 4.2 + index * .45, repeat: Infinity, ease: 'easeInOut' } }}
    >
      <span className="hot-crystal-cut-v3" />
      <small>{signal}</small>
      <strong>{identity}</strong>
      <em>{item.cvss_score != null ? `CVSS ${item.cvss_score.toFixed(1)} · ${item.cvss_severity ?? ''}` : item.source_id}</em>
      {item.changed_fields.length > 0 && <i className="hot-change-v3" />}
      {(item.active || item.pinned) && <span className="hot-orbit-v3" />}
    </motion.button>
  )
}

function SourceLens({
  source,
  health,
}: {
  source: (typeof sources)[number]
  health: { healthy: number; degraded: number; blocked: number } | undefined
}) {
  const narrative = sourceNarrative[source.key]
  const total = health ? health.healthy + health.degraded + health.blocked : 0
  const Icon = source.icon

  return (
    <div className="lens-stack-v3">
      <div className="lens-index-v3">SOURCE CONSTELLATION / {source.key.toUpperCase()}</div>
      <div className="lens-title-v3"><span><Icon size={18} /></span><div><small>{source.sub}</small><strong>{source.label}</strong></div></div>
      <p>{narrative.summary}</p>
      <div className="lens-facts-v3">
        <LensFact label="PROCESSING PATH" value={narrative.lane} />
        <LensFact label="WORLD ROLE" value={narrative.role} />
        <LensFact label="HEALTH" value={health ? `${health.healthy}/${total} healthy` : 'snapshot unavailable'} />
      </div>
      {health && total > 0 && (
        <div className="lens-health-v3">
          <span className="healthy" style={{ width: `${health.healthy / total * 100}%` }} />
          <span className="degraded" style={{ width: `${health.degraded / total * 100}%` }} />
          <span className="blocked" style={{ width: `${health.blocked / total * 100}%` }} />
        </div>
      )}
      <div className="lens-coordinate-v3 mono">{source.key} / operational category</div>
    </div>
  )
}

function HotLens({ item, onInspect }: { item: HotBug; onInspect: () => void }) {
  const signal = item.pinned ? 'PINNED' : item.active ? 'ACTIVE' : item.priority_signals[0]?.replaceAll('_', ' ') ?? 'HOT'
  return (
    <div className="lens-stack-v3">
      <div className="lens-index-v3">HOT WORKING SET / REDIS READ SEAM</div>
      <div className="lens-title-v3"><span><Flame size={18} /></span><div><small>{signal}</small><strong>{item.cve_id ?? item.external_object_id}</strong></div></div>
      <p>{item.description ?? item.title ?? 'Current Hot Bug projection. No demo content substituted.'}</p>
      <div className="lens-facts-v3 two">
        <LensFact label="SOURCE" value={item.source_id} />
        <LensFact label="REVISION" value={item.external_revision ?? 'content revision'} />
        <LensFact label="CVSS" value={item.cvss_score != null ? `${item.cvss_score.toFixed(1)} ${item.cvss_severity ?? ''}` : '—'} />
        <LensFact label="TTL" value={item.ttl_seconds != null ? `${Math.max(0, Math.round(item.ttl_seconds / 60))} min` : item.pinned ? 'pinned' : '—'} />
      </div>
      <div className="lens-signal-v3"><small>CHANGED FIELDS</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : 'none reported'}</span></div>
      <div className="lens-signal-v3"><small>PRIORITY SIGNALS</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : 'none reported'}</span></div>
      <button className="lens-primary-v3" onClick={onInspect}>OPEN INTELLIGENCE DOSSIER <ArrowUpRight size={13} /></button>
      <div className="lens-coordinate-v3 mono">{item.source_id}:{item.external_object_id}</div>
    </div>
  )
}

function LensFact({ label, value }: { label: string; value: string }) {
  return <div><small>{label}</small><strong>{value}</strong></div>
}

function Telemetry({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return <div className={`telemetry-readout-v3 tone-${tone}`}><small>{label}</small><strong>{value}</strong><span>{detail}</span></div>
}

function sourceState(health: { healthy: number; degraded: number; blocked: number } | undefined) {
  if (!health) return 'unknown'
  const total = health.healthy + health.degraded + health.blocked
  if (total > 0 && health.blocked === total) return 'blocked'
  if (health.degraded > 0 || health.blocked > 0) return 'degraded'
  if (health.healthy > 0) return 'healthy'
  return 'unknown'
}

function laneClass(source: (typeof sources)[number] | null, lane: string) {
  if (!source) return ''
  return sourceNarrative[source.key]?.lane === lane ? 'active' : 'dimmed'
}

function hotIdentity(item: HotBug) {
  return `${item.source_id}:${item.external_object_id}`
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
