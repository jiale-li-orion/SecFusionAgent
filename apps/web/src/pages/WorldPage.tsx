import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import {
  Boxes,
  Bug,
  Building2,
  Code2,
  FileBadge,
  Flame,
  GraduationCap,
  RadioTower,
  ShieldAlert,
  ArrowUpRight,
  Crosshair,
  X,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getHotWorld, getWorldOverview, type HotBug } from '../lib/api'

const sources = [
  { key: 'vulnerability', label: 'VULNERABILITY', sub: 'CVE · NVD · KEV', icon: Bug, x: 14, y: 25, tone: 'cyan' },
  { key: 'development', label: 'DEVELOPMENT', sub: 'Git · Package · Release', icon: Code2, x: 34, y: 10, tone: 'cyan' },
  { key: 'academic', label: 'ACADEMIC', sub: 'Paper · Preprint', icon: GraduationCap, x: 62, y: 9, tone: 'violet' },
  { key: 'vendor', label: 'VENDOR', sub: 'Advisory · PSIRT', icon: Building2, x: 84, y: 24, tone: 'blue' },
  { key: 'independent', label: 'INDEPENDENT', sub: 'OSINT · Analysis', icon: RadioTower, x: 89, y: 70, tone: 'violet' },
  { key: 'normative', label: 'NORMATIVE', sub: 'Standard · Regulation', icon: FileBadge, x: 66, y: 84, tone: 'blue' },
  { key: 'assets', label: 'ASSETS', sub: 'Exposure · Inventory', icon: Boxes, x: 36, y: 85, tone: 'blue' },
  { key: 'incidents', label: 'INCIDENTS', sub: 'Report · Signal', icon: ShieldAlert, x: 12, y: 67, tone: 'lime' },
]

const sourceNarrative: Record<string, { lane: string; role: string; summary: string }> = {
  vulnerability: { lane: 'BUG STREAM', role: 'deterministic + canonical identity', summary: 'CVE / NVD / KEV form the vulnerability spine and feed normalized security facts into the durable world.' },
  development: { lane: 'DEVELOPMENT INDEX', role: 'graph + fix intelligence', summary: 'Repository, release and package evidence expands fix, version and development relationships.' },
  academic: { lane: 'INSIGHT CORPUS', role: 'semantic enrichment', summary: 'Papers and research signals add strong-anchor analytical context without overriding authoritative source facts.' },
  vendor: { lane: 'BUG STREAM', role: 'primary advisory authority', summary: 'Vendor advisories provide product, remediation and fix-boundary evidence with source authority kept visible.' },
  independent: { lane: 'INSIGHT CORPUS', role: 'secondary analysis', summary: 'Independent analysis contributes supporting observations and cross-source context.' },
  normative: { lane: 'INSIGHT CORPUS', role: 'standards / normative context', summary: 'Standards and normative documents contribute constrained policy and technical context.' },
  assets: { lane: 'DEVELOPMENT INDEX', role: 'applicability / exposure', summary: 'Observed assets bind canonical product/version facts to deployment applicability.' },
  incidents: { lane: 'INCIDENT WATCH', role: 'signal → candidate → durable incident', summary: 'Incident signals remain provisional until evidence is strong enough to enter the durable Incident world.' },
}

