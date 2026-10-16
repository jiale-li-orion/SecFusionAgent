import { productTerm } from '../../lib/productVocabulary'
import { useNavigate } from 'react-router-dom'
import { Activity, Database, RadioTower } from '../ui/icons'
import type { WorldOverview } from '../../lib/api/world'
import { useI18n } from '../../lib/i18n'
import { linePath, type ObservatoryWindow } from '../../lib/observatoryPresentation'
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card'
import './observatory-overview.css'

export function ObservatoryPulse({ world, windowKey, failed }: { world: WorldOverview | null; windowKey: ObservatoryWindow; failed: boolean }) {
  const { text, language } = useI18n()
  const navigate = useNavigate()
  const hours = windowKey === '168h' ? 168 : Number.parseInt(windowKey)
  const series = (world?.hourly_series ?? []).slice(-hours)
  const health = world?.source_health
  const count = health ? health.healthy + health.degraded + health.blocked : null
  const trends = [
    { key: 'fresh', icon: Activity, value: world?.windows[windowKey]?.fresh_external_changes, values: series.map(point => typeof point.fresh_external_changes === 'number' ? point.fresh_external_changes : null), label: text('外部新变化', 'Fresh changes') },
    { key: 'writes', icon: Database, value: world?.windows[windowKey]?.canonical_writes, values: series.map(point => typeof point.canonical_writes === 'number' ? point.canonical_writes : null), label: text('知识写入', 'Knowledge writes') },
  ]
  const time = (value: string) => new Date(value).toLocaleTimeString(language === 'zh' ? 'zh-CN' : 'en-US', { hour: '2-digit', minute: '2-digit' })
  return <section className="observatory-overview" aria-label={text('数据运行概览', 'Data overview')}>
    <div className="observatory-summary-grid">
      {trends.map(({ key, icon: Icon, value, values, label }) => {
        const peak = Math.max(1, ...values.map(value => value ?? 0))
        return <Card className={`observatory-summary-card summary-${key}`} key={key}>
          <CardHeader><CardTitle><Icon size={16}/>{label}</CardTitle></CardHeader>
          <CardContent><strong className="observatory-summary-value">{value?.toLocaleString() ?? '—'}</strong>
            <div className="observatory-sparkline">
              {values.length ? <svg viewBox="0 0 320 72" preserveAspectRatio="none" role="img" aria-label={text(`${label}，${series.length} 个小时样本`, `${label}, ${series.length} hourly samples`)}>
                <path className="observatory-chart-baseline" d="M0 67H320"/>
                <path key={`${windowKey}-${key}`} pathLength={1} className="observatory-chart-line" d={linePath(values, 320, 72, peak)}/>
                {values.length === 1 && values[0] !== null && <circle cx="160" cy={72 - Math.min(values[0] / peak, 1) * 62 - 5} r="3" fill="currentColor"/>}
              </svg> : <span>{failed ? text('读数暂不可用', 'Readings unavailable') : text('等待小时样本', 'Awaiting hourly samples')}</span>}
            </div>
            <div className="observatory-chart-foot"><span>{text('按小时记录', 'Hourly observations')}</span><span>{series.length} {text('个样本', 'samples')}</span></div>
          </CardContent>
        </Card>
      })}
      <Card className="observatory-summary-card summary-health">
        <CardHeader><CardTitle><RadioTower size={16}/>{text('来源健康', 'Source health')}</CardTitle></CardHeader>
        <CardContent><strong className="observatory-summary-value">{health?.healthy ?? '—'}<small>/ {count ?? '—'}</small></strong>
          <div className="observatory-source-grid">{world?.sources.map(source => <button key={source.source_id} className={`health-${source.health}`} aria-label={`${source.source_name ?? source.source_id} · ${productTerm(source.health, text)}`} title={`${source.source_name ?? source.source_id} · ${productTerm(source.health, text)}`} onClick={() => navigate(`/?source=${encodeURIComponent(source.measurement_category)}`)}/>)}</div>
          <div className="observatory-health-legend"><span><i className="health-healthy"/>{text('健康', 'Healthy')} {health?.healthy ?? '—'}</span><span><i className="health-degraded"/>{text('降级', 'Degraded')} {health?.degraded ?? '—'}</span><span><i className="health-blocked"/>{text('阻塞', 'Blocked')} {health?.blocked ?? '—'}</span></div>
        </CardContent>
      </Card>
    </div>
    <p className="observatory-measured-at">{world ? text(`读数更新于 ${time(world.generated_at)}`, `Measured at ${time(world.generated_at)}`) : failed ? text('读数暂不可用，可通过上方按钮重试。', 'Readings are unavailable. Retry using Refresh above.') : text('正在读取运行状态…', 'Loading operational state…')}</p>
  </section>
}
