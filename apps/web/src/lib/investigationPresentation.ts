import type { InvestigationFinding, InvestigationView, ProductRuntimeEvent } from './api'
import { rolePresentation } from './agentRuntimePresentation'

type Translate = (zh: string, en: string) => string

export function runtimeActorLabel(roleId: string | null | undefined, text: Translate) {
  const role = roleId ? rolePresentation[roleId] : null
  return role ? text(role.cn, role.alias) : text('系统', 'Runtime')
}

export function runtimeTaskLabel(kind: string, text: Translate) {
  const labels: Record<string, [string, string]> = {
    lookup: ['事实查询', 'Fact lookup'], retrieve: ['证据检索', 'Evidence retrieval'],
    verify_version_fix: ['修复版本核验', 'Fix verification'], resolve_conflict: ['来源冲突核验', 'Conflict resolution'],
    investigate_relation: ['关联调查', 'Relation investigation'], investigate_incident: ['事件调查', 'Incident investigation'],
    watch_incident: ['事件守望', 'Incident watch'], research_insight: ['研究材料分析', 'Research analysis'],
    assess_normative_applicability: ['标准适用性分析', 'Standard applicability'], observe_live_asset: ['在线资产观测', 'Live asset observation'],
    enrichment: ['证据富化', 'Evidence enrichment'],
  }
  return labels[kind] ? text(...labels[kind]) : kind.replaceAll('_', ' ')
}

export function runtimeEventSummary(event: ProductRuntimeEvent, text: Translate) {
  if (event.source_kind === 'case_state') {
    const caseFallbacks: Record<string, [string, string]> = {
      'Finding confirmed': ['确认了一项事实。', 'Finding confirmed.'],
      'Confirmed finding retracted': ['撤回了一项已确认事实。', 'Confirmed finding retracted.'],
      'Tentative finding added': ['记录了一项待核验发现。', 'Tentative finding added.'],
      'Tentative finding removed': ['移除了一项待核验发现。', 'Tentative finding removed.'],
      'Evidence conflict opened': ['记录了证据冲突。', 'Evidence conflict opened.'],
      'Evidence conflict resolved': ['证据冲突已解决。', 'Evidence conflict resolved.'],
      'Unknown recorded': ['记录了未决问题。', 'Unknown recorded.'],
      'Unknown resolved': ['一项未决问题已解决。', 'Unknown resolved.'],
      'Hypothesis added': ['提出了待核验假设。', 'Hypothesis added.'],
      'Hypothesis rejected': ['排除了一项假设。', 'Hypothesis rejected.'],
      'New evidence need opened': ['记录了新的证据需求。', 'New evidence need opened.'],
      'Evidence need resolved': ['一项证据需求已满足。', 'Evidence need resolved.'],
      'Evidence attached': ['将证据加入调查。', 'Evidence attached.'],
      'Decision became available': ['已形成带引用的研判。', 'A cited decision is available.'],
      'Perception recorded': ['记录了新的观察。', 'Perception recorded.'],
    }
    return caseFallbacks[event.summary] ? text(...caseFallbacks[event.summary]) : event.summary
  }
  if (event.source_kind !== 'task') return event.summary
  const actions: Record<string, [string, string]> = {
    TaskCreated: ['已接收任务', 'accepted a task'], TaskStarted: ['开始执行', 'started work'],
    TaskPatched: ['更新执行状态', 'updated the task'], ContextUpdated: ['更新调查上下文', 'updated context'],
    EvidenceFound: ['取得新的证据', 'found evidence'], KnowledgeChanged: ['更新情报知识', 'updated knowledge'],
    EnrichmentStateChanged: ['更新富化状态', 'updated enrichment'], InvestigationStateChanged: ['更新调查状态', 'updated investigation'],
    TaskBlocked: ['执行受到阻碍', 'was blocked'], NeedInput: ['等待补充信息', 'needs input'],
    NeedContext: ['等待依赖结果', 'needs a dependency'], BudgetWarning: ['执行额度接近上限', 'approached its budget'],
    ArtifactProduced: ['产出运行材料', 'produced an artifact'], Progress: ['报告新进展', 'reported progress'],
    TaskCompleted: ['完成本轮执行', 'completed this run'], TaskFailed: ['本轮执行失败', 'failed this run'],
    TaskCanceled: ['本轮执行已取消', 'canceled this run'],
  }
  const action = actions[event.technical_type]
  return action ? text(`${runtimeActorLabel(event.role_id, text)}${action[0]}。`, `${runtimeActorLabel(event.role_id, text)} ${action[1]}.`) : event.summary
}

export type CaseStateFocus = 'confirmed' | 'conflicts' | 'unknowns' | 'needs' | 'decision'
export type EventCue = { eventId: string; state: CaseStateFocus }

export function displayUnknowns(investigation: InvestigationView): InvestigationFinding[] {
  const unknowns = [...investigation.unknowns]
  const seen = new Set(unknowns.map(item => item.proposition.trim()))
  for (const proposition of investigation.latest_decision?.unknowns ?? []) {
    const normalized = proposition.trim()
    if (!normalized || seen.has(normalized)) continue
    unknowns.push({ proposition: normalized, target_ref: null, evidence_refs: [], updated_revision: investigation.revision })
    seen.add(normalized)
  }
  return unknowns
}

export function investigationStopMessage(reason: string, text: (zh: string, en: string) => string) {
  const messages: Record<string, [string, string]> = {
    no_progress: ['重复读取未带来新进展，本轮已停止。可补充线索后继续调查。', 'Repeated reads yielded no progress. Add a lead to continue the investigation.'],
    budget_exhausted: ['本轮执行额度已用完，尚未完成调查。', 'This episode exhausted its execution budget before completing the investigation.'],
    deadline_reached: ['本轮运行已达到时间上限，调查尚未完成。', 'This episode reached its time limit before completing the investigation.'],
    waiting_not_allowed: ['本轮需要等待额外信息，当前执行设置不允许继续等待。', 'This episode needs additional information, but its execution settings do not allow waiting.'],
  }
  const message = messages[reason]
  return message ? text(...message) : text('本轮运行已停止，请查看执行记录了解原因。', 'This episode stopped. Open the execution record for details.')
}

export function eventState(eventType: string): CaseStateFocus | null {
  if (eventType === 'finding_added' || eventType === 'finding_changed') return 'confirmed'
  if (eventType === 'conflict_changed') return 'conflicts'
  if (eventType === 'unknown_changed') return 'unknowns'
  if (eventType === 'evidence_need_changed') return 'needs'
  if (eventType === 'decision_ready' || eventType === 'completed') return 'decision'
  return null
}


export function mergeRuntimeEvents(initial: ProductRuntimeEvent[], streamed: ProductRuntimeEvent[]) {
  const byId = new Map<string, ProductRuntimeEvent>()
  for (const event of initial) byId.set(event.event_id, event)
  for (const event of streamed) byId.set(event.event_id, event)
  return [...byId.values()].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at))
}
