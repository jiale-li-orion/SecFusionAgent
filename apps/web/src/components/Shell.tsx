import { Button } from './ui/button'
import { useReducedMotion } from 'motion/react'
import * as motion from 'motion/react-m'
import { UiThemeProvider } from './ui/theme'
import { lazy, Suspense, useDeferredValue, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import { ArrowUp } from "@phosphor-icons/react/dist/csr/ArrowUp"
import { ArrowDown } from "@phosphor-icons/react/dist/csr/ArrowDown"
import { GlobeHemisphereWest as Globe2 } from "@phosphor-icons/react/dist/csr/GlobeHemisphereWest"
import { Newspaper as Layers3 } from "@phosphor-icons/react/dist/csr/Newspaper"
import { ChatCircle as MessageCircle } from "@phosphor-icons/react/dist/csr/ChatCircle"
import { MagnifyingGlass as Search } from "@phosphor-icons/react/dist/csr/MagnifyingGlass"
import { UserCircle as UserRound } from "@phosphor-icons/react/dist/csr/UserCircle"
import { X } from "@phosphor-icons/react/dist/csr/X"
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ProductGlyph } from './instrument/ProductGlyph'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { getAgentRuntime, getHotWorld, listIncidents, listInvestigations, searchIntelligence } from '../lib/api'
import { buildCommandItems, shouldSearchGlobalKnowledge, type CommandObjectItem } from '../lib/shellPresentation'

const AccountControl = lazy(() => import('./AccountControl').then(module => ({ default: module.AccountControl })))
const WorkspaceNavigation = lazy(() => import('./workspace/WorkspaceNavigation').then(module => ({ default: module.WorkspaceNavigation })))

