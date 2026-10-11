import { useMemo, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { ArrowLeft } from "@phosphor-icons/react/dist/csr/ArrowLeft"
import { ArrowClockwise } from "@phosphor-icons/react/dist/csr/ArrowClockwise"
import { BookOpen } from "@phosphor-icons/react/dist/csr/BookOpen"
import { CaretRight } from "@phosphor-icons/react/dist/csr/CaretRight"
import { getAgentExperiences, getAgentLearning, getAgentRuntime, getAgentSkill, getAgentSkills, getAgentTask, listAgentTasks } from '../lib/api'
import { ExperienceMemory, SkillFamilyDetail } from '../components/agents/LearningSurfaces'
import { TaskCard, TaskDossier } from '../components/agents/RuntimeSurfaces'
import { groupSkillFamilies, skillFamilyKeyFromRef } from '../lib/agentLearning'
import { activeStatuses, rolePresentation } from '../lib/agentRuntimePresentation'
import { taskOutcome, taskTitle } from '../lib/taskPresentation'
import { useI18n } from '../lib/i18n'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs'
import '../components/agents/operations-tasks.css'

function SkillBlueprintList() { const { text } = useI18n(); return <p className="ops-empty">{text('暂无已保存的技能。', 'No saved skills yet.')}</p> }
function SkillBlueprintDetail() { const { text } = useI18n(); return <p className="ops-empty">{text('选择技能，查看适用条件和执行步骤。', 'Select a skill to read its conditions and procedure.')}</p> }
function ExperienceBlueprint() { const { text } = useI18n(); return <p className="ops-empty">{text('暂无已保存的经验。', 'No saved experiences yet.')}</p> }

export function AgentsPage() {
  const { text } = useI18n()
  const [params, setParams] = useSearchParams()
  const sectionParam = params.get('section')
  const memoryOpen = sectionParam === 'memory'
  const selectedTask = params.get('run')
  const roleParam = params.get('role')
  const focusedRole = roleParam && rolePresentation[roleParam] ? roleParam : null
  const runtimeQuery = useQuery({ queryKey: ['agent-runtime'], queryFn: getAgentRuntime, refetchInterval: 15_000 })
  const runtime = runtimeQuery.data
  const taskArchive = useInfiniteQuery({
    queryKey: ['agent-task-archive', focusedRole],
    queryFn: ({ pageParam }) => listAgentTasks({ roleId: focusedRole ?? undefined, limit: 24, cursor: pageParam ?? undefined }),
    initialPageParam: null as string | null,
    getNextPageParam: page => page.next_cursor,
    enabled: !memoryOpen,
    refetchInterval: 15_000,
  })
  const detailQuery = useQuery({ queryKey: ['agent-task', selectedTask], queryFn: () => getAgentTask(selectedTask!), enabled: Boolean(selectedTask) && !memoryOpen, refetchInterval: 10_000 })
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const tasks = useMemo(() => {
    const all = new Map((runtime?.recent_tasks ?? []).filter(task => !focusedRole || task.role_id === focusedRole).map(task => [task.run_id, task]))
    for (const task of taskArchive.data?.pages.flatMap(page => page.items) ?? []) all.set(task.run_id, task)
    return [...all.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  }, [runtime?.recent_tasks, taskArchive.data, focusedRole])
  const visible = tasks.filter(task => {
    if (filter === 'active' && !activeStatuses.has(task.status)) return false
    if (filter === 'history' && activeStatuses.has(task.status)) return false
    if (filter === 'failed' && !['failed', 'timed_out'].includes(task.status)) return false
    return `${taskTitle(task, text)} ${task.target_label ?? ''} ${taskOutcome(task, text)}`.toLowerCase().includes(search.toLowerCase())
  })
  const learningQuery = useQuery({ queryKey: ['agent-learning'], queryFn: getAgentLearning, enabled: memoryOpen })
  const learning = learningQuery.data
  const skillsQuery = useQuery({ queryKey: ['agent-skills'], queryFn: getAgentSkills, enabled: memoryOpen })
  const experiencesQuery = useQuery({ queryKey: ['agent-experiences'], queryFn: getAgentExperiences, enabled: memoryOpen })
  const skillFamilies = useMemo(() => groupSkillFamilies(skillsQuery.data ?? []), [skillsQuery.data])
  const [selectedSkillFamily, setSelectedSkillFamily] = useState<string | null>(null)
  const selectedSkill = skillFamilies.find(item => item.key === (selectedSkillFamily ?? skillFamilies[0]?.key)) ?? null
  const selectedSkillRef = selectedSkill?.records[0]?.skill_ref ?? null
  const selectedSkillDetailQuery = useQuery({ queryKey: ['agent-skill', selectedSkillRef], queryFn: () => getAgentSkill(selectedSkillRef!), enabled: memoryOpen && Boolean(selectedSkillRef) })
  function selectTask(run: string) { const next = new URLSearchParams(params); next.set('run', run); setParams(next) }
  function inspectSkillRef(ref: string) { setSelectedSkillFamily(skillFamilyKeyFromRef(ref)); const next = new URLSearchParams(params); next.set('section', 'memory'); setParams(next) }
  function closeTask() { const next = new URLSearchParams(params); next.delete('run'); setParams(next) }
  return <section className="ops-tasks-page">
    <header className="workspace-heading"><div><h1>{memoryOpen ? text('技能与经验', 'Skills & experience') : text('任务记录', 'Task records')}</h1><p>{text('查看任务进展、结果和执行中遇到的问题。', 'Review task progress, results and blockers.')}</p></div><Button variant="outline" onClick={() => void Promise.all([runtimeQuery.refetch(), taskArchive.refetch()])} disabled={runtimeQuery.isFetching || taskArchive.isFetching}><ArrowClockwise size={16} />{text('刷新', 'Refresh')}</Button></header>
    <div className="ops-task-sections"><Tabs value={memoryOpen ? 'memory' : 'tasks'} onValueChange={value => { const next = new URLSearchParams(params); if (value === 'memory') next.set('section', value); else next.delete('section'); setParams(next) }}><TabsList variant="line"><TabsTrigger value="tasks">{text('任务记录', 'Task records')}</TabsTrigger><TabsTrigger value="memory">{text('技能与经验', 'Skills & experience')}</TabsTrigger></TabsList></Tabs></div>
    {!memoryOpen && <>
      {(runtimeQuery.isError || taskArchive.isError) && <p className="error-block" role="alert">{text('部分任务记录读取失败。下方可能保留上次读取的记录，请刷新重试。', 'Some task records could not be loaded. Previous readings may remain below; refresh to retry.')}</p>}
      {selectedTask ? <>
        <div className="ops-task-back"><Button variant="ghost" onClick={closeTask}><ArrowLeft size={16} />{text('返回任务记录', 'Back to task records')}</Button></div>
        {detailQuery.isError ? <p className="error-block" role="alert">{text('任务详情读取失败或不属于当前账户。', 'Task detail could not be read or is not available to your account.')} <Button variant="outline" onClick={() => void detailQuery.refetch()}>{text('重新读取', 'Reload')}</Button></p> : detailQuery.data ? <TaskDossier key={selectedTask} detail={detailQuery.data} onSkillSelect={inspectSkillRef} onTaskSelect={selectTask} /> : <p className="ops-empty" role="status">{text('正在读取任务详情…', 'Loading task details…')}</p>}
      </> : <>
        <div className="ops-task-toolbar"><Tabs value={filter} onValueChange={setFilter}><TabsList variant="line"><TabsTrigger value="all">{text('全部', 'All')}</TabsTrigger><TabsTrigger value="active">{text('进行中', 'Active')}</TabsTrigger><TabsTrigger value="history">{text('历史', 'History')}</TabsTrigger><TabsTrigger value="failed">{text('失败', 'Failed')}</TabsTrigger></TabsList></Tabs><Input aria-label={text('搜索已加载任务', 'Search loaded tasks')} placeholder={text('搜索目标或任务内容', 'Search goal or target')} value={search} onChange={event => setSearch(event.target.value)} /></div>
        {focusedRole && <div className="ops-role-filter">{text('已按执行角色筛选', 'Filtered by role')} · {rolePresentation[focusedRole].cn}<Button variant="ghost" onClick={() => { const next = new URLSearchParams(params); next.delete('role'); setParams(next) }}>{text('清除筛选', 'Clear filter')}</Button></div>}
        <div className="ops-task-table"><div className="ops-task-table-heading"><span>{text('任务与目标', 'Task & target')}</span><span>{text('结果 / 状态', 'Outcome / state')}</span><span>{text('最近更新', 'Updated')}</span></div>{visible.map(task => <TaskCard key={task.run_id} task={task} selected={false} onSelect={selectTask} />)}</div>
        {!visible.length && <p className="ops-empty" role="status">{taskArchive.isPending ? text('正在读取任务…', 'Loading tasks…') : taskArchive.isError ? text('任务记录暂不可用。', 'Task records unavailable.') : text('当前筛选下没有任务。', 'No tasks match the current filters.')}</p>}
        <footer className="ops-task-list-footer"><span>{text(`已加载 ${tasks.length} 条记录；搜索和状态筛选作用于已加载记录。`, `${tasks.length} records loaded; search and state filters apply to loaded records.`)}</span>{taskArchive.hasNextPage && <Button variant="outline" disabled={taskArchive.isFetchingNextPage} onClick={() => void taskArchive.fetchNextPage()}>{taskArchive.isFetchingNextPage ? text('正在读取…', 'Loading…') : text('加载更早记录', 'Load earlier records')}</Button>}</footer>
        <Link className="ops-overview-link" to="/workspace/operations">{text('查看运行概览与待关注事项', 'Open operations overview and attention items')}<CaretRight size={15} /></Link>
      </>}
    </>}
    {memoryOpen && (learningQuery.isError || skillsQuery.isError || experiencesQuery.isError || selectedSkillDetailQuery.isError) && <p role="alert" className="error-block">{text('技能或经验读取失败，请重新读取。', 'Skills or experience could not be loaded.')}<Button variant="outline" onClick={() => void Promise.all([learningQuery.refetch(), skillsQuery.refetch(), experiencesQuery.refetch(), selectedSkillRef ? selectedSkillDetailQuery.refetch() : Promise.resolve()])}>{text('重新读取', 'Reload')}</Button></p>}
      {sectionParam === 'memory' && <div id="agent-memory-field" className="agent-memory-complex">
        <section id="skill-codex" className="skill-codex">
          <div className="instrument-section-head"><div><small>{text('SKILL 典藏', 'SKILL CODEX')}</small><strong>{text('持久程序记忆', 'DURABLE PROCEDURAL MEMORY')}</strong></div><span>{text(String(skillsQuery.data?.length ?? 0) + ' 条记录 · ' + String(skillFamilies.length) + ' 个家族', String(skillsQuery.data?.length ?? 0) + ' records · ' + String(skillFamilies.length) + ' families')}</span></div>
          <div className="skill-codex-body">
            <div className="skill-family-list">
              {skillFamilies.length
                ? skillFamilies.map((family) => <button key={family.key} className={family.key === selectedSkill?.key ? 'selected' : ''} onClick={() => setSelectedSkillFamily(family.key)}><span className="skill-glyph"><BookOpen size={15} /></span><span><small>{family.records.map((item) => item.status).join(' · ')}</small><strong>{family.label}</strong><em>{text(`${family.records.length} 条 durable 记录`, `${family.records.length} durable records`)}</em></span><CaretRight size={14} /></button>)
                : <SkillBlueprintList />}
            </div>
            <div className="skill-detail">
              {selectedSkill ? <SkillFamilyDetail family={selectedSkill} primaryDetail={selectedSkillDetailQuery.data ?? null} /> : <SkillBlueprintDetail />}
            </div>
          </div>
        </section>

        <section className="experience-memory">
          <div className="instrument-section-head"><div><small>{text('经验记忆', 'EXPERIENCE MEMORY')}</small><strong>TRAJECTORY → EXPERIENCE → SKILL</strong></div><span>{text(`${experiencesQuery.data?.length ?? 0} 条 durable Experience`, `${experiencesQuery.data?.length ?? 0} durable experiences`)}</span></div>
          {learning && experiencesQuery.data && skillsQuery.data
            ? <ExperienceMemory stats={learning} experiences={experiencesQuery.data} skills={skillsQuery.data} />
            : <ExperienceBlueprint />}
        </section>
      </div>}
  </section>
}
