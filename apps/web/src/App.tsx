import { Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { AgentsPage } from './pages/AgentsPage'
import { IntelligencePage } from './pages/IntelligencePage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { StartPage } from './pages/StartPage'
import { WorldPage } from './pages/WorldPage'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<WorldPage />} />
        <Route path="/start" element={<StartPage />} />
        <Route path="/intelligence" element={<IntelligencePage />} />
        <Route path="/investigations" element={<PlaceholderPage eyebrow="DURABLE CASE · CONTINUOUS SESSION" title="INVESTIGATIONS" description="Case state、ProductEvent/SSE、持续会话与 Decision 收束。" items={['CASE FILE', 'LIVE ACTIVITY', 'EVIDENCE NEEDS', 'SESSION FOLLOW-UP']} />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/observatory" element={<PlaceholderPage eyebrow="LIVE RUNTIME · FROZEN PROOF" title="OBSERVATORY" description="Data Plane 曲线、source health、Agent runtime 与正式 benchmark proof。" items={['LIVE DATA PLANE', 'SOURCE HEALTH', 'AGENT RUNTIME', 'FORMAL PROOF']} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}
