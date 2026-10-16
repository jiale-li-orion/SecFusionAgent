import { productTerm, skillName } from '../../lib/productVocabulary'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BrainCircuit, ChevronRight, Orbit, Waypoints } from '../ui/icons'
import { useNavigate } from 'react-router-dom'

import { getAgentExperience, type AgentLearningOverview, type ProductExperience, type ProductSkill } from '../../lib/api'
import type { SkillFamily } from '../../lib/agentLearning'
import { useI18n } from '../../lib/i18n'

export function SkillFamilyDetail({ family, primaryDetail }: { family: SkillFamily; primaryDetail: ProductSkill | null }) {
  const { text } = useI18n()
    const records = primaryDetail
    ? family.records.map((item) => item.skill_ref === primaryDetail.skill_ref ? primaryDetail : item)
    : family.records
  return <div className="skill-detail-stack">
    <div className="skill-detail-head">
      <div><small>{text('技能', 'Skill')}</small><strong>{skillName(family.label, text)}</strong></div>
      <div className="skill-status-stack">{records.map((item) => <span key={item.skill_ref} className={`skill-status status-${productTerm(item.status, text)}`}>{productTerm(item.status, text)}</span>)}</div>
    </div>
    <div className="skill-record-stack">{records.map((item) => (
      <article key={item.skill_ref} className={`skill-record status-${productTerm(item.status, text)}`}>
        <div className="skill-record-title">
          <div><small>{productTerm(item.source_type, text)}</small><strong>{skillName(family.label, text)} · v{item.version}</strong></div>
          <b>{productTerm(item.status, text)}</b>
        </div>
        {item.status === 'candidate' && (
          <div className="skill-candidate-boundary">
            <span>{text('待验证', 'Candidate')}</span>
            <p>{text('候选版本，尚待验证后启用。', 'Candidate version awaiting validation before activation.')}</p>
          </div>
        )}
        <div className="skill-record-body">
          <section className="skill-procedure-pane">
            <div className="skill-chips">{item.task_patterns.map((value) => <span key={value}>{productTerm(value, text)}</span>)}{item.required_capability_classes.map((value) => <span key={value}>{productTerm(value, text)}</span>)}</div>
            <div className="skill-procedure">{item.steps.map((step, index) => <div key={String(step.step_id ?? index)}><span>{String(index + 1).padStart(2,'0')}</span><p>{step.semantic_instruction ? String(step.semantic_instruction) : productTerm(String(step.step_id ?? 'procedure_step'), text)}</p></div>)}</div>
            {item.failure_guards.length > 0 && <div className="skill-guards"><small>{text('失败护栏', 'FAILURE GUARDS')}</small><p>{item.failure_guards.map(presentGuard).join(' · ')}</p></div>}
            {item.fallbacks.length > 0 && <div className="skill-guards"><small>{text('回退路径', 'FALLBACKS')}</small><p>{item.fallbacks.map(presentGuard).join(' · ')}</p></div>}
            {item.stop_conditions.length > 0 && <div className="skill-guards"><small>{text('停止条件', 'STOP CONDITIONS')}</small><p>{item.stop_conditions.map(presentGuard).join(' · ')}</p></div>}
          </section>
          <details className="skill-governance"><summary>{text("验证与来源记录", "Validation and provenance")}</summary>
            <SkillGovernanceRef label={text("技能标识", "Skill reference")} values={[item.skill_ref]} empty="—" />
            <SkillGovernanceRef label={text("验证记录", "Validation")} values={item.validation_ref ? [item.validation_ref] : []} empty={text('尚无验证记录', 'no validation ref')} />
            <SkillGovernanceRef label={text("支持记录", "Support Trajectory")} values={item.supporting_trajectory_refs} empty="—" />
            <SkillGovernanceRef label={text("经验记录", "Experience Pattern")} values={item.supporting_experience_pattern_refs} empty="—" />
            <SkillGovernanceRef label={text("验证调查", "Validation Case")} values={item.validation_case_refs} empty="—" />
            <SkillGovernanceRef label={text("启用记录", "Promotion History")} values={item.promotion_history} empty="—" />
            <div className="skill-origin"><small>{text("来源", "Origin")}</small><strong>{productTerm(item.provenance_origin, text)}</strong></div>
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
    <div className="experience-pipeline">{stages.map(([label, count], index) => <div key={label} className="experience-stage"><span className="experience-stage-icon"><BrainCircuit size={16} /></span><div><small>{text("阶段", "Stage")} {index + 1}</small><strong>{productTerm(label, text)}</strong><b>{count}</b></div>{index < stages.length - 1 && <ChevronRight size={14} className="experience-arrow" />}</div>)}</div>
    {experiences.length === 0 ? <div className="experience-empty"><Orbit size={30} /><div><strong>{text('尚无可复用经验', 'No reusable experience yet')}</strong><p>{text('尚未形成可复用经验。完成的调查轨迹经评估后会留存在这里。', 'No reusable experience has formed yet. Evaluated investigation experience will appear here.')}</p></div></div> : <div className="experience-workbench">
      <div className="experience-list">{experiences.map((item, index) => <button key={item.experience_version_id} className={item.experience_version_id === selectedExperience?.experience_version_id ? 'selected' : ''} onClick={() => setSelectedExperienceId(item.experience_version_id)}><span>{String(index + 1).padStart(2,'0')}</span><div><small>{productTerm(item.status, text)} · v{item.version}</small><strong>{item.name}</strong><em>{productTerm(item.task_signature, text)}</em></div><b>{item.success_count}/{item.failure_count}/{item.partial_count}</b></button>)}</div>
      {selectedExperience && <div className="experience-inspector">
        <div className="experience-inspector-head"><div><small>{text('已保存的经验', 'Saved experience')}</small><strong>{selectedExperience.name}</strong><details><summary>{text("技术标识", "Technical reference")}</summary><span>{selectedExperience.experience_version_id}</span></details></div><div><small>{text('结果历史', 'OUTCOME HISTORY')}</small><strong>{selectedExperience.success_count} / {selectedExperience.failure_count} / {selectedExperience.partial_count}</strong><span>{text('成功 · 失败 · 部分完成', 'success · failure · partial')}</span></div></div>
        <div className="experience-evidence-wall">
          <section className="trajectory-wall support">
            <div className="trajectory-wall-head"><small>{text('支持轨迹', 'SUPPORT TRAJECTORIES')}</small><strong>{supportTrajectories.length}</strong></div>
            <div>
              {supportTrajectories.map((item) => <TrajectoryEvidence key={item.trajectory_id} record={item} experienceRef={selectedExperience.experience_version_id} />)}
              {supportTrajectories.length === 0 && <p>{text('当前经验版本尚无支持记录。', 'No persisted support trajectory for this ExperienceVersion.')}</p>}
            </div>
          </section>
          <section className="experience-pattern-core">
            <small>{text("经验模式", "Experience pattern")}</small>
            <strong>{selectedExperience.name}</strong>
            <span>{productTerm(selectedExperience.status, text)} · v{selectedExperience.version}</span>
            <div className="experience-pattern-score"><b>{selectedExperience.success_count}</b><i /><b>{selectedExperience.failure_count}</b></div>
            <em>{text(linkedSkills.length + ' 个关联技能改进', linkedSkills.length + ' declared Skill Patch links')}</em>
          </section>
          <section className="trajectory-wall counterexample">
            <div className="trajectory-wall-head"><small>{text('反例轨迹', 'COUNTEREXAMPLES')}</small><strong>{counterexampleTrajectories.length}</strong></div>
            <div>
              {counterexampleTrajectories.map((item) => <TrajectoryEvidence key={item.trajectory_id} record={item} experienceRef={selectedExperience.experience_version_id} />)}
              {counterexampleTrajectories.length === 0 && <p>{text('当前经验版本尚无反例记录。', 'No persisted counterexample for this ExperienceVersion.')}</p>}
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
        <div className="experience-linked-skills"><small>{text('关联的技能改进', 'DECLARED SKILL PATCH LINKS')}</small>{linkedSkills.length ? <div>{linkedSkills.map((skill) => <span key={skill.skill_ref}>{skillName(skill.skill_id, text)} · v{skill.version} · {productTerm(skill.status, text)}</span>)}</div> : <p>{text('暂无技能声明使用这条经验。', 'No Skill in the current registry declares a supporting reference to this Experience pattern.')}</p>}</div>
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
      <span><small>{productTerm(record.outcome, text)}</small><strong>{text("调查执行记录", "Investigation run")}</strong></span>
      <div>{formatEvaluation(record.evaluation, text).map((item) => <em key={item}>{item}</em>)}</div>
      <div className="trajectory-runtime-coordinate">
        <span>{productTerm(record.trajectory_status, text)}</span>
        <span>{text(`${record.tool_calls} 次工具调用`, `${record.tool_calls} tool calls`)}</span>
        <span>{record.latency_ms != null ? `${record.latency_ms}ms` : 'latency —'}</span>
      </div>
      <button onClick={() => navigate(casePath)}><Waypoints size={10} /> {text('打开来源调查', 'Open source investigation')}</button>
      <details><summary>{text("评估与技术详情", "Evaluation & technical details")}</summary><p>{record.trajectory_id}</p><p>{record.case_id}</p><p>{record.evaluator}</p></details>
    </article>
  )
}

function formatEvaluation(evaluation: Record<string, unknown>, text: (zh: string, en: string) => string) {
  const items = Object.entries(evaluation).map(([key, value]) => {
    if (typeof value === 'number') return productTerm(key, text) + ' · ' + (Number.isInteger(value) ? String(value) : value.toFixed(3))
    if (typeof value === 'boolean' || typeof value === 'string') return productTerm(key, text) + ' · ' + String(value)
    return productTerm(key, text)
  })
  return items.length ? items : [text('评估已保存', 'Evaluation saved')]
}

function ExperienceVector({ label, values, tone = 'default' }: { label: string; values: string[]; tone?: 'default' | 'failure' }) {
  return <div className={`experience-vector tone-${tone}`}><small>{label}</small>{values.length ? <div>{values.map((value, index) => <span key={`${value}:${index}`}>{value}</span>)}</div> : <p>—</p>}</div>
}
