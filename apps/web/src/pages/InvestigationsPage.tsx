import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import {
  Activity,
  BadgeCheck,
  CircleAlert,
  CircleDot,
  FileWarning,
  Link2,
  MessageSquareText,
  Orbit,
  Radar,
  SearchCheck,
  Sparkles,
  TerminalSquare,
} from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import {
  getEvidence,
  getInvestigation,
  getInvestigationActivity,
  listInvestigations,
  type EvidenceDetail,
  type InvestigationFinding,
  type InvestigationView,
  type ProductRuntimeEvent,
} from '../lib/api'

const liveStatuses = new Set(['active', 'waiting'])

export function InvestigationsPage() {
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const listQuery = useQuery({ queryKey: ['investigations'], queryFn: () => listInvestigations(48), refetchInterval: 20_000 })
  const preferredCase = params.get('case')
  const fallbackCase = listQuery.data?.items.find((item) => liveStatuses.has(item.status))?.case_id ?? listQuery.data?.items[0]?.case_id ?? null
  const selectedCase = preferredCase ?? fallbackCase
  const detailQuery = useQuery({ queryKey: ['investigation', selectedCase], queryFn: () => getInvestigation(selectedCase!), enabled: Boolean(selectedCase), refetchInterval: selectedCase ? 15_000 : false })
  const activityQuery = useQuery({ queryKey: ['investigation-activity', selectedCase], queryFn: () => getInvestigationActivity(selectedCase!), enabled: Boolean(selectedCase) })
  const [events, setEvents] = useState<ProductRuntimeEvent[]>([])
  const [streamState, setStreamState] = useState<'idle' | 'connecting' | 'live' | 'retrying'>('idle')
  const [selectedEvidence, setSelectedEvidence] = useState<string | null>(null)
  const eventIds = useRef(new Set<string>())

  useEffect(() => {
    const initial = activityQuery.data?.events ?? []
    eventIds.current = new Set(initial.map((item) => item.event_id))
    setEvents(initial)
  }, [activityQuery.data, selectedCase])

  useEffect(() => {
    if (!selectedCase) {
      setStreamState('idle')
      return
    }
    setStreamState('connecting')
    const source = new EventSource(`/api/v1/investigations/${encodeURIComponent(selectedCase)}/events`)
    source.onopen = () => setStreamState('live')
    const eventNames = ['started', 'status_changed', 'progress', 'finding_added', 'finding_changed', 'conflict_changed', 'unknown_changed', 'evidence_need_changed', 'decision_ready', 'waiting', 'completed', 'failed', 'canceled']
    const onEvent = (message: MessageEvent<string>) => {
      try {
        const item = JSON.parse(message.data) as ProductRuntimeEvent
        if (!eventIds.current.has(item.event_id)) {
          eventIds.current.add(item.event_id)
          setEvents((current) => [...current, item].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)))
        }
        void queryClient.invalidateQueries({ queryKey: ['investigation', selectedCase] })
        void queryClient.invalidateQueries({ queryKey: ['investigations'] })
      } catch {
        // Keep the stream alive if one ProductEvent cannot be decoded.
      }
    }
    eventNames.forEach((name) => source.addEventListener(name, onEvent as EventListener))
    source.onerror = () => setStreamState('retrying')
    return () => {
      eventNames.forEach((name) => source.removeEventListener(name, onEvent as EventListener))
      source.close()
    }
  }, [queryClient, selectedCase])

  const selected = detailQuery.data
  const cases = listQuery.data?.items ?? []
  const liveCount = cases.filter((item) => liveStatuses.has(item.status)).length

  function selectCase(caseId: string) {
    setSelectedEvidence(null)
    setParams({ case: caseId })
  }

  return (
    <section className="page investigations-page">
      <div className="page-heading investigation-heading">
        <div>
          <p className="eyebrow">DURABLE CASE · PRODUCT EVENT · EVIDENCE GAP · DECISION</p>
          <h1>INVESTIGATIONS</h1>
          <p className="lede">持续调查不是一串聊天记录。Case State、EvidenceNeed、Task Runtime 与 Decision 在同一个 durable workspace 里演化。</p>
        </div>
        <div className="investigation-stats">
          <span><CircleDot size={12} /> LIVE <strong>{liveCount}</strong></span>
          <span>CASES <strong>{cases.length}</strong></span>
          <span className={`stream-state stream-${streamState}`}><RadioState state={streamState} /> {streamState.toUpperCase()}</span>
        </div>
      </div>

      <div className="investigation-layout">
        <aside className="case-rail panel-glass">
          <div className="case-rail-head"><SearchCheck size={15} /><strong>CASE FILES</strong><span>{cases.length}</span></div>
          <div className="case-list">
            {cases.map((item) => (
              <button key={item.case_id} className={`case-card ${item.case_id === selectedCase ? 'selected' : ''} case-${item.status}`} onClick={() => selectCase(item.case_id)}>
                <span className="case-status-dot" />
                <span className="case-card-copy"><small>{item.execution_profile ?? item.current_activity.task_kind ?? 'INVESTIGATION'}</small><strong>{item.goal}</strong><em>{item.current_activity.actor_role ?? 'runtime'} · {item.current_activity.phase}</em></span>
                <span className="case-card-tail"><b>{item.status}</b><small>r{item.revision}</small></span>
              </button>
            ))}
            {listQuery.isLoading && <div className="case-list-empty">Loading durable cases…</div>}
            {!listQuery.isLoading && cases.length === 0 && <div className="case-list-empty">No investigations yet. Launch VERIFY / INVESTIGATE / WATCH from START.</div>}
          </div>
        </aside>

        <main className="case-workspace">
          {selected ? <CaseWorkspace investigation={selected} events={events} onEvidence={setSelectedEvidence} /> : <div className="case-empty panel-glass"><Orbit size={46} /><strong>Select a durable case</strong><p>启动 VERIFY / INVESTIGATE / WATCH 后，调查会在这里持续演化。</p></div>}
        </main>

        <aside className="activity-rail panel-glass">
          <div className="activity-head"><div><small>PRODUCT EVENT STREAM</small><strong>LIVE ACTIVITY</strong></div><span className={`stream-beacon stream-${streamState}`} /></div>
          <RuntimeEventRail events={events} />
        </aside>
      </div>

      <AnimatePresence>{selectedEvidence && <EvidenceOverlay evidenceRef={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}</AnimatePresence>
    </section>
  )
}

