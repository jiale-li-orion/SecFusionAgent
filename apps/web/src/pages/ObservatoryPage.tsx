import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useSearchParams } from 'react-router-dom'
import { Activity, Archive, TriangleAlert } from 'lucide-react'
import { getAgentRuntime, getCompetitionProof, getSystemOverview, getWorldOverview } from '../lib/api'
import { LiveObservatory } from '../components/observatory/ObservatoryLive'
import type { ObservatoryWindow } from '../lib/observatoryPresentation'
import { ProofObservatory } from '../components/observatory/ObservatoryProof'
import { useI18n } from '../lib/i18n'


type ObservatoryMode = 'live' | 'proof'

export function ObservatoryPage() {
  const { text } = useI18n()
  const [params, setParams] = useSearchParams()
  const preferredRunId = params.get('run')
  const preferredCaseRunId = params.get('caseRun')
  const reduceMotion = Boolean(useReducedMotion())
  const mode: ObservatoryMode = params.get('mode') === 'proof' ? 'proof' : 'live'
  const [windowKey, setWindowKey] = useState<ObservatoryWindow>('24h')
  const worldQuery = useQuery({ queryKey: ['observatory-world'], queryFn: getWorldOverview, refetchInterval: 30_000 })
  const agentsQuery = useQuery({ queryKey: ['observatory-agents'], queryFn: getAgentRuntime, refetchInterval: 15_000 })
  const systemQuery = useQuery({ queryKey: ['observatory-system'], queryFn: getSystemOverview, refetchInterval: 15_000 })
  const proofQuery = useQuery({ queryKey: ['competition-proof'], queryFn: getCompetitionProof, staleTime: 60_000 })

  function selectMode(nextMode: ObservatoryMode) {
    setParams((current) => {
      const next = new URLSearchParams(current)
      if (nextMode === 'proof') {
        next.set('mode', 'proof')
      } else {
        next.delete('mode')
        next.delete('run')
        next.delete('caseRun')
      }
      return next
    }, { replace: true })
  }

  useEffect(() => {
    const openProof = () => {
      setParams((current) => {
        const next = new URLSearchParams(current)
        next.set('mode', 'proof')
        return next
      }, { replace: true })
    }
    window.addEventListener('secfusion:proof', openProof)
    return () => window.removeEventListener('secfusion:proof', openProof)
  }, [setParams])

  return (
    <section className={`observatory-space observatory-page observatory-${mode}`}>
      <header className="observatory-switchboard-heading observatory-heading">
        <div>
          <p>{mode === 'live'
            ? text('测量此刻正在发生的运行', 'MEASURE THE SYSTEM WHILE IT LIVES')
            : text('让完成的实验留下可复验记录', 'LET THE FINISHED EXPERIMENT STAND')}</p>
          <h1>{mode === 'live'
            ? <>{text('运行', 'LIVE')} <span>{text('观测', 'OBSERVATORY')}</span></>
            : <>{text('冻结', 'FROZEN')} <span>{text('证明', 'PROOF')}</span></>}</h1>
          <small>{mode === 'live'
            ? text(
              'Data Plane、source health、queue / execution 与 Agent runtime 按当前测量窗口展开；所有读数来自当前运行快照。',
              'Data Plane, source health, queue / execution, and Agent runtime unfold over the current measurement window; every reading comes from the live operational snapshot.',
            )
            : text(
              'CompetitionReport、BenchmarkRun、CaseRun 与 MetricObservation 形成冻结证据链；运行坐标、测量值和 EvidenceRef 保持可追溯。',
              'CompetitionReport, BenchmarkRun, CaseRun, and MetricObservation form the frozen proof chain; runtime coordinates, measurements, and EvidenceRefs remain traceable.',
            )}</small>
        </div>
        <div className="observatory-mode-switch" role="tablist" aria-label={text('观测模式', 'Observatory mode')}>
          <button role="tab" aria-selected={mode === 'live'} className={mode === 'live' ? 'active' : ''} onClick={() => selectMode('live')}><Activity size={14} /> {text('实时', 'LIVE')}</button>
          <button role="tab" aria-selected={mode === 'proof'} className={mode === 'proof' ? 'active' : ''} onClick={() => selectMode('proof')}><Archive size={14} /> {text('冻结证明', 'PROOF')}</button>
          <motion.span className="mode-cursor" animate={{ x: mode === 'live' ? 0 : '100%' }} transition={{ type: 'spring', stiffness: 320, damping: 28 }} />
        </div>
      </header>

      <AnimatePresence mode="wait">
        {mode === 'live' ? (
          <motion.div
            key="live"
            className="observatory-live observatory-live-stage"
            initial={reduceMotion ? false : { opacity: 0, scaleY: .06, filter: 'brightness(1.8) saturate(.7)', transformOrigin: 'center top' }}
            animate={{ opacity: 1, scaleY: 1, filter: 'brightness(1) saturate(1)' }}
            exit={reduceMotion ? undefined : { opacity: .18, scaleY: .025, filter: 'brightness(2.2) saturate(.5)', transformOrigin: 'center top' }}
            transition={{ duration: reduceMotion ? 0 : .3, ease: [0.22, 1, 0.36, 1] }}
          >
            {(worldQuery.isError || agentsQuery.isError || systemQuery.isError) && (
              <div className="observatory-live-fault">
                <TriangleAlert size={14} />
                <div><small>{text('LIVE 读取降级', 'LIVE READ DEGRADED')}</small><strong>{worldQuery.isError ? text('Data Plane 快照不可用', 'Data Plane snapshot unavailable') : agentsQuery.isError ? text('Agent Runtime 快照不可用', 'Agent Runtime snapshot unavailable') : text('System overview 不可用', 'System overview unavailable')}</strong></div>
                <button onClick={() => selectMode('proof')}><Archive size={12} /> {text('打开冻结 PROOF', 'OPEN FROZEN PROOF')}</button>
              </div>
            )}
            <LiveObservatory
              world={worldQuery.data ?? null}
              agents={agentsQuery.data ?? null}
              system={systemQuery.data ?? null}
              proof={proofQuery.data ?? null}
              proofUnavailable={proofQuery.isError}
              windowKey={windowKey}
              setWindowKey={setWindowKey}
            />
          </motion.div>
        ) : (
          <motion.div
            key="proof"
            className="observatory-proof observatory-proof-stage"
            initial={reduceMotion ? false : { opacity: 0, y: -12, rotateX: 1.2, clipPath: 'inset(0 0 100% 0)', filter: 'brightness(1.12)' }}
            animate={{ opacity: 1, y: 0, rotateX: 0, clipPath: 'inset(0 0 0% 0)', filter: 'brightness(1)' }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 8, clipPath: 'inset(100% 0 0 0)', filter: 'brightness(.94)' }}
            transition={{ duration: reduceMotion ? 0 : .38, ease: [0.22, 1, 0.36, 1] }}
          >
            {proofQuery.isError && <div className="observatory-proof-fault"><TriangleAlert size={14} /><span>{text('冻结 CompetitionReport 当前不可读。', 'Frozen CompetitionReport read unavailable.')}</span></div>}
            <ProofObservatory key={`${preferredRunId ?? 'proof-default'}:${preferredCaseRunId ?? 'case-default'}`} proof={proofQuery.data ?? null} loading={proofQuery.isLoading} preferredRunId={preferredRunId} preferredCaseRunId={preferredCaseRunId} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
