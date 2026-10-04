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
          <div><span className="live-dot" /> PRODUCT P0</div>
          <small>World shell online</small>
          <small>Runtime views connecting</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="search-shell">
            <Search size={16} />
            <input aria-label="Search" placeholder="Search CVE, entity, source…" />
            <kbd>⌘K</kbd>
          </div>
          <div className="topbar-state">
            <span className="live-pill"><CircleDot size={13} /> LIVE</span>
            <span className="demo-user">DEMO / ANALYST</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}
