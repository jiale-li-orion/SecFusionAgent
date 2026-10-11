import { Activity, ChevronRight, LayoutDashboard, Network, Settings2, Telescope, UserRound } from '../ui/icons'
import { Link, useLocation } from 'react-router-dom'
import { useI18n } from '../../lib/i18n'

export function WorkspaceNavigation() {
  const { text } = useI18n()
  const { pathname } = useLocation()
  const operations = ['/agents', '/observatory', '/workspace/operations'].includes(pathname)
  const entries = operations ? [
    { to: '/workspace/operations', label: text('运行概览', 'Overview'), icon: LayoutDashboard },
    { to: '/agents', label: text('任务记录', 'Task records'), icon: Network },
    { to: '/observatory', label: text('服务状态', 'Service status'), icon: Activity },
  ] : [
    { to: '/workspace', label: text('我的空间', 'My workspace'), icon: UserRound },
    { to: '/investigations', label: text('我的调查', 'Investigations'), icon: Telescope },
    { to: '/workspace/profile', label: text('资料与偏好', 'Profile & interests'), icon: Settings2 },
  ]
  return <div className="workspace-navigation">
    {operations && <Link className="workspace-back" to="/workspace">{text('我的', 'Workspace')}<ChevronRight size={13} />{text('运行工作台', 'Operations')}</Link>}
    <nav aria-label={text('工作空间导航', 'Workspace navigation')}>{entries.map(({ to, label, icon: Icon }) => <Link key={to} to={to} aria-current={pathname === to ? 'page' : undefined}><Icon size={16} />{label}</Link>)}</nav>
  </div>
}
