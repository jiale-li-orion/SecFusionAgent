import type { ReactNode } from 'react'
import { Link2 } from 'lucide-react'
import type { DecisionView } from '../lib/api'
import { useI18n } from '../lib/i18n'

/** Presentation of the persisted M6 result; never a second decision authority. */
export function DecisionReport({ decision, onEvidence, dialogue = false }: { decision: DecisionView; onEvidence: (ref: string) => void; dialogue?: boolean }) {
  const { text } = useI18n()
  const refs = [...new Set([
    ...decision.citations.map((citation) => citation.evidence_ref),
    ...decision.conclusions.flatMap((conclusion) => conclusion.evidence_refs),
  ])]
  const boundaries = [
    { label: text('来源冲突', 'SOURCE CONFLICTS'), items: decision.conflicts, tone: 'conflict' },
    { label: text('尚未确认', 'UNKNOWNS'), items: decision.unknowns, tone: 'unknown' },
    { label: text('研判前提', 'ASSUMPTIONS'), items: decision.assumptions, tone: 'assumption' },
  ]
  const answerFields = Object.keys(decision.answer).length > 0 && <dl className="decision-answer-fields">
    {Object.entries(decision.answer).map(([key, value]) => <div key={key}><dt>{answerLabel(key, text)}</dt><dd><AnswerValue value={value} /></dd></div>)}
  </dl>
  const conclusions = decision.conclusions.map((conclusion, index) => ({ conclusion, index }))
  const findings = dialogue ? conclusions.filter(({ conclusion }) => conclusion.type !== 'fact') : conclusions
  const primary = findings.length > 0 ? findings : conclusions
  const supportingFacts = dialogue && findings.length > 0 ? conclusions.filter(({ conclusion }) => conclusion.type === 'fact') : []
  const renderConclusion = ({ conclusion, index }: (typeof conclusions)[number]) => <article key={index}>
    <small>{String(index + 1).padStart(2, '0')} / {conclusionLabel(conclusion.type, text)}</small>
    <p>{conclusion.statement}</p>
    <div className="decision-report-citations">{[...new Set(conclusion.evidence_refs)].map((ref) => <button type="button" key={ref} onClick={() => onEvidence(ref)}><Link2 size={12} />{text('证据', 'EVIDENCE')} {refs.indexOf(ref) + 1}</button>)}</div>
  </article>
  return (
    <div className="decision-report">
      {(dialogue || decision.conclusions.length === 0) && answerFields}
      <div className="decision-report-conclusions">
        {primary.map(renderConclusion)}
      </div>
      {supportingFacts.length > 0 && <details className="decision-report-facts"><summary>{text(`支撑事实 · ${supportingFacts.length}`, `SUPPORTING FACTS · ${supportingFacts.length}`)}</summary><div className="decision-report-conclusions">{supportingFacts.map(renderConclusion)}</div></details>}
      {!dialogue && decision.conclusions.length > 0 && answerFields && <details className="decision-report-coordinate"><summary>{text('回答补充', 'Additional answer details')}</summary>{answerFields}</details>}
      {boundaries.filter(({ items }) => items.length > 0).map(({ label, items, tone }) => <section className={`decision-report-boundary boundary-${tone}`} key={tone}><h3>{label}</h3><ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul></section>)}
      {refs.length > 0 && <details className="decision-report-sources"><summary>{text(`全部证据 · ${refs.length}`, `ALL EVIDENCE · ${refs.length}`)}</summary><div className="decision-report-citations">{refs.map((ref, index) => <button type="button" key={ref} onClick={() => onEvidence(ref)} title={ref}><Link2 size={12} />{text('证据', 'EVIDENCE')} {index + 1}</button>)}</div></details>}
      <details className="decision-report-coordinate"><summary>{text('研判坐标', 'DECISION COORDINATES')}</summary><dl><dt>ID</dt><dd>{decision.decision_id}</dd><dt>REV</dt><dd>{decision.case_revision}</dd><dt>STOP</dt><dd>{decision.stop_reason}</dd><dt>TIME</dt><dd>{new Date(decision.created_at).toLocaleString()}</dd></dl></details>
    </div>
  )
}

function AnswerValue({ value }: { value: unknown }): ReactNode {
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><AnswerValue value={item} /></li>)}</ul>
  if (typeof value === 'object') return <dl>{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><AnswerValue value={item} /></dd></div>)}</dl>
  return String(value)
}

function conclusionLabel(kind: string, text: (zh: string, en: string) => string) {
  const labels: Record<string, [string, string]> = { fact: ['事实', 'FACT'], inference: ['推断', 'INFERENCE'], recommendation: ['建议', 'RECOMMENDATION'] }
  return labels[kind] ? text(...labels[kind]) : kind
}

function answerLabel(key: string, text: (zh: string, en: string) => string) {
  const labels: Record<string, [string, string]> = {
    cve_id: ['漏洞编号', 'CVE'], package: ['软件包', 'PACKAGE'], first_fixed_version: ['首个修复版本', 'FIRST FIXED VERSION'],
    affected_versions: ['受影响版本', 'AFFECTED VERSIONS'], summary: ['研判摘要', 'SUMMARY'], answer: ['回答', 'ANSWER'],
    remediation: ['修复建议', 'REMEDIATION'], severity: ['严重性', 'SEVERITY'], cvss: ['CVSS 评分', 'CVSS'],
  }
  return labels[key] ? text(...labels[key]) : key.replaceAll('_', ' ')
}
