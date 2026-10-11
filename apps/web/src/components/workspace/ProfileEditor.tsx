import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Card, CardContent } from '../ui/card'
import { useDeferredValue, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check } from "@phosphor-icons/react/dist/csr/Check"
import { Plus } from "@phosphor-icons/react/dist/csr/Plus"
import { MagnifyingGlass as Search } from "@phosphor-icons/react/dist/csr/MagnifyingGlass"
import { X } from "@phosphor-icons/react/dist/csr/X"
import { Link } from 'react-router-dom'
import { updateAccountProfile } from '../../lib/api/auth'
import { getIntelligencePreferences, resolveIntelligenceFollow, saveIntelligencePreferences, type FollowedIntelligenceObject, type IntelligencePreferences } from '../../lib/api/recommendations'
import { useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'

export function ProfileEditor() {
  const { text } = useI18n()
  const preferences = useQuery({ queryKey: ['intelligence-preferences'], queryFn: getIntelligencePreferences })
  return <div className="workspace-profile">
    <header className="workspace-heading"><h1>{text('资料与偏好', 'Profile & preferences')}</h1><p>{text('管理个人资料、关注关键词与对象。', 'Manage your profile, topics, and followed objects.')}</p></header>
    <IdentityEditor />
    {preferences.isPending ? <p className="empty-block" role="status">{text('正在读取关注设置…', 'Loading interests…')}</p> : preferences.isError ? <div className="error-block" role="alert">{text('无法读取关注设置。', 'Could not load your interests.')}<button onClick={() => void preferences.refetch()}>{text('重试', 'Retry')}</button></div> : <InterestsEditor preferences={preferences.data} />}
  </div>
}

function IdentityEditor() {
  const auth = useAuth()
  const { text } = useI18n()
  const [draft, setDraft] = useState<string | null>(null)
  const mutation = useMutation({ mutationFn: updateAccountProfile, onSuccess: async () => { await auth.refresh(); setDraft(null) } })
  function submit(event: FormEvent) { event.preventDefault(); mutation.mutate((draft ?? auth.user?.display_name ?? '').trim()) }
  return <Card><CardContent className="profile-identity"><div><h2>{text('个人资料', 'Profile')}</h2><p>{text('这个名字会显示在你的工作空间。', 'Your name appears in your workspace.')}</p></div><form onSubmit={submit}>
    <label>{text('显示名称', 'Display name')}<Input value={draft ?? auth.user?.display_name ?? ''} onChange={event => setDraft(event.target.value)} required maxLength={80} autoComplete="nickname" /></label>
    <label>{text('账户邮箱', 'Account email')}<Input value={auth.user?.email ?? ''} readOnly type="email" /></label>
    <div className="profile-save"><Button disabled={mutation.isPending || !(draft ?? auth.user?.display_name)?.trim()}>{mutation.isPending ? text('保存中…', 'Saving…') : text('保存资料', 'Save profile')}</Button>{mutation.isSuccess && draft === null && <span role="status"><Check size={14}/>{text('已保存', 'Saved')}</span>}{mutation.isError && <span className="profile-error" role="alert">{text('保存失败，请重试。', 'Could not save. Please retry.')}</span>}</div>
  </form></CardContent></Card>
}

function InterestsEditor({ preferences }: { preferences: IntelligencePreferences }) {
  const { text } = useI18n()
  const queryClient = useQueryClient()
  const [keywords, setKeywords] = useState(preferences.keywords)
  const [targets, setTargets] = useState<FollowedIntelligenceObject[]>(preferences.target_object_ids.map(id => preferences.target_objects.find(item => item.object_id === id) ?? { object_id: id, object_type: 'Object', canonical_key: id, label: text('暂时不可用的对象', 'Temporarily unavailable object') }))
  const [search, setSearch] = useState('')
  const searchQuery = useDeferredValue(search.trim())
  const objects = useQuery({ queryKey: ['profile-object-search', searchQuery], queryFn: () => resolveIntelligenceFollow(searchQuery), enabled: searchQuery.length >= 2 })
  const save = useMutation({ mutationFn: () => saveIntelligencePreferences({ keywords, target_object_ids: targets.map(target => target.object_id) }), onSuccess: async data => {
    queryClient.setQueryData(['intelligence-preferences'], data)
    setKeywords(data.keywords)
    await queryClient.invalidateQueries({ queryKey: ['intelligence-recommendations'] })
    await queryClient.invalidateQueries({ queryKey: ['intelligence-feed'] })
  } })
  function addKeyword(value: string) {
    const next = value.trim()
    if (next && !keywords.some(item => item.toLocaleLowerCase() === next.toLocaleLowerCase())) setKeywords(current => [...current, next].slice(0, 20))
    setSearch(''); save.reset()
  }
  const exact = searchQuery === search.trim() ? objects.data?.exact_match : null
  return <Card><CardContent className="profile-interests">
    <div className="profile-section-title"><div><h2>{text('我的关注', 'Your interests')}</h2><p>{text('输入名称查找具体对象，或明确保存为关注主题。', 'Find an object by name, or explicitly save a topic.')}</p></div><span>{keywords.length + targets.length} {text('项关注', 'interests')}</span></div>
    <div className="profile-interest-group"><h3>{text('关注领域', 'Topics')} <small>{keywords.length}/20</small></h3><div className="profile-chips">{keywords.map(value => <button key={value} onClick={() => { setKeywords(items => items.filter(item => item !== value)); save.reset() }} aria-label={text(`移除 ${value}`, `Remove ${value}`)}>#{value}<X size={13}/></button>)}</div>
    </div>
    <div className="profile-interest-group"><h3>{text('关注对象', 'Follow specific objects')} <small>{targets.length}/20</small></h3><div className="profile-targets">{targets.map(target => <div key={target.object_id}><Link to={`/intelligence?channel=following&object=${encodeURIComponent(target.object_id)}`}>{target.label}</Link><button aria-label={text(`取消关注 ${target.label}`, `Unfollow ${target.label}`)} onClick={() => { setTargets(items => items.filter(item => item.object_id !== target.object_id)); save.reset() }}><X size={14}/></button></div>)}</div>
      <div className="profile-object-search"><Search size={17}/><Input maxLength={128} value={search} onChange={event => setSearch(event.target.value)} placeholder={text('搜索项目、产品、论文或 CVE', 'Search projects, products, papers or CVEs')} aria-label={text('查找关注对象', 'Find objects to follow')}/></div>
      {search.trim() && <div className="flex flex-wrap gap-2 py-2"><Button disabled={!exact || targets.length >= 20 || targets.some(item => item.object_id === exact.object_id)} onClick={() => { if (exact) { setTargets(current => [...current, exact]); setSearch(''); save.reset() } }}><Plus size={15}/>{text('关注精确匹配对象', 'Follow exact match')}</Button><Button variant="outline" disabled={keywords.length >= 20} onClick={() => addKeyword(search)}>{text(`将「${search.trim()}」保存为主题`, `Save “${search.trim()}” as a topic`)}</Button></div>}
      {searchQuery.length >= 2 && <div className="profile-search-results">{objects.isPending ? <p role="status">{text('查找中…', 'Searching…')}</p> : objects.isError ? <button onClick={() => void objects.refetch()}>{text('读取失败，点击重试', 'Could not search. Retry')}</button> : objects.data?.candidates.length ? objects.data.candidates.map(item => <button key={item.object_id} disabled={targets.length >= 20 || targets.some(target => target.object_id === item.object_id)} onClick={() => { setTargets(current => [...current, item]); setSearch(''); save.reset() }}><span>{item.label}<small>{item.object_type} · {item.canonical_key}</small></span>{targets.some(target => target.object_id === item.object_id) ? <Check size={15}/> : <Plus size={15}/>}</button>) : <p>{text('未找到对象，可以保存为主题。', 'No object found. You can save this as a topic.')}</p>}</div>}
    </div>
    <div className="profile-save"><Button disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? text('保存中…', 'Saving…') : text('保存关注', 'Save interests')}</Button>{save.isSuccess && <span role="status"><Check size={14}/>{text('已保存，推荐将使用新的关注范围', 'Saved. Your recommendations will use these interests.')}<Link to="/intelligence">{text('查看推荐', 'View recommendations')}</Link></span>}{save.isError && <span className="profile-error" role="alert">{text('保存失败，请重试。', 'Could not save. Please retry.')}</span>}</div>
  </CardContent></Card>
}
