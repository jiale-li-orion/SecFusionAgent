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
  X,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
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
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const [searchError, setSearchError] = useState('')
  const readiness = useQuery({
    queryKey: ['shell-readiness'],
    queryFn: checkReadiness,
    refetchInterval: 15_000,
    retry: false,
  })

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
        window.setTimeout(() => searchRef.current?.focus(), 0)
      }
      if (event.key === 'Escape') setSearchOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  function submitSearch(event: React.FormEvent) {
    event.preventDefault()
    const value = searchValue.trim().toUpperCase()
    if (!/^CVE-\d{4}-\d+$/.test(value)) {
      setSearchError('Use a canonical CVE ID')
      return
    }
    setSearchError('')
    setSearchOpen(false)
    navigate(`/intelligence?cve=${encodeURIComponent(value)}`)
  }

  const readinessState = readiness.isLoading ? 'checking' : readiness.data ? 'ready' : 'degraded'

  return (
    <div className="product-shell-v3">
      <header className="instrument-bar-v3">
        <button className="instrument-brand-v3" onClick={() => navigate('/')} aria-label="SecFusionAgent home">
          <span className="brand-sigil-v3"><Waypoints size={18} /></span>
          <span className="brand-copy-v3">
            <strong>SECFUSION</strong>
            <small>EVIDENCE INTELLIGENCE</small>
          </span>
        </button>

        <nav className="instrument-nav-v3" aria-label="Primary navigation">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setSearchOpen(false)}
              className={({ isActive }) => `instrument-nav-item-v3 ${isActive ? 'active' : ''}`}
            >
              <Icon size={14} strokeWidth={1.7} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="instrument-actions-v3">
          <button className="command-trigger-v3" onClick={() => setSearchOpen(true)} aria-label="Open command search">
            <Search size={14} />
            <span>JUMP</span>
            <kbd>⌘K</kbd>
          </button>
          <span className={`runtime-state-v3 state-${readinessState}`}>
            <CircleDot size={11} />
            {readiness.isLoading ? 'SYNC' : readiness.data ? 'READY' : 'DEGRADED'}
          </span>
          <button className="global-start-v3" onClick={() => navigate('/start')}>
            <span className="global-start-glyph-v3"><Sparkles size={14} /></span>
            <strong>START</strong>
          </button>
        </div>
      </header>

      <div className="shell-scan-v3" aria-hidden="true" />
      <main className="product-workspace-v3">{children}</main>

      <AnimatePresence>
        {searchOpen && (
          <motion.div
            className="command-lens-v3"
            role="dialog"
            aria-modal="true"
            aria-label="Jump to canonical CVE"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.form
              onSubmit={submitSearch}
              initial={{ y: -16, opacity: 0, scale: .985 }}
              animate={{ y: 0, opacity: 1, scale: 1 }}
              exit={{ y: -8, opacity: 0, scale: .99 }}
              transition={{ type: 'spring', stiffness: 280, damping: 26 }}
            >
              <span className="command-index-v3">01 / INTELLIGENCE JUMP</span>
              <div className={`command-input-line-v3 ${searchError ? 'invalid' : ''}`}>
                <Search size={20} />
                <input
                  ref={searchRef}
                  aria-label="Canonical CVE ID"
                  value={searchValue}
                  onChange={(event) => {
                    setSearchValue(event.target.value)
                    if (searchError) setSearchError('')
                  }}
                  placeholder={searchError || 'CVE-2026-…'}
                />
                <button type="button" onClick={() => setSearchOpen(false)} aria-label="Close command search">
                  <X size={17} />
                </button>
              </div>
              <div className="command-foot-v3">
                <span>CANONICAL CVE ONLY</span>
                <span>ENTER → OPEN DOSSIER</span>
                <span>ESC → CLOSE</span>
              </div>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>
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
