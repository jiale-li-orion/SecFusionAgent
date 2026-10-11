import { useEffect, useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence } from 'motion/react'
import { ArrowLeft, LoaderCircle } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { getInvestigation, getInvestigationActivity, listInvestigations, type ProductRuntimeEvent } from '../lib/api'
import { EvidenceOverlay } from '../components/investigations/CaseSurfaces'
import { InvestigationIndex } from '../components/investigations/InvestigationIndex'
import { InvestigationDetail } from '../components/investigations/InvestigationDetail'
import { Button } from '../components/ui/button'
import { eventState, mergeRuntimeEvents, type CaseStateFocus } from '../lib/investigationPresentation'
import { useI18n } from '../lib/i18n'
import '../components/investigations/research-workspace.css'

export function InvestigationsPage() {
  const { text } = useI18n()
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const selectedCase = params.get('case')
  const focus = normalizeCaseFocus(params.get('focus'))
  const selectedEvidence = params.get('evidence')
  const listQuery = useInfiniteQuery({
    queryKey: ['investigations'],
    queryFn: ({ pageParam }) => listInvestigations(48, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => (page.has_more ? (page.next_cursor ?? undefined) : undefined),
    refetchInterval: 20_000,
  })
  const cases = useMemo(() => listQuery.data?.pages.flatMap((page) => page.items) ?? [], [listQuery.data?.pages])
  const detail = useQuery({
    queryKey: ['investigation', selectedCase],
    queryFn: () => getInvestigation(selectedCase!),
    enabled: Boolean(selectedCase),
    refetchInterval: selectedCase ? 15_000 : false,
  })
  const activity = useQuery({
    queryKey: ['investigation-activity', selectedCase],
    queryFn: () => getInvestigationActivity(selectedCase!),
    enabled: Boolean(selectedCase),
  })
  const [streamEvents, setStreamEvents] = useState<Record<string, ProductRuntimeEvent[]>>({})
  const [connection, setConnection] = useState<{ caseId: string; state: 'live' | 'retrying' } | null>(null)
  const events = useMemo(
    () => mergeRuntimeEvents(activity.data?.events ?? [], selectedCase ? (streamEvents[selectedCase] ?? []) : []),
    [activity.data?.events, selectedCase, streamEvents],
  )
  const streamState = connection?.caseId === selectedCase ? (connection?.state ?? 'connecting') : 'connecting'

  useEffect(() => {
    if (!selectedCase) return
    const source = new EventSource(`/api/v1/investigations/${encodeURIComponent(selectedCase)}/events`)
    source.onopen = () => setConnection({ caseId: selectedCase, state: 'live' })
    const names = [
      'started',
      'status_changed',
      'progress',
      'finding_added',
      'finding_changed',
      'conflict_changed',
      'unknown_changed',
      'evidence_need_changed',
      'decision_ready',
      'waiting',
      'completed',
      'failed',
      'canceled',
    ]
    const onEvent = (message: MessageEvent<string>) => {
      try {
        const item = JSON.parse(message.data) as ProductRuntimeEvent
        setStreamEvents((current) => {
          const existing = current[selectedCase] ?? []
          return existing.some((event) => event.event_id === item.event_id) ? current : { ...current, [selectedCase]: [...existing, item] }
        })
        void queryClient.invalidateQueries({ queryKey: ['investigation', selectedCase] })
        void queryClient.invalidateQueries({ queryKey: ['investigations'] })
      } catch {
        /* A malformed event must not close the remaining event stream. */
      }
    }
    names.forEach((name) => source.addEventListener(name, onEvent as EventListener))
    source.onerror = () => setConnection({ caseId: selectedCase, state: 'retrying' })
    return () => {
      names.forEach((name) => source.removeEventListener(name, onEvent as EventListener))
      source.close()
    }
  }, [queryClient, selectedCase])

  function updateParams(values: Record<string, string | null>, replace = false) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        Object.entries(values).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)))
        return next
      },
      { replace },
    )
  }
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['investigation', selectedCase] })
    void queryClient.invalidateQueries({ queryKey: ['investigations'] })
    void activity.refetch()
  }
  const requestedView = params.get('view')
  const view = ['report', 'findings', 'activity'].includes(requestedView ?? '')
    ? requestedView!
    : focus && focus !== 'decision'
      ? 'findings'
      : 'report'

  return (
    <section className="research-workspace">
      {!selectedCase ? (
        <InvestigationIndex
          cases={cases}
          loading={listQuery.isPending}
          failed={listQuery.isError && !listQuery.isFetchNextPageError}
          retry={() => void listQuery.refetch()}
          query={params.get('q') ?? ''}
          onQuery={(q) => updateParams({ q }, true)}
          filter={['active', 'resolved', 'stopped'].includes(params.get('status') ?? '') ? params.get('status')! : 'all'}
          onFilter={(status) => updateParams({ status })}
          onSelect={(caseId) => updateParams({ case: caseId, view: null, focus: null, evidence: null, session: null })}
          hasMore={listQuery.hasNextPage}
          loadingMore={listQuery.isFetchingNextPage}
          moreFailed={listQuery.isFetchNextPageError}
          loadMore={() => void listQuery.fetchNextPage()}
        />
      ) : (
        <>
          <div className="research-breadcrumb">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => updateParams({ case: null, session: null, view: null, focus: null, evidence: null, from: null, run: null })}
            >
              <ArrowLeft size={15} />
              {text('调查记录', 'Investigations')}
            </Button>
            <span>/</span>
            <span>{text('调查详情', 'Investigation')}</span>
            {params.get('from') === 'task' && params.get('run') && (
              <Link to={`/agents?run=${encodeURIComponent(params.get('run')!)}`}>{text('返回任务', 'Back to task')}</Link>
            )}
          </div>
          {detail.isPending && (
            <div className="research-empty" role="status">
              <LoaderCircle className="research-loading" size={24} />
              <p>{text('正在读取调查…', 'Loading investigation…')}</p>
            </div>
          )}
          {detail.isError && (
            <div className="research-notice" role="alert">
              <span>{text('这份调查暂时无法读取。', 'This investigation could not be loaded.')}</span>
              <Button variant="outline" onClick={() => void detail.refetch()}>
                {text('重新读取', 'Retry')}
              </Button>
            </div>
          )}
          {detail.data && (
            <InvestigationDetail
              key={detail.data.case_id}
              investigation={detail.data}
              sessionId={detail.data.continuation_session_id ?? params.get('session')}
              events={events}
              streamState={streamState}
              activityLoading={activity.isPending}
              activityFailed={activity.isError}
              retryActivity={() => void activity.refetch()}
              view={view}
              onView={(next) => updateParams({ view: next, focus: null })}
              focus={focus}
              onFocus={(next) => updateParams({ view: next === 'decision' ? 'report' : 'findings', focus: next })}
              onEvent={(event) => {
                const state = eventState(event.event_type)
                if (state) updateParams({ view: state === 'decision' ? 'report' : 'findings', focus: state })
              }}
              onEvidence={(evidence) => updateParams({ evidence }, true)}
              onChanged={refresh}
            />
          )}
        </>
      )}
      <AnimatePresence>
        {selectedEvidence && selectedCase && (
          <EvidenceOverlay key={selectedEvidence} evidenceRef={selectedEvidence} onClose={() => updateParams({ evidence: null }, true)} />
        )}
      </AnimatePresence>
    </section>
  )
}

function normalizeCaseFocus(value: string | null): CaseStateFocus | null {
  return value === 'confirmed' || value === 'conflicts' || value === 'unknowns' || value === 'needs' || value === 'decision' ? value : null
}
