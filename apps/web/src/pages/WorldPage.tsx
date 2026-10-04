import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
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
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getWorldOverview } from '../lib/api'

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

export function WorldPage() {
  const navigate = useNavigate()
  const worldQuery = useQuery({ queryKey: ['world-overview'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const snapshot = worldQuery.data
  const oneHour = snapshot?.windows['1h']
  const categoryHealth = new Map(snapshot?.categories.map((item) => [item.category, item]) ?? [])

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

      <div className="world-stage panel-glass">
        <div className="world-grid" />
        <div className="world-halo halo-a" />
        <div className="world-halo halo-b" />

        <svg className="world-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {sources.map((source) => (
            <path key={source.label} d={`M ${source.x} ${source.y} Q 50 50 50 50`} />
          ))}
        </svg>

        <motion.div
          className="evidence-core"
          initial={{ scale: 0.92, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.75 }}
        >
          <span className="core-glyph"><WaypointsCore /></span>
          <strong>EVIDENCE CORE</strong>
          <small>durable world</small>
          <div className="core-pulse" />
        </motion.div>

        {sources.map(({ key, label, sub, icon: Icon, x, y, tone }, index) => {
          const health = categoryHealth.get(key)
          const healthSummary = health ? `${health.healthy} healthy · ${health.degraded} degraded · ${health.blocked} blocked` : sub
          return <motion.button
            key={label}
            className={`source-node tone-${tone}`}
            style={{ left: `${x}%`, top: `${y}%` }}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.12 + index * 0.05 }}
          >
            <span className="source-icon"><Icon size={18} /></span>
            <span><strong>{label}</strong><small>{healthSummary}</small></span>
          </motion.button>
        })}

        <div className="hot-layer-label">
          <Flame size={13} /> HOT LAYER · Redis read seam connecting
        </div>
        <div className="world-path path-bug">BUG STREAM</div>
        <div className="world-path path-dev">DEVELOPMENT INDEX</div>
        <div className="world-path path-insight">INSIGHT CORPUS</div>
        <div className="world-path path-incident">INCIDENT WATCH</div>
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