function CaseWorkspace({ investigation, events, onEvidence }: { investigation: InvestigationView; events: ProductRuntimeEvent[]; onEvidence: (ref: string) => void }) {
  return (
    <div className="case-workspace-stack">
      <article className="case-hero panel-glass">
        <div className="case-hero-main">
          <span className="case-hero-sigil"><Radar size={25} /></span>
          <div><small>CASE / {investigation.execution_profile ?? 'RUNTIME'}</small><strong>{investigation.goal}</strong><span className="mono">{investigation.case_id}</span></div>
        </div>
        <div className="case-hero-state"><span className={`case-state-badge state-${investigation.status}`}>{investigation.status}</span><strong>REV {investigation.revision}</strong><small>{investigation.current_activity.actor_role ?? 'runtime'} · {investigation.current_activity.phase}</small></div>
      </article>

      <div className="case-state-grid">
        <StateColumn title="CONFIRMED" tone="lime" icon={BadgeCheck} items={investigation.confirmed_findings} onEvidence={onEvidence} />
        <StateColumn title="CONFLICTS" tone="amber" icon={CircleAlert} items={investigation.conflicts} onEvidence={onEvidence} />
        <StateColumn title="UNKNOWNS" tone="violet" icon={FileWarning} items={investigation.unknowns} onEvidence={onEvidence} />
        <EvidenceNeeds investigation={investigation} />
      </div>

      <DecisionPanel investigation={investigation} onEvidence={onEvidence} />

      <section className="conversation-shell panel-glass">
        <div className="conversation-title"><MessageSquareText size={15} /><div><small>CONTINUOUS INTERACTION</small><strong>CASE SESSION</strong></div><span>session seam next</span></div>
        <div className="conversation-preview">
          <div className="system-message"><Sparkles size={14} /><p>{latestNarrative(events, investigation)}</p></div>
          <div className="composer-disabled"><input disabled placeholder="持续追问会复用当前 Case；session binding 正在接入…" /><button disabled>SEND</button></div>
        </div>
      </section>
    </div>
  )
}

