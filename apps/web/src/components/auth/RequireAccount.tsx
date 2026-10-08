import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ArrowRight, LockKeyhole } from 'lucide-react'
import { safeAccountReturnTo, useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'

export function AccountLoginPrompt({ title, description }: { title: string; description: string }) {
  const auth = useAuth()
  const { text } = useI18n()
  const location = useLocation()
  const returnTo = safeAccountReturnTo(`${location.pathname}${location.search}${location.hash}`)
  if (auth.loading) return <div className="account-required" role="status">{text('正在确认登录状态…', 'Checking your sign-in…')}</div>
  if (auth.error) return <div className="account-required" role="alert"><p>{text('暂时无法确认账户，请重试。', 'Your account could not be checked. Please retry.')}</p><button type="button" onClick={() => void auth.refresh()}>{text('重试', 'Retry')}</button></div>
  return <section className="account-required">
    <LockKeyhole size={21} aria-hidden="true" />
    <div><h3>{title}</h3><p>{description}</p></div>
    <Link className="ew-primary" to={`/auth?${new URLSearchParams({ returnTo }).toString()}`}>{text('登录并继续', 'Sign in to continue')}<ArrowRight size={15} /></Link>
  </section>
}

export function RequireAccount({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const { text } = useI18n()
  if (auth.loading) return <div className="account-required" role="status">{text('正在确认登录状态…', 'Checking your sign-in…')}</div>
  if (auth.error) return <div className="account-required" role="alert"><p>{text('暂时无法确认账户，请重试后继续。', 'Your account could not be checked. Retry to continue.')}</p><button type="button" onClick={() => void auth.refresh()}>{text('重试', 'Retry')}</button></div>
  if (!auth.authenticated) return <AccountLoginPrompt title={text('登录后继续你的工作', 'Sign in to continue your work')} description={text('你的提问、调查与任务会保存在账户下。', 'Your questions, investigations and tasks stay with your account.')} />
  return children
}
