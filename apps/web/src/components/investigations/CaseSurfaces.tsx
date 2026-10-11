import { useRef } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'motion/react'
import { BadgeCheck, BrainCircuit, Link2, Orbit, X } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { evidenceBoundObjectIds, getEvidence, type EvidenceDetail } from '../../lib/api'
import { evidenceFieldLabel, formatValue } from '../../lib/intelligencePresentation'
import { useI18n } from '../../lib/i18n'
import { Button } from '../ui/button'
import { SourceIdentity } from '../ui/source-identity'

export function EvidenceOverlay({ evidenceRef, onClose }: { evidenceRef: string; onClose: () => void }) {
  const { text } = useI18n()
  const previousFocus = useRef<HTMLElement | null>(null)
  const reduceMotion = Boolean(useReducedMotion())
  const query = useQuery({ queryKey: ['evidence-overlay', evidenceRef], queryFn: () => getEvidence(evidenceRef) })
  const item = query.data
  return <Dialog.Root open onOpenChange={open => { if (!open) onClose() }}><Dialog.Portal>
    <Dialog.Overlay className="evidence-dialog-overlay"/>
    <Dialog.Content asChild onOpenAutoFocus={() => {
      previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    }} onCloseAutoFocus={event => {
      event.preventDefault()
      const target = previousFocus.current?.isConnected ? previousFocus.current : document.getElementById('product-main')
      target?.focus({ preventScroll: true })
    }}><motion.aside
      className="investigation-evidence-lens"
      initial={reduceMotion ? false : { opacity: 0, x: 36, clipPath: 'inset(0 0 0 18%)' }}
      animate={{ opacity: 1, x: 0, clipPath: 'inset(0 0 0 0%)' }}
      exit={reduceMotion ? undefined : { opacity: 0, x: 28, clipPath: 'inset(0 0 0 14%)' }}
      transition={{ type: 'spring', stiffness: 250, damping: 28 }}
    >
      <Dialog.Title className="sr-only">{text('证据查看', 'Evidence inspector')}</Dialog.Title>
      <Dialog.Description className="sr-only">{text('核对原始来源、证据内容及其定位。', 'Inspect the original source, evidence and locator.')}</Dialog.Description>
      <div className="overlay-head">
        <div><small>{text('来源证据', 'Source evidence')}</small>{item ? <SourceIdentity source={item.source.source_id} url={item.observation.canonical_url}/> : <strong>{text('读取中…', 'Loading…')}</strong>}</div>
        <Dialog.Close asChild><Button variant="ghost" size="icon" aria-label={text('关闭证据', 'Close evidence')}><X/></Button></Dialog.Close>
      </div>
      {item ? <EvidenceTrace item={item} /> : <div className="inspector-empty"><Orbit size={30} />{query.isError ? <><strong>{text('证据读取失败', 'Evidence read failed')}</strong><p>{String(query.error.message)}</p><button className="evidence-read-retry" onClick={() => void query.refetch()}>{text('重新读取', 'Retry')}</button></> : text('解析 Evidence…', 'resolving evidence…')}</div>}
    </motion.aside></Dialog.Content>
  </Dialog.Portal></Dialog.Root>
}

