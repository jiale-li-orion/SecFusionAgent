import { useState } from 'react'
import { BadgeCheck, FileText, Link2 } from '../ui/icons'
import { DecisionReport } from '../DecisionReport'
import { EvidenceCitation } from '../questions/EvidenceCitation'
import { Button } from '../ui/button'
import type { InvestigationView } from '../../lib/api/investigations'
import { useI18n } from '../../lib/i18n'
import './investigation-report.css'

export function InvestigationReport({
  investigation,
  onEvidence,
}: {
  investigation: InvestigationView
  onEvidence: (ref: string) => void
}) {
  const { text, language } = useI18n()
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const decision = investigation.latest_decision
  if (!decision) return null
  const paragraphs = decision.report_paragraphs ?? []
  const insufficient = ['evidence_insufficient', 'evidence_validation_failed', 'no_bound_investigation_target'].includes(
    decision.stop_reason,
  )
  const refs = [
    ...new Set([
      ...decision.citations.map((item) => item.evidence_ref),
      ...decision.conclusions.flatMap((item) => item.evidence_refs),
      ...paragraphs.flatMap((item) => item.evidence_refs),
    ]),
  ]
  const cveId = investigation.goal.match(/\bCVE-\d{4}-\d{4,}\b/i)?.[0]
  const labels: Record<string, [string, string]> = {
    fact: ['已证实的事实', 'Verified fact'],
    inference: ['基于证据的推断', 'Evidence-based inference'],
    recommendation: ['建议', 'Recommendation'],
  }
  const sections = paragraphs.length
    ? paragraphs.map((item) => ({ ...item, label: null }))
    : decision.conclusions.map((item) => ({
        text: item.statement,
        evidence_refs: item.evidence_refs,
        label: labels[item.type] ? text(...labels[item.type]) : item.type,
      }))
  const boundaries = [
    { title: text('仍有待确认', 'What remains uncertain'), items: decision.unknowns },
    { title: text('来源之间的分歧', 'Where sources disagree'), items: decision.conflicts },
    { title: text('研判所依据的前提', 'Assumptions'), items: decision.assumptions },
  ].filter((item) => item.items.length)
  return (
    <article className="investigation-report">
      <header className="report-masthead">
        <div>
          <small>
            <FileText size={15} />
            {text('调查报告', 'Research report')}
          </small>
          <h2>
            {insufficient
              ? text('现有证据与未解问题', 'Evidence and open questions')
              : cveId
                ? `${cveId} · ${text('调查结论', 'Investigation findings')}`
                : text('调查结论', 'Investigation findings')}
          </h2>
        </div>
        <span>
          <BadgeCheck size={15} />
          {insufficient ? text('证据仍不充分', 'More evidence needed') : text('引用可追溯', 'Traceable sources')}
        </span>
      </header>
      <div className="report-byline">
        <span>{new Date(decision.created_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')}</span>
        <span>
          {refs.length} {text('条引用', 'references')} · {text('研判版本', 'Decision revision')} {decision.case_revision}
        </span>
      </div>
      <div className="report-body">
        {!paragraphs.length && sections.length > 0 && (
          <p className="report-archive-note">
            {text(
              '这份历史记录未保存独立报告正文，以下呈现当时已验证的结论与引用。',
              'This historical record has no separate report prose. Its validated findings and citations are shown below.',
            )}
          </p>
        )}
        {sections.map((paragraph, index) => (
          <section className="report-paragraph" key={index}>
            {paragraph.label && <small className="report-finding-label">{paragraph.label}</small>}
            <p>{paragraph.text}</p>
            {paragraph.evidence_refs.length > 0 && (
              <div className="report-evidence">
                {[...new Set(paragraph.evidence_refs)].map((ref) => (
                  <Button variant="outline" size="sm" key={ref} onClick={() => onEvidence(ref)} title={ref}>
                    <Link2 size={12} />
                    {text('证据', 'Source')} {refs.indexOf(ref) + 1}
                  </Button>
                ))}
              </div>
            )}
          </section>
        ))}
        {!sections.length && (
          <p className="report-empty">
            {text(
              '这份决策没有留存可阅读的正文或结论。下方仍可核对原始决策字段。',
              'This decision has no retained prose or findings. Its original decision fields remain available below.',
            )}
          </p>
        )}
        {boundaries.map((boundary) => (
          <section className="report-boundary" key={boundary.title}>
            <h3>{boundary.title}</h3>
            {boundary.items.map((value, index) => (
              <p key={index}>{value}</p>
            ))}
          </section>
        ))}
      </div>
      {refs.length > 0 && (
        <details className="report-sources" onToggle={(event) => setSourcesOpen(event.currentTarget.open)}>
          <summary>
            {text('引用来源', 'Sources')}
            <span>{refs.length}</span>
          </summary>
          {sourcesOpen && (
            <div>
              {refs.map((ref, index) => (
                <EvidenceCitation key={ref} evidenceRef={ref} index={index} onOpen={onEvidence} />
              ))}
            </div>
          )}
        </details>
      )}
      <details className="report-audit">
        <summary>
          {text('决策字段与审计信息', 'Decision fields & audit details')}
          <span>REV {decision.case_revision}</span>
        </summary>
        <DecisionReport decision={decision} onEvidence={onEvidence} />
      </details>
    </article>
  )
}
