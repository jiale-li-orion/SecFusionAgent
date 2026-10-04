import { Suspense, lazy } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Shell } from './components/Shell'

const WorldPage = lazy(() => import('./pages/WorldPage').then((module) => ({ default: module.WorldPage })))
const StartPage = lazy(() => import('./pages/StartPage').then((module) => ({ default: module.StartPage })))
const IntelligencePage = lazy(() => import('./pages/IntelligencePage').then((module) => ({ default: module.IntelligencePage })))
const InvestigationsPage = lazy(() => import('./pages/InvestigationsPage').then((module) => ({ default: module.InvestigationsPage })))
const AgentsPage = lazy(() => import('./pages/AgentsPage').then((module) => ({ default: module.AgentsPage })))
const ObservatoryPage = lazy(() => import('./pages/ObservatoryPage').then((module) => ({ default: module.ObservatoryPage })))

export default function App() {
  const location = useLocation()

  return (
    <Shell>
      <Suspense fallback={<ProductSpaceLoader />}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            className="route-stage-v3"
            initial={{ opacity: 0, clipPath: 'inset(0 0 7% 0)' }}
            animate={{ opacity: 1, clipPath: 'inset(0 0 0% 0)' }}
            exit={{ opacity: 0, clipPath: 'inset(4% 0 0 0)' }}
            transition={{ duration: .28, ease: [0.22, 1, 0.36, 1] }}
          >
            <Routes location={location}>
              <Route path="/" element={<WorldPage />} />
              <Route path="/start" element={<StartPage />} />
              <Route path="/intelligence" element={<IntelligencePage />} />
              <Route path="/investigations" element={<InvestigationsPage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/observatory" element={<ObservatoryPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </Suspense>
    </Shell>
  )
}

function ProductSpaceLoader() {
  return (
    <div className="product-space-loader-v3" role="status" aria-live="polite">
      <div className="loader-field-v3" />
      <div className="loader-core-v3">
        <span />
        <span />
        <strong>RESOLVING PRODUCT SPACE</strong>
        <small>SECFUSION / PRODUCT RUNTIME</small>
      </div>
    </div>
  )
}
