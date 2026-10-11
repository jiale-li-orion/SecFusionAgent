import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowUpRight, BookOpen, ChevronRight, Compass, History, LayoutDashboard, Network, Pencil, Plus, ShieldCheck, Telescope } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { AccountConversations } from '../components/start/AccountConversations'
import { ProfileEditor } from '../components/workspace/ProfileEditor'
import { OperationsOverview } from '../components/workspace/OperationsOverview'
import { getIntelligencePreferences } from '../lib/api/recommendations'
import { listAccountConversations, listInvestigations } from '../lib/api/investigations'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Avatar, AvatarFallback } from '../components/ui/avatar'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card'
import './workspace.css'
import './personal-space.css'

export function WorkspacePage() {
  const { pathname } = useLocation()
  if (pathname === '/workspace/profile') return <ProfileEditor />
  if (pathname === '/workspace/operations') return <OperationsOverview />
  return <PersonalWorkspace />
}

function PersonalWorkspace() {
  const auth = useAuth()
  const { text, language } = useI18n()
  const preferences = useQuery({ queryKey: ['intelligence-preferences'], queryFn: getIntelligencePreferences })
  const conversations = useQuery({ queryKey: ['account-conversations'], queryFn: ({ signal }) => listAccountConversations(20, signal), retry: false })
  const investigations = useQuery({ queryKey: ['workspace-investigations'], queryFn: () => listInvestigations(12), refetchInterval: 30_000 })
  const active = investigations.data?.items.filter(item => !['resolved', 'closed', 'cancelled', 'failed'].includes(item.status)) ?? []
  const interests = preferences.data
  const shortcuts = [
    { to: '/start?history=1', icon: History, title: text('会话记录', 'History') },
    { to: '/intelligence?channel=following', icon: Compass, title: text('关注情报', 'Following') },
    { to: '/investigations', icon: Telescope, title: text('调查报告', 'Reports') },
    { to: '/intelligence?channel=library', icon: BookOpen, title: text('资料库', 'Library') },
  ]
  const services = [
    { to: '/workspace/operations', icon: LayoutDashboard, title: text('运行概览', 'Overview'), description: text('任务进展与待处理事项', 'Progress and attention') },
    { to: '/agents', icon: Network, title: text('智能体与任务', 'Agents & tasks'), description: text('协作、工具与执行记录', 'Collaboration and execution') },
    { to: '/observatory', icon: Activity, title: text('数据与服务', 'Data & services'), description: text('来源健康与服务状态', 'Sources and service health') },
  ]
  return <div className="personal-space">
    <Card className="personal-identity rounded-none border-0 shadow-none">
      <CardContent>
        <div className="personal-profile-row">
          <Avatar className="personal-avatar"><AvatarFallback>{Array.from(auth.user?.display_name ?? 'S')[0]?.toUpperCase()}</AvatarFallback></Avatar>
          <div className="personal-profile-name"><h1>{auth.user?.display_name}</h1><p>{text('我的安全情报空间', 'Your security intelligence space')}</p></div>
          <Button variant="outline" size="sm" asChild><Link to="/workspace/profile"><Pencil/>{text('编辑资料', 'Edit profile')}</Link></Button>
        </div>
        <div className="personal-stats" aria-label={text('我的记录', 'Your activity')}>
          <div><strong>{conversations.data ? `${conversations.data.items.length}${conversations.data.has_more ? '+' : ''}` : '—'}</strong><span>{text('近期会话', 'Recent conversations')}</span></div>
          <div><strong>{interests ? interests.keywords.length + interests.target_object_ids.length : '—'}</strong><span>{text('我的关注', 'Interests')}</span></div>
          <div><strong>{investigations.data ? `${investigations.data.items.length}${investigations.data.has_more ? '+' : ''}` : '—'}</strong><span>{text('近期调查', 'Recent investigations')}</span></div>
        </div>
        <nav className="personal-shortcuts" aria-label={text('常用功能', 'Quick access')}>
          {shortcuts.map(({ to, icon: Icon, title }) => <Link to={to} key={to}><Icon size={24} strokeWidth={1.6}/><span>{title}</span></Link>)}
        </nav>
      </CardContent>
    </Card>

    <Card className="personal-services">
      <CardHeader><div className="personal-section-heading"><CardTitle>{text('运行工作台', 'Operations')}</CardTitle><Button size="sm" variant="ghost" asChild><Link to="/workspace/operations">{text('进入工作台', 'Open workspace')}<ArrowUpRight/></Link></Button></div><CardDescription>{text('查看安全情报背后的任务、协作与数据。', 'Tasks, collaboration, and the data behind your intelligence.')}</CardDescription></CardHeader>
      <CardContent><div className="personal-service-grid">{services.map(({ to, icon: Icon, title, description }) => <Link key={to} to={to}><span className="personal-service-icon"><Icon size={20}/></span><div><strong>{title}</strong><small>{description}</small></div><ChevronRight size={16}/></Link>)}</div></CardContent>
    </Card>

    <div className="personal-records">
      <Card className="personal-conversations rounded-none border-0 shadow-none"><CardContent><AccountConversations/></CardContent></Card>
      <Card className="personal-interests rounded-none border-0 shadow-none">
        <CardHeader><div className="personal-section-heading"><CardTitle>{text('我的关注', 'Your interests')}</CardTitle><Button variant="ghost" size="sm" asChild><Link to="/workspace/profile">{text('管理', 'Manage')}<ChevronRight/></Link></Button></div><CardDescription>{text('推荐会参考这些关键词和对象。', 'Your keywords and objects guide recommendations.')}</CardDescription></CardHeader>
        <CardContent>{preferences.isError ? <p className="personal-muted">{text('关注设置暂不可用。', 'Interests are unavailable.')}<Button variant="link" size="sm" onClick={() => void preferences.refetch()}>{text('重试', 'Retry')}</Button></p> : <div className="personal-interest-list">{interests?.keywords.map(keyword => <span key={keyword}>#{keyword}</span>)}{interests?.target_objects.slice(0, 4).map(object => <Link key={object.object_id} to={`/intelligence?object=${encodeURIComponent(object.object_id)}`}>{object.label}</Link>)}{interests && !interests.keywords.length && !interests.target_object_ids.length && <p className="personal-muted">{text('还没有设置关注。', 'No interests yet.')}</p>}<Button variant="outline" size="sm" asChild><Link to="/workspace/profile"><Plus/>{text('添加关注', 'Add an interest')}</Link></Button></div>}</CardContent>
      </Card>
      <Card className="personal-investigations rounded-none border-0 shadow-none">
        <CardHeader><div className="personal-section-heading"><CardTitle>{text('正在跟进', 'In progress')}</CardTitle><Button variant="ghost" size="sm" asChild><Link to="/investigations">{text('全部调查', 'All investigations')}<ChevronRight/></Link></Button></div></CardHeader>
        <CardContent>{investigations.isPending ? <p role="status" className="personal-muted">{text('读取调查中…', 'Loading investigations…')}</p> : investigations.isError ? <p role="alert" className="personal-muted">{text('暂时无法读取调查。', 'Investigations are unavailable.')}<Button variant="link" size="sm" onClick={() => void investigations.refetch()}>{text('重试', 'Retry')}</Button></p> : active.length ? <div className="workspace-case-list">{active.slice(0, 4).map(item => <Link key={item.case_id} to={`/investigations?case=${encodeURIComponent(item.case_id)}`}><span className={`workspace-status status-${item.status}`}/><div><strong>{item.goal}</strong><small>{new Date(item.updated_at).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US')} · {item.status === 'waiting' ? text('等待新证据', 'Awaiting evidence') : text('调查进行中', 'In progress')}</small></div><ArrowUpRight size={16}/></Link>)}</div> : <div className="personal-empty"><Telescope size={24}/><span>{text('暂无进行中的调查', 'No investigations in progress')}</span><Button variant="outline" size="sm" asChild><Link to="/start">{text('提出新问题', 'Ask a question')}<Plus/></Link></Button></div>}</CardContent>
      </Card>
    </div>
    <p className="personal-privacy"><ShieldCheck size={14}/>{text('会话和调查仅自己可见。', 'Your conversations and investigations are private.')}</p>
  </div>
}
