import { BadgeCheck, Link2 } from 'lucide-react'
import { DecisionReport } from '../DecisionReport'
import type { InvestigationView } from '../../lib/api/investigations'
import { useI18n } from '../../lib/i18n'
import './investigation-report.css'

export function InvestigationReport({ investigation, onEvidence }: { investigation: InvestigationView; onEvidence: (ref: string) => void }) {
  const { text, language } = useI18n()
  const decision = investigation.latest_decision
  if (!decision) return null

  const paragraphs = decision.report_paragraphs ?? []
  const insufficient = decision.stop_reason === 'evidence_insufficient'
  const citedRefs = [...new Set(decision.citations.map(item => item.evidence_ref))]
  const cveId = investigation.goal.match(/\bCVE-\d{4}-\d{4,}\b/i)?.[0]
  const reportTitle = insufficient
    ? text('当前证据还不足以回答', 'The evidence is not enough yet')
    : cveId
    ? `${cveId} · ${text('修复与证据研判', 'Fix and evidence analysis')}`
    : text('调查研究报告', 'Investigation research report')

  return <article className="investigation-report">
    <header className="report-masthead">
      <div><small>{text('调查报告', 'INVESTIGATION REPORT')} / ORACLE</small><h2>{reportTitle}</h2></div>
      <span><BadgeCheck size={14} />{insufficient ? text('等待更多证据', 'MORE EVIDENCE NEEDED') : text('已形成研判', 'DECISION READY')}</span>
    </header>
    <div className="report-byline">
      <span>{insufficient ? text('已明确标出当前证据边界', 'Current evidence boundary is explicit') : text('基于已验证的决策与证据', 'Grounded in validated decisions and evidence')}</span>
      <span>{new Date(decision.created_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')} · {citedRefs.length} {text('条可追溯证据', 'traceable references')}</span>
    </div>
    <div className="report-body">
      {paragraphs.length > 0
        ? paragraphs.map((paragraph, index) => <div className="report-paragraph" key={`${index}:${paragraph.text}`}>
          <p>{paragraph.text}</p>
          {paragraph.evidence_refs.length > 0 && <div className="report-evidence"><small>{text('参考证据', 'SOURCES')}</small>{[...new Set(paragraph.evidence_refs)].map(ref => <button type="button" key={ref} onClick={() => onEvidence(ref)} title={ref}><Link2 size={11} />{String(citedRefs.indexOf(ref) + 1).padStart(2, '0')}</button>)}</div>}
        </div>)
        : <p className="report-empty">{text('这份决策没有留存研究报告正文。下方仍可查看经过验证的结论、字段与原始证据。', 'This decision has no retained research report. Its validated conclusions, fields, and source evidence remain available below.')}</p>}
    </div>
    <details className="report-audit"><summary>{text('查看完整决策字段与引用', 'Inspect complete decision fields and citations')} <span>REV {investigation.revision}</span></summary><DecisionReport decision={decision} onEvidence={onEvidence} /></details>
  </article>
}
