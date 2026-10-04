import { Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { StartPage } from './pages/StartPage'
import { WorldPage } from './pages/WorldPage'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<WorldPage />} />
        <Route path="/start" element={<StartPage />} />
        <Route path="/intelligence" element={<PlaceholderPage eyebrow="EVIDENCE-FIRST DOSSIERS" title="INTELLIGENCE" description="Vulnerability / Incident dossier、focused graph 与 Evidence Inspector。" items={['VULNERABILITY DOSSIER', 'FOCUSED KNOWLEDGE GRAPH', 'EVIDENCE INSPECTOR', 'INCIDENT CONTEXT']} />} />
        <Route path="/investigations" element={<PlaceholderPage eyebrow="DURABLE CASE · CONTINUOUS SESSION" title="INVESTIGATIONS" description="Case state、ProductEvent/SSE、持续会话与 Decision 收束。" items={['CASE FILE', 'LIVE ACTIVITY', 'EVIDENCE NEEDS', 'SESSION FOLLOW-UP']} />} />
        <Route path="/agents" element={<PlaceholderPage eyebrow="ROLE · TASK · SKILL · EXPERIENCE" title="AGENT OPERATIONS" description="ORACLE / ARGUS / ALCHEMIST 的真实 Task、Capability、Skill 与 Experience。" items={['ORACLE', 'ARGUS', 'ALCHEMIST', 'TASK ORCHESTRATION']} />} />
        <Route path="/observatory" element={<PlaceholderPage eyebrow="LIVE RUNTIME · FROZEN PROOF" title="OBSERVATORY" description="Data Plane 曲线、source health、Agent runtime 与正式 benchmark proof。" items={['LIVE DATA PLANE', 'SOURCE HEALTH', 'AGENT RUNTIME', 'FORMAL PROOF']} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}
