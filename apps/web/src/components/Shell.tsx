import { useDeferredValue, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowUpRight,
  CircleDot,
  Search,
  Waypoints,
  X,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { BrandMark, ProductGlyph } from './instrument/ProductGlyph'
import { AccountControl } from './AccountControl'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { getAgentRuntime, getHotWorld, listIncidents, listInvestigations, searchIntelligence } from '../lib/api'
import { buildCommandItems, buildContextTrace, checkReadiness, shouldSearchGlobalKnowledge, type CommandObjectItem, type CommandObjectKind } from '../lib/shellPresentation'

const nav = [
  { to: '/', label: 'WORLD', compact: 'WORLD', zh: '世界', sub: 'Evidence World', subZh: '证据世界', kind: 'world' },
  { to: '/intelligence', label: 'INTELLIGENCE', compact: 'INTEL', zh: '情报', sub: 'Objects & Knowledge', subZh: '对象与知识', kind: 'intelligence' },
  { to: '/investigations', label: 'INVESTIGATIONS', compact: 'CASES', zh: '调查', sub: 'Continuous Inquiry', subZh: '持续调查', kind: 'investigations' },
  { to: '/agents', label: 'AGENTS', compact: 'AGENTS', zh: '智能体', sub: 'Runtime & Memory', subZh: '运行与记忆', kind: 'agents' },
  { to: '/observatory', label: 'OBSERVATORY', compact: 'HEALTH', zh: '观测', sub: 'Operations & Health', subZh: '运行与健康', kind: 'observatory' },
]

export function Shell({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  const { language, setLanguage, text } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const shellRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const [searchOpen, setSearchOpen] = useState(false)
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
  const storyHot = useQuery({ queryKey: ['command-hot'], queryFn: () => getHotWorld(8), enabled: searchOpen, staleTime: 20_000 })
  const storyCases = useQuery({ queryKey: ['command-cases'], queryFn: () => listInvestigations(20), enabled: searchOpen && auth.authenticated, staleTime: 15_000 })
  const storyAgents = useQuery({ queryKey: ['command-agents'], queryFn: getAgentRuntime, enabled: searchOpen && auth.authenticated, staleTime: 15_000 })
  const commandIncidents = useQuery({ queryKey: ['command-incidents'], queryFn: () => listIncidents(8), enabled: searchOpen, staleTime: 20_000 })
  const commandKnowledge = useQuery({
    queryKey: ['command-knowledge', deferredSearchValue],
    queryFn: () => searchIntelligence(deferredSearchValue, 12),
    enabled: searchOpen && shouldSearchGlobalKnowledge(deferredSearchValue),
    staleTime: 20_000,
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
  const commandItems = buildCommandItems({
    knowledge: commandKnowledge.data?.items ?? [],
    hot: storyHot.data?.items ?? [],
    cases: storyCases.data?.items ?? [],
    tasks: storyAgents.data?.recent_tasks ?? [],
    incidents: commandIncidents.data?.items ?? [],
    query: searchValue,
  })
  const commandLoading = searchOpen && (storyHot.isLoading || storyCases.isLoading || storyAgents.isLoading || commandIncidents.isLoading || commandKnowledge.isLoading)

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
          <span className="brand-sigil"><BrandMark /></span>
          <span className="brand-copy">
            <strong>SECFUSION</strong>
            <small>EVIDENCE INTELLIGENCE</small>
          </span>
        </button>

        <nav className="instrument-nav" aria-label={text('主导航', 'Primary navigation')}>
          {nav.map(({ to, label, compact, zh, sub, subZh, kind }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              aria-label={text(zh, label)}
              onClick={() => setSearchOpen(false)}
              className={({ isActive }) => `instrument-nav-item ${isActive ? 'active' : ''}`}
            >
              <ProductGlyph kind={kind} size={23} />
              <span className="nav-copy"><strong className="nav-label-full">{text(zh, label)}</strong><strong className="nav-label-compact">{text(zh, compact)}</strong><small>{text(subZh, sub)}</small></span>
            </NavLink>
          ))}
        </nav>

        <div className="instrument-actions">
          <AccountControl />
          <button className="command-trigger" onClick={() => { setCommandIndex(0); setCommandKeyboardActive(false); setSearchOpen(true) }} aria-label={text('打开对象定位', 'Open command search')}>
            <Search size={14} />
            <span>{text('定位对象', 'LOCATE OBJECT')}</span>
            <kbd>⌘K</kbd>
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
            <span className="global-start-glyph"><ProductGlyph kind="start" size={19} /></span>
            <strong>{text('启动任务', 'START')}</strong>
          </button>
        </div>
      </aside>

      <div className="shell-scan" aria-hidden="true" />
      <main id="product-main" className="product-workspace" tabIndex={-1}><div className="studio-topbar"><span><BrandMark size={17} />SECFUSION / <b>{shellSpace.toUpperCase()}</b></span><div className="studio-topbar-actions"><button className="studio-start-action" onClick={() => navigate('/start')} aria-label={text('启动任务', 'Start a task')}><ProductGlyph kind="start" size={19}/><span>{text('启动任务', 'Start')}</span></button><button aria-label={text('搜索情报与调查', 'Search intelligence and investigations')} onClick={() => { setSearchOpen(true); setCommandIndex(0) }}><Search size={14}/>{text('搜索情报与调查', 'Search intelligence & investigations')}<kbd>⌘K</kbd></button></div></div>      <AnimatePresence>
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
<div className="studio-page-content">{children}</div></main>

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

function CommandObjectIcon({ kind }: { kind: CommandObjectKind }) {
  if (kind === 'CASE') return <ProductGlyph kind="investigations" size={19} />
  if (kind === 'TASK') return <ProductGlyph kind="agents" size={19} />
  if (kind === 'INCIDENT') return <ProductGlyph kind="incidents" size={19} />
  return <ProductGlyph kind="intelligence" size={19} />
}
