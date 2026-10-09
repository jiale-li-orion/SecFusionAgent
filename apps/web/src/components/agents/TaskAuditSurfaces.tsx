import { ArrowUpRight, BrainCircuit, Braces, Link2, Waypoints } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { AgentTaskDetail } from '../../lib/api/agents'
import { useI18n } from '../../lib/i18n'
import { ProductGlyph } from '../instrument/ProductGlyph'

type TaskContext = AgentTaskDetail['context']
type ModelAttempt = AgentTaskDetail['model_attempts'][number]

export function TaskContextLedger({ context }: { context: TaskContext }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  return <>
    <div className="task-events-title"><Waypoints size={14} /><strong>{text('上下文与输入证据', 'CONTEXT & INPUT EVIDENCE')}</strong><span>{context?.evidence_refs.length ?? 0}</span></div>
    {context ? <section className="task-context-ledger">
      <div className="task-context-head"><small>CONTEXT · REV {context.context_revision}</small><strong className="mono">{context.context_id}</strong><span>{text('知识版本', 'Knowledge revision')} {context.knowledge_revision ?? '—'} · {context.role_ref}</span></div>
      <div className="task-context-metrics"><span><b>{context.evidence_refs.length}</b> {text('证据', 'evidence')}</span><span><b>{context.object_refs.length}</b> {text('对象', 'objects')}</span><span><b>{context.relation_refs.length}</b> {text('关系', 'relations')}</span><span><b>{context.retrieval_invocation_refs.length}</b> {text('检索', 'retrievals')}</span></div>
      {context.evidence_refs.length > 0 && <details><summary><Link2 size={12} />{text('打开输入证据', 'Open input evidence')}<span>{context.evidence_refs.length}</span></summary><div className="task-context-refs">{context.evidence_refs.map(ref => <button key={ref} onClick={() => navigate(`/intelligence?${new URLSearchParams({ evidence: ref })}`)}><span className="mono">{ref}</span><ArrowUpRight size={12} /></button>)}</div></details>}
      {context.object_refs.length > 0 && <details><summary><Braces size={12} />{text('打开上下文对象', 'Open context objects')}<span>{context.object_refs.length}</span></summary><div className="task-context-refs">{context.object_refs.map(ref => <button key={ref} onClick={() => navigate(`/intelligence?${new URLSearchParams({ object: ref })}`)}><span className="mono">{ref}</span><ArrowUpRight size={12} /></button>)}</div></details>}
      {context.relation_refs.length > 0 && <details><summary><Waypoints size={12} />{text('关系坐标', 'Relation coordinates')}<span>{context.relation_refs.length}</span></summary><div className="task-context-refs">{context.relation_refs.map(ref => <span className="mono" key={ref}>{ref}</span>)}</div></details>}
      {context.retrieval_invocation_refs.length > 0 && <details><summary><Waypoints size={12} />{text('检索调用坐标', 'Retrieval invocations')}<span>{context.retrieval_invocation_refs.length}</span></summary><div className="task-context-refs">{context.retrieval_invocation_refs.map(ref => <span className="mono" key={ref}>{ref}</span>)}</div></details>}
      <details className="task-context-technical"><summary>{text('策略与能力边界', 'Policy & capability boundary')}</summary><div className="task-context-refs"><span className="mono">{context.policy_context_ref}</span><span className="mono">{context.capability_envelope_ref}</span><span className="mono">{context.budget_ref}</span>{context.parent_context_id && <span className="mono">{text('父上下文', 'Parent context')} · {context.parent_context_id}</span>}</div></details>
    </section> : <div className="capability-empty">{text('当前 Task 没有可读取的 ContextManifest。', 'No ContextManifest is available for this Task.')}</div>}
  </>
}

export function TaskModelLedger({ attempts }: { attempts: ModelAttempt[] }) {
  const { text } = useI18n()
  return <>
    <div className="task-events-title"><BrainCircuit size={14} /><strong>{text('模型调用记录', 'MODEL ATTEMPTS')}</strong><span>{attempts.length}</span></div>
    {attempts.length ? <div className="task-model-ledger">{attempts.map(item => <article key={item.model_attempt_id} className={`task-model-attempt status-${item.status}`}>
      <div className="task-model-head"><ProductGlyph kind="agents" size={27} /><span><small>{text(`第 ${item.ordinal} 次调用`, `ATTEMPT ${item.ordinal}`)} · {item.purpose}</small><strong>{item.actual_model}</strong></span><b>{item.status}</b></div>
      {item.requested_model !== item.actual_model && <p>{text('请求模型', 'Requested model')} · {item.requested_model}</p>}
      <div className="task-model-usage"><span>{item.usage_source === 'provider_exact' ? text('提供方精确用量', 'Provider-reported usage') : text('提供方未返回用量', 'Provider usage unavailable')}</span><strong>{item.total_tokens == null ? '—' : `${item.total_tokens.toLocaleString()} tokens`}</strong></div>
      <div className="task-model-breakdown"><span>{item.input_tokens ?? '—'} in</span><span>{item.output_tokens ?? '—'} out</span>{item.reasoning_tokens != null && <span>{item.reasoning_tokens} reasoning</span>}<span>{item.latency_ms == null ? '—' : `${item.latency_ms} ms`}</span></div>
      <p className="task-model-settlement">{settlementLabel(item, text)}</p>
      <details><summary>{text('查看调用坐标', 'Inspect call coordinates')}</summary><div className="task-model-coordinates mono"><span>{item.model_request_id}</span><span>{item.model_attempt_id}</span><span>{item.prompt_revision}</span><time dateTime={item.started_at}>{new Date(item.started_at).toLocaleString()}</time></div></details>
    </article>)}</div> : <div className="capability-empty">{text('当前 Task 没有持久化模型调用。', 'No persisted model attempt for this Task.')}</div>}
  </>
}

function settlementLabel(item: ModelAttempt, text: (zh: string, en: string) => string) {
  if (item.budget_settlement === 'upper_bound') return `${text('预算按上界结算', 'Budget settled at upper bound')} · ${item.budget_committed_model_tokens?.toLocaleString() ?? '—'} tokens`
  if (item.budget_settlement === 'provider_exact_overrun') return text('预算按实际用量结算，超过预留估算', 'Budget settled at actual usage, above the reservation estimate')
  if (item.budget_settlement === 'provider_exact') return text('预算按提供方精确用量结算', 'Budget settled at provider-reported usage')
  if (item.budget_settlement === 'released_before_dispatch') return text('请求未发出，预算预留已释放', 'Reservation released before dispatch')
  return text('没有可读取的预算结算记录', 'No budget settlement record available')
}
