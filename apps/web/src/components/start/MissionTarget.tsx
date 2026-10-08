import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { searchIntelligence } from '../../lib/api/intelligence'
import { parseMissionTarget } from '../../lib/startMissionPresentation'
import { useI18n } from '../../lib/i18n'

export function MissionTarget({ value, label, optional, disabled, onChange }: { value: string; label: string; optional: boolean; disabled: boolean; onChange: (value: string, label: string) => void }) {
  const { text } = useI18n()
  const [search, setSearch] = useState('')
  const [direct, setDirect] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => { const timer = setTimeout(() => setDebounced(search.trim()), 250); return () => clearTimeout(timer) }, [search])
  const query = useQuery({ queryKey: ['mission-target-search', debounced], queryFn: () => searchIntelligence(debounced, 6), enabled: debounced.length > 1 && !disabled, retry: false })
  return <div className="mission-target-picker">
    <span>{text('调查对象', 'Target')} {optional ? text('· 可选', '· optional') : text('· 必选', '· required')}</span>
    {value ? <div className="mission-target-selection"><strong>{label || (value.startsWith('object:') ? text('已选择的情报对象', 'Selected intelligence object') : value)}</strong><button disabled={disabled} onClick={() => onChange('', '')} aria-label={text('更换调查对象', 'Change target')}><X size={15} /></button><details><summary>{text('对象坐标', 'Object coordinate')}</summary><code>{value}</code></details></div> : <>
      <label className="mission-target-search"><Search size={15} /><input value={search} disabled={disabled} onChange={e => setSearch(e.target.value)} placeholder={text('查找论文、仓库、漏洞或标准', 'Find a paper, repository, vulnerability or standard')} aria-label={text('查找调查对象', 'Find a target')} /></label>
      {query.isFetching && <small role="status">{text('查找中…', 'Searching…')}</small>}
      {query.isError && <button onClick={() => void query.refetch()}>{text('重试查找', 'Retry search')}</button>}
      {debounced.length > 1 && query.data && <div className="mission-target-results">{query.data.items.map(item => <button key={item.object_id} disabled={disabled} onClick={() => { onChange(`object:${item.object_id}`, item.label); setSearch('') }}><strong>{item.label}</strong><small>{item.object_type}</small></button>)}{!query.data.items.length && <small>{text('未找到匹配对象，可直接输入 CVE。', 'No matching object; you can enter a CVE directly.')}</small>}</div>}
      <details><summary>{text('直接输入 CVE 或对象坐标', 'Enter a CVE or object coordinate')}</summary><input value={direct} disabled={disabled} onChange={e => setDirect(e.target.value)} aria-label={text('直接输入调查目标', 'Enter target directly')} placeholder="CVE-YYYY-NNNN / object:…" /><button disabled={disabled || !parseMissionTarget(direct)} onClick={() => onChange(direct, '')}>{text('使用这个对象', 'Use this target')}</button></details>
    </>}
  </div>
}
