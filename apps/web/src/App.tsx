import { Component, Suspense, lazy, type ErrorInfo, type ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
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
  const reduceMotion = Boolean(useReducedMotion())
  const transition = routeTransition(location.pathname, reduceMotion)
  const routeSpace = routeSpaceName(location.pathname)
  const aperture = routeAperture(routeSpace, reduceMotion)

  return (
    <ProductErrorBoundary key={`${location.pathname}:${location.search}`}>
      <Shell>
        <Suspense fallback={<ProductSpaceLoader space={routeSpace} />}>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              className={`route-stage route-space-${routeSpace}`}
              initial={transition.initial}
              animate={transition.animate}
              exit={transition.exit}
              transition={{ duration: transition.duration, ease: [0.22, 1, 0.36, 1] }}
            >
              {!reduceMotion && (
                <motion.div
                  className={`route-aperture aperture-${routeSpace}`}
                  initial={aperture.initial}
                  animate={aperture.animate}
                  transition={{ duration: aperture.duration, ease: [0.16, 1, 0.3, 1] }}
                  aria-hidden="true"
                />
              )}
              <Routes location={location}>
                <Route path="/" element={<WorldPage />} />
                <Route path="/start" element={<StartPage key={`start:${location.search}`} />} />
                <Route path="/intelligence" element={<IntelligencePage key={`intelligence:${location.search}`} />} />
                <Route path="/investigations" element={<InvestigationsPage key={`investigations:${location.search}`} />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/observatory" element={<ObservatoryPage key={`observatory:${location.search}`} />} />
                <Route path="/demo" element={<Navigate to="/?guide=live" replace />} />
                <Route path="/demo/frozen" element={<Navigate to="/observatory?mode=proof&guide=frozen" replace />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </Suspense>
      </Shell>
    </ProductErrorBoundary>
  )
}

type ProductErrorBoundaryState = {
  failed: boolean
}

class ProductErrorBoundary extends Component<{ children: ReactNode }, ProductErrorBoundaryState> {
  state: ProductErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): ProductErrorBoundaryState {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error('SecFusion product render failure', error, info)
    }
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <main className="product-render-fault" role="alert">
        <div className="product-render-fault-mark" aria-hidden="true">!</div>
        <div>
          <small>PRODUCT RENDER BOUNDARY</small>
          <strong>当前空间未能完成渲染</strong>
          <p>Runtime 与持久数据没有因此被修改。可以重新装载当前空间，或返回 Evidence World。</p>
        </div>
        <div className="product-render-fault-actions">
          <button onClick={() => window.location.reload()}>重新装载</button>
          <button onClick={() => window.location.assign(import.meta.env.BASE_URL)}>返回 WORLD</button>
        </div>
      </main>
    )
  }
}

function routeAperture(space: ReturnType<typeof routeSpaceName>, reduceMotion = false) {
  if (reduceMotion) return {
    duration: 0,
    initial: { opacity: 0 },
    animate: { opacity: 0 },
  }
  if (space === 'world') return {
    duration: .62,
    initial: { opacity: .75, scale: .74, clipPath: 'ellipse(16% 34% at 50% 50%)' },
    animate: { opacity: 0, scale: 1.08, clipPath: 'ellipse(78% 82% at 50% 50%)' },
  }
  if (space === 'start') return {
    duration: .52,
    initial: { opacity: .88, scale: .8, rotate: -2, clipPath: 'circle(8% at 50% 48%)' },
    animate: { opacity: 0, scale: 1.12, rotate: 0, clipPath: 'circle(76% at 50% 48%)' },
  }
  if (space === 'intelligence') return {
    duration: .44,
    initial: { opacity: .72, x: 72, skewX: -2, clipPath: 'inset(0 0 0 72%)' },
    animate: { opacity: 0, x: 0, skewX: 0, clipPath: 'inset(0 0 0 0%)' },
  }
  if (space === 'investigations') return {
    duration: .38,
    initial: { opacity: .72, x: -54, rotate: -.45, clipPath: 'polygon(0 0,34% 0,29% 100%,0 100%)' },
    animate: { opacity: 0, x: 0, rotate: 0, clipPath: 'polygon(0 0,100% 0,100% 100%,0 100%)' },
  }
  if (space === 'agents') return {
    duration: .52,
    initial: { opacity: .88, scale: .36, clipPath: 'circle(10% at 50% 36%)' },
    animate: { opacity: 0, scale: 1.16, clipPath: 'circle(74% at 50% 42%)' },
  }
  return {
    duration: .4,
    initial: { opacity: .86, scaleY: .02, transformOrigin: 'center top' },
    animate: { opacity: 0, scaleY: 1, transformOrigin: 'center top' },
  }
}

