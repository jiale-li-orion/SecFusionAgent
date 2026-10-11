import { useState } from 'react'
import { ChevronDown, LogIn, LogOut, Settings2, UserRound } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { safeAccountReturnTo, useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Avatar, AvatarFallback } from './ui/avatar'
import { Button } from './ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from './ui/dropdown-menu'

export function AccountControl() {
  const auth = useAuth()
  const { text } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const [failed, setFailed] = useState(false)
  const returnTo = safeAccountReturnTo(`${location.pathname}${location.search}${location.hash}`)

  if (auth.loading) return <span className="text-xs text-muted-foreground" role="status">{text('读取账户…', 'Loading account…')}</span>
  if (auth.error) return <Button variant="ghost" size="sm" onClick={() => void auth.refresh()}>{text('重试账户', 'Retry account')}</Button>
  if (!auth.authenticated || !auth.user) return <Button variant="outline" size="sm" asChild><Link to={`/auth?${new URLSearchParams({ returnTo })}`}><LogIn/>{text('登录', 'Sign in')}</Link></Button>

  async function signOut() {
    setFailed(false)
    try { await auth.logout(); navigate('/', { replace: true }) }
    catch { setFailed(true) }
  }

  return <DropdownMenu>
    <DropdownMenuTrigger asChild><Button variant="ghost" className="sf-account-trigger" aria-label={text('打开账户菜单', 'Open account menu')}><Avatar size="sm"><AvatarFallback>{Array.from(auth.user.display_name)[0]?.toUpperCase()}</AvatarFallback></Avatar><span>{auth.user.display_name}</span><ChevronDown className="size-3"/></Button></DropdownMenuTrigger>
    <DropdownMenuContent align="end" className="w-64" sideOffset={12}>
      <DropdownMenuLabel><div className="grid gap-1 py-1"><span className="text-sm font-semibold">{auth.user.display_name}</span><span className="text-xs font-normal text-muted-foreground">{auth.user.email}</span></div></DropdownMenuLabel>
      <DropdownMenuSeparator/>
      <DropdownMenuItem asChild><Link to="/workspace"><UserRound/>{text('我的空间', 'My workspace')}</Link></DropdownMenuItem>
      <DropdownMenuItem asChild><Link to="/workspace/profile"><Settings2/>{text('资料与偏好', 'Profile & interests')}</Link></DropdownMenuItem>
      <DropdownMenuSeparator/>
      <DropdownMenuItem disabled={auth.isBusy} onSelect={event => { event.preventDefault(); void signOut() }}><LogOut/>{auth.isBusy ? text('正在退出…', 'Signing out…') : text('退出登录', 'Sign out')}</DropdownMenuItem>
      {failed && <p className="px-2 py-2 text-xs text-destructive" role="alert">{text('退出未完成，请重试。', 'Sign out did not finish. Please retry.')}</p>}
    </DropdownMenuContent>
  </DropdownMenu>
}
