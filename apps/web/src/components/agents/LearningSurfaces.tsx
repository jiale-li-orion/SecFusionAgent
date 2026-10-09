import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, ChevronRight, Orbit, Waypoints } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { getAgentExperience, type AgentLearningOverview, type ProductExperience, type ProductSkill } from '../../lib/api'
import type { SkillFamily } from '../../lib/agentLearning'
import { useI18n } from '../../lib/i18n'

export function SkillFamilyDetail({ family, primaryDetail }: { family: SkillFamily; primaryDetail: ProductSkill | null }) {
  const { text } = useI18n()
  const primary = primaryDetail ?? family.records[0]
  const records = primaryDetail
    ? family.records.map((item) => item.skill_ref === primaryDetail.skill_ref ? primaryDetail : item)
    : family.records
  return <div className="skill-detail-stack">
    <div className="skill-detail-head">
      <div><small>{text('SKILL 家族', 'SKILL FAMILY')}</small><strong>{family.label}</strong><span className="mono">{primary.skill_ref}</span></div>
      <div className="skill-status-stack">{records.map((item) => <span key={item.skill_ref} className={`skill-status status-${item.status}`}>{item.status}</span>)}</div>
    </div>
    <div className="skill-record-stack">{records.map((item) => (
      <article key={item.skill_ref} className={`skill-record status-${item.status}`}>
        <div className="skill-record-title">
          <div><small>{item.source_type}</small><strong>{family.label} · v{item.version}</strong><span className="mono">{item.skill_ref}</span></div>
          <b>{item.status}</b>
        </div>
        {item.status === 'candidate' && (
          <div className="skill-candidate-boundary">
            <span>CANDIDATE</span>
            <p>{text('候选版本，尚待验证后启用。', 'Candidate version awaiting validation before activation.')}</p>
          </div>
        )}
        <div className="skill-record-body">
          <section className="skill-procedure-pane">
            <div className="skill-chips">{item.task_patterns.map((value) => <span key={value}>{value}</span>)}{item.required_capability_classes.map((value) => <span key={value}>{value}</span>)}</div>
            <div className="skill-procedure">{item.steps.map((step, index) => <div key={String(step.step_id ?? index)}><span>{String(index + 1).padStart(2,'0')}</span><p>{String(step.semantic_instruction ?? step.step_id ?? text('流程步骤', 'procedure step'))}</p></div>)}</div>
            {item.failure_guards.length > 0 && <div className="skill-guards"><small>{text('失败护栏', 'FAILURE GUARDS')}</small><p>{item.failure_guards.map(presentGuard).join(' · ')}</p></div>}
            {item.fallbacks.length > 0 && <div className="skill-guards"><small>{text('回退路径', 'FALLBACKS')}</small><p>{item.fallbacks.map(presentGuard).join(' · ')}</p></div>}
            {item.stop_conditions.length > 0 && <div className="skill-guards"><small>{text('停止条件', 'STOP CONDITIONS')}</small><p>{item.stop_conditions.map(presentGuard).join(' · ')}</p></div>}
          </section>
          <details className="skill-governance"><summary>{text("验证与来源记录", "Validation and provenance")}</summary>
            <SkillGovernanceRef label="VALIDATION" values={item.validation_ref ? [item.validation_ref] : []} empty={text('尚无 validation ref', 'no validation ref')} />
            <SkillGovernanceRef label="SUPPORT TRAJECTORY" values={item.supporting_trajectory_refs} empty="—" />
            <SkillGovernanceRef label="EXPERIENCE PATTERN" values={item.supporting_experience_pattern_refs} empty="—" />
            <SkillGovernanceRef label="VALIDATION CASE" values={item.validation_case_refs} empty="—" />
            <SkillGovernanceRef label="PROMOTION HISTORY" values={item.promotion_history} empty="—" />
            <div className="skill-origin"><small>PROVENANCE ORIGIN</small><strong>{item.provenance_origin}</strong></div>
          </details>
        </div>
      </article>
    ))}</div>
  </div>
}

function presentGuard(value: string) {
  return value.replaceAll('required observation unavailable', 'required observation not present')
}

function SkillGovernanceRef({ label, values, empty }: { label: string; values: string[]; empty: string }) {
  return (
    <div className="skill-governance-ref">
      <small>{label}</small>
      {values.length ? values.map((value) => <span key={value} className="mono">{value}</span>) : <em>{empty}</em>}
    </div>
  )
}

