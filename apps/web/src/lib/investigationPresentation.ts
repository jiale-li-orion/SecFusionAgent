import type { ProductRuntimeEvent } from './api'

export type CaseStateFocus = 'confirmed' | 'conflicts' | 'unknowns' | 'needs' | 'decision'
export type EventCue = { eventId: string; state: CaseStateFocus }

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
