import { DevelopingField } from '../ui/developing-field'
import { useMemo, useState, type ReactNode } from 'react'
import { FileText, GitBranch, Layers, Library, Sparkles } from '../ui/icons'
import type { getDocumentByObject, IntelligenceEnrichmentState, KnowledgeObject } from '../../lib/api'
import { evidenceFieldLabel, evidenceValueLabel, formatDate, groupClaims } from '../../lib/intelligencePresentation'
import { sourceIdentity } from '../../lib/source-identity'
import { useI18n } from '../../lib/i18n'
import { useAuth } from '../../lib/auth'
import { AccountLoginPrompt } from '../auth/RequireAccount'
import { Button } from '../ui/button'
import { SourceIdentity } from '../ui/source-identity'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { DocumentIndexDossier } from './DossierSurfaces'
import { EnrichmentConstellation } from './EnrichmentConstellation'
import { EvidenceCapsules } from './KnowledgeSurfaces'
import { KnowledgeNetwork } from './KnowledgeNetwork'
import { ProductEnrichmentActions } from './ProductEnrichmentActions'
import './dossier-reader.css'

export type DossierView = 'dossier' | 'graph' | 'evidence' | 'enrichment'
type Props = {
  obj: KnowledgeObject
  headline: string
  cveId: string
  view: DossierView
  onView: (view: DossierView) => void
  onEvidence: (ref: string) => void
  onMission: (profile: 'VERIFY' | 'INVESTIGATE') => void
  onOpenTarget: (id: string) => void
  enrichment: IntelligenceEnrichmentState | null
  enrichmentLoading: boolean
  enrichmentError: boolean
  retryEnrichment: () => void
  refresh: () => Promise<void>
  document: Awaited<ReturnType<typeof getDocumentByObject>> | null
  documentLoading: boolean
  documentError: string | null
}

export function DossierHeading({
  title,
  kind,
  coordinate,
  stats,
  children,
}: {
  title: string
  kind: string
  coordinate: string
  stats: Array<{ label: string; value: string | number }>
  children?: ReactNode
}) {
  const { text } = useI18n()
  return (
    <header className="dossier-reader-heading development-heading" data-develop-scope><DevelopingField variant="reading" className="heading-imprint imprint-research"/>
      <div className="dossier-reader-kind">
        <Layers size={16} />
        {kind}
      </div>
      <h1>{title}</h1>
      <div className="dossier-reader-meta">
        {stats.map((stat) => (
          <span key={stat.label}>
            <b>{stat.value}</b>
            {stat.label}
          </span>
        ))}
        <details>
          <summary>{text('档案标识', 'Identifier')}</summary>
          <code>{coordinate}</code>
        </details>
      </div>
      <div className="dossier-reader-actions">{children}</div>
    </header>
  )
}