export function ExperienceMemory({ stats, experiences, skills }: { stats: AgentLearningOverview; experiences: ProductExperience[]; skills: ProductSkill[] }) {
  const { text } = useI18n()
  const [selectedExperienceId, setSelectedExperienceId] = useState<string | null>(null)
  const selectedExperienceRef = selectedExperienceId ?? experiences[0]?.experience_version_id ?? null
  const detailQuery = useQuery({
    queryKey: ['agent-experience', selectedExperienceRef],
    queryFn: () => getAgentExperience(selectedExperienceRef!),
    enabled: Boolean(selectedExperienceRef),
    staleTime: 30_000,
  })
  const stages = [
    ['Trajectory', stats.trajectory_count],
    ['Candidate', stats.experience_candidate_count],
    ['Experience', experiences.length],
    ['Skill Patch', skills.filter((item) => item.source_type === 'experience_derived').length],
  ] as const
  const selectedExperience = detailQuery.data
    ?? experiences.find((item) => item.experience_version_id === selectedExperienceRef)
    ?? null
  const supportTrajectories = selectedExperience?.support_records.filter((item) => item.outcome !== 'failure') ?? []
  const counterexampleTrajectories = selectedExperience?.support_records.filter((item) => item.outcome === 'failure') ?? []
  const linkedSkills = selectedExperience ? skills.filter((skill) => {
    const aliases = new Set([
      selectedExperience.experience_id,
      selectedExperience.experience_version_id,
      `experience:${selectedExperience.experience_id}`,
      `experience:${selectedExperience.experience_id}@${selectedExperience.version}`,
    ])
    return skill.supporting_experience_pattern_refs.some((ref) => aliases.has(ref))
  }) : []
  return <div className="experience-body">
    <div className="experience-pipeline">{stages.map(([label, count], index) => <div key={label} className="experience-stage"><span className="experience-stage-icon"><BrainCircuit size={16} /></span><div><small>STAGE {String(index + 1).padStart(2,'0')}</small><strong>{label}</strong><b>{count}</b></div>{index < stages.length - 1 && <ChevronRight size={14} className="experience-arrow" />}</div>)}</div>
    {experiences.length === 0 ? <div className="experience-empty"><Orbit size={30} /><div><strong>{text('尚无 durable Experience', 'NO DURABLE EXPERIENCE YET')}</strong><p>{text('尚未形成可复用经验。完成的调查轨迹经评估后会留存在这里。', 'No reusable experience has formed yet. Evaluated investigation experience will appear here.')}</p></div></div> : <div className="experience-workbench">
      <div className="experience-list">{experiences.map((item, index) => <button key={item.experience_version_id} className={item.experience_version_id === selectedExperience?.experience_version_id ? 'selected' : ''} onClick={() => setSelectedExperienceId(item.experience_version_id)}><span>{String(index + 1).padStart(2,'0')}</span><div><small>{item.status} · v{item.version}</small><strong>{item.name}</strong><em>{item.task_signature}</em></div><b>{item.success_count}/{item.failure_count}/{item.partial_count}</b></button>)}</div>
      {selectedExperience && <div className="experience-inspector">
        <div className="experience-inspector-head"><div><small>{text('持久 Experience', 'DURABLE EXPERIENCE')}</small><strong>{selectedExperience.name}</strong><span className="mono">{selectedExperience.experience_version_id}</span></div><div><small>{text('结果历史', 'OUTCOME HISTORY')}</small><strong>{selectedExperience.success_count} / {selectedExperience.failure_count} / {selectedExperience.partial_count}</strong><span>{text('成功 · 失败 · 部分完成', 'success · failure · partial')}</span></div></div>
        <div className="experience-evidence-wall">
          <section className="trajectory-wall support">
            <div className="trajectory-wall-head"><small>{text('支持轨迹', 'SUPPORT TRAJECTORIES')}</small><strong>{supportTrajectories.length}</strong></div>
            <div>
              {supportTrajectories.map((item) => <TrajectoryEvidence key={item.trajectory_id} record={item} experienceRef={selectedExperience.experience_version_id} />)}
              {supportTrajectories.length === 0 && <p>{text('当前 ExperienceVersion 没有持久化 support trajectory。', 'No persisted support trajectory for this ExperienceVersion.')}</p>}
            </div>
          </section>
          <section className="experience-pattern-core">
            <small>EXPERIENCE PATTERN</small>
            <strong>{selectedExperience.name}</strong>
            <span>{selectedExperience.status} · v{selectedExperience.version}</span>
            <div className="experience-pattern-score"><b>{selectedExperience.success_count}</b><i /><b>{selectedExperience.failure_count}</b></div>
            <em>{text(linkedSkills.length + ' 个声明关联 Skill Patch', linkedSkills.length + ' declared Skill Patch links')}</em>
          </section>
          <section className="trajectory-wall counterexample">
            <div className="trajectory-wall-head"><small>{text('反例轨迹', 'COUNTEREXAMPLES')}</small><strong>{counterexampleTrajectories.length}</strong></div>
            <div>
              {counterexampleTrajectories.map((item) => <TrajectoryEvidence key={item.trajectory_id} record={item} experienceRef={selectedExperience.experience_version_id} />)}
              {counterexampleTrajectories.length === 0 && <p>{text('当前 ExperienceVersion 没有持久化 counterexample。', 'No persisted counterexample for this ExperienceVersion.')}</p>}
            </div>
          </section>
        </div>
        <ExperienceVector label={text('触发信号', 'TRIGGER SIGNALS')} values={selectedExperience.trigger_signals} />
        <ExperienceVector label={text('适用条件', 'APPLICABLE CONDITIONS')} values={selectedExperience.applicable_conditions} />
        <ExperienceVector label={text('推荐动作', 'RECOMMENDED ACTIONS')} values={selectedExperience.recommended_actions} />
        <ExperienceVector label={text('证据预期', 'EVIDENCE EXPECTATION')} values={selectedExperience.evidence_expectation} />
        <ExperienceVector label={text('失败模式', 'FAILURE MODES')} values={selectedExperience.failure_modes} tone="failure" />
        <ExperienceVector label={text('停止条件', 'STOP CONDITIONS')} values={selectedExperience.stop_conditions} />
        <ExperienceVector label={text('回退动作', 'FALLBACK ACTIONS')} values={selectedExperience.fallback_actions} />
        <div className="experience-linked-skills"><small>{text('声明关联的 Skill Patch', 'DECLARED SKILL PATCH LINKS')}</small>{linkedSkills.length ? <div>{linkedSkills.map((skill) => <span key={skill.skill_ref}>{skill.skill_id}@{skill.version} · {skill.status}</span>)}</div> : <p>{text('当前 Skill registry 没有声明指向该 Experience pattern 的 supporting ref。', 'No Skill in the current registry declares a supporting reference to this Experience pattern.')}</p>}</div>
      </div>}
    </div>}
  </div>
}

