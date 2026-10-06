import { getAgentRuntime, getCompetitionProof, getHotWorld, listIncidents, listInvestigations, searchIntelligence } from './api'

export type ContextTraceSegment = { kind: string; ref: string; path?: string }

export function buildContextTrace(
  pathname: string,
  search: string,
  text: (zh: string, en: string) => string,
): ContextTraceSegment[] {
  const params = new URLSearchParams(search)
  const trace: ContextTraceSegment[] = []
  const add = (kind: string, ref: string | null | undefined, path?: string) => {
    if (!ref) return
    if (trace.some((item) => item.kind === kind && item.ref === ref)) return
    trace.push({ kind, ref, path })
  }

  const origin = params.get('from')
  const worldRef = params.get('worldRef')
  const caseRef = params.get('caseRef') ?? params.get('case')
  const runRef = params.get('run')
  const proofRun = params.get('proofRun') ?? (pathname === '/observatory' ? params.get('run') : null)
  const caseRun = params.get('caseRun')

  if (origin === 'world' || worldRef) add('WORLD', worldRef ?? text('证据世界', 'Evidence World'), '/')
  if (origin === 'start') add('START', compactTraceRef(params.get('request') ?? text('任务准入', 'Mission Admission')), '/start')
  if (origin === 'experience') {
    add('MEMORY', text('经验记忆', 'Experience Memory'), '/agents?section=memory')
    add('EXPERIENCE', compactTraceRef(params.get('experience')))
    add('TRAJECTORY', compactTraceRef(params.get('trajectory')))
  }
  if (origin === 'proof' || proofRun || caseRun) {
    add('PROOF', proofRun ?? text('冻结证明', 'Frozen Proof'), proofRun ? `/observatory?mode=proof&run=${encodeURIComponent(proofRun)}` : '/observatory?mode=proof')
    if (caseRun) add('CASE RUN', compactTraceRef(caseRun), proofRun ? `/observatory?mode=proof&run=${encodeURIComponent(proofRun)}&caseRun=${encodeURIComponent(caseRun)}` : undefined)
  }
  if (origin === 'case' || origin === 'task' || caseRef) {
    add('CASE', compactTraceRef(caseRef), caseRef ? `/investigations?case=${encodeURIComponent(caseRef)}` : undefined)
  }

  if (pathname === '/start') {
    const target = params.get('cve') ?? params.get('object') ?? params.get('origin')
    if (origin === 'intelligence' && target) add('INTELLIGENCE', compactTraceRef(target), params.get('cve') ? `/intelligence?cve=${encodeURIComponent(params.get('cve')!)}` : params.get('object') ? `/intelligence?object=${encodeURIComponent(params.get('object')!)}` : undefined)
    add('START', params.get('profile') ?? text('任务舱', 'Mission Control'))
  } else if (pathname === '/intelligence') {
    const ref = params.get('cve') ?? params.get('object') ?? params.get('incident')
    add(params.get('incident') ? 'INCIDENT' : 'INTELLIGENCE', compactTraceRef(ref ?? text('档案', 'Dossier')))
  } else if (pathname === '/investigations') {
    add('CASE', compactTraceRef(params.get('case') ?? text('调查现场', 'Investigation Field')))
    const focus = params.get('focus')
    if (focus) add('FOCUS', focus.toUpperCase())
  } else if (pathname === '/agents') {
    if (runRef) add('TASK', compactTraceRef(runRef))
    else if (params.get('role')) add('ROLE', params.get('role')!)
    else if (params.get('section') === 'memory') add('MEMORY', 'SKILL / EXPERIENCE')
  } else if (pathname === '/observatory') {
    const mode = params.get('mode') === 'proof' ? 'PROOF' : 'LIVE'
    add('OBSERVATORY', mode)
    if (proofRun) add('RUN', compactTraceRef(proofRun))
    if (caseRun) add('CASE RUN', compactTraceRef(caseRun))
  } else if (pathname === '/') {
    add('WORLD', text('证据世界', 'Evidence World'))
    if (params.get('source')) add('SOURCE', params.get('source')!.toUpperCase())
    if (params.get('lane')) add('PATH', params.get('lane')!)
  }

  return trace.slice(-5)
}

function compactTraceRef(value: string | null | undefined) {
  if (!value) return ''
  return value.length > 30 ? `${value.slice(0, 13)}…${value.slice(-8)}` : value
}

export type CommandObjectKind = 'CVE' | 'OBJECT' | 'CASE' | 'TASK' | 'INCIDENT' | 'PROOF'
export type CommandObjectItem = { kind: CommandObjectKind; ref: string; label: string; meta: string; path: string }