export function WorldPage() {
  const navigate = useNavigate()
  const [focusedSource, setFocusedSource] = useState<string | null>(null)
  const [focusedHotKey, setFocusedHotKey] = useState<string | null>(null)
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const hotQuery = useQuery({ queryKey: ['world-hot'], queryFn: () => getHotWorld(5), refetchInterval: 20_000 })
  const snapshot = worldQuery.data
  const oneHour = snapshot?.windows['1h']
  const categoryHealth = new Map(snapshot?.categories.map((item) => [item.category, item]) ?? [])
  const hotItems = hotQuery.data?.items ?? []
  const focusedHot = useMemo(() => hotItems.find((item) => hotIdentity(item) === focusedHotKey) ?? null, [hotItems, focusedHotKey])
  const focusedSourceMeta = sources.find((source) => source.key === focusedSource) ?? null
  const hasFocus = Boolean(focusedSourceMeta || focusedHot)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setFocusedSource(null)
        setFocusedHotKey(null)
      }
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
    <section className="page world-page">
      <div className="page-heading world-heading">
        <div>
          <p className="eyebrow">CONTINUOUSLY INGESTING · ENRICHING · CORRELATING · STABILIZING</p>
          <h1>THE EVIDENCE WORLD</h1>
          <p className="lede">八类来源围绕 Evidence Core 持续形成可追溯、可调查、可验证的安全情报世界。</p>
        </div>
        <div className="world-actions">
          <button className="ghost-action" onClick={() => navigate('/observatory')}>VIEW LIVE RUNTIME</button>
          <button className="primary-action" onClick={() => navigate('/start')}>START ANALYSIS</button>
        </div>
      </div>

      <div className={`world-stage panel-glass ${hasFocus ? 'has-focus' : ''}`}>
        <motion.div
          className="world-scene"
          animate={{ x: hasFocus ? -150 : 0, scale: hasFocus ? 1.055 : 1 }}
          transition={{ type: 'spring', stiffness: 170, damping: 24, mass: .75 }}
        >
          <div className="world-grid" />
          <div className="world-halo halo-a" />
          <div className="world-halo halo-b" />

          <svg className="world-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {sources.map((source) => (
              <path key={source.label} className={focusedSource && focusedSource !== source.key ? 'muted-link' : focusedSource === source.key ? 'focused-link' : ''} d={`M ${source.x} ${source.y} Q 50 50 50 50`} />
            ))}
          </svg>

          <motion.div
            className={`evidence-core ${hasFocus ? 'focus-active' : ''}`}
            initial={{ scale: 0.92, opacity: 0 }}
            animate={{ scale: hasFocus ? 1.05 : 1, opacity: 1 }}
            transition={{ duration: 0.55 }}
          >
            <span className="core-glyph"><WaypointsCore /></span>
            <strong>EVIDENCE CORE</strong>
            <small>durable world</small>
            <div className="core-pulse" />
          </motion.div>

          {sources.map(({ key, label, sub, icon: Icon, x, y, tone }, index) => {
            const health = categoryHealth.get(key)
            const healthSummary = health ? `${health.healthy} healthy · ${health.degraded} degraded · ${health.blocked} blocked` : sub
            const selected = focusedSource === key
            const dimmed = Boolean(focusedSource && !selected) || Boolean(focusedHot)
            return <motion.button
              key={label}
              className={`source-node tone-${tone} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
              style={{ left: `${x}%`, top: `${y}%` }}
              onClick={() => focusSource(key)}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: dimmed ? .18 : 1, scale: selected ? 1.11 : dimmed ? .94 : 1 }}
              transition={{ delay: hasFocus ? 0 : 0.12 + index * 0.05, duration: .22 }}
            >
              <span className="source-icon"><Icon size={18} /></span>
              <span><strong>{label}</strong><small>{healthSummary}</small></span>
            </motion.button>
          })}

          {hotItems.length > 0 ? (
            <div className="hot-cloud">
              {hotItems.slice(0, 5).map((item, index) => (
                <HotBugCard
                  key={`${item.source_id}:${item.external_object_id}`}
                  item={item}
                  index={index}
                  selected={focusedHotKey === hotIdentity(item)}
                  dimmed={Boolean(focusedSource) || Boolean(focusedHotKey && focusedHotKey !== hotIdentity(item))}
                  onOpen={() => focusHot(item)}
                />
              ))}
            </div>
          ) : (
            <div className={`hot-layer-label ${hotQuery.isError ? 'unavailable' : ''}`}>
              <Flame size={13} /> {hotQuery.isError ? 'HOT LAYER UNAVAILABLE' : hotQuery.isLoading ? 'HOT LAYER CONNECTING' : 'HOT LAYER EMPTY'}
            </div>
          )}
          <div className={`world-path path-bug ${focusedSourceMeta && focusedSourceMeta.key !== 'vulnerability' && sourceNarrative[focusedSourceMeta.key]?.lane !== 'BUG STREAM' ? 'dimmed' : focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane === 'BUG STREAM' ? 'active' : ''}`}>BUG STREAM</div>
          <div className={`world-path path-dev ${focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane !== 'DEVELOPMENT INDEX' ? 'dimmed' : focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane === 'DEVELOPMENT INDEX' ? 'active' : ''}`}>DEVELOPMENT INDEX</div>
          <div className={`world-path path-insight ${focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane !== 'INSIGHT CORPUS' ? 'dimmed' : focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane === 'INSIGHT CORPUS' ? 'active' : ''}`}>INSIGHT CORPUS</div>
          <div className={`world-path path-incident ${focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane !== 'INCIDENT WATCH' ? 'dimmed' : focusedSourceMeta && sourceNarrative[focusedSourceMeta.key]?.lane === 'INCIDENT WATCH' ? 'active' : ''}`}>INCIDENT WATCH</div>
        </motion.div>

        <AnimatePresence>
          {hasFocus && (
            <motion.aside
              className="world-focus-dossier"
              initial={{ opacity: 0, x: 42, scale: .98 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, scale: .985 }}
              transition={{ type: 'spring', stiffness: 230, damping: 27 }}
            >
              <button className="world-focus-close" onClick={clearFocus} aria-label="Close world focus"><X size={16} /></button>
              {focusedHot ? (
                <HotFocusDossier item={focusedHot} onInspect={() => navigate(`/intelligence?cve=${encodeURIComponent(focusedHot.cve_id ?? focusedHot.external_object_id)}`)} />
              ) : focusedSourceMeta ? (
                <SourceFocusDossier source={focusedSourceMeta} health={categoryHealth.get(focusedSourceMeta.key)} />
              ) : null}
            </motion.aside>
          )}
        </AnimatePresence>

        {!hasFocus && <div className="world-focus-hint"><Crosshair size={13} /> SELECT A SOURCE OR HOT OBJECT TO FOCUS</div>}
      </div>

      <div className="runtime-strip">
        <RuntimeMetric label="SOURCE HEALTH" value={snapshot ? `${snapshot.source_health.healthy} / ${snapshot.source_health.healthy + snapshot.source_health.degraded + snapshot.source_health.blocked}` : '—'} detail={snapshot ? `${(snapshot.healthy_rate * 100).toFixed(1)}% healthy` : worldQuery.isError ? 'unavailable' : 'loading'} tone="lime" />
        <RuntimeMetric label="FRESH CHANGES · 1H" value={oneHour ? String(oneHour.fresh_external_changes) : '—'} detail={oneHour ? `${oneHour.observations} observations` : 'snapshot'} tone="cyan" />
        <RuntimeMetric label="QUEUE P95" value={oneHour?.queue_delay_p95_seconds != null ? `${oneHour.queue_delay_p95_seconds.toFixed(2)}s` : '—'} detail={oneHour ? `${oneHour.scheduled_runs} scheduled runs` : 'snapshot'} tone="violet" />
        <RuntimeMetric label="EXECUTION P95" value={oneHour?.execution_p95_seconds != null ? `${oneHour.execution_p95_seconds.toFixed(2)}s` : '—'} detail={oneHour?.scheduled_run_success_rate != null ? `${(oneHour.scheduled_run_success_rate * 100).toFixed(1)}% run success` : 'snapshot'} tone="amber" />
        <RuntimeMetric label="SNAPSHOT" value={snapshot ? snapshotAge(snapshot.generated_at) : '—'} detail={snapshot ? new Date(snapshot.generated_at).toLocaleString() : 'loading operational truth'} tone="blue" />
      </div>
    </section>
  )
}

const hotSlots = [
  { left: '25%', top: '44%' },
  { left: '74%', top: '43%' },
  { left: '62%', top: '69%' },
  { left: '37%', top: '70%' },
  { left: '52%', top: '31%' },
]

function HotBugCard({ item, index, selected, dimmed, onOpen }: { item: HotBug; index: number; selected: boolean; dimmed: boolean; onOpen: () => void }) {
  const slot = hotSlots[index % hotSlots.length]
  const tone = item.pinned ? 'amber' : item.active ? 'lime' : item.priority_signals.includes('critical_severity') ? 'coral' : 'violet'
  const identity = item.cve_id ?? item.external_object_id
  const signal = item.pinned ? 'PINNED' : item.active ? 'ACTIVE' : item.priority_signals[0]?.replaceAll('_', ' ') ?? 'HOT'
  return (
    <motion.button
      className={`hot-cve tone-${tone} ${selected ? 'selected' : ''} ${dimmed ? 'dimmed' : ''}`}
      style={slot}
      onClick={onOpen}
      initial={{ opacity: 0, scale: 0.86 }}
      animate={{ opacity: dimmed ? .16 : 1, scale: selected ? 1.08 : dimmed ? .94 : 1, y: selected ? 0 : [0, -4, 0] }}
      transition={{ opacity: { duration: .25 }, scale: { duration: .25 }, y: { duration: 4.6 + index * .4, repeat: Infinity, ease: 'easeInOut' } }}
    >
      <span className="hot-cve-top"><Flame size={12} /><strong>{identity}</strong></span>
      <span className="hot-cve-meta">
        {item.cvss_score != null && <b>{item.cvss_score.toFixed(1)}</b>}
        <em>{item.cvss_severity ?? item.status ?? signal}</em>
      </span>
      <small>{signal} · access {item.access_count.toFixed(0)}</small>
    </motion.button>
  )
}

function SourceFocusDossier({ source, health }: { source: (typeof sources)[number]; health: { healthy: number; degraded: number; blocked: number } | undefined }) {
  const narrative = sourceNarrative[source.key]
  const total = health ? health.healthy + health.degraded + health.blocked : 0
  return <div className="world-focus-content">
    <div className="world-focus-kicker"><span className={`focus-glyph tone-${source.tone}`}><source.icon size={18} /></span><div><small>SOURCE CONSTELLATION</small><strong>{source.label}</strong><span>{source.sub}</span></div></div>
    <p>{narrative.summary}</p>
    <div className="world-focus-facts">
      <FocusFact label="PROCESSING LANE" value={narrative.lane} />
      <FocusFact label="ROLE IN WORLD" value={narrative.role} />
      <FocusFact label="SOURCE HEALTH" value={health ? `${health.healthy}/${total} healthy` : 'snapshot unavailable'} />
    </div>
    {health && <div className="focus-health-bar"><span className="healthy" style={{ width: total ? `${health.healthy / total * 100}%` : '0%' }} /><span className="degraded" style={{ width: total ? `${health.degraded / total * 100}%` : '0%' }} /><span className="blocked" style={{ width: total ? `${health.blocked / total * 100}%` : '0%' }} /></div>}
    <div className="world-focus-coordinate mono">{source.key} · operational category</div>
  </div>
}

function HotFocusDossier({ item, onInspect }: { item: HotBug; onInspect: () => void }) {
  const signal = item.pinned ? 'PINNED' : item.active ? 'ACTIVE' : item.priority_signals[0]?.replaceAll('_', ' ') ?? 'HOT'
  return <div className="world-focus-content hot-focus-content">
    <div className="world-focus-kicker"><span className="focus-glyph tone-amber"><Flame size={18} /></span><div><small>HOT WORKING SET</small><strong>{item.cve_id ?? item.external_object_id}</strong><span>{signal}</span></div></div>
    <p>{item.description ?? item.title ?? 'A recently observed vulnerability object currently held in the Redis Hot Layer.'}</p>
    <div className="world-focus-facts two-column">
      <FocusFact label="SOURCE" value={item.source_id} />
      <FocusFact label="REVISION" value={item.external_revision ?? 'content revision'} />
      <FocusFact label="CVSS" value={item.cvss_score != null ? `${item.cvss_score.toFixed(1)} ${item.cvss_severity ?? ''}` : '—'} />
      <FocusFact label="TTL" value={item.ttl_seconds != null ? `${Math.max(0, Math.round(item.ttl_seconds / 60))} min` : item.pinned ? 'persisted' : '—'} />
    </div>
    <div className="focus-signal-block"><small>CHANGED FIELDS</small><span>{item.changed_fields.length ? item.changed_fields.join(' · ') : 'none reported'}</span></div>
    <div className="focus-signal-block"><small>PRIORITY SIGNALS</small><span>{item.priority_signals.length ? item.priority_signals.join(' · ') : 'none reported'}</span></div>
    <button className="world-focus-primary" onClick={onInspect}>OPEN INTELLIGENCE DOSSIER <ArrowUpRight size={14} /></button>
    <div className="world-focus-coordinate mono">{item.source_id}:{item.external_object_id}</div>
  </div>
}

function FocusFact({ label, value }: { label: string; value: string }) {
  return <div className="focus-fact"><small>{label}</small><strong>{value}</strong></div>
}

function hotIdentity(item: HotBug) { return `${item.source_id}:${item.external_object_id}` }

function RuntimeMetric({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) {
  return (
    <article className={`runtime-metric panel-glass tone-${tone}`}>
      <small>{label}</small>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  )
}

function snapshotAge(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function WaypointsCore() {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" fill="none" aria-hidden="true">
      <circle cx="22" cy="22" r="6" />
      <circle cx="8" cy="11" r="3" />
      <circle cx="36" cy="11" r="3" />
      <circle cx="8" cy="33" r="3" />
      <circle cx="36" cy="33" r="3" />
      <path d="M12 13L18 19M32 13L26 19M12 31L18 25M32 31L26 25" />
    </svg>
  )
}
