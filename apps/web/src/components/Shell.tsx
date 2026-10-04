import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  Bot,
  BrainCircuit,
  CircleDot,
  Radar,
  Search,
  Sparkles,
  Telescope,
  Waypoints,
} from 'lucide-react'
import { NavLink, useNavigate } from 'react-router-dom'

const nav = [
  { to: '/', label: 'WORLD', icon: Radar },
  { to: '/intelligence', label: 'INTELLIGENCE', icon: BrainCircuit },
  { to: '/investigations', label: 'INVESTIGATIONS', icon: Telescope },
  { to: '/agents', label: 'AGENTS', icon: Bot },
  { to: '/observatory', label: 'OBSERVATORY', icon: Activity },
]

export function Shell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const searchRef = useRef<HTMLInputElement>(null)
  const [searchValue, setSearchValue] = useState('')
  const [searchError, setSearchError] = useState('')
  const readiness = useQuery({ queryKey: ['shell-readiness'], queryFn: checkReadiness, refetchInterval: 15_000, retry: false })

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchRef.current?.focus()
        searchRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    const value = searchValue.trim().toUpperCase()
    if (!value) return
    if (!/^CVE-\d{4}-\d+$/.test(value)) {
      setSearchError('Use a canonical CVE ID')
      return
    }
    setSearchError('')
    navigate(`/intelligence?cve=${encodeURIComponent(value)}`)
  }

  const readinessState = readiness.isLoading ? 'checking' : readiness.data ? 'ready' : 'degraded'

  return (
    <div className="app-shell">
      <aside className="rail">
        <button className="brand" onClick={() => navigate('/')} aria-label="SecFusionAgent home">
          <span className="brand-mark"><Waypoints size={22} /></span>
          <span className="brand-copy">
            <strong>SecFusionAgent</strong>
            <small>EVIDENCE INTELLIGENCE</small>
          </span>
        </button>

        <nav className="rail-nav" aria-label="Primary navigation">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `rail-link ${isActive ? 'active' : ''}`}>
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <button className="start-orb" onClick={() => navigate('/start')}>
          <span className="start-orb-core"><Sparkles size={19} /></span>
          <strong>START</strong>
          <small>GLOBAL ANALYSIS</small>
        </button>

        <div className="system-mini">
          <div><span className={`live-dot state-${readinessState}`} /> PRODUCT APP</div>
          <small>{readiness.data ? 'API readiness verified' : readiness.isLoading ? 'Checking API readiness' : 'Runtime degraded / unavailable'}</small>
          <small>Evidence-first product surface</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <form className={`search-shell ${searchError ? 'invalid' : ''}`} onSubmit={submitSearch}>
            <Search size={16} />
            <input ref={searchRef} aria-label="Jump to CVE" value={searchValue} onChange={(event) => { setSearchValue(event.target.value); if (searchError) setSearchError('') }} placeholder={searchError || 'Jump to CVE…'} />
            <kbd>⌘K</kbd>
          </form>
          <div className="topbar-state">
            <span className={`live-pill readiness-${readinessState}`}><CircleDot size={13} /> {readiness.isLoading ? 'CHECKING' : readiness.data ? 'API READY' : 'DEGRADED'}</span>
            <span className="demo-user">DEMO / ANALYST</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}

async function checkReadiness() {
  try {
    const response = await fetch('/health/ready', { cache: 'no-store' })
    return response.ok
  } catch {
    return false
  }
}