function StateColumn({ title, tone, icon: Icon, items, onEvidence }: { title: string; tone: string; icon: typeof BadgeCheck; items: InvestigationFinding[]; onEvidence: (ref: string) => void }) {
  return (
    <section className={`state-column panel-glass tone-${tone}`}>
      <div className="state-column-head"><Icon size={14} /><strong>{title}</strong><span>{items.length}</span></div>
      <div className="state-items">
        {items.slice(0, 8).map((item, index) => (
          <motion.article key={`${item.proposition}:${index}`} className="state-item" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            <strong>{item.proposition}</strong>
            <small>revision {item.updated_revision}</small>
            <EvidenceButtons refs={item.evidence_refs} onEvidence={onEvidence} />
          </motion.article>
        ))}
        {items.length === 0 && <div className="state-empty">No current items.</div>}
      </div>
    </section>
  )
}

function EvidenceNeeds({ investigation }: { investigation: InvestigationView }) {
  return (
    <section className="state-column panel-glass tone-cyan">
      <div className="state-column-head"><SearchCheck size={14} /><strong>EVIDENCE NEEDS</strong><span>{investigation.open_evidence_needs.length}</span></div>
      <div className="state-items">
        {investigation.open_evidence_needs.slice(0, 8).map((need) => (
          <article key={need.need_id} className="state-item evidence-need-item">
            <strong>{need.question}</strong><small>{need.purpose} · priority {need.priority}</small>
            <div className="need-roles">{need.required_source_roles.map((role) => <span key={role}>{role}</span>)}</div>
          </article>
        ))}
        {investigation.open_evidence_needs.length === 0 && <div className="state-empty">No open evidence gaps.</div>}
      </div>
    </section>
  )
}

function DecisionPanel({ investigation, onEvidence }: { investigation: InvestigationView; onEvidence: (ref: string) => void }) {
  const decision = investigation.latest_decision
  return (
    <section className={`decision-panel panel-glass ${decision ? 'ready' : ''}`}>
      <div className="decision-oracle"><div className="oracle-mini"><div /><div /><Sparkles size={19} /></div><div><small>ORACLE / DECISION</small><strong>{decision ? 'DECISION READY' : 'WAITING FOR EVIDENCE'}</strong></div></div>
      {decision ? (
        <div className="decision-content">
          {decision.conclusions.map((item, index) => (
            <div key={`${index}:${item.statement}`} className="decision-conclusion"><span>{String(index + 1).padStart(2, '0')}</span><div><small>{item.type}</small><strong>{item.statement}</strong><EvidenceButtons refs={item.evidence_refs} onEvidence={onEvidence} /></div></div>
          ))}
          {(decision.conflicts.length > 0 || decision.unknowns.length > 0) && <div className="decision-boundary"><span>{decision.conflicts.length} conflicts</span><span>{decision.unknowns.length} unknowns</span><span>{decision.stop_reason}</span></div>}
        </div>
      ) : <p className="decision-waiting">ARGUS 仍在围绕 EvidenceNeed 工作。Decision 只有在证据边界满足时才会收束。</p>}
    </section>
  )
}

