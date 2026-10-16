import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getIncident, type IncidentSummary } from '../../lib/api/intelligence'
import type { WorldIncidentCandidate } from '../../lib/api/world'
import { groupLibraryMoments, orderIncidentHistory, validLibraryTime } from '../../lib/libraryPresentation'
import { useI18n } from '../../lib/i18n'
import { DevelopingField } from '../ui/developing-field'
import { Button } from '../ui/button'
import { dateLabel } from './feedPresentation'
import './library-explorers.css'

type Props = {
  incidents: IncidentSummary[]; candidates: WorldIncidentCandidate[]
  loading: boolean; candidatesLoading: boolean; error: boolean; candidateError: string | null
  onRetry: () => void; onRetryCandidates: () => void
  onIncident: (id: string) => void; onCandidate: (item: WorldIncidentCandidate) => void
}
export function EventLibrary({ incidents, candidates, loading, candidatesLoading, error, candidateError, onRetry, onRetryCandidates, onIncident, onCandidate }: Props) {
  const { text, language } = useI18n()
  const dateAxis = useRef<HTMLDivElement>(null)
  const [day, setDay] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const groups = groupLibraryMoments(incidents, candidates)
  const current = groups.find(group => group.day === day) ?? groups.at(-1)
  useEffect(() => {
    const axis = dateAxis.current
    const active = axis?.querySelector<HTMLButtonElement>('[aria-pressed=true]')
    if (axis && active) {
      const offset = active.getBoundingClientRect().left - axis.getBoundingClientRect().left
      if (offset < 0 || offset + active.offsetWidth > axis.clientWidth) axis.scrollLeft += offset - (axis.clientWidth - active.offsetWidth) / 2
    }
  }, [current?.day])
  const selected = current?.items.find(item => item.id === selectedId) ?? current?.items.at(-1)
  const detail = useQuery({ queryKey: ['incident', selected?.incident?.incident_id], queryFn: () => getIncident(selected!.incident!.incident_id), enabled: Boolean(selected?.incident) })
  const history = orderIncidentHistory(detail.data?.timeline ?? [])
  const [historyId, setHistoryId] = useState('')
  const historyEvent = history.find(event => event.event_id === historyId) ?? history.at(-1)
  const basis = (value: string) => value === 'reported_date' ? text('档案起始日期', 'Dossier starts') : value === 'record_updated' ? text('档案更新', 'Dossier updated') : value === 'published' ? text('来源发布', 'Source published') : value === 'observed' ? text('系统发现', 'System observed') : text('时间未提供', 'Date unavailable')
  return <section className="event-library" aria-label={text('事件时间轴', 'Event timeline')} data-develop-scope>
    <header className="library-intro"><div><span className="library-eyebrow">{text('事件库', 'Event library')}</span><h2>{text('沿时间，追踪变化', 'Follow change through time')}</h2></div><p>{text('选择日期，让当天的事件与线索显现。', 'Choose a date to reveal its events and signals.')}</p></header>
    {(loading || candidatesLoading) && <p role="status" className="library-notice">{text('正在读取时间轴…', 'Loading the timeline…')}</p>}
    {error && <p role="alert" className="library-notice">{text('事件档案暂时无法读取。', 'Event dossiers could not be loaded.')} <Button variant="ghost" onClick={onRetry}>{text('重试档案', 'Retry dossiers')}</Button></p>}
    {candidateError && <p role="alert" className="library-notice">{text('候选线索暂时无法读取。', 'Candidate signals could not be loaded.')} <Button variant="ghost" onClick={onRetryCandidates}>{text('重试线索', 'Retry signals')}</Button></p>}
    {!loading && !candidatesLoading && !error && !candidateError && !groups.length && <p className="library-empty">{text('还没有可展示的事件或线索。新的记录会按日期在这里展开。', 'No events or signals yet. New records will appear here by date.')}</p>}
    {selected && current && <>
      <div className="event-date-axis" ref={dateAxis} aria-label={text('按日期浏览，UTC', 'Browse dates, UTC')}>
        {groups.map(group => <button type="button" key={group.day} aria-pressed={current.day === group.day} onClick={() => { setDay(group.day); setSelectedId('') }}><span>{group.day === 'unknown' ? text('日期待确认', 'Undated') : group.day.slice(0, 4)}</span><strong>{group.day === 'unknown' ? '—' : group.day.slice(5).replace('-', ' / ')}</strong><i aria-hidden="true"/><span>{text(`${group.items.length} 条记录`, `${group.items.length} records`)}</span></button>)}
      </div>
      <div className="event-reveal" key={selected.id}>
        <DevelopingField variant="events" className="event-diffusion"/>
        <div className="event-date-caption"><span>{basis(selected.basis)}</span><time dateTime={selected.timestamp ?? undefined}>{current.day === 'unknown' ? '—' : current.day}</time><span>{text('日期按 UTC 归组', 'Dates grouped in UTC')}</span></div>
        <article className="event-reveal-copy"><div className="library-eyebrow">{selected.incident ? text('已建立事件档案', 'Retained event dossier') : text('候选线索 · 尚待确认', 'Candidate signal · unconfirmed')}</div><h3>{selected.title}</h3>{selected.summary && <p>{selected.summary}</p>}<p className="event-provenance">{selected.incident ? text(`${selected.incident.source_diversity_count} 个独立来源 · ${selected.incident.timeline_event_count} 条演化记录`, `${selected.incident.source_diversity_count} independent sources · ${selected.incident.timeline_event_count} timeline records`) : selected.candidate?.source_name ?? selected.candidate?.source_id}</p><Button variant="outline" onClick={() => selected.incident ? onIncident(selected.incident.incident_id) : selected.candidate && onCandidate(selected.candidate)}>{selected.incident ? text('阅读事件档案', 'Read event dossier') : text('核对线索与来源', 'Inspect signal and sources')}</Button></article>
      </div>
      {current.items.length > 1 && <nav className="event-within-day" aria-label={text('当天记录', 'Records on this date')}><span>{text('当天记录', 'On this date')}</span>{current.items.map((item, index) => <button key={item.id} aria-label={`${index + 1}. ${item.title}`} aria-pressed={item.id === selected.id} onClick={() => setSelectedId(item.id)}>{String(index + 1).padStart(2, '0')}</button>)}</nav>}
      {selected.incident && <section className="event-history" aria-label={text('事件演化', 'Event evolution')}><h3>{text('事件演化', 'Event evolution')}</h3>{detail.isPending && <p role="status">{text('读取演化记录…', 'Loading event history…')}</p>}{detail.isError && <p role="alert">{text('演化记录暂时无法读取。', 'History could not be loaded.')}<Button variant="ghost" onClick={() => void detail.refetch()}>{text('重试', 'Retry')}</Button></p>}{!detail.isPending && !detail.isError && !history.length && <p>{text('这份档案尚无演化记录。', 'This dossier has no timeline records yet.')}</p>}{historyEvent && <><div className="event-history-axis">{history.map((event, index) => <button key={event.event_id} aria-pressed={event.event_id === historyEvent.event_id} onClick={() => setHistoryId(event.event_id)}><span>{String(index + 1).padStart(2, '0')}</span><time>{dateLabel(validLibraryTime(event.event_time) ?? event.observed_at, language)}</time></button>)}</div><article className="event-history-copy" key={historyEvent.event_id}><p>{historyEvent.summary}</p><span>{validLibraryTime(historyEvent.event_time) ? (historyEvent.time_basis === 'reported_date' ? text('来源记载日期', 'Date reported by source') : historyEvent.time_basis === 'published' ? text('来源发布', 'Source published') : historyEvent.time_basis === 'observed' ? text('资料入库', 'Retained') : text('来源时间', 'Source time')) : text('事件时间缺失；系统发现', 'Event time missing; observed')} · {dateLabel(validLibraryTime(historyEvent.event_time) ?? historyEvent.observed_at, language)}</span><span>{text('系统发现', 'System observed')} · {dateLabel(historyEvent.observed_at, language)}</span></article></>}</section>}
      <p className="library-scope">{text(`当前载入 ${incidents.length} 份事件档案、${candidates.length} 条候选线索。`, `${incidents.length} loaded dossiers · ${candidates.length} candidate signals.`)}</p>
    </>}
  </section>
}
