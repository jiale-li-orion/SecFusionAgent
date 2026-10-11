import { useEffect, useState } from 'react'
import { ArrowRight, FileText, Plus, Search, Telescope } from '../ui/icons'
import { Link } from 'react-router-dom'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { Badge } from '../ui/badge'
import type { InvestigationView } from '../../lib/api/investigations'
import { displayUnknowns, investigationStatusLabel } from '../../lib/investigationPresentation'
import { useI18n } from '../../lib/i18n'

export function InvestigationIndex({
  cases,
  loading,
  failed,
  retry,
  query,
  onQuery,
  filter,
  onFilter,
  onSelect,
  hasMore,
  loadingMore,
  moreFailed,
  loadMore,
}: {
  cases: InvestigationView[]
  loading: boolean
  failed: boolean
  retry: () => void
  query: string
  onQuery: (value: string) => void
  filter: string
  onFilter: (value: string) => void
  onSelect: (caseId: string) => void
  hasMore: boolean
  loadingMore: boolean
  moreFailed: boolean
  loadMore: () => void
}) {
  const { text, language } = useI18n()
  const [search, setSearch] = useState({ url: query, draft: query })
  if (search.url !== query) setSearch({ url: query, draft: query })
  useEffect(() => {
    if (search.draft === query) return
    const timer = window.setTimeout(() => onQuery(search.draft), 250)
    return () => window.clearTimeout(timer)
  }, [search.draft, query, onQuery])
  const filters = [
    ['all', text('全部调查', 'All investigations')],
    ['active', text('进行中', 'In progress')],
    ['resolved', text('已完成', 'Completed')],
    ['stopped', text('已停止', 'Stopped')],
  ]
  const visible = cases.filter((item) => {
    const matches =
      filter === 'all' ||
      (filter === 'active'
        ? ['created', 'active', 'waiting'].includes(item.status)
        : filter === 'resolved'
          ? item.status === 'resolved'
          : ['failed', 'cancelled', 'canceled', 'closed'].includes(item.status))
    return matches && `${item.goal} ${item.case_id}`.toLowerCase().includes(search.draft.trim().toLowerCase())
  })
  return (
    <div className="research-index">
      <header className="research-heading">
        <div>
          <h1>{text('调查记录', 'Investigations')}</h1>
          <p>
            {text('回到一个问题，查看它的发现、证据和结论。', 'Return to a question and follow its findings, evidence and conclusions.')}
          </p>
        </div>
        <Button asChild>
          <Link to="/start">
            <Plus size={16} />
            {text('发起调查', 'New investigation')}
          </Link>
        </Button>
      </header>
      <Tabs value={filter} onValueChange={onFilter}>
        <div className="research-index-toolbar">
          <TabsList variant="line" aria-label={text('调查状态', 'Investigation status')}>
            {filters.map(([value, label]) => (
              <TabsTrigger value={value} key={value}>
                {label}
              </TabsTrigger>
            ))}
          </TabsList>
          <label className="research-search">
            <Search size={16} />
            <Input
              aria-label={text('搜索已载入调查', 'Search loaded investigations')}
              placeholder={text('搜索调查…', 'Search investigations…')}
              value={search.draft}
              onChange={(event) => setSearch(current => ({ ...current, draft: event.target.value }))}
            />
          </label>
        </div>
        <TabsContent value={filter}>
          {failed && (
            <div className="research-notice" role="alert">
              <span>{text('调查记录暂时无法读取。', 'Investigations could not be loaded.')}</span>
              <Button variant="outline" size="sm" onClick={retry}>
                {text('重新读取', 'Retry')}
              </Button>
            </div>
          )}
          {loading && (
            <div className="research-empty" role="status">
              <Telescope size={26} />
              <p>{text('正在读取你的调查…', 'Loading your investigations…')}</p>
            </div>
          )}
          {!loading && !failed && !visible.length && (
            <div className="research-empty">
              <Telescope size={30} />
              <h2>
                {search.draft || filter !== 'all'
                  ? text('没有匹配的调查', 'No matching investigations')
                  : text('让一个问题，有据可查', 'Give a question an evidence trail')}
              </h2>
              <p>
                {search.draft || filter !== 'all'
                  ? text('试试其他关键词或状态；也可以载入更早的记录。', 'Try another query or status, or load older records.')
                  : text(
                      '从问答中提出问题，调查的进展和报告会保存在这里。',
                      'Ask a question. Investigation progress and reports will be saved here.',
                    )}
              </p>
              {!search.draft && filter === 'all' && (
                <Button asChild variant="outline">
                  <Link to="/start">
                    {text('提出第一个问题', 'Ask your first question')}
                    <ArrowRight size={15} />
                  </Link>
                </Button>
              )}
            </div>
          )}
          {visible.length > 0 && (
            <div className="research-records">
              {visible.map((item) => (
                <button className="research-record" key={item.case_id} onClick={() => onSelect(item.case_id)}>
                  <span className="research-record-icon">
                    <FileText size={21} />
                  </span>
                  <span className="research-record-content">
                    <span className="research-record-top">
                      <Badge variant="secondary" className={`research-status status-${item.status}`}>
                        {investigationStatusLabel(item.status, text)}
                      </Badge>
                      <time dateTime={item.updated_at}>
                        {new Date(item.updated_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </time>
                    </span>
                    <strong>{item.goal}</strong>
                    <span className="research-record-meta">
                      <span>
                        {item.confirmed_findings.length} {text('条发现', 'findings')}
                      </span>
                      <span>
                        {displayUnknowns(item).length} {text('个未解问题', 'open questions')}
                      </span>
                      <span>{item.latest_decision ? text('报告可读', 'Report available') : text('尚未形成报告', 'Report pending')}</span>
                    </span>
                  </span>
                  <ArrowRight className="research-record-arrow" size={18} />
                </button>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
      {!loading && (
        <footer className="research-index-footer">
          <span>
            {text(
              `当前载入 ${cases.length} 条${hasMore ? '，筛选在已载入记录中进行' : ''}`,
              `${cases.length} loaded${hasMore ? '; filters apply to loaded records' : ''}`,
            )}
          </span>
          {hasMore && (
            <Button variant="outline" onClick={loadMore} disabled={loadingMore}>
              {loadingMore
                ? text('读取中…', 'Loading…')
                : moreFailed
                  ? text('重试载入更早记录', 'Retry older records')
                  : text('载入更早记录', 'Load older records')}
            </Button>
          )}
        </footer>
      )}
    </div>
  )
}
