import { Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { AgentsPage } from './pages/AgentsPage'
import { IntelligencePage } from './pages/IntelligencePage'
import { ObservatoryPage } from './pages/ObservatoryPage'
import { InvestigationsPage } from './pages/InvestigationsPage'
import { StartPage } from './pages/StartPage'
import { WorldPage } from './pages/WorldPage'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<WorldPage />} />
        <Route path="/start" element={<StartPage />} />
        <Route path="/intelligence" element={<IntelligencePage />} />
        <Route path="/investigations" element={<InvestigationsPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/observatory" element={<ObservatoryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}
