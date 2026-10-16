import { Component, Suspense, lazy, type ErrorInfo, type ReactNode } from 'react'
import { AnimatePresence, LazyMotion, useReducedMotion } from 'motion/react'
import * as motion from 'motion/react-m'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Shell } from './components/Shell'
import { useI18n } from './lib/i18n'
import { RequireAccount } from './components/auth/RequireAccount'

const loadMotionFeatures = () => import('./lib/motionFeatures').then(module => module.default)

const WorldPage = lazy(() => import('./pages/WorldPage').then((module) => ({ default: module.WorldPage })))
const QuestionsPage = lazy(() => import('./pages/QuestionsPage').then((module) => ({ default: module.QuestionsPage })))
const IntelligencePage = lazy(() => import('./pages/IntelligencePage').then((module) => ({ default: module.IntelligencePage })))
const InvestigationsPage = lazy(() => import('./pages/InvestigationsPage').then((module) => ({ default: module.InvestigationsPage })))
const AgentsPage = lazy(() => import('./pages/AgentsPage').then((module) => ({ default: module.AgentsPage })))
const ObservatoryPage = lazy(() => import('./pages/ObservatoryPage').then((module) => ({ default: module.ObservatoryPage })))
const WorkspacePage = lazy(() => import('./pages/WorkspacePage').then((module) => ({ default: module.WorkspacePage })))
const AuthPage = lazy(() => import('./pages/AuthPage').then((module) => ({ default: module.AuthPage })))

export default function App() {
  const location = useLocation()
  const reduceMotion = Boolean(useReducedMotion())
  const transition = routeTransition(location.pathname, reduceMotion)
  const routeSpace = routeSpaceName(location.pathname)
  const selection = new URLSearchParams(location.search)
  const intelligenceIdentity = ['object', 'incident', 'cve', 'q', 'hot'].map(key => selection.get(key) ?? '').join('|')

  return (
    <ProductErrorBoundary key={location.pathname}>
      <LazyMotion features={loadMotionFeatures}>
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
              <Routes location={location}>
                <Route path="/" element={<WorldPage />} />
                <Route path="/auth" element={<AuthPage />} />
                <Route path="/workspace/*" element={<RequireAccount><WorkspacePage /></RequireAccount>} />
                <Route path="/start" element={<RequireAccount><QuestionsPage /></RequireAccount>} />
                <Route path="/intelligence" element={<IntelligencePage key={`intelligence:${intelligenceIdentity}`} />} />
                <Route path="/investigations" element={<RequireAccount><InvestigationsPage /></RequireAccount>} />
                <Route path="/agents" element={<RequireAccount><AgentsPage /></RequireAccount>} />
                <Route path="/observatory" element={<ObservatoryPage key={`observatory:${location.search}`} />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </Suspense>
      </Shell>
      </LazyMotion>
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
          <small>SECFUSION</small>
          <strong>当前空间未能完成渲染</strong>
          <p>可以重新打开当前页面，或返回世界继续浏览。</p>
        </div>
        <div className="product-render-fault-actions">
          <button onClick={() => window.location.reload()}>重新装载</button>
          <button onClick={() => window.location.assign(import.meta.env.BASE_URL)}>返回世界</button>
        </div>
      </main>
    )
  }
}

function routeSpaceName(pathname: string) {
  if (pathname.startsWith('/workspace')) return 'workspace'
  if (pathname.startsWith('/auth')) return 'auth'
  if (pathname.startsWith('/start')) return 'start'
  if (pathname.startsWith('/intelligence')) return 'intelligence'
  if (pathname.startsWith('/investigations')) return 'investigations'
  if (pathname.startsWith('/agents')) return 'agents'
  if (pathname.startsWith('/observatory')) return 'observatory'
  return 'world'
}

function routeTransition(pathname: string, reduceMotion = false) {
  return {
    duration: reduceMotion ? 0 : .16,
    initial: { opacity: reduceMotion ? 1 : 0, y: reduceMotion || pathname === '/' ? 0 : 6 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 0 },
  }
}

function ProductSpaceLoader({ space }: { space: ReturnType<typeof routeSpaceName> }) {
  const { text } = useI18n()
  const label = {
    auth: text('正在打开账户…', 'Opening your account…'),
    workspace: text('正在打开工作空间…', 'Opening your workspace…'),
    world: text('正在读取世界动态…', 'Loading world activity…'),
    start: text('正在打开问答…', 'Opening your conversation…'),
    intelligence: text('正在读取情报…', 'Loading intelligence…'),
    investigations: text('正在读取调查…', 'Loading your investigations…'),
    agents: text('正在读取任务…', 'Loading tasks…'),
    observatory: text('正在读取运行状态…', 'Loading service state…'),
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
        <small>SECFUSION</small>
      </div>
    </div>
  )
}