function TrajectoryEvidence({ record, experienceRef }: { record: ProductExperience['support_records'][number]; experienceRef: string }) {
  const { text } = useI18n()
  const navigate = useNavigate()
  const casePath = `/investigations?${new URLSearchParams({ case: record.case_id, from: 'experience', experience: experienceRef, trajectory: record.trajectory_id }).toString()}`
  return (
    <article className={'trajectory-evidence outcome-' + record.outcome}>
      <span><small>{record.outcome}</small><strong className="mono">{record.trajectory_id}</strong></span>
      <div>{formatEvaluation(record.evaluation).map((item) => <em key={item}>{item}</em>)}</div>
      <div className="trajectory-runtime-coordinate">
        <span>{record.trajectory_status}</span>
        <span>{record.tool_calls} tools</span>
        <span>{record.latency_ms != null ? `${record.latency_ms}ms` : 'latency —'}</span>
      </div>
      <button onClick={() => navigate(casePath)}><Waypoints size={10} /> {text('打开来源 Case', 'OPEN SOURCE CASE')}<span className="mono">{record.case_id}</span></button>
      <b>{record.evaluator}</b>
    </article>
  )
}

function formatEvaluation(evaluation: Record<string, unknown>) {
  const items = Object.entries(evaluation).map(([key, value]) => {
    if (typeof value === 'number') return key + '=' + (Number.isInteger(value) ? String(value) : value.toFixed(3))
    if (typeof value === 'boolean' || typeof value === 'string') return key + '=' + String(value)
    return key
  })
  return items.length ? items : ['evaluation persisted']
}

function ExperienceVector({ label, values, tone = 'default' }: { label: string; values: string[]; tone?: 'default' | 'failure' }) {
  return <div className={`experience-vector tone-${tone}`}><small>{label}</small>{values.length ? <div>{values.map((value, index) => <span key={`${value}:${index}`}>{value}</span>)}</div> : <p>—</p>}</div>
}