function routeSpaceName(pathname: string) {
  if (pathname.startsWith('/start')) return 'start'
  if (pathname.startsWith('/intelligence')) return 'intelligence'
  if (pathname.startsWith('/investigations')) return 'investigations'
  if (pathname.startsWith('/agents')) return 'agents'
  if (pathname.startsWith('/observatory')) return 'observatory'
  return 'world'
}

function routeTransition(pathname: string, reduceMotion = false) {
  if (reduceMotion) return {
    duration: 0,
    initial: { opacity: 1 },
    animate: { opacity: 1 },
    exit: { opacity: 1 },
  }
  const space = routeSpaceName(pathname)
  if (space === 'start') return {
    duration: .5,
    initial: { opacity: 0, scale: .94, clipPath: 'circle(16% at 50% 48%)', filter: 'brightness(1.28) blur(5px)' },
    animate: { opacity: 1, scale: 1, clipPath: 'circle(78% at 50% 48%)', filter: 'brightness(1) blur(0px)' },
    exit: { opacity: 0, scale: 1.025, clipPath: 'circle(22% at 50% 48%)', filter: 'brightness(1.18) blur(3px)' },
  }
  if (space === 'world') return {
    duration: .52,
    initial: { opacity: 0, scale: 1.035, filter: 'brightness(1.12) blur(5px)' },
    animate: { opacity: 1, scale: 1, filter: 'brightness(1) blur(0px)' },
    exit: { opacity: 0, scale: .992, filter: 'brightness(.9) blur(3px)' },
  }
  if (space === 'intelligence') return {
    duration: .42,
    initial: { opacity: 0, x: 34, rotateY: -1.5, filter: 'brightness(1.06) blur(2px)' },
    animate: { opacity: 1, x: 0, rotateY: 0, filter: 'brightness(1) blur(0px)' },
    exit: { opacity: 0, x: -18, rotateY: 1, filter: 'brightness(.94) blur(1px)' },
  }
  if (space === 'investigations') return {
    duration: .36,
    initial: { opacity: 0, x: -26, filter: 'contrast(1.06) blur(2px)' },
    animate: { opacity: 1, x: 0, filter: 'contrast(1) blur(0px)' },
    exit: { opacity: 0, x: 18, filter: 'contrast(.94) blur(1px)' },
  }
  if (space === 'agents') return {
    duration: .46,
    initial: { opacity: 0, y: 18, scale: .982, filter: 'brightness(1.3) blur(4px)' },
    animate: { opacity: 1, y: 0, scale: 1, filter: 'brightness(1) blur(0px)' },
    exit: { opacity: 0, y: -10, scale: .992, filter: 'brightness(.8) blur(2px)' },
  }
  if (space === 'observatory') return {
    duration: .34,
    initial: { opacity: 0, clipPath: 'inset(0 0 100% 0)', filter: 'brightness(1.18)' },
    animate: { opacity: 1, clipPath: 'inset(0 0 0% 0)', filter: 'brightness(1)' },
    exit: { opacity: 0, clipPath: 'inset(100% 0 0 0)', filter: 'brightness(.88)' },
  }
  return {
    duration: .4,
    initial: { opacity: 0, scale: .99, filter: 'blur(2px)' },
    animate: { opacity: 1, scale: 1, filter: 'blur(0px)' },
    exit: { opacity: 0, scale: .99, filter: 'blur(1px)' },
  }
}

function ProductSpaceLoader({ space }: { space: ReturnType<typeof routeSpaceName> }) {
  const label = {
    world: 'RESOLVING EVIDENCE WORLD',
    start: 'PREPARING MISSION CONTROL',
    intelligence: 'OPENING CANONICAL DOSSIER',
    investigations: 'RESOLVING DURABLE CASE',
    agents: 'RESOLVING AGENT RUNTIME',
    observatory: 'RESOLVING MEASUREMENT SPACE',
  }[space]

  return (
    <div className={`product-space-loader loader-space-${space}`} role="status" aria-live="polite">
      {space === 'world' && <div className="loader-world"><i /><i /><i /><span /></div>}
      {space === 'start' && <div className="loader-start"><i /><i /><b /></div>}
      {space === 'intelligence' && <div className="loader-intelligence"><i /><i /><i /><i /></div>}
      {space === 'investigations' && <div className="loader-investigations"><i /><i /><i /></div>}
      {space === 'agents' && <div className="loader-agents"><i /><i /><i /><span /></div>}
      {space === 'observatory' && <div className="loader-observatory"><svg viewBox="0 0 100 32" preserveAspectRatio="none"><path d="M0 22 L13 22 L18 11 L24 28 L32 16 L39 20 L47 8 L56 24 L64 18 L75 18 L82 12 L89 23 L100 19" /></svg></div>}
      <div className="loader-core">
        <strong>{label}</strong>
        <small>SECFUSION / PRODUCT READ</small>
      </div>
    </div>
  )
}