export function DossierReader(props: Props) {
  const { text } = useI18n()
  const auth = useAuth()
  const { obj, headline, onEvidence } = props
  const evidenceCount = new Set([...obj.claims, ...obj.relations].flatMap((item) => item.evidence.map((ref) => ref.evidence_ref))).size
  const isDocument = ['Document', 'ResearchWork'].includes(obj.object_type)
  const view = props.view === 'enrichment' && obj.object_type !== 'Vulnerability' ? 'dossier' : props.view
  return (
    <Tabs value={view} onValueChange={(next) => props.onView(next as DossierView)} className={`dossier-reader ${view === 'graph' ? 'is-network' : ''}`}>
      <DossierHeading
        title={headline}
        kind={
          obj.object_type === 'Vulnerability'
            ? text('漏洞档案', 'Vulnerability dossier')
            : isDocument
              ? text('文献档案', 'Document dossier')
              : text('情报档案', 'Intelligence dossier')
        }
        coordinate={obj.object_id}
        stats={[
          { label: text('事实', 'facts'), value: obj.claims.length },
          { label: text('关系', 'relations'), value: obj.relations.length },
          { label: text('份证据', 'evidence references'), value: evidenceCount },
        ]}
      >
        <Button onClick={() => props.onMission('INVESTIGATE')}>
          {text('展开调查', 'Investigate')}

        </Button>
        <Button variant="outline" onClick={() => props.onMission('VERIFY')}>
          {text('核验事实', 'Verify facts')}
        </Button>
      </DossierHeading>
      <TabsList variant="line" className="dossier-reader-tabs" aria-label={text('档案内容', 'Dossier content')}>
        <TabsTrigger value="dossier">
          <FileText />
          {text('事实', 'Facts')}
        </TabsTrigger>
        <TabsTrigger value="graph">
          <GitBranch />
          {text('关系', 'Relations')}
        </TabsTrigger>
        <TabsTrigger value="evidence">
          <Library />
          {text('来源', 'Sources')}
        </TabsTrigger>
        {obj.object_type === 'Vulnerability' && (
          <TabsTrigger value="enrichment">
            <Sparkles />
            {text('富化', 'Enrichment')}
          </TabsTrigger>
        )}
      </TabsList>
      <TabsContent value="dossier">
        {isDocument && <DocumentIndexDossier document={props.document} loading={props.documentLoading} error={props.documentError} />}
        <DossierFacts obj={obj} onEvidence={onEvidence} />
      </TabsContent>
      <TabsContent value="graph">
        <KnowledgeNetwork objectId={obj.object_id} onEvidence={onEvidence} onOpenTarget={props.onOpenTarget} />
      </TabsContent>
      <TabsContent value="evidence">
        <DossierSources obj={obj} onEvidence={onEvidence} />
      </TabsContent>
      <TabsContent value="enrichment">
        <EnrichmentConstellation
          claims={obj.claims}
          relations={obj.relations}
          cveId={props.cveId}
          state={props.enrichment}
          stateLoading={props.enrichmentLoading}
          stateError={props.enrichmentError}
          onEvidence={onEvidence}
        />
        {props.enrichmentError && (
          <Button variant="outline" onClick={props.retryEnrichment}>
            {text('重新读取维度状态', 'Retry coverage')}
          </Button>
        )}
        {auth.authenticated ? (
          <ProductEnrichmentActions objectId={obj.object_id} cveId={props.cveId} state={props.enrichment} onChanged={props.refresh} />
        ) : (
          <AccountLoginPrompt
            title={text('继续补全这份漏洞档案', 'Continue enriching this vulnerability')}
            description={text('登录后可选择缺失维度，跟踪补全结果。', 'Sign in to select missing dimensions and track enrichment results.')}
          />
        )}
      </TabsContent>
    </Tabs>
  )
}

const groupLabels: Record<string, [string, string]> = {
  'IDENTITY & SEVERITY': ['基本信息与严重性', 'Identity and severity'],
  'AFFECTED & FIX': ['影响范围与修复', 'Affected products and remediation'],
  'EXPLOIT & LIKELIHOOD': ['利用情况与风险', 'Exploitation and likelihood'],
  'SOURCE & TIMELINE': ['参考资料与时间', 'References and timeline'],
  'OTHER CANONICAL FACTS': ['其他已知事实', 'Other known facts'],
}