function EvidenceTrace({ item }: { item: EvidenceDetail }) {
  const { text, language } = useI18n()
  const navigate = useNavigate()
  const locator = Object.entries(item.locator).map(([key, value]) => key + '=' + String(value)).join(' · ') || 'root'
  const objectIds = evidenceBoundObjectIds(item)
  return <div className="overlay-body">
    <div className="trace-hero">
      <BadgeCheck size={22} />
      <div>
        <small>{text('这条证据说明了什么', 'What this evidence supports')}</small>
        <strong>{evidenceFieldLabel(item.target.label, text)}</strong>
        <span className="mono" title={item.observation.external_object_id}>{compactEvidenceObjectRef(item.observation.external_object_id)}</span>
      </div>
    </div>
    {item.target.target_kind === 'claim' && item.target.detail.value !== undefined &&
      <div className="trace-statement">
        <small>{text('来源支持的断言', 'SOURCE-BOUND CLAIM')}</small>
        <p>{item.target.label === 'known_exploited' && typeof item.target.detail.value === 'boolean' ? item.target.detail.value ? text('该漏洞已有已知利用记录。', 'This vulnerability has a known exploitation record.') : text('该来源未将此漏洞标记为已知被利用。', 'This source does not mark this vulnerability as known to be exploited.') : typeof item.target.detail.value === 'boolean' ? item.target.detail.value ? text('是', 'Yes') : text('否', 'No') : formatValue(item.target.detail.value)}</p>
      </div>}
    {item.document_passages?.length > 0 &&
      <section className="evidence-document-passages">
        <header>
          <small>{text('原文节选', 'Source passages')}</small>
          <p>{text('摘自此证据引用的来源版本。', 'Excerpts from the source version cited by this evidence.')}</p>
        </header>
        {item.document_passages.map((passage, index) =>
          <article key={passage.chunk_ref} title={passage.chunk_ref}>
            <span>{String(index + 1).padStart(2, '0')} / {passage.section ?? text('正文', 'BODY')}</span>
            <p>{passage.text}</p>
          </article>)}
      </section>}
    {item.observation.canonical_url && <Button asChild variant="outline" className="investigation-evidence-source"><a href={item.observation.canonical_url} target="_blank" rel="noreferrer"><Link2 size={15}/>{text('阅读原始来源', 'Read original source')}</a></Button>}
    <TraceRow label={text('来源版本', 'Source version')} value={item.observation.external_revision ?? text('按内容哈希归档', 'Content-addressed version')} />
    <TraceRow label={text('系统发现时间', 'Observed by system')} value={new Date(item.observation.observed_at).toLocaleString(language === 'zh' ? 'zh-CN' : 'en-US')} />
    {objectIds.length > 0 && <div className="evidence-object-links">
      <small>{text('相关档案', 'Related records')}</small>
      <div>{objectIds.map((objectId, index) =>
        <button key={objectId} onClick={() => navigate(`/intelligence?object=${encodeURIComponent(objectId)}&from=case`)}>
          <BrainCircuit size={11} />
          {index === 0 ? text('打开主体档案', 'OPEN SUBJECT DOSSIER') : text('打开关系对象', 'OPEN RELATED OBJECT')}
          <span className="mono" title={objectId}>{index === 0 ? compactEvidenceObjectRef(item.observation.external_object_id) : compactEvidenceObjectRef(objectId)}</span>
        </button>)}</div>
    </div>}
    <details className="evidence-technical-details">
      <summary>{text('溯源详情', 'Provenance details')}</summary>
      <TraceRow label={text('证据标识', 'Evidence reference')} value={item.evidence_ref}/>
      <TraceRow label={text('来源标识', 'Source ID')} value={item.source.source_id}/>
      <TraceRow label={text('来源家族', 'Source family')} value={item.source.source_family}/>
      <TraceRow label={text('权威范围', 'Authority scope')} value={item.source.authority_scope.join(' · ') || text('未指定', 'Unspecified')}/>
      <TraceRow label={text('目标记录', 'Target record')} value={formatValue(item.target.detail)}/>
      <TraceRow label={text('来源角色与类型', 'Source role and class')} value={`${item.source.source_role} / ${item.source.source_class}`}/>
      <TraceRow label={text('观测记录', 'Observation ID')} value={item.observation.observation_id}/>
      <TraceRow label={text('来源对象', 'External object ID')} value={item.observation.external_object_id}/>
      <TraceRow label={text('引用目标', 'Evidence target')} value={`${item.target.target_kind}: ${item.target.target_id}`}/>
      <TraceRow label={text('原始字段', 'Original field')} value={item.target.label}/>
      <TraceRow label={text('原文定位', 'Source locator')} value={locator}/>
      <TraceRow label={text('内容信任类型', 'Content trust class')} value={item.artifact?.trust_class ?? 'observation-bound'}/>
      <TraceRow label={text('内容哈希', 'Content hash')} value={item.observation.content_hash}/>
    </details>
  </div>
}

function compactEvidenceObjectRef(value: string) { return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-8)}` : value }

function TraceRow({ label, value }: { label: string; value: string }) { return <div className="trace-row"><small>{label}</small><strong>{value}</strong></div> }
