import { useMemo } from 'react'
import { useI18n } from '../../lib/i18n'
import { usePacedStreamText } from './usePacedStreamText'

function streamingString(raw: string, start: number): string {
  let escaped = false
  let text = ''
  for (const char of raw.slice(start)) {
    if (escaped) {
      text += char === 'n' ? '\n' : char === 't' ? ' ' : char
      escaped = false
    } else if (char === '\\') escaped = true
    else if (char === '"') break
    else text += char
  }
  return text
}

function previewReport(raw: string): string {
  const reportStart = raw.indexOf('"report_paragraphs"')
  if (reportStart < 0) return ''
  const arrayStart = raw.indexOf('[', reportStart + '"report_paragraphs"'.length)
  if (arrayStart < 0) return ''
  let depth = 1
  let inString = false
  let escaped = false
  let arrayEnd = raw.length
  for (let index = arrayStart + 1; index < raw.length; index += 1) {
    const char = raw[index]
    if (inString) {
      if (escaped) escaped = false
      else if (char === '\\') escaped = true
      else if (char === '"') inString = false
    } else if (char === '"') inString = true
    else if (char === '[') depth += 1
    else if (char === ']' && --depth === 0) { arrayEnd = index; break }
  }
  const paragraphs = raw.slice(arrayStart + 1, arrayEnd)
  return [...paragraphs.matchAll(/"text"\s*:\s*"/g)]
    .map(match => streamingString(paragraphs, (match.index ?? 0) + match[0].length))
    .filter(Boolean)
    .join('\n\n')
}

export function StreamedDecisionDraft({ draftRaw, reasoningRaw, reasoningOpen, onReasoningOpen, phase }: {
  draftRaw: string
  reasoningRaw: string
  reasoningOpen: boolean
  onReasoningOpen: (open: boolean) => void
  phase: string
}) {
  const { text } = useI18n()
  const report = useMemo(() => previewReport(draftRaw), [draftRaw])
  const visibleReport = usePacedStreamText(report)
  const visibleReasoning = usePacedStreamText(reasoningRaw)
  const failed = phase === 'failed'

  return <div className="qa-answer">
    <small>{!failed && <i className="qa-live-dot" />}{failed ? text('本次生成未完成', 'ANSWER STREAM INTERRUPTED') : text('正在形成证据研判', 'EVIDENCE DECISION IN PROGRESS')}</small>
    {report ? <p className="qa-draft-text" aria-live="off">{failed ? report : visibleReport}{!failed && <span className="qa-caret" />}</p>
      : <p className="qa-muted">{failed ? text('未形成可验证答案，可修改问题后重试。', 'No validated answer was formed. Edit the question and retry.') : draftRaw ? text('正在组织可追溯报告…', 'Composing the traceable report…') : phase === 'connecting' ? text('正在建立安全流…', 'Connecting to the answer stream…') : text('正在检索上下文并核对证据…', 'Retrieving context and checking evidence…')}</p>}
    {draftRaw && <small className="qa-draft-label">{failed ? text('未完成草稿 · 未经证据校验', 'INCOMPLETE DRAFT · NOT EVIDENCE-VALIDATED') : text('生成中 · 尚未经证据校验', 'GENERATING · NOT YET EVIDENCE-VALIDATED')}</small>}
    {reasoningRaw && <details open={reasoningOpen} onToggle={event => onReasoningOpen(event.currentTarget.open)} className="qa-reasoning"><summary>{text('模型推理流', 'Model reasoning stream')}</summary><pre aria-live="off">{failed ? reasoningRaw : visibleReasoning}</pre></details>}
  </div>
}
