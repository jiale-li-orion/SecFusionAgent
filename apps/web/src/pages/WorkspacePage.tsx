import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowRight, ArrowUpRight, BookOpen, ChevronRight, Compass, History, LayoutDashboard, Network, Pencil, Plus, ShieldCheck, Telescope } from '../components/ui/icons'
import { Link, useLocation } from 'react-router-dom'
import { AccountConversations } from '../components/start/AccountConversations'
import { ProfileEditor } from '../components/workspace/ProfileEditor'
import { OperationsOverview } from '../components/workspace/OperationsOverview'
import { getIntelligencePreferences } from '../lib/api/recommendations'
import { listAccountConversations, listInvestigations } from '../lib/api/investigations'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { Avatar, AvatarFallback } from '../components/ui/avatar'
import { Item, ItemMedia, ItemContent, ItemTitle, ItemDescription, ItemActions } from '../components/ui/item'
import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
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
    { to: '/start?history=1', icon: History, title: text('会话', 'Conversations'), detail: text('接着上次的问题', 'Resume a question') },
    { to: '/intelligence?channel=following', icon: Compass, title: text('关注', 'Following'), detail: text('只看与你相关的', 'Your intelligence') },
    { to: '/investigations', icon: Telescope, title: text('调查', 'Investigations'), detail: text('报告与证据', 'Reports and evidence') },
    { to: '/intelligence?channel=library', icon: BookOpen, title: text('资料库', 'Library'), detail: text('查找原始材料', 'Explore sources') },
  ]
  const services = [
    { to: '/workspace/operations', icon: LayoutDashboard, title: text('运行概览', 'Operations'), description: text('任务进展与待处理事项', 'Progress and attention') },
    { to: '/agents', icon: Network, title: text('智能体与任务', 'Agents & tasks'), description: text('协作、工具与执行记录', 'Collaboration and execution') },
    { to: '/observatory', icon: Activity, title: text('数据与服务', 'Data & services'), description: text('来源健康与服务状态', 'Sources and service health') },
  ]

  return <div className="personal-space">
    <section className="personal-hero" aria-labelledby="personal-hero-title">
      <div className="personal-hero-main">
        <Avatar className="size-16"><AvatarFallback className="bg-primary/10 text-xl text-primary">{Array.from(auth.user?.display_name ?? 'S')[0]?.toUpperCase()}</AvatarFallback></Avatar>
        <div className="personal-profile-name"><h1 id="personal-hero-title">{auth.user?.display_name}</h1><p>{text('我的情报空间', 'Your intelligence space')}</p></div>
        <Button variant="outline" size="sm" asChild><Link to="/workspace/profile"><Pencil size={15}/>{text('编辑资料', 'Edit profile')}</Link></Button>
      </div>
      <div className="personal-hero-bottom">
        <div className="personal-stats" aria-label={text('我的记录', 'Your activity')}>
          <div><strong>{conversations.data ? `${conversations.data.items.length}${conversations.data.has_more ? '+' : ''}` : '—'}</strong><span>{text('近期会话', 'Recent conversations')}</span></div>
          <div><strong>{interests ? interests.keywords.length + interests.target_object_ids.length : '—'}</strong><span>{text('关注方向', 'Interests')}</span></div>
          <div><strong>{investigations.data ? `${investigations.data.items.length}${investigations.data.has_more ? '+' : ''}` : '—'}</strong><span>{text('近期调查', 'Recent investigations')}</span></div>
        </div>
        <div className="personal-hero-interests" aria-label={text('关注关键词', 'Followed topics')}>
          {interests?.keywords.slice(0, 3).map(keyword => <Badge variant="secondary" key={keyword}>{keyword}</Badge>)}
          {!interests?.keywords.length && <span>{text('定义你关心的方向', 'Set your interests')}</span>}
        </div>
      </div>
    </section>

    <nav className="personal-shortcuts" aria-label={text('常用功能', 'Quick access')}>
      {shortcuts.map(({ to, icon: Icon, title }) => <Button variant="ghost" className="h-auto flex-col gap-2 py-4" asChild key={to}><Link to={to}><span className="personal-shortcut-symbol"><Icon className="size-6" weight="regular"/></span><span>{title}</span></Link></Button>)}
    </nav>

    <div className="personal-records">
      <section className="personal-conversations"><AccountConversations/></section>
      <div className="personal-records-side">
        <section className="personal-investigations">
          <div className="personal-section-heading"><div><small>{text('你的进展', 'YOUR PROGRESS')}</small><h2>{text('正在跟进', 'In progress')}</h2></div><Link to="/investigations">{text('全部', 'All')}<ArrowUpRight size={15}/></Link></div>
          {investigations.isPending ? <p role="status" className="personal-muted">{text('读取调查中…', 'Loading investigations…')}</p> : investigations.isError ? <p role="alert" className="personal-muted">{text('暂时无法读取调查。', 'Investigations are unavailable.')}<Button variant="link" size="sm" onClick={() => void investigations.refetch()}>{text('重试', 'Retry')}</Button></p> : active.length ? <div className="workspace-case-list">{active.slice(0, 3).map(item => <Link key={item.case_id} to={`/investigations?case=${encodeURIComponent(item.case_id)}`}><span className={`workspace-status status-${item.status}`}/><div><strong>{item.goal}</strong><small>{new Date(item.updated_at).toLocaleDateString(language === 'zh' ? 'zh-CN' : 'en-US')} · {item.status === 'waiting' ? text('等待新证据', 'Awaiting evidence') : text('调查进行中', 'In progress')}</small></div><ArrowUpRight size={16}/></Link>)}</div> : <div className="personal-empty"><Telescope size={22}/><span>{text('暂无进行中的调查', 'No investigations in progress')}</span><Link to="/start">{text('提出新问题', 'Ask a question')}<ArrowRight size={14}/></Link></div>}
        </section>
        <section className="personal-interests"><div className="personal-section-heading"><div><small>{text('个人化情报', 'PERSONAL INTELLIGENCE')}</small><h2>{text('我的关注', 'Your interests')}</h2></div><Link to="/workspace/profile">{text('管理', 'Manage')}<ArrowUpRight size={15}/></Link></div><p>{text('推荐会参考这些关键词和对象。', 'These topics and objects guide your feed.')}</p>{preferences.isError ? <p className="personal-muted">{text('关注设置暂不可用。', 'Interests are unavailable.')}<Button variant="link" size="sm" onClick={() => void preferences.refetch()}>{text('重试', 'Retry')}</Button></p> : <div className="personal-interest-list">{interests?.keywords.map(keyword => <Badge variant="secondary" key={keyword}>{keyword}</Badge>)}{interests?.target_objects.slice(0, 4).map(object => <Link key={object.object_id} to={`/intelligence?object=${encodeURIComponent(object.object_id)}`}>{object.label}</Link>)}{interests && !interests.keywords.length && !interests.target_object_ids.length && <span>{text('还没有设置关注', 'No interests yet')}</span>}<Link className="personal-interest-add" to="/workspace/profile"><Plus size={14}/>{text('添加关注', 'Add interest')}</Link></div>}</section>
      </div>
    </div>

    <section className="personal-services" aria-labelledby="personal-services-title"><div className="personal-services-heading"><div><span className="personal-services-kicker">SECFUSION / SERVICES</span><h2 id="personal-services-title">{text('工作台与服务', 'Workspace & services')}</h2></div><img src={`${import.meta.env.BASE_URL}art/workspace-slides.webp`} width="96" height="96" alt="" aria-hidden="true" draggable={false}/></div><div className="personal-service-grid">{services.map(({ to, icon: Icon, title, description }) => <Item asChild key={to} className="rounded-none px-0"><Link to={to}><ItemMedia><Icon className="size-5 text-muted-foreground"/></ItemMedia><ItemContent><ItemTitle>{title}</ItemTitle><ItemDescription>{description}</ItemDescription></ItemContent><ItemActions><ChevronRight size={17}/></ItemActions></Link></Item>)}</div></section>
    <p className="personal-privacy"><ShieldCheck size={15}/>{text('会话和调查仅自己可见。', 'Your conversations and investigations are private.')}</p>
  </div>
}