export function buildCommandItems(input: {
  knowledge: Awaited<ReturnType<typeof searchIntelligence>>['items']
  hot: Awaited<ReturnType<typeof getHotWorld>>['items']
  cases: Awaited<ReturnType<typeof listInvestigations>>['items']
  tasks: Awaited<ReturnType<typeof getAgentRuntime>>['recent_tasks']
  incidents: Awaited<ReturnType<typeof listIncidents>>['items']
  runs: Awaited<ReturnType<typeof getCompetitionProof>>['runs']
  query: string
}): CommandObjectItem[] {
  const items: CommandObjectItem[] = []
  for (const item of input.knowledge) {
    const cve = item.external_identifiers.cve?.[0]?.toUpperCase() ?? null
    items.push({
      kind: cve ? 'CVE' : 'OBJECT',
      ref: cve ?? item.object_id,
      label: item.label,
      meta: `${item.object_type} · ${compactTraceRef(item.canonical_key)} · rev ${item.created_revision}`,
      path: cve ? `/intelligence?cve=${encodeURIComponent(cve)}&from=command` : `/intelligence?object=${encodeURIComponent(item.object_id)}&from=command`,
    })
  }
  for (const item of input.hot.slice(0, 8)) {
    const cve = item.cve_id?.toUpperCase() ?? null
    const ref = cve ?? item.external_object_id
    items.push({
      kind: cve ? 'CVE' : 'OBJECT',
      ref,
      label: cve ?? item.title ?? item.external_object_id,
      meta: [item.title && item.title !== cve ? item.title : null, item.status, item.source_id].filter(Boolean).join(' · '),
      path: cve ? `/intelligence?cve=${encodeURIComponent(cve)}&from=command` : `/intelligence?object=${encodeURIComponent(item.external_object_id)}&from=command`,
    })
  }
  for (const item of input.cases.slice(0, 8)) {
    items.push({
      kind: 'CASE',
      ref: item.case_id,
      label: compactCommandLabel(item.goal, item.case_id),
      meta: `${item.execution_profile ?? 'RUNTIME'} · ${item.status} · ${compactTraceRef(item.case_id)}`,
      path: `/investigations?case=${encodeURIComponent(item.case_id)}&from=command`,
    })
  }
  for (const item of input.tasks.slice(0, 8)) {
    const params = new URLSearchParams({ run: item.run_id, from: item.case_id ? 'case' : 'command', ...(item.case_id ? { caseRef: item.case_id } : {}) })
    items.push({
      kind: 'TASK',
      ref: item.run_id,
      label: item.task_kind.replaceAll('_', ' '),
      meta: `${item.role_id} · ${item.status} · ${compactTraceRef(item.run_id)}`,
      path: `/agents?${params.toString()}`,
    })
  }
  for (const item of input.incidents.slice(0, 8)) {
    items.push({
      kind: 'INCIDENT',
      ref: item.incident_id,
      label: compactCommandLabel(item.current_summary ?? item.incident_type, item.incident_id),
      meta: `${item.lifecycle} · ${item.timeline_event_count} events · ${compactTraceRef(item.incident_id)}`,
      path: `/intelligence?incident=${encodeURIComponent(item.incident_id)}&from=command`,
    })
  }
  for (const item of input.runs.slice(0, 6)) {
    items.push({
      kind: 'PROOF',
      ref: item.benchmark_run_id,
      label: item.suite_ref,
      meta: `${item.passed_case_count}/${item.case_count} cases · ${item.status} · ${compactTraceRef(item.benchmark_run_id)}`,
      path: `/observatory?mode=proof&run=${encodeURIComponent(item.benchmark_run_id)}&from=command`,
    })
  }

  const deduped = [...new Map(items.map((item) => [`${item.kind}:${item.ref}`, item])).values()]
  const query = input.query.trim().toLowerCase()
  const filtered = query
    ? deduped.filter((item) => `${item.kind} ${item.ref} ${item.label} ${item.meta}`.toLowerCase().includes(query))
    : deduped
  return filtered.slice(0, 14)
}

export function shouldSearchGlobalKnowledge(value: string) {
  if (value.length < 2) return false
  if (/^(object|incident|case|task):/i.test(value)) return false
  if (/^CVE-\d{4}-\d+$/i.test(value)) return false
  return true
}

export function guidedModeFromSearch(search: string): 'live' | 'frozen' | null {
  const guide = new URLSearchParams(search).get('guide')
  return guide === 'live' || guide === 'frozen' ? guide : null
}

export function withGuidedMode(path: string, mode: 'live' | 'frozen') {
  const [pathname, search = ''] = path.split('?')
  const params = new URLSearchParams(search)
  params.set('guide', mode)
  return `${pathname}?${params.toString()}`
}

function compactCommandLabel(value: string, fallback: string) {
  const clean = value.trim() || fallback
  return clean.length > 64 ? `${clean.slice(0, 61)}…` : clean
}

export function storyStepMatches(path: string, pathname: string, search: string) {
  const [stepPathname, stepSearch = ''] = path.split('?')
  if (stepPathname !== pathname) return false
  const expected = new URLSearchParams(stepSearch)
  if ([...expected.keys()].length === 0) return true
  const current = new URLSearchParams(search)
  for (const [key, value] of expected.entries()) {
    if (current.get(key) !== value) return false
  }
  return true
}

export async function checkReadiness() {
  try {
    const response = await fetch('/health/ready', { cache: 'no-store' })
    return response.ok
  } catch {
    return false
  }
}
