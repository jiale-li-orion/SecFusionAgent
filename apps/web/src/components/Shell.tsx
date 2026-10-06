import { useDeferredValue, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowUpRight,
  Bot,
  BrainCircuit,
  CircleDot,
  Radar,
  Search,
  Sparkles,
  Telescope,
  Waypoints,
  X,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useI18n } from '../lib/i18n'
import { getAgentRuntime, getCompetitionProof, getCompetitionProofRun, getHotWorld, listIncidents, listInvestigations, searchIntelligence } from '../lib/api'

const nav = [
  { to: '/', label: 'WORLD', zh: '世界', sub: 'Evidence World', subZh: '证据世界', icon: Radar },
  { to: '/intelligence', label: 'INTELLIGENCE', zh: '情报', sub: 'Objects & Knowledge', subZh: '对象与知识', icon: BrainCircuit },
  { to: '/investigations', label: 'INVESTIGATIONS', zh: '调查', sub: 'Continuous Inquiry', subZh: '持续调查', icon: Telescope },
  { to: '/agents', label: 'AGENTS', zh: '智能体', sub: 'Runtime & Memory', subZh: '运行与记忆', icon: Bot },
  { to: '/observatory', label: 'OBSERVATORY', zh: '观测', sub: 'Metrics & Proof', subZh: '运行与证明', icon: Activity },
]

