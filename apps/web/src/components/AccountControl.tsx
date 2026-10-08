import { useState } from 'react'
import { ChevronDown, LogIn, LogOut } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { safeAccountReturnTo, useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'

export function AccountControl() {
  const auth = useAuth()
  const { text } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const [failed, setFailed] = useState(false)
  const returnTo = safeAccountReturnTo(`${location.pathname}${location.search}${location.hash}`)

  if (auth.loading) return <div className="account-control account-loading" role="status">{text('读取账户…', 'Loading account…')}</div>
  if (auth.error) return <div className="account-control account-unavailable"><button type="button" onClick={() => void auth.refresh()}>{text('重试账户', 'Retry account')}</button></div>
  if (!auth.authenticated || !auth.user) return <div className="account-control">
    <Link className="account-login" to={`/auth?${new URLSearchParams({ returnTo }).toString()}`}><LogIn size={15} /><span>{text('登录', 'Sign in')}</span></Link>
  </div>

  async function signOut() {
    setFailed(false)
    try {
      await auth.logout()
      navigate('/', { replace: true })
    } catch { setFailed(true) }
  }

  return <details className="account-control account-menu">
    <summary aria-label={text('打开账户菜单', 'Open account menu')}><span>{auth.user.display_name}</span><ChevronDown size={13} /></summary>
    <div className="account-menu-panel">
      <strong>{auth.user.display_name}</strong><small>{auth.user.email}</small>
      <button type="button" disabled={auth.isBusy} onClick={() => void signOut()}><LogOut size={15} />{auth.isBusy ? text('正在退出…', 'Signing out…') : text('退出登录', 'Sign out')}</button>
      {failed && <p role="alert">{text('退出未完成，请重试。', 'Sign out did not finish. Please retry.')}</p>}
    </div>
  </details>
}
