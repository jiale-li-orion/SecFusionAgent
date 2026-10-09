import type { InvestigationFinding, InvestigationView, ProductRuntimeEvent } from './api'

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
