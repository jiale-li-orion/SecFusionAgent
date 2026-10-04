import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { WorldPage } from './pages/WorldPage'

const StartPage = lazy(() => import('./pages/StartPage').then((module) => ({ default: module.StartPage })))
const IntelligencePage = lazy(() => import('./pages/IntelligencePage').then((module) => ({ default: module.IntelligencePage })))
const InvestigationsPage = lazy(() => import('./pages/InvestigationsPage').then((module) => ({ default: module.InvestigationsPage })))
const AgentsPage = lazy(() => import('./pages/AgentsPage').then((module) => ({ default: module.AgentsPage })))
const ObservatoryPage = lazy(() => import('./pages/ObservatoryPage').then((module) => ({ default: module.ObservatoryPage })))

export default function App() {
  return (
    <Shell>
      <Suspense fallback={<ProductSpaceLoader />}>
        <Routes>
          <Route path="/" element={<WorldPage />} />
          <Route path="/start" element={<StartPage />} />
          <Route path="/intelligence" element={<IntelligencePage />} />
          <Route path="/investigations" element={<InvestigationsPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/observatory" element={<ObservatoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Shell>
  )
}

function ProductSpaceLoader() {
  return (
    <div className="product-space-loader" role="status" aria-live="polite">
      <div className="loader-grid" />
      <div className="loader-core">
        <span className="loader-ring ring-a" />
        <span className="loader-ring ring-b" />
        <strong>RESOLVING PRODUCT SPACE</strong>
        <small>SecFusionAgent</small>
      </div>
      <div className="loader-scan" />
    </div>
  )
}
