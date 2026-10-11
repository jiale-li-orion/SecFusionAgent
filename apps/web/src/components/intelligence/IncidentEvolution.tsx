import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Clock3, GitBranch, Link2, Radio } from 'lucide-react'
import type { IncidentDetail, IncidentTimelineEvent } from '../../lib/api'
import { useI18n } from '../../lib/i18n'

type Clock = 'observed_at' | 'event_time'
function validTime(value: string) { return Number.isFinite(Date.parse(value)) }
function timestamp(value: string) { return validTime(value) ? new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—' }
function eventLabel(value: string) { return value.replaceAll('_', ' ').replaceAll('-', ' ') }
function nodePosition(index: number, total: number) {
  const angle = -Math.PI / 2 + index / Math.max(total, 1) * Math.PI * 2
  return { x: 420 + Math.cos(angle) * 240, y: 230 + Math.sin(angle) * 155, angle }
}

export function IncidentEvolution({ incident, onEvidence }: { incident: IncidentDetail; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const [clock, setClock] = useState<Clock>('observed_at')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const timeline = useMemo(() => incident.timeline.filter(event => validTime(event[clock])).sort((a, b) => Date.parse(a[clock]) - Date.parse(b[clock]) || a.event_id.localeCompare(b.event_id)), [incident.timeline, clock])
  const selectedIndex = Math.max(0, selectedId ? timeline.findIndex(event => event.event_id === selectedId) : timeline.length - 1)
  const current = timeline[selectedIndex]
  const visibleEvents = new Set(timeline.slice(0, selectedIndex + 1).map(event => event.event_id))
  // Positions come from the complete retained event set, never the scrubber's visible slice.
  const graphEvents = useMemo(() => [...incident.timeline].sort((a, b) => a.created_revision - b.created_revision || a.event_id.localeCompare(b.event_id)).slice(0, 16), [incident.timeline])
  const currentRefs = new Set(timeline.slice(0, selectedIndex + 1).flatMap(event => event.evidence_refs))
  const currentClaims = new Set(timeline.slice(0, selectedIndex + 1).flatMap(event => event.claim_refs))
  function select(index: number) { setSelectedId(timeline[index]?.event_id ?? null) }
  return <section className="intel-evolution" aria-label={text('事件演化', 'Event evolution')}>
    <header className="intel-evolution-header"><div><span><GitBranch size={15}/>{text('事件演化', 'Event evolution')}</span><h2>{text('线索如何汇成事件', 'How signals form an event')}</h2><p>{text('沿真实记录回看，每一次新增的事实与证据。', 'Revisit the retained record, one fact and source at a time.')}</p></div><div className="intel-clock-switch" aria-label={text('时间视角', 'Time perspective')}><button aria-pressed={clock === 'observed_at'} className={clock === 'observed_at' ? 'active' : ''} onClick={() => { setClock('observed_at'); setSelectedId(null) }}>{text('系统发现', 'System discovery')}</button><button aria-pressed={clock === 'event_time'} className={clock === 'event_time' ? 'active' : ''} onClick={() => { setClock('event_time'); setSelectedId(null) }}>{text('来源事件', 'Source events')}</button></div></header>
    {!timeline.length ? <div className="intel-feed-empty"><Clock3 size={28}/><h3>{text('尚无可回放的历史记录', 'No recorded history to replay')}</h3><p>{text('这份事件档案尚未提供有效时间记录。下方仍可查看已保留的来源。', 'This dossier has no valid timestamped records yet. Its retained sources are available below.')}</p></div> : <>
      <div className="intel-evolution-body">
        <div className="intel-evolution-timeline" aria-label={text('历史记录', 'Historical records')}>{timeline.map((event, index) => <button key={event.event_id} className={`${index === selectedIndex ? 'active' : ''} ${index > selectedIndex ? 'future' : ''}`} aria-current={index === selectedIndex ? 'step' : undefined} onClick={() => select(index)}><span className="intel-timeline-dot"/><time dateTime={event[clock]}>{timestamp(event[clock])}</time><strong>{eventLabel(event.event_type)}</strong><p>{event.summary}</p><small>{text(`${event.evidence_refs.length} 份证据`, `${event.evidence_refs.length} evidence refs`)}</small></button>)}</div>
        <div className="intel-growth-stage"><div className="intel-growth-caption"><span><Radio size={13}/>{text('已留存的事件关联', 'Retained event relationships')}</span><time dateTime={current?.[clock]}>{current && timestamp(current[clock])}</time></div>
          <svg viewBox="0 0 840 460" role="img" aria-label={text('事件与证据的生长关系图；可在左侧选择记录，或拖动下方时间轴。', 'Event and evidence growth map. Select records in the timeline or use the slider below.')}>
            <defs><radialGradient id="intel-event-glow"><stop offset="0%" stopColor="#4263eb" stopOpacity=".22"/><stop offset="100%" stopColor="#4263eb" stopOpacity="0"/></radialGradient></defs>
            <circle cx="420" cy="230" r="195" fill="url(#intel-event-glow)"/><ellipse cx="420" cy="230" rx="240" ry="155" className="intel-graph-orbit"/><ellipse cx="420" cy="230" rx="340" ry="205" className="intel-graph-orbit"/>
            {graphEvents.map((event, index) => {
              const pos = nodePosition(index, graphEvents.length)
              const visible = visibleEvents.has(event.event_id)
              const refs = [...new Set(event.evidence_refs)].slice(0, 3)
              return <g key={event.event_id} className={`intel-growth-branch ${visible ? 'is-visible' : ''} ${current?.event_id === event.event_id ? 'is-selected' : ''}`}>
                <path d={`M420,230 Q${420 + (pos.x - 420) * .65},230 ${pos.x},${pos.y}`} className="intel-growth-edge"/>
                {refs.map((ref, refIndex) => {
                  const angle = pos.angle + (refIndex - (refs.length - 1) / 2) * .12
                  const x = 420 + Math.cos(angle) * 336
                  const y = 230 + Math.sin(angle) * 204
                  return <g key={ref}><line x1={pos.x} y1={pos.y} x2={x} y2={y} className="intel-evidence-edge"/><circle cx={x} cy={y} r="5" className="intel-evidence-node"/><title>{ref}</title></g>
                })}
                <circle cx={pos.x} cy={pos.y} r={current?.event_id === event.event_id ? 15 : 10} className="intel-event-node"/><text x={pos.x} y={pos.y + 30} textAnchor="middle">{text('记录', 'Record')} {incident.timeline.findIndex(item => item.event_id === event.event_id) + 1}</text><title>{event.summary}</title>
              </g>
            })}
            <circle cx="420" cy="230" r="57" className="intel-graph-core"/><text x="420" y="225" textAnchor="middle" className="intel-core-title">{text('事件档案', 'EVENT')}</text><text x="420" y="247" textAnchor="middle" className="intel-core-count">{visibleEvents.size} {text('条记录', 'records')}</text>
          </svg>
          <div className="intel-growth-legend"><span><i/>{text('事件记录', 'Event record')}</span><span><i/>{text('来源证据', 'Source evidence')}</span><span>{text(`${currentRefs.size} 份证据 · ${currentClaims.size} 条事实引用`, `${currentRefs.size} evidence refs · ${currentClaims.size} claim refs`)}</span></div>
          {graphEvents.length < incident.timeline.length && <p className="intel-graph-limit">{text('关系图显示最早 16 条记录；完整历史可在左侧浏览。', 'The map displays the earliest 16 records. Browse the full history in the timeline.')}</p>}
        </div>
      </div>
      <div className="intel-evolution-controls"><button aria-label={text('上一条记录', 'Previous record')} disabled={selectedIndex === 0} onClick={() => select(selectedIndex - 1)}><ArrowLeft size={17}/></button><div><label htmlFor={`incident-time-${incident.incident.incident_id}`}>{text('拖动时间轴，回看证据关联', 'Scrub the timeline to explore evidence connections')}<span>{selectedIndex + 1} / {timeline.length}</span></label><input id={`incident-time-${incident.incident.incident_id}`} type="range" min={0} max={Math.max(0, timeline.length - 1)} value={selectedIndex} disabled={timeline.length < 2} onChange={event => select(Number(event.target.value))} aria-valuetext={current ? `${timestamp(current[clock])} ${current.summary}` : undefined}/></div><button aria-label={text('下一条记录', 'Next record')} disabled={selectedIndex >= timeline.length - 1} onClick={() => select(selectedIndex + 1)}><ArrowRight size={17}/></button></div>
      {current && <EventRecord event={current} onEvidence={onEvidence}/>}
    </>}
    <p className="intel-evolution-note">{clock === 'observed_at' ? text('按系统实际发现时间排列；图中的关联来自记录携带的证据引用。', 'Ordered by actual system discovery time. Connections come from evidence references retained on each record.') : text('按来源记录的事件时间排列，不代表系统在该时刻已经发现；来源发布时间仅在证据中单独展示。', 'Ordered by the source event time, not when the system discovered it. Source publication timestamps remain separate in the evidence.')}{incident.timeline.length > timeline.length && ` ${text(`${incident.timeline.length - timeline.length} 条记录缺少有效时间，未进入回放。`, `${incident.timeline.length - timeline.length} records have no valid timestamp and are excluded from playback.`)}`}</p>
  </section>
}
function EventRecord({ event, onEvidence }: { event: IncidentTimelineEvent; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  return <article className="intel-selected-record"><div><span>{eventLabel(event.event_type)}</span><strong>{event.summary}</strong></div><dl><div><dt>{text('来源事件时间', 'Source event time')}</dt><dd>{timestamp(event.event_time)}</dd></div><div><dt>{text('系统发现时间', 'System discovery')}</dt><dd>{timestamp(event.observed_at)}</dd></div></dl><div className="intel-source-chips">{event.evidence_refs.map((ref, index) => ref.startsWith('evidence:') ? <button key={ref} onClick={() => onEvidence(ref)}><Link2 size={13}/>{text(`证据 ${index + 1}`, `Evidence ${index + 1}`)}<ArrowRight size={12}/></button> : <span key={ref} title={ref}>{ref.split(':')[0]}</span>)}</div>{event.supersedes_event_id && <p>{text('这条记录修订了先前的事件记录。', 'This record supersedes an earlier event record.')}</p>}</article>
}