export function Shell({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  const { language, setLanguage, text } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const reducedMotion = useReducedMotion()
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const [commandIndex, setCommandIndex] = useState(0)
  const searchRef = useRef<HTMLInputElement>(null)
  const deferredSearchValue = useDeferredValue(searchValue.trim())
  const workspace = /^\/(workspace|agents|observatory|investigations)(\/|$)/.test(location.pathname)
  const space = workspace ? 'workspace' : location.pathname === '/' ? 'world' : location.pathname.split('/')[1]
  const shellTheme = 'light'
  const shellThemeClass = 'ui-day'
  const hot = useQuery({ queryKey: ['command-hot'], queryFn: () => getHotWorld(8), enabled: searchOpen, staleTime: 20_000 })
  const cases = useQuery({ queryKey: ['command-cases'], queryFn: () => listInvestigations(20), enabled: searchOpen && auth.authenticated, staleTime: 15_000 })
  const agents = useQuery({ queryKey: ['command-agents'], queryFn: getAgentRuntime, enabled: searchOpen && auth.authenticated, staleTime: 20_000 })
  const incidents = useQuery({ queryKey: ['command-incidents'], queryFn: () => listIncidents(8), enabled: searchOpen, staleTime: 20_000 })
  const knowledge = useQuery({ queryKey: ['command-knowledge', deferredSearchValue], queryFn: () => searchIntelligence(deferredSearchValue, 12), enabled: searchOpen && shouldSearchGlobalKnowledge(deferredSearchValue), staleTime: 20_000 })
  const items = buildCommandItems({ knowledge: knowledge.data?.items ?? [], hot: hot.data?.items ?? [], cases: cases.data?.items ?? [], tasks: agents.data?.recent_tasks ?? [], incidents: incidents.data?.items ?? [], query: searchValue })
  const loading = hot.isLoading || cases.isLoading || agents.isLoading || incidents.isLoading || knowledge.isLoading
  const failed = hot.isError || cases.isError || agents.isError || incidents.isError || knowledge.isError

  function openItem(item: CommandObjectItem) {
    navigate(item.path)
    setSearchOpen(false)
    setSearchValue('')
  }
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(open => !open)
        setCommandIndex(0)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const nav = [
    { path: '/', key: 'world', label: text('世界', 'World'), icon: Globe2 },
    { path: '/intelligence', key: 'intelligence', label: text('情报', 'Intelligence'), icon: Layers3 },
    { path: '/start', key: 'start', label: text('问答', 'Ask'), icon: MessageCircle },
    { path: '/workspace', key: 'workspace', label: text('我的', 'Workspace'), icon: UserRound },
  ]

  return <UiThemeProvider theme={shellTheme}><div className={`product-shell shell-space-${space}`}>
    <a className="product-skip-link" href="#product-main">{text('跳到主内容', 'Skip to content')}</a>
    <UiThemeProvider theme="light"><header className="sf-header ui-day">
      <Link className="sf-brand" to="/" aria-label="SecFusion"><span className="sf-wordmark">sec<span>fusion</span></span></Link>
      <nav className="sf-navigation" aria-label={text('主导航', 'Main navigation')}>
        {nav.map(({ path, key, label, icon: Icon }) => <Link key={key} to={path} aria-current={space === key ? 'page' : undefined}>{space === key && <motion.span aria-hidden="true" className="sf-nav-selection" layoutId="primary-navigation" transition={reducedMotion ? { duration: 0 } : { type: 'spring', stiffness: 440, damping: 34 }} />}<Icon size={21} weight={space === key ? 'fill' : 'regular'} aria-hidden="true"/><span>{label}</span></Link>)}
      </nav>
      <div className="sf-header-tools">
        <Button variant="ghost" size="sm" className="sf-search-trigger" onClick={() => { setSearchOpen(true); setCommandIndex(0) }} aria-label={text('搜索情报、事件和任务', 'Search intelligence, events and tasks')}><Search size={17} /><span>{text('搜索', 'Search')}</span><kbd>⌘ K</kbd></Button>
        <button className="sf-language" onClick={() => setLanguage(language === 'zh' ? 'en' : 'zh')} aria-label={text('切换英文', 'Switch to Chinese')}>{language === 'zh' ? 'EN' : '中'}</button>
        <Suspense fallback={<span className="text-xs text-muted-foreground" role="status">{text('读取账户…', 'Loading account…')}</span>}><AccountControl /></Suspense>
      </div>
    </header></UiThemeProvider>
    <main id="product-main" className={`product-workspace ${shellThemeClass}`} tabIndex={-1}>
      {workspace && location.pathname !== '/workspace' && <Suspense fallback={null}><WorkspaceNavigation /></Suspense>}
      <div className="studio-page-content">{children}</div>
    </main>
    <Dialog.Root open={searchOpen} onOpenChange={setSearchOpen}>
      <Dialog.Portal><Dialog.Overlay className={`sf-dialog-overlay ${shellThemeClass}`} /><Dialog.Content className={`sf-search-dialog ${shellThemeClass}`} onOpenAutoFocus={event => { event.preventDefault(); searchRef.current?.focus() }}>
        <Dialog.Title className="sr-only">{text('搜索情报、事件和任务', 'Search intelligence, events and tasks')}</Dialog.Title>
        <Dialog.Description className="sr-only">{text('输入关键词，用方向键选择结果，回车打开。', 'Search by keyword, use arrow keys to select, and Enter to open.')}</Dialog.Description>
        <div className="sf-search-input"><Search size={21} /><input ref={searchRef} value={searchValue} aria-label={text('搜索关键词', 'Search query')} placeholder={text('搜索事件、项目、漏洞或研究…', 'Search events, projects, vulnerabilities…')} onChange={event => { setSearchValue(event.target.value); setCommandIndex(0) }} onKeyDown={event => {
          if (event.key === 'ArrowDown') { event.preventDefault(); setCommandIndex(index => Math.min(index + 1, items.length - 1)) }
          if (event.key === 'ArrowUp') { event.preventDefault(); setCommandIndex(index => Math.max(index - 1, 0)) }
          if (event.key === 'Enter' && items[commandIndex]) openItem(items[commandIndex])
        }} /><Dialog.Close aria-label={text('关闭搜索', 'Close search')}><X size={19} /></Dialog.Close></div>
        <div className="sf-search-results">
          <p className="sf-search-caption">{loading ? text('正在查找…', 'Searching…') : searchValue ? text('搜索结果', 'Search results') : text('最近的情报与活动', 'Recent intelligence and activity')}</p>
          {items.map((item, index) => <button key={`${item.kind}:${item.ref}`} className={index === commandIndex ? 'selected' : ''} onClick={() => openItem(item)} onMouseEnter={() => setCommandIndex(index)}><ProductGlyph kind={item.kind === 'CASE' ? 'investigations' : item.kind === 'TASK' ? 'agents' : item.kind === 'INCIDENT' ? 'incidents' : 'intelligence'} size={19} /><span className="sf-search-result-copy"><strong>{item.label}</strong><small>{item.meta}</small></span></button>)}
          {!loading && !items.length && <p className="empty-block">{text('没有找到匹配内容，换一个关键词试试。', 'No matching results. Try another keyword.')}</p>}
          {failed && <p className="sf-search-caption" role="status">{text('部分内容暂时不可用，已展示成功读取的结果。', 'Some sources are unavailable. Available results are shown.')}</p>}
        </div>
        <footer className="sf-search-footer"><span className="sf-search-key-hints"><kbd aria-label={text('向上键', 'Up arrow')}><ArrowUp size={12} aria-hidden="true" /></kbd><kbd aria-label={text('向下键', 'Down arrow')}><ArrowDown size={12} aria-hidden="true" /></kbd><span>{text('选择', 'Select')}</span><kbd>Enter</kbd><span>{text('打开', 'Open')}</span></span><span className="sf-search-key-hints"><kbd>Esc</kbd><span>{text('关闭', 'Close')}</span></span></footer>
      </Dialog.Content></Dialog.Portal>
    </Dialog.Root>
  </div></UiThemeProvider>
}
