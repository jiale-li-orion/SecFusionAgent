import './public-briefings.css'
import { useQuery } from '@tanstack/react-query'
import { useI18n } from '../../lib/i18n'
import { dateLabel } from './feedPresentation'

type PublicBrief = {
  brief_id: string
  title: string
  topic: string
  summary?: string | null
  excerpt: string
  created_at: string
  window_start: string | null
  window_end: string | null
  source_count: number
  report_url: string
}

async function readBriefs(): Promise<PublicBrief[]> {
  const response = await fetch('/api/v1/intelligence/briefs?limit=3')
  if (!response.ok) throw new Error('Public reports are temporarily unavailable')
  return response.json() as Promise<PublicBrief[]>
}

export function PublicBriefings() {
  const { text, language } = useI18n()
  const briefs = useQuery({ queryKey: ['public-intelligence-briefs'], queryFn: readBriefs, staleTime: 60_000, refetchInterval: 60_000 })
  if (briefs.isError) return <p className="intel-feed-error">{text('编研报告暂时无法读取。', 'Editorial reports are temporarily unavailable.')}<button onClick={() => void briefs.refetch()}>{text('重试', 'Retry')}</button></p>
  if (!briefs.data?.length) return null
  return <section aria-label={text('情报编研', 'Intelligence reports')}>
    <div className="intel-stream-label"><span>{text('情报编研', 'Intelligence reports')}</span><small>{text('事实 · 分析 · 来源', 'Facts · Analysis · Sources')}</small></div>
    {briefs.data.map(brief => <article key={brief.brief_id} className="intel-feed-card">
      <div className="intel-card-meta"><span>{brief.topic}</span><span>{brief.window_start ? text('时段简报', 'Period briefing') : text('专题报告', 'Research brief')}</span></div>
      <h2><a href={brief.report_url} target="_blank" rel="noopener noreferrer">{brief.title}</a></h2>
      <p className={`intel-card-excerpt${brief.summary ? ' public-brief-summary' : ''}`}>{brief.summary ?? brief.excerpt}</p>
      <footer><span>{text('编研于', 'Prepared')} {dateLabel(brief.created_at, language)} · {text(`${brief.source_count} 个来源`, `${brief.source_count} sources`)}</span><a href={brief.report_url} target="_blank" rel="noopener noreferrer">{text('阅读全文', 'Read report')}</a></footer>
    </article>)}
  </section>
}