function DossierFacts({ obj, onEvidence }: { obj: KnowledgeObject; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const groups = groupClaims(obj.claims)
  const properties = Object.entries(obj.properties).filter(([, value]) => value != null)
  return (
    <div className="dossier-facts-layout">
      {groups.length > 0 && (
        <nav className="dossier-outline" aria-label={text('事实目录', 'Fact sections')}>
          <span>{text('档案内容', 'Contents')}</span>
          {groups.map((group, index) => (
            <a key={group.title} href={`#dossier-section-${index}`}>
              {text(...groupLabels[group.title])}
              <span>{group.claims.length}</span>
            </a>
          ))}
        </nav>
      )}
      <div className="dossier-facts-paper">
        {groups.map((group, index) => (
          <section id={`dossier-section-${index}`} key={group.title} className="dossier-fact-section">
            <h2>{text(...groupLabels[group.title])}</h2>
            {group.claims.map((claim) => (
              <article key={claim.claim_id} className="dossier-fact">
                <h3>{evidenceFieldLabel(claim.predicate, text)}</h3>
                <p>{evidenceValueLabel(claim.predicate, claim.value, text)}</p>
                <div className="dossier-fact-footer">
                  <EvidenceCapsules evidence={claim.evidence} onEvidence={onEvidence} compact />
                  <details>
                    <summary>{text('记录详情', 'Record details')}</summary>
                    <span>
                      {claim.origin} · {text('修订', 'Revision')} {claim.created_revision}
                    </span>
                    <code>{claim.claim_id}</code>
                  </details>
                </div>
              </article>
            ))}
          </section>
        ))}
        {!groups.length && (
          <div className="dossier-reading-empty">
            <FileText size={26} />
            <h2>{text('尚无已保留的事实', 'No retained facts yet')}</h2>
            <p>{text('可以查看已有关系和来源，或发起调查。', 'Explore existing relations and sources, or start an investigation.')}</p>
          </div>
        )}
        {(properties.length > 0 || Object.keys(obj.external_identifiers).length > 0) && (
          <details className="dossier-object-properties">
            <summary>{text('对象属性与外部标识', 'Object properties and external identifiers')}</summary>
            <dl>
              {[...properties, ...Object.entries(obj.external_identifiers)].map(([key, value]) => (
                <div key={key}>
                  <dt>{evidenceFieldLabel(key, text)}</dt>
                  <dd>{evidenceValueLabel(key, value, text)}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </div>
    </div>
  )
}

function DossierSources({ obj, onEvidence }: { obj: KnowledgeObject; onEvidence: (ref: string) => void }) {
  const { text } = useI18n()
  const [source, setSource] = useState('all')
  const [limit, setLimit] = useState(20)
  const entries = useMemo(() => {
    const records = [
      ...obj.claims.map((claim) => ({ ...claim, label: claim.predicate })),
      ...obj.relations.map((relation) => ({ ...relation, label: relation.relation_type })),
    ]
    const refs = new Map<string, { ref: (typeof obj.claims)[number]['evidence'][number]; labels: Set<string> }>()
    records.forEach((record) =>
      record.evidence.forEach((ref) => {
        const existing = refs.get(ref.evidence_ref)
        if (existing) existing.labels.add(record.label)
        else refs.set(ref.evidence_ref, { ref, labels: new Set([record.label]) })
      }),
    )
    return [...refs.values()]
  }, [obj])
  const publishers = [...new Set(entries.map((entry) => entry.ref.source_id))]
  const filtered = entries.filter((entry) => source === 'all' || entry.ref.source_id === source)
  return (
    <section className="dossier-source-library">
      <header>
        <div>
          <h2>{text('每条事实，都能回到来源', 'Follow each fact to its source')}</h2>
          <p>
            {text(
              `${publishers.length} 个数据源 · ${entries.length} 份保留的证据。打开记录可查看原文、版本与溯源信息。`,
              `${entries.length} retained evidence references from ${publishers.length} sources. Open a record for its content, revision and provenance.`,
            )}
          </p>
        </div>
      </header>
      {publishers.length > 1 && (
        <div className="dossier-source-filters">
          <Button
            variant={source === 'all' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => {
              setSource('all')
              setLimit(20)
            }}
            aria-pressed={source === 'all'}
          >
            {text('全部来源', 'All sources')}
          </Button>
          {publishers.map((id) => (
            <Button
              variant={source === id ? 'secondary' : 'ghost'}
              size="sm"
              key={id}
              onClick={() => {
                setSource(id)
                setLimit(20)
              }}
              aria-pressed={source === id}
            >
              {sourceIdentity(id).name}
            </Button>
          ))}
        </div>
      )}
      <div className="dossier-source-list">
        {filtered.slice(0, limit).map(({ ref, labels }, index) => (
          <button className="dossier-source-record" key={ref.evidence_ref} onClick={() => onEvidence(ref.evidence_ref)}>
            <span className="dossier-source-number">{String(index + 1).padStart(2, '0')}</span>
            <div>
              <SourceIdentity source={ref.source_id} url={ref.canonical_url} />
              <strong>{[...labels].map((label) => evidenceFieldLabel(label, text)).join(' · ')}</strong>
              <small>
                {text('采集于', 'Observed')} {formatDate(ref.observed_at)}
                {ref.external_revision ? ` · ${text('版本', 'Revision')} ${ref.external_revision}` : ''}
              </small>
            </div>

          </button>
        ))}
      </div>
      {!entries.length && (
        <p className="dossier-reading-empty">{text('当前档案尚未关联证据。', 'No evidence is linked to this dossier yet.')}</p>
      )}
      {filtered.length > limit && (
        <Button variant="outline" className="dossier-source-more" onClick={() => setLimit((current) => current + 20)}>
          {text(`继续读取 · 还有 ${filtered.length - limit} 份`, `Load more · ${filtered.length - limit} remaining`)}
        </Button>
      )}
    </section>
  )
}