function RuntimeEventRail({ events }: { events: ProductRuntimeEvent[] }) {
  const visible = events.slice(-32).reverse()
  return <div className="runtime-event-list">{visible.map((event, index) => <motion.article key={event.event_id} className={`runtime-event event-${event.event_type}`} initial={{ opacity: 0, x: 18, scale: .98 }} animate={{ opacity: 1, x: 0, scale: 1 }} transition={{ delay: Math.min(index * .015, .18) }}><span className="event-symbol"><EventIcon type={event.event_type} /></span><div><small>{event.role_id ?? event.actor ?? event.source_kind}</small><strong>{event.summary}</strong><em>{event.technical_type} · {new Date(event.occurred_at).toLocaleTimeString()}</em>{event.evidence_refs.length > 0 && <span className="event-evidence">{event.evidence_refs.length} evidence refs</span>}</div></motion.article>)}</div>
}

function EvidenceButtons({ refs, onEvidence }: { refs: string[]; onEvidence: (ref: string) => void }) {
  if (!refs.length) return null
  return <div className="finding-evidence">{refs.slice(0, 3).map((ref) => <button key={ref} onClick={() => onEvidence(ref)}><Link2 size={10} /> EVIDENCE</button>)}{refs.length > 3 && <span>+{refs.length - 3}</span>}</div>
}

function EvidenceOverlay({ evidenceRef, onClose }: { evidenceRef: string; onClose: () => void }) {
  const query = useQuery({ queryKey: ['evidence-overlay', evidenceRef], queryFn: () => getEvidence(evidenceRef) })
  const item = query.data
  return <motion.div className="evidence-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}><motion.div className="evidence-overlay-card panel-glass" initial={{ x: 40, scale: .98 }} animate={{ x: 0, scale: 1 }} exit={{ x: 40, scale: .98 }} onClick={(event) => event.stopPropagation()}><div className="overlay-head"><div><small>EVIDENCE TRACE</small><strong>{item?.source.source_id ?? 'Resolving…'}</strong></div><button onClick={onClose}>CLOSE</button></div>{item ? <EvidenceTrace item={item} /> : <div className="inspector-empty"><Orbit size={30} />{query.isError ? String(query.error.message) : 'resolving evidence…'}</div>}</motion.div></motion.div>
}

function EvidenceTrace({ item }: { item: EvidenceDetail }) {
  return <div className="overlay-body"><div className="trace-hero"><BadgeCheck size={22} /><div><small>{item.source.source_role} / {item.source.source_class}</small><strong>{item.target.target_kind} · {item.target.label}</strong><span>{item.observation.external_object_id}</span></div></div><TraceRow label="SOURCE REVISION" value={item.observation.external_revision ?? 'content-addressed'} /><TraceRow label="LOCATOR" value={Object.entries(item.locator).map(([key, value]) => `${key}=${String(value)}`).join(' · ') || 'root'} /><TraceRow label="OBSERVED" value={new Date(item.observation.observed_at).toLocaleString()} /><TraceRow label="TRUST" value={item.artifact?.trust_class ?? 'observation-bound'} /><div className="mono overlay-ref">{item.evidence_ref}</div></div>
}

function TraceRow({ label, value }: { label: string; value: string }) { return <div className="trace-row"><small>{label}</small><strong>{value}</strong></div> }
function EventIcon({ type }: { type: string }) { if (type === 'failed') return <CircleAlert size={13} />; if (type === 'decision_ready') return <Sparkles size={13} />; if (type === 'finding_added') return <BadgeCheck size={13} />; if (type === 'evidence_need_changed') return <SearchCheck size={13} />; if (type === 'waiting') return <Orbit size={13} />; return <TerminalSquare size={13} /> }
function RadioState({ state }: { state: string }) { return state === 'live' ? <CircleDot size={11} /> : <Activity size={11} /> }
function latestNarrative(events: ProductRuntimeEvent[], investigation: InvestigationView) { const latest = events[events.length - 1]; return latest?.summary ?? `${investigation.current_activity.actor_role ?? 'Runtime'} is ${investigation.current_activity.phase}.` }