export function Shell({ children }: { children: React.ReactNode }) {
  const { language, setLanguage, text } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const shellRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [storyOpen, setStoryOpen] = useState(false)
  const [storyMode, setStoryMode] = useState<'live' | 'frozen'>('live')
  const [searchValue, setSearchValue] = useState('')
  const deferredSearchValue = useDeferredValue(searchValue.trim())
  const [searchError, setSearchError] = useState('')
  const [commandIndex, setCommandIndex] = useState(0)
  const [commandKeyboardActive, setCommandKeyboardActive] = useState(false)
  const readiness = useQuery({
    queryKey: ['shell-readiness'],
    queryFn: checkReadiness,
    refetchInterval: 15_000,
    retry: false,
  })
  const storyHot = useQuery({ queryKey: ['guided-story-hot'], queryFn: () => getHotWorld(8), enabled: (storyOpen && storyMode === 'live') || searchOpen, staleTime: 20_000 })
  const storyCases = useQuery({ queryKey: ['guided-story-cases'], queryFn: () => listInvestigations(20), enabled: (storyOpen && storyMode === 'live') || searchOpen, staleTime: 15_000 })
  const storyAgents = useQuery({ queryKey: ['guided-story-agents'], queryFn: getAgentRuntime, enabled: (storyOpen && storyMode === 'live') || searchOpen, staleTime: 15_000 })
  const storyProof = useQuery({ queryKey: ['guided-story-proof'], queryFn: getCompetitionProof, enabled: storyOpen || searchOpen, staleTime: 60_000 })
  const commandIncidents = useQuery({ queryKey: ['command-incidents'], queryFn: () => listIncidents(8), enabled: searchOpen, staleTime: 20_000 })
  const commandKnowledge = useQuery({
    queryKey: ['command-knowledge', deferredSearchValue],
    queryFn: () => searchIntelligence(deferredSearchValue, 12),
    enabled: searchOpen && shouldSearchGlobalKnowledge(deferredSearchValue),
    staleTime: 20_000,
  })
  const frozenRunId = storyProof.data?.runs.slice().sort((a, b) => b.case_count - a.case_count)[0]?.benchmark_run_id ?? null
  const storyFrozenRun = useQuery({
    queryKey: ['guided-story-frozen-run', frozenRunId],
    queryFn: () => getCompetitionProofRun(frozenRunId!),
    enabled: storyOpen && storyMode === 'frozen' && Boolean(frozenRunId),
    staleTime: 60_000,
  })

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandIndex(0)
        setCommandKeyboardActive(false)
        setSearchOpen(true)
        window.setTimeout(() => searchRef.current?.focus(), 0)
      }
      if (event.key === 'Escape') {
        setSearchOpen(false)
        setStoryOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    if (commandKeyboardActive && commandItems[commandIndex]) {
      openCommandItem(commandItems[commandIndex])
      return
    }
    const raw = searchValue.trim()
    const cve = raw.toUpperCase()
    const objectMatch = raw.match(/^object:(.+)$/i)
    const incidentMatch = raw.match(/^incident:(.+)$/i)
    const caseMatch = raw.match(/^case:(.+)$/i)
    const taskMatch = raw.match(/^task:(.+)$/i)
    if (!/^CVE-\d{4}-\d+$/.test(cve) && !objectMatch?.[1]?.trim() && !incidentMatch?.[1]?.trim() && !caseMatch?.[1]?.trim() && !taskMatch?.[1]?.trim()) {
      if (commandItems[0]) {
        openCommandItem(commandItems[0])
        return
      }
      setSearchError(text('没有匹配对象；也可输入 CVE、object:<id>、incident:<id>、case:<id> 或 task:<id>', 'No matching object. You can also use CVE, object:<id>, incident:<id>, case:<id>, or task:<id>.'))
      return
    }
    setSearchError('')
    setSearchOpen(false)
    if (caseMatch?.[1]?.trim()) navigate('/investigations?case=' + encodeURIComponent(caseMatch[1].trim()))
    else if (taskMatch?.[1]?.trim()) navigate('/agents?run=' + encodeURIComponent(taskMatch[1].trim()))
    else if (incidentMatch?.[1]?.trim()) navigate('/intelligence?incident=' + encodeURIComponent(incidentMatch[1].trim()))
    else if (objectMatch?.[1]?.trim()) navigate(`/intelligence?object=${encodeURIComponent(objectMatch[1].trim())}`)
    else navigate(`/intelligence?cve=${encodeURIComponent(cve)}`)
  }

  function openCommandItem(item: CommandObjectItem) {
    navigate(item.path)
    setSearchOpen(false)
    setSearchValue('')
    setSearchError('')
    setCommandKeyboardActive(false)
  }

  const readinessState = readiness.isLoading ? 'checking' : readiness.data ? 'ready' : 'degraded'
  const shellSpace = location.pathname === '/'
    ? 'world'
    : location.pathname.split('/').filter(Boolean)[0] ?? 'world'
  const contextTrace = buildContextTrace(location.pathname, location.search, text)
  const storyHotCve = storyHot.data?.items.find((item) => item.cve_id)?.cve_id ?? null
  const storyCase = storyCases.data?.items.find((item) => storyHotCve && item.goal.toUpperCase().includes(storyHotCve))
    ?? storyCases.data?.items.find((item) => item.status === 'active' || item.status === 'waiting')
    ?? storyCases.data?.items[0]
    ?? null
  const storyTask = storyAgents.data?.recent_tasks.find((item) => storyCase && item.case_id === storyCase.case_id)
    ?? storyAgents.data?.recent_tasks[0]
    ?? null
  const storyEvidence = storyCase?.latest_decision?.citations[0]?.evidence_ref
    ?? storyCase?.confirmed_findings.find((item) => item.evidence_refs.length > 0)?.evidence_refs[0]
    ?? storyCase?.conflicts.find((item) => item.evidence_refs.length > 0)?.evidence_refs[0]
    ?? null
  const storyRun = storyProof.data?.runs[0] ?? null
  const caseDecisionPath = storyCase
    ? `/investigations?${new URLSearchParams({
      case: storyCase.case_id,
      focus: 'decision',
      ...(storyEvidence ? { evidence: storyEvidence } : {}),
    }).toString()}`
    : null
  const liveStorySteps = [
    { index: '01', titleZh: '证据世界', titleEn: 'EVIDENCE WORLD', scopeZh: 'M1–M3 · 多源监测与 Evidence Plane', scopeEn: 'M1–M3 · monitoring & Evidence Plane', detail: storyHot.data ? text(`${storyHot.data.items.length} 个真实 Hot 对象`, `${storyHot.data.items.length} real Hot objects`) : text('读取当前世界', 'resolve current world'), path: '/' },
    { index: '02', titleZh: '情报档案', titleEn: 'INTELLIGENCE DOSSIER', scopeZh: 'M2–M3 · 规范化、富化与关系证据', scopeEn: 'M2–M3 · normalization, enrichment & relations', detail: storyHotCve ?? text('等待 Hot CVE', 'awaiting Hot CVE'), path: storyHotCve ? `/intelligence?cve=${encodeURIComponent(storyHotCve)}` : null },
    { index: '03', titleZh: '精准核验', titleEn: 'VERIFY', scopeZh: 'M4–M6 · Product Intelligence 入口', scopeEn: 'M4–M6 · Product Intelligence admission', detail: storyHotCve ? `${storyHotCve} · ARGUS` : 'VERIFY · ARGUS', path: `/start?${new URLSearchParams({ profile: 'VERIFY', ...(storyHotCve ? { cve: storyHotCve, from: 'intelligence', origin: storyHotCve } : {}) }).toString()}` },
    { index: '04', titleZh: '证据缺口', titleEn: 'EVIDENCE NEED', scopeZh: 'M4–M6 · durable Investigation 状态', scopeEn: 'M4–M6 · durable Investigation state', detail: storyCase?.case_id ?? text('等待 durable Case', 'awaiting durable Case'), path: storyCase ? `/investigations?case=${encodeURIComponent(storyCase.case_id)}&focus=needs` : null },
    { index: '05', titleZh: '执行链', titleEn: 'AGENT RUNTIME', scopeZh: 'M5 · Role / Task / Capability / Recovery', scopeEn: 'M5 · Role / Task / Capability / Recovery', detail: storyTask?.run_id ?? text('等待 TaskRun', 'awaiting TaskRun'), path: storyTask ? `/agents?${new URLSearchParams({ run: storyTask.run_id, ...(storyCase ? { from: 'case', caseRef: storyCase.case_id } : {}) }).toString()}` : null },
    { index: '06', titleZh: '判决与证据', titleEn: 'DECISION / EVIDENCE', scopeZh: 'M4–M6 · Decision / citations / conflicts / unknowns', scopeEn: 'M4–M6 · Decision / citations / conflicts / unknowns', detail: storyEvidence ?? storyCase?.latest_decision?.decision_id ?? text('等待 Decision', 'awaiting Decision'), path: caseDecisionPath },
    { index: '07', titleZh: '记忆演化', titleEn: 'SKILL / EXPERIENCE', scopeZh: 'M5 + M7 · 程序记忆与 replay', scopeEn: 'M5 + M7 · procedural memory & replay', detail: text('真实 Skill / Experience read', 'real Skill / Experience read'), path: '/agents?section=memory' },
    { index: '08', titleZh: '冻结证明', titleEn: 'PROOF', scopeZh: 'M7–M8 · Benchmark / Operations / Recovery', scopeEn: 'M7–M8 · Benchmark / Operations / Recovery', detail: storyRun?.benchmark_run_id ?? text('等待正式 Run', 'awaiting formal Run'), path: storyRun ? `/observatory?mode=proof&run=${encodeURIComponent(storyRun.benchmark_run_id)}` : '/observatory?mode=proof' },
  ]
  const frozenCases = storyFrozenRun.data?.cases ?? []
  const frozenCase = frozenCases.find((item) => item.task_run_id && item.decision_ref && item.target_refs.length > 0 && item.case_ref.includes('cross-source-risk'))
    ?? frozenCases.find((item) => item.task_run_id && item.decision_ref && item.target_refs.length > 0)
    ?? null
  const frozenTarget = frozenCase?.target_refs.find((ref) => ref.startsWith('cve:'))?.slice(4) ?? null
  const frozenProofPath = frozenRunId && frozenCase
    ? `/observatory?${new URLSearchParams({ mode: 'proof', run: frozenRunId, caseRun: frozenCase.case_run_id }).toString()}`
    : frozenRunId
      ? `/observatory?mode=proof&run=${encodeURIComponent(frozenRunId)}`
      : '/observatory?mode=proof'
  const frozenStorySteps = [
    { index: '01', titleZh: '冻结目标', titleEn: 'FROZEN TARGET', scopeZh: 'M7 · BenchmarkCase target / world coordinate', scopeEn: 'M7 · BenchmarkCase target / world coordinate', detail: frozenTarget ?? text('等待正式 Case target', 'awaiting formal case target'), path: frozenTarget ? `/intelligence?cve=${encodeURIComponent(frozenTarget)}&from=proof` : null },
    { index: '02', titleZh: '正式 CaseRun', titleEn: 'FORMAL CASE RUN', scopeZh: 'M7 · 冻结输入 / 状态 / artifact 坐标', scopeEn: 'M7 · frozen input / status / artifact coordinates', detail: frozenCase?.case_ref ?? text('等待 CaseRun', 'awaiting CaseRun'), path: frozenProofPath },
    { index: '03', titleZh: '执行 TaskRun', titleEn: 'TASK RUNTIME', scopeZh: 'M5 + M7 · 真实 Role / Task 执行坐标', scopeEn: 'M5 + M7 · real Role / Task execution coordinate', detail: frozenCase?.task_run_id ?? text('等待 TaskRun', 'awaiting TaskRun'), path: frozenCase?.task_run_id ? `/agents?${new URLSearchParams({ run: frozenCase.task_run_id, from: 'proof', ...(frozenRunId ? { proofRun: frozenRunId } : {}), caseRun: frozenCase.case_run_id }).toString()}` : null },
    { index: '04', titleZh: '冻结 Decision', titleEn: 'FROZEN DECISION', scopeZh: 'M6 + M7 · persisted Decision / citations', scopeEn: 'M6 + M7 · persisted Decision / citations', detail: frozenCase?.decision_ref ?? text('等待 Decision', 'awaiting Decision'), path: frozenProofPath },
    { index: '05', titleZh: '评测证明', titleEn: 'METRIC PROOF', scopeZh: 'M7–M8 · MetricObservation / EvidenceRef / DeploymentRevision', scopeEn: 'M7–M8 · MetricObservation / EvidenceRef / DeploymentRevision', detail: frozenRunId ?? text('等待正式 Run', 'awaiting formal Run'), path: frozenProofPath },
  ]
  const storySteps = storyMode === 'live' ? liveStorySteps : frozenStorySteps
  const storyLoading = storyMode === 'live'
    ? storyHot.isLoading || storyCases.isLoading || storyAgents.isLoading || storyProof.isLoading
    : storyProof.isLoading || storyFrozenRun.isLoading
  const storyError = storyMode === 'live'
    ? storyHot.isError || storyCases.isError || storyAgents.isError || storyProof.isError
    : storyProof.isError || storyFrozenRun.isError
  const commandItems = buildCommandItems({
    knowledge: commandKnowledge.data?.items ?? [],
    hot: storyHot.data?.items ?? [],
    cases: storyCases.data?.items ?? [],
    tasks: storyAgents.data?.recent_tasks ?? [],
    incidents: commandIncidents.data?.items ?? [],
    runs: storyProof.data?.runs ?? [],
    query: searchValue,
  })
  const commandLoading = searchOpen && (storyHot.isLoading || storyCases.isLoading || storyAgents.isLoading || storyProof.isLoading || commandIncidents.isLoading || commandKnowledge.isLoading)

  return (
    <div
      ref={shellRef}
      className={`product-shell shell-space-${shellSpace}`}
      onPointerMove={(event) => {
        const rect = shellRef.current?.getBoundingClientRect()
        if (!rect || !shellRef.current) return
        shellRef.current.style.setProperty('--pointer-x', `${event.clientX - rect.left}px`)
        shellRef.current.style.setProperty('--pointer-y', `${event.clientY - rect.top}px`)
      }}
    >
      <a className="product-skip-link" href="#product-main">{text('跳到产品主内容', 'SKIP TO PRODUCT CONTENT')}</a>
      <aside className="instrument-bar" aria-label={text('SecFusion 产品导航', 'SecFusion product navigation')}>
        <button className="instrument-brand" onClick={() => navigate('/')} aria-label={text('返回 SecFusionAgent 首页', 'SecFusionAgent home')}>
          <span className="brand-sigil"><Waypoints size={18} /></span>
          <span className="brand-copy">
            <strong>SECFUSION</strong>
            <small>EVIDENCE INTELLIGENCE</small>
          </span>
        </button>

        <nav className="instrument-nav" aria-label={text('主导航', 'Primary navigation')}>
          {nav.map(({ to, label, zh, sub, subZh, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setSearchOpen(false)}
              className={({ isActive }) => `instrument-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={14} strokeWidth={1.7} />
              <span className="nav-copy"><strong>{language === 'zh' ? zh : label}</strong><small>{language === 'zh' ? subZh : sub}</small></span>
            </NavLink>
          ))}
        </nav>

        <div className="instrument-actions">
          <button className="command-trigger" onClick={() => { setCommandIndex(0); setCommandKeyboardActive(false); setSearchOpen(true) }} aria-label={text('打开对象定位', 'Open command search')}>
            <Search size={14} />
            <span>{text('定位对象', 'LOCATE OBJECT')}</span>
            <kbd>⌘K</kbd>
          </button>
          <button className={`story-trigger ${storyOpen ? 'active' : ''}`} onClick={() => setStoryOpen((value) => !value)}>
            <Waypoints size={14} />
            <span>{text('演示主路径', 'GUIDED PATH')}</span>
            <b>{storyMode === 'live' ? 8 : 5}</b>
          </button>
          <div className="language-switch" role="group" aria-label={text('产品语言', 'Product language')}>
            <button className={language === 'zh' ? 'active' : ''} onClick={() => setLanguage('zh')}>中</button>
            <span>/</span>
            <button className={language === 'en' ? 'active' : ''} onClick={() => setLanguage('en')}>EN</button>
          </div>
          <button
            type="button"
            className={`runtime-state state-${readinessState}`}
            role="status"
            aria-live="polite"
            onClick={() => void readiness.refetch()}
            title={text('重新探测运行状态', 'Recheck runtime readiness')}
          >
            <CircleDot size={11} />
            {readiness.isLoading ? 'SYNC' : readiness.data ? 'READY' : 'DEGRADED'}
          </button>
          <button className="global-start" onClick={() => navigate('/start')}>
            <span className="global-start-glyph"><Sparkles size={14} /></span>
            <strong>{text('启动任务', 'START')}</strong>
          </button>
        </div>
      </aside>

      <div className="shell-scan" aria-hidden="true" />
      <AnimatePresence>
        {contextTrace.length > 1 && (
          <motion.nav
            key={`${location.pathname}:${location.search}`}
            className={`context-trace trace-space-${shellSpace}`}
            aria-label={text('当前产品上下文', 'Current product context')}
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: .18 }}
          >
            <span className="context-trace-mark"><Waypoints size={11} /> TRACE</span>
            <div className="context-trace-chain">
              {contextTrace.map((segment, index) => (
                <span key={`${segment.kind}:${segment.ref}:${index}`} className={`context-trace-node ${index === contextTrace.length - 1 ? 'current' : ''}`}>
                  {index > 0 && <i aria-hidden="true">→</i>}
                  {segment.path && index !== contextTrace.length - 1 ? (
                    <button onClick={() => navigate(segment.path!)}>
                      <small>{segment.kind}</small>
                      <strong>{segment.ref}</strong>
                    </button>
                  ) : (
                    <span>
                      <small>{segment.kind}</small>
                      <strong>{segment.ref}</strong>
                    </span>
                  )}
                </span>
              ))}
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
      <main id="product-main" className="product-workspace" tabIndex={-1}>{children}</main>

      <AnimatePresence>
        {storyOpen && (
          <motion.aside
            className={`guided-story story-space-${shellSpace}`}
            role="dialog"
            aria-modal="true"
            aria-label={text('真实系统演示路径', 'Real system guided path')}
            initial={{ opacity: 0, x: -24, clipPath: 'inset(0 0 0 18%)' }}
            animate={{ opacity: 1, x: 0, clipPath: 'inset(0 0 0 0%)' }}
            exit={{ opacity: 0, x: -16, clipPath: 'inset(0 0 0 12%)' }}
            transition={{ type: 'spring', stiffness: 260, damping: 28 }}
          >
            <div className="guided-story-head">
              <div><small>REAL PRODUCT STORY</small><strong>{storyMode === 'live' ? text('八幕实时系统路径', 'EIGHT-ACT LIVE PATH') : text('五幕冻结证明路径', 'FIVE-ACT FROZEN PATH')}</strong><span>{storyMode === 'live' ? text('对象从当前 Product read 派生', 'objects resolve from current Product reads') : text('对象从正式 BenchmarkRun / CaseRun 派生', 'objects resolve from formal BenchmarkRun / CaseRun')}</span></div>
              <button onClick={() => setStoryOpen(false)} aria-label={text('关闭演示路径', 'Close guided path')}><X size={14} /></button>
            </div>
            <div className="guided-story-mode" role="tablist" aria-label={text('演示路径模式', 'Guided path mode')}>
              <button role="tab" aria-selected={storyMode === 'live'} className={storyMode === 'live' ? 'active' : ''} onClick={() => setStoryMode('live')}>{text('实时链', 'LIVE PATH')}</button>
              <button role="tab" aria-selected={storyMode === 'frozen'} className={storyMode === 'frozen' ? 'active' : ''} onClick={() => setStoryMode('frozen')}>{text('冻结链', 'FROZEN PATH')}</button>
            </div>
            <div className="guided-story-truth">
              <span className={storyError ? 'degraded' : 'ready'} />
              <small>{storyLoading ? text('解析真实路径…', 'RESOLVING REAL PATH…') : storyError ? text('部分 read seam 不可用；相关 step 已禁用', 'some read seams unavailable; affected steps disabled') : storyMode === 'live' ? text('LIVE / DURABLE refs 已绑定', 'LIVE / DURABLE refs bound') : text('BenchmarkRun / CaseRun / TaskRun / Decision 已绑定', 'BenchmarkRun / CaseRun / TaskRun / Decision bound')}</small>
            </div>
            <div className="guided-story-steps">
              {storySteps.map((step) => {
                const active = step.path ? storyStepMatches(step.path, location.pathname, location.search) : false
                return (
                  <button
                    key={step.index}
                    className={`${active ? 'active' : ''} ${step.path ? '' : 'unavailable'}`}
                    disabled={!step.path}
                    onClick={() => { if (step.path) navigate(step.path) }}
                  >
                    <span>{step.index}</span>
                    <div><small>{language === 'zh' ? step.titleZh : step.titleEn}</small><strong>{step.detail}</strong><em>{language === 'zh' ? step.scopeZh : step.scopeEn}</em></div>
                    <ArrowUpRight size={12} />
                  </button>
                )
              })}
            </div>
            <p className="guided-story-boundary">{storyMode === 'live'
              ? text('LIVE Guide 负责导航，不生成 telemetry、Case、Task、Skill 或评测结果。', 'LIVE Guide navigates existing facts; it creates no telemetry, Case, Task, Skill, or evaluation result.')
              : text('FROZEN Guide 使用正式 Benchmark 坐标，不把冻结评测冒充当前运行。', 'FROZEN Guide uses formal benchmark coordinates and never presents frozen evaluation as current runtime.')}</p>
          </motion.aside>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {searchOpen && (
          <motion.div
            className="command-lens"
            role="dialog"
            aria-modal="true"
            aria-label={text('定位产品对象', 'Locate product object')}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.form
              onSubmit={submitSearch}
              role="search"
              initial={{ y: -16, opacity: 0, scale: .985 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: -8, opacity: 0, scale: .99 }}
              transition={{ type: 'spring', stiffness: 280, damping: 26 }}
            >
              <span className="command-index">{text('SECFUSION / 规范对象定位', 'SECFUSION / CANONICAL LOCATOR')}</span>
              <div className={`command-input-line ${searchError ? 'invalid' : ''}`}>
                <Search size={20} />
                <input
                  ref={searchRef}
                  aria-label={text('CVE、Object、Incident、Case 或 Task 编号', 'CVE, Object, Incident, Case, or Task ID')}
                  value={searchValue}
                  onChange={(event) => {
                    setSearchValue(event.target.value)
                    setCommandIndex(0)
                    setCommandKeyboardActive(false)
                    if (searchError) setSearchError('')
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'ArrowDown' && commandItems.length) {
                      event.preventDefault()
                      setCommandKeyboardActive(true)
                      setCommandIndex((current) => Math.min(current + 1, commandItems.length - 1))
                    } else if (event.key === 'ArrowUp' && commandItems.length) {
                      event.preventDefault()
                      setCommandKeyboardActive(true)
                      setCommandIndex((current) => Math.max(current - 1, 0))
                    } else if (event.key === 'Enter' && commandKeyboardActive && commandItems[commandIndex]) {
                      event.preventDefault()
                      openCommandItem(commandItems[commandIndex])
                    }
                  }}
                  placeholder={searchError || 'CVE-2026-… / object:<id> / incident:<id> / case:<id> / task:<id>'}
                />
                <button type="button" onClick={() => setSearchOpen(false)} aria-label={text('关闭对象定位', 'Close command search')}>
                  <X size={17} />
                </button>
              </div>
              <div className="command-live-index">
                <div className="command-live-head">
                  <div><small>{text('实时对象', 'LIVE OBJECTS')}</small><strong>{text('从当前 Product reads 直接进入', 'ENTER FROM CURRENT PRODUCT READS')}</strong></div>
                  <span>{commandLoading ? text('解析中…', 'RESOLVING…') : `${commandItems.length} ${text('个匹配', 'matches')}`}</span>
                </div>
                <div className="command-live-results">
                  {commandItems.map((item, index) => (
                    <button key={`${item.kind}:${item.ref}`} type="button" className={commandKeyboardActive && index === commandIndex ? 'selected' : ''} onMouseEnter={() => { setCommandIndex(index); setCommandKeyboardActive(true) }} onClick={() => openCommandItem(item)}>
                      <span className={`command-object-glyph kind-${item.kind.toLowerCase()}`}><CommandObjectIcon kind={item.kind} /></span>
                      <span className="command-object-copy"><small>{item.kind}</small><strong>{item.label}</strong><em>{item.meta}</em></span>
                      <ArrowUpRight size={12} />
                    </button>
                  ))}
                  {!commandLoading && commandItems.length === 0 && <div className="command-live-empty"><Search size={15} /><span>{text('没有匹配的当前对象；仍可输入规范坐标后按 Enter。', 'No current object matches; canonical coordinates still open with Enter.')}</span></div>}
                </div>
              </div>
              <div className="command-foot">
                <span>{text('↑↓ 选择实时对象', '↑↓ SELECT LIVE OBJECT')}</span>
                <span>{text('ENTER → 打开选择 / 解析规范坐标', 'ENTER → OPEN SELECTION / RESOLVE COORDINATE')}</span>
                <span>{text('ESC → 返回当前空间', 'ESC → RETURN')}</span>
              </div>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

type ContextTraceSegment = { kind: string; ref: string; path?: string }

function buildContextTrace(
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

type CommandObjectKind = 'CVE' | 'OBJECT' | 'CASE' | 'TASK' | 'INCIDENT' | 'PROOF'
type CommandObjectItem = { kind: CommandObjectKind; ref: string; label: string; meta: string; path: string }

function buildCommandItems(input: {
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

function shouldSearchGlobalKnowledge(value: string) {
  if (value.length < 2) return false
  if (/^(object|incident|case|task):/i.test(value)) return false
  if (/^CVE-\d{4}-\d+$/i.test(value)) return false
  return true
}

function compactCommandLabel(value: string, fallback: string) {
  const clean = value.trim() || fallback
  return clean.length > 64 ? `${clean.slice(0, 61)}…` : clean
}

function CommandObjectIcon({ kind }: { kind: CommandObjectKind }) {
  if (kind === 'CASE') return <Telescope size={14} />
  if (kind === 'TASK') return <Bot size={14} />
  if (kind === 'PROOF') return <Activity size={14} />
  if (kind === 'INCIDENT') return <Radar size={14} />
  return <BrainCircuit size={14} />
}

function storyStepMatches(path: string, pathname: string, search: string) {
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

async function checkReadiness() {
  try {
    const response = await fetch('/health/ready', { cache: 'no-store' })
    return response.ok
  } catch {
    return false
  }
}
